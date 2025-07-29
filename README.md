<<<<<<< HEAD
# CS2 Farm Bot ve Yönetim Sistemi

Bu proje, CS2 oyununda tam otomatik XP farming, drop talep etme ve ekran görüntüsü alma gibi işlemleri yapabilen bir sistemdir. YOLOv8 tabanlı görüntü işleme kullanarak rakipleri tespit eder, hedefler ve yüksek hassasiyetle ateş eder.

## Özellikler

- **YOLOv8 Nesne Tespiti**: Özel eğitilmiş modelinizi kullanarak oyuncu tespiti
- **Özerk Çalışma**: Kullanıcı girdisi olmadan düşmanları taramak, hedef almak ve ateş etmek için otomatik döndürme
- **Akıllı Hedef Seçimi**: Mesafe, boyut ve güven düzeyine dayalı öncelikli hedefler
- **Geri Tepme Kontrolü**: Silah geri tepmesini kontrol etmek için kompanse edici fare hareketleri
- **Burst Atış Modu**: Daha gerçekçi atış desenleri için yapılandırılabilir seri atış boyutu ve gecikmesi
- **Ayarlanabilir Parametreler**: Tüm parametreleri yapılandırma dosyası üzerinden kolayca ayarlama
- **Oturum İstatistikleri**: Performansı izler ve ayrıntılı günlükler kaydeder
- **Tam AFK Çalışma**: Tamamen gözetimsiz çalışır
- **Web Tabanlı Yönetim**: Çoklu VM yönetimi için web arayüzü
- **VM Entegrasyonu**: Hyper-V sanal makineleri ile entegrasyon

## Sistem Bileşenleri

Proje üç ana bileşenden oluşur:

1. **CS2 Bot (cs2_aimbot.py ve cs2_advanced_bot.py)**
   - YOLOv8 tabanlı hedef tespiti
   - Hassas nişan alma ve ateş etme mekanizmaları
   - Gelişmiş silah geri tepme kontrolü
   - Hareket tahmini ve izleme

2. **Web Kontrol Paneli (web_control.py)**
   - Flask tabanlı web arayüzü
   - VM ve bot yönetimi
   - Kullanıcı yönetimi ve kimlik doğrulama
   - İş kuyruğu ve durumu izleme

3. **VM İstemcisi (client.py)**
   - Sunucuyla iletişim
   - Bot işlerini yerel olarak çalıştırma
   - Steam ve CS2 otomatik başlatma
   - Oturum istatistikleri ve ekran görüntüleri

## Kurulum

### Sunucu (Web Kontrol Paneli)

1. Gereksinimleri yükleyin:
```bash
pip install Flask flask-login werkzeug psutil requests
```

2. Sunucuyu başlatın:
```bash
python web_control.py
```

3. Tarayıcınızda `http://localhost:8000` adresine gidin ve varsayılan kullanıcı adı/şifre ile giriş yapın (admin/admin)

### VM İstemcisi

1. Gereksinimleri yükleyin:
```bash
pip install ultralytics opencv-python numpy pyautogui keyboard mss torch pywin32 requests psutil
=======
# CS2 AimBot - Yüksek Performanslı Hedef Tespit ve Ateş Sistemi

Bu CS2 AimBot, YOLOv8 nesne tespiti modeli kullanarak oyundaki düşmanları tespit eden, onları hedefleyen ve otomatik olarak ateş eden gelişmiş bir sistemdir.

## Özellikler

- **YOLOv8 Nesne Tespiti**: Özel eğitilmiş YOLOv8 modeli ile yüksek doğrulukta tespit
- **Arka Plan Çalışma**: Bot oyun penceresini etkilemeden arka planda çalışır
- **Yüksek Performans**: Optimize edilmiş kod ile düşük CPU/GPU kullanımı
- **İki Farklı Hassasiyet Modu**: Hızlı tarama ve hassas nişan alma için ayrı ayarlar
- **Hassas Nişan Alma**: İlk harekette hedefe yaklaşıp sonra hassas ayarla tam isabet
- **Recoil (Tepme) Kontrolü**: Otomatik tepme kompanzasyonu ile hedefi şaşırmama
- **Burst Atış Modu**: Kontrollü burst atışlarla daha gerçekçi ve etkili ateş
- **360 Derece Tarama**: Periyodik olarak 360 derece çevreyi tarama özelliği
- **Hedef Filtresi**: Beklemede olan oyuncuları filtreler (10 saniye bekleyenler)
- **Tam Otonomluk**: Otomatik tarama, hedefleme ve ateş etme özellikleri
- **Kafa Hedefleme**: Tespit edilen bölgenin kafa kısmını hedefleme
- **Özelleştirilebilir Ayarlar**: Hassasiyet, tarama hızı, ateş etme ve daha fazlası için ayarlar
- **Gelişmiş Kontroller**: Klavye kısayolları ve detaylı ayarlar

## Başlarken

### Gereksinimler

- Python 3.8 veya daha yüksek
- CS2 (Counter-Strike 2) oyunu
- Eğitilmiş bir YOLOv8 modeli (varsayılan: `runs\detect\cs2_model2\weights\best.pt`)

### Kurulum

1. Gerekli paketleri yükleyin:
```
pip install numpy opencv-python mss keyboard ultralytics torch pywin32
>>>>>>> parent of 2b548f6 (deleted unused files and modified web_control.py)
```

2. YOLOv8 modelinizi `runs\detect\cs2_model2\weights\best.pt` konumuna yerleştirin.

<<<<<<< HEAD
3. İstemciyi başlatın:
```bash
python client.py --server http://localhost:8000 --api-key API_ANAHTARINIZ
```

## Kullanım

### Web Arayüzünden

1. VM'leri yönetin (başlatma, durdurma, yapılandırma)
2. Bot işleri oluşturun (XP farm, ekran görüntüsü, drop talep etme)
3. İş durumlarını ve istatistiklerini izleyin

### VM Yapılandırması

VM'ler için `bot_config.json` dosyasını düzenleyerek şu ayarları yapabilirsiniz:

- `model_path`: YOLOv8 modelinizin yolu
- `confidence_threshold`: Düşman tespiti için minimum güven düzeyi (0.0-1.0)
- `rotation_speed`: Tarama yaparken dönüş hızı
- `aim_speed`: Fare hareketi hızı çarpanı
- `fov_x`, `fov_y`: Tespit için görüş alanı (ekranın yüzdesi)
- `headshot_offset`: Kafadan vuruş için dikey ofset (negatif değerler daha yükseğe nişan alır)
- `aim_smoothness`: Daha doğal, insan benzeri hareketler için daha yüksek değerler
- `recoil_control`: Geri tepme telafisini etkinleştir/devre dışı bırak
- `burst_fire`: Seri atış modunu etkinleştir/devre dışı bırak
- `burst_size`: Seri başına atış sayısı
- `burst_delay`: Seriler arasındaki gecikme (saniye)
- `auto_reload`: Otomatik yeniden doldurmayı etkinleştir/devre dışı bırak
- `reload_ammo_threshold`: Otomatik yeniden doldurmayı tetikleyecek atış sayısı

## Önemli Notlar

- Bu bot yalnızca eğitim amaçlıdır
- Rekabetçi çevrimiçi oyunlarda bot kullanmak hizmet şartlarını ihlal edebilir
- Her zaman sorumlu ve etik bir şekilde kullanın
- Yalnızca özel/çevrimdışı modlarda kullanmayı düşünün

## YOLOv8 Modelini Özelleştirme

En iyi tespit performansı için, YOLOv8 modelinizi şunlarla eğitin:
- Çeşitli oyun içi ekran görüntüleri
- Farklı karakter modelleri ve haritalar
- Çeşitli aydınlatma koşulları
- Farklı silah görünümleri

Bot'un takım arkadaşları ve düşmanlar arasında ayrım yapabilmesi için sınıf etiketlerini dahil etmeyi unutmayın. 
=======
### Kullanım

Botu başlatmak için:
```
python optimized_cs2_bot.py
```

## Klavye Kontrolleri

- **F10**: Botu açma/kapatma
- **F9**: Debug görüntülemeyi açma/kapatma
- **F8**: Otomatik ateş etmeyi açma/kapatma
- **F7**: Fare yönlendirme modunu değiştirme
- **F5/F6**: Nişan alma hassasiyetini azaltma/artırma
- **F3/F4**: Tarama hassasiyetini azaltma/artırma
- **P**: Hassas nişan alma modunu açma/kapatma
- **B**: Burst atış modunu açma/kapatma
- **R**: Tepme (recoil) kontrolünü açma/kapatma
- **W**: Bekleyen oyuncu filtresini açma/kapatma
- **T**: 360 derece tam taramayı başlatma
- **H**: Kafa hedefleme modunu açma/kapatma
- **Yukarı/Aşağı**: Kafa hedefi yüksekliğini ayarlama
- **F1**: Programdan çıkış

## Hassasiyet Ayarları

Bot iki farklı hassasiyet sistemi kullanır:

1. **Tarama Hassasiyeti**: Düşman tespit etmek için geniş ve hızlı tarama yapar
   - F3/F4 tuşları ile ayarlanır
   - Yüksek değerler daha hızlı tarama sağlar

2. **Nişan Alma Hassasiyeti**: Tespit edilen hedefe tam isabet için hassas ayar
   - F5/F6 tuşları ile ayarlanır
   - Düşük değerler daha hassas nişan almanızı sağlar

3. **Hassas Nişan Alma Modu**: Hedefi önce hızlıca yakalar, sonra hassas ayar yapar
   - P tuşu ile açılıp kapatılabilir
   - Özellikle kafa atışları için çok etkilidir

## Gelişmiş Atış Sistemi

Bot, daha iyi kontrol için gelişmiş atış mekanizmaları kullanır:

1. **Burst Atış Modu**: 
   - B tuşu ile açılıp kapatılabilir
   - Belirli sayıda mermiyi hızlı gruplar halinde ateşler
   - Gruplar arası otomatik bekleme ile tepme kontrolü sağlar

2. **Tepme (Recoil) Kontrolü**:
   - R tuşu ile açılıp kapatılabilir
   - Her atışla birlikte artan bir tepme kompanzasyonu uygular
   - Silahın yukarı kaymasını engelleyerek hedefte kalmanızı sağlar
   - Belirli süre atış yapılmadığında otomatik sıfırlanır

## Tarama Stratejileri

Bot, düşmanları tespit etmek için farklı tarama stratejileri kullanır:

1. **Standart Tarama**:
   - Kademeli olarak sağa ve sola dönüş yapar
   - Daha büyük adımlarla (30°) ve daha az sıklıkla dönüş yapar
   - 5 dönüşte bir yön değiştirir

2. **360 Derece Tarama**:
   - T tuşu ile manuel olarak tetiklenebilir
   - Her 5 saniyede bir otomatik olarak gerçekleşir
   - 12 adımda tam 360 derecelik dönüş tamamlar
   - Arkada veya yanlarda kalan düşmanları tespit eder

3. **Oyuncu Filtreleme**:
   - Hareketsiz kalan veya beklemede olan oyuncuları tespit eder
   - 10 saniye boyunca respawn bekleyen oyuncuları hedeflemez
   - W tuşu ile açılıp kapatılabilir

## Optimizasyonlar

Bu bot, aşağıdaki optimizasyonlarla yüksek performanslı bir şekilde çalışmak üzere tasarlanmıştır:

1. Küçük FOV (görüş alanı) ile daha hızlı tespit
2. İstem dışı fare hareketlerini önlemek için DirectInput benzeri kontroller
3. Kademeli tarama sistemi ile tüm görüş alanını kapsama
4. İki farklı hassasiyet sistemi ile hem hızlı tarama hem de hassas nişan alma
5. Tepme kontrolü ile silahın yukarı kaymasını engelleme
6. Burst atış sistemi ile daha kontrollü ateş
7. Beklemede olan oyuncuları filtreleme
8. Tüm duyarlı operasyonlar için istisna yönetimi
9. Kullanıcı etkileşimi olmadığında düşük CPU kullanımı
10. Mümkün olduğunda GPU hızlandırma (CUDA/TensorRT)

## Önemli Notlar

- Bu bot yalnızca eğitim amaçlıdır ve gerçek oyunlarda kullanımı oyun hüküm ve koşullarını ihlal edebilir
- Yalnızca kendi özel sunucularınızda veya yapay zeka test ortamlarında kullanın
- Yüksek doğruluk için modelin belirli düşman koşullarında eğitilmiş olması gerekir 
>>>>>>> parent of 2b548f6 (deleted unused files and modified web_control.py)
