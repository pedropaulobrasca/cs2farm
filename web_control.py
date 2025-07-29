import os
import json
import time
import threading
import subprocess
import datetime
import logging
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import psutil
import platform
import requests
from pathlib import Path
import sys

# Kendi modüllerimizi import ediyoruz
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cs2_aimbot import CS2Aimbot
from cs2_advanced_bot import CS2AdvancedBot

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("web_control.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("FarmLabs")

# Flask uygulaması
app = Flask(__name__)
app.config['SECRET_KEY'] = 'farmlabs-cs2-farming-secret-key'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB maksimum upload

# Flask login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Veritabanı dosyaları
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
USER_DB = os.path.join(DATA_DIR, 'users.json')
VM_DB = os.path.join(DATA_DIR, 'vms.json')
BOT_CONFIG_DIR = os.path.join(DATA_DIR, 'bot_configs')
BOT_JOBS_DB = os.path.join(DATA_DIR, 'bot_jobs.json')
MANAGER_JOBS_DB = os.path.join(DATA_DIR, 'manager_jobs.json')
LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')

# Dizinleri oluştur
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BOT_CONFIG_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Aktif VM ve Bot işleri
active_vms = {}
active_bot_jobs = {}
active_manager_jobs = {}

# Kullanıcı sınıfı
class User(UserMixin):
    def __init__(self, id, username, password_hash, role='user', api_key=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role
        self.api_key = api_key

# VMs işlemleri
class VMManager:
    @staticmethod
    def load_vms():
        if os.path.exists(VM_DB):
            with open(VM_DB, 'r') as f:
                return json.load(f)
        return {}
    
    @staticmethod
    def save_vms(vms):
        with open(VM_DB, 'w') as f:
            json.dump(vms, f, indent=4)
    
    @staticmethod
    def add_vm(name, ip, username, password, vm_type='hyperv'):
        vms = VMManager.load_vms()
        vm_id = str(uuid.uuid4())
        vms[vm_id] = {
            'id': vm_id,
            'name': name,
            'ip': ip,
            'username': username,
            'password': password,
            'type': vm_type,
            'status': 'offline',
            'created_at': datetime.datetime.now().isoformat()
        }
        VMManager.save_vms(vms)
        return vm_id
    
    @staticmethod
    def delete_vm(vm_id):
        vms = VMManager.load_vms()
        if vm_id in vms:
            del vms[vm_id]
            VMManager.save_vms(vms)
            return True
        return False
    
    @staticmethod
    def update_vm_status(vm_id, status):
        vms = VMManager.load_vms()
        if vm_id in vms:
            vms[vm_id]['status'] = status
            VMManager.save_vms(vms)
            return True
        return False
    
    @staticmethod
    def start_vm(vm_id):
        vms = VMManager.load_vms()
        if vm_id not in vms:
            return False
        
        vm = vms[vm_id]
        if vm['type'] == 'hyperv':
            try:
                # Hyper-V VM başlatma
                subprocess.run(['powershell', '-Command', f"Start-VM -Name '{vm['name']}'"], check=True)
                VMManager.update_vm_status(vm_id, 'starting')
                logger.info(f"VM {vm['name']} starting...")
                return True
            except Exception as e:
                logger.error(f"Error starting VM {vm['name']}: {str(e)}")
                return False
        return False
    
    @staticmethod
    def stop_vm(vm_id):
        vms = VMManager.load_vms()
        if vm_id not in vms:
            return False
        
        vm = vms[vm_id]
        if vm['type'] == 'hyperv':
            try:
                # Hyper-V VM durdurma
                subprocess.run(['powershell', '-Command', f"Stop-VM -Name '{vm['name']}' -Force"], check=True)
                VMManager.update_vm_status(vm_id, 'stopping')
                logger.info(f"VM {vm['name']} stopping...")
                return True
            except Exception as e:
                logger.error(f"Error stopping VM {vm['name']}: {str(e)}")
                return False
        return False

# Bot ve Yönetici işleri
class JobManager:
    @staticmethod
    def load_bot_jobs():
        if os.path.exists(BOT_JOBS_DB):
            with open(BOT_JOBS_DB, 'r') as f:
                return json.load(f)
        return {}
    
    @staticmethod
    def save_bot_jobs(jobs):
        with open(BOT_JOBS_DB, 'w') as f:
            json.dump(jobs, f, indent=4)
    
    @staticmethod
    def load_manager_jobs():
        if os.path.exists(MANAGER_JOBS_DB):
            with open(MANAGER_JOBS_DB, 'r') as f:
                return json.load(f)
        return {}
    
    @staticmethod
    def save_manager_jobs(jobs):
        with open(MANAGER_JOBS_DB, 'w') as f:
            json.dump(jobs, f, indent=4)
    
    @staticmethod
    def create_bot_job(bot_id, job_type, params=None):
        jobs = JobManager.load_bot_jobs()
        job_id = str(uuid.uuid4())
        
        if params is None:
            params = {}
        
        # XP Farm için varsayılan parametreler
        if job_type == 'xp_farm' and 'target_xp' not in params:
            params['target_xp'] = 1000
            
        if job_type == 'xp_farm' and 'target_level' not in params:
            params['target_level'] = 20
        
        jobs[job_id] = {
            'id': job_id,
            'bot_id': bot_id,
            'type': job_type,
            'status': 'pending',
            'params': params,
            'created_at': datetime.datetime.now().isoformat(),
            'start_time': None,
            'completion_time': None,
            'result': None
        }
        
        JobManager.save_bot_jobs(jobs)
        return job_id
    
    @staticmethod
    def create_manager_job(manager_id, job_type, params=None):
        jobs = JobManager.load_manager_jobs()
        job_id = str(uuid.uuid4())
        
        if params is None:
            params = {}
        
        jobs[job_id] = {
            'id': job_id,
            'manager_id': manager_id,
            'type': job_type,
            'status': 'pending',
            'params': params,
            'created_at': datetime.datetime.now().isoformat(),
            'start_time': None,
            'completion_time': None,
            'result': None
        }
        
        JobManager.save_manager_jobs(jobs)
        return job_id
    
    @staticmethod
    def update_bot_job(job_id, updates):
        jobs = JobManager.load_bot_jobs()
        if job_id in jobs:
            for key, value in updates.items():
                if key in jobs[job_id]:
                    jobs[job_id][key] = value
            JobManager.save_bot_jobs(jobs)
            return True
        return False
    
    @staticmethod
    def update_manager_job(job_id, updates):
        jobs = JobManager.load_manager_jobs()
        if job_id in jobs:
            for key, value in updates.items():
                if key in jobs[job_id]:
                    jobs[job_id][key] = value
            JobManager.save_manager_jobs(jobs)
            return True
        return False
    
    @staticmethod
    def delete_bot_job(job_id):
        jobs = JobManager.load_bot_jobs()
        if job_id in jobs:
            del jobs[job_id]
            JobManager.save_bot_jobs(jobs)
            return True
        return False
    
    @staticmethod
    def delete_manager_job(job_id):
        jobs = JobManager.load_manager_jobs()
        if job_id in jobs:
            del jobs[job_id]
            JobManager.save_manager_jobs(jobs)
            return True
        return False

# Bot yapılandırmaları
class BotConfigManager:
    @staticmethod
    def load_bot_config(bot_id):
        config_file = os.path.join(BOT_CONFIG_DIR, f"{bot_id}.json")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        
        # Varsayılan yapılandırma
        return {
            "model_path": r"runs\detect\cs2_model2\weights\best.pt",
            "confidence_threshold": 0.4,
            "rotation_speed": 1.0,
            "aim_speed": 0.5,
            "fov_x": 70,
            "fov_y": 40,
            "headshot_offset": -10,
            "aim_smoothness": 2.0,
            "recoil_control": True,
            "target_enemies_only": True,
            "burst_fire": True,
            "burst_size": 3,
            "burst_delay": 0.3,
            "auto_reload": True,
            "reload_ammo_threshold": 5,
            "hotkeys": {
                "toggle": "f6",
                "pause": "f7",
                "stop": "f8"
            }
        }
    
    @staticmethod
    def save_bot_config(bot_id, config):
        config_file = os.path.join(BOT_CONFIG_DIR, f"{bot_id}.json")
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)
        return True

# Kullanıcı veritabanı işlemleri
class UserManager:
    @staticmethod
    def load_users():
        if os.path.exists(USER_DB):
            with open(USER_DB, 'r') as f:
                return json.load(f)
        
        # İlk kez - admin kullanıcısı oluştur
        admin_id = str(uuid.uuid4())
        users = {
            admin_id: {
                'id': admin_id,
                'username': 'admin',
                'password_hash': generate_password_hash('admin'),
                'role': 'admin',
                'api_key': str(uuid.uuid4())
            }
        }
        
        with open(USER_DB, 'w') as f:
            json.dump(users, f, indent=4)
        
        return users
    
    @staticmethod
    def save_users(users):
        with open(USER_DB, 'w') as f:
            json.dump(users, f, indent=4)
    
    @staticmethod
    def add_user(username, password, role='user'):
        users = UserManager.load_users()
        
        # Kullanıcı adı kontrolü
        for user_id, user in users.items():
            if user['username'] == username:
                return None  # Kullanıcı zaten var
        
        user_id = str(uuid.uuid4())
        users[user_id] = {
            'id': user_id,
            'username': username,
            'password_hash': generate_password_hash(password),
            'role': role,
            'api_key': str(uuid.uuid4())
        }
        
        UserManager.save_users(users)
        return user_id
    
    @staticmethod
    def delete_user(user_id):
        users = UserManager.load_users()
        if user_id in users:
            del users[user_id]
            UserManager.save_users(users)
            return True
        return False
    
    @staticmethod
    def update_user(user_id, updates):
        users = UserManager.load_users()
        if user_id in users:
            for key, value in updates.items():
                if key in users[user_id] and key != 'id':
                    if key == 'password':
                        users[user_id]['password_hash'] = generate_password_hash(value)
                    else:
                        users[user_id][key] = value
            
            UserManager.save_users(users)
            return True
        return False
    
    @staticmethod
    def verify_user(username, password):
        users = UserManager.load_users()
        
        for user_id, user in users.items():
            if user['username'] == username:
                if check_password_hash(user['password_hash'], password):
                    return User(
                        user_id,
                        user['username'],
                        user['password_hash'],
                        user.get('role', 'user'),
                        user.get('api_key', None)
                    )
        return None
    
    @staticmethod
    def get_user_by_id(user_id):
        users = UserManager.load_users()
        
        if user_id in users:
            user = users[user_id]
            return User(
                user_id,
                user['username'],
                user['password_hash'],
                user.get('role', 'user'),
                user.get('api_key', None)
            )
        return None
    
    @staticmethod
    def get_user_by_api_key(api_key):
        users = UserManager.load_users()
        
        for user_id, user in users.items():
            if user.get('api_key') == api_key:
                return User(
                    user_id,
                    user['username'],
                    user['password_hash'],
                    user.get('role', 'user'),
                    api_key
                )
        return None

# Flask-Login yükleyici
@login_manager.user_loader
def load_user(user_id):
    return UserManager.get_user_by_id(user_id)

# API anahtarı ile kimlik doğrulama
def authenticate_api_key():
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return None
    
    return UserManager.get_user_by_api_key(api_key)

# Web rotaları
@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = UserManager.verify_user(username, password)
        if user:
            login_user(user)
            return redirect(url_for('index'))
        
        return render_template('login.html', error='Geçersiz kullanıcı adı veya şifre')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# VM yönetim rotaları
@app.route('/managers')
@login_required
def managers():
    vms = VMManager.load_vms()
    return render_template('managers.html', vms=vms)

@app.route('/managers/create', methods=['GET', 'POST'])
@login_required
def create_manager():
    if request.method == 'POST':
        name = request.form.get('name')
        ip = request.form.get('ip')
        username = request.form.get('username')
        password = request.form.get('password')
        vm_type = request.form.get('type', 'hyperv')
        
        vm_id = VMManager.add_vm(name, ip, username, password, vm_type)
        return redirect(url_for('managers'))
    
    return render_template('manager_create.html')

@app.route('/managers/delete/<vm_id>', methods=['POST'])
@login_required
def delete_manager(vm_id):
    VMManager.delete_vm(vm_id)
    return redirect(url_for('managers'))

@app.route('/managers/start/<vm_id>', methods=['POST'])
@login_required
def start_manager(vm_id):
    VMManager.start_vm(vm_id)
    return redirect(url_for('managers'))

@app.route('/managers/stop/<vm_id>', methods=['POST'])
@login_required
def stop_manager(vm_id):
    VMManager.stop_vm(vm_id)
    return redirect(url_for('managers'))

# Bot yönetimi
@app.route('/bots')
@login_required
def bots():
    vms = VMManager.load_vms()
    bot_configs = {}
    
    for vm_id in vms:
        config_file = os.path.join(BOT_CONFIG_DIR, f"{vm_id}.json")
        if os.path.exists(config_file):
            bot_configs[vm_id] = True
        else:
            bot_configs[vm_id] = False
    
    return render_template('bots.html', vms=vms, bot_configs=bot_configs)

@app.route('/bots/config/<vm_id>', methods=['GET', 'POST'])
@login_required
def bot_config(vm_id):
    if request.method == 'POST':
        config = {
            "model_path": request.form.get('model_path'),
            "confidence_threshold": float(request.form.get('confidence_threshold')),
            "rotation_speed": float(request.form.get('rotation_speed')),
            "aim_speed": float(request.form.get('aim_speed')),
            "fov_x": int(request.form.get('fov_x')),
            "fov_y": int(request.form.get('fov_y')),
            "headshot_offset": int(request.form.get('headshot_offset')),
            "aim_smoothness": float(request.form.get('aim_smoothness')),
            "recoil_control": request.form.get('recoil_control') == 'on',
            "target_enemies_only": request.form.get('target_enemies_only') == 'on',
            "burst_fire": request.form.get('burst_fire') == 'on',
            "burst_size": int(request.form.get('burst_size')),
            "burst_delay": float(request.form.get('burst_delay')),
            "auto_reload": request.form.get('auto_reload') == 'on',
            "reload_ammo_threshold": int(request.form.get('reload_ammo_threshold')),
            "hotkeys": {
                "toggle": request.form.get('hotkey_toggle'),
                "pause": request.form.get('hotkey_pause'),
                "stop": request.form.get('hotkey_stop')
            }
        }
        
        BotConfigManager.save_bot_config(vm_id, config)
        return redirect(url_for('bots'))
    
    config = BotConfigManager.load_bot_config(vm_id)
    vms = VMManager.load_vms()
    vm = vms.get(vm_id, {'name': 'Unknown'})
    
    return render_template('bot_config.html', vm=vm, config=config)

# Bot işleri
@app.route('/bot-jobs')
@login_required
def bot_jobs():
    jobs = JobManager.load_bot_jobs()
    vms = VMManager.load_vms()
    
    return render_template('bot_jobs.html', jobs=jobs, vms=vms)

@app.route('/bot-jobs/create', methods=['GET', 'POST'])
@login_required
def create_bot_job():
    if request.method == 'POST':
        bot_id = request.form.get('bot_id')
        job_type = request.form.get('type')
        
        params = {}
        if job_type == 'xp_farm':
            params['target_xp'] = int(request.form.get('target_xp', 1000))
            params['target_level'] = int(request.form.get('target_level', 20))
        
        JobManager.create_bot_job(bot_id, job_type, params)
        return redirect(url_for('bot_jobs'))
    
    vms = VMManager.load_vms()
    return render_template('bot_job_create.html', vms=vms)

@app.route('/bot-jobs/delete/<job_id>', methods=['POST'])
@login_required
def delete_bot_job(job_id):
    JobManager.delete_bot_job(job_id)
    return redirect(url_for('bot_jobs'))

# Manager işleri
@app.route('/manager-jobs')
@login_required
def manager_jobs():
    jobs = JobManager.load_manager_jobs()
    vms = VMManager.load_vms()
    
    return render_template('manager_jobs.html', jobs=jobs, vms=vms)

@app.route('/manager-jobs/create', methods=['GET', 'POST'])
@login_required
def create_manager_job():
    if request.method == 'POST':
        manager_id = request.form.get('manager_id')
        job_type = request.form.get('type')
        
        JobManager.create_manager_job(manager_id, job_type)
        return redirect(url_for('manager_jobs'))
    
    vms = VMManager.load_vms()
    return render_template('manager_job_create.html', vms=vms)

@app.route('/manager-jobs/delete/<job_id>', methods=['POST'])
@login_required
def delete_manager_job(job_id):
    JobManager.delete_manager_job(job_id)
    return redirect(url_for('manager_jobs'))

# API rotaları
@app.route('/api/v1/heartbeat', methods=['POST'])
def api_heartbeat():
    user = authenticate_api_key()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    vm_id = data.get('vm_id')
    
    if not vm_id:
        return jsonify({'error': 'Missing VM ID'}), 400
    
    # VM durumunu güncelle
    VMManager.update_vm_status(vm_id, 'online')
    
    # Yeni işler var mı kontrol et
    bot_jobs = JobManager.load_bot_jobs()
    pending_jobs = []
    
    for job_id, job in bot_jobs.items():
        if job['bot_id'] == vm_id and job['status'] == 'pending':
            pending_jobs.append(job)
    
    return jsonify({
        'status': 'ok',
        'has_jobs': len(pending_jobs) > 0,
        'pending_jobs': pending_jobs
    })

@app.route('/api/v1/job/update', methods=['POST'])
def api_job_update():
    user = authenticate_api_key()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    job_id = data.get('job_id')
    job_type = data.get('job_type', 'bot')
    updates = data.get('updates', {})
    
    if not job_id or not updates:
        return jsonify({'error': 'Missing job ID or updates'}), 400
    
    if job_type == 'bot':
        success = JobManager.update_bot_job(job_id, updates)
    else:
        success = JobManager.update_manager_job(job_id, updates)
    
    if not success:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({'status': 'ok'})

@app.route('/api/v1/bot/config/<vm_id>', methods=['GET'])
def api_bot_config(vm_id):
    user = authenticate_api_key()
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401
    
    config = BotConfigManager.load_bot_config(vm_id)
    return jsonify(config)

# Ana işlev
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True) 