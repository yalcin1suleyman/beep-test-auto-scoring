# Otomatik Mekik Testi Değerlendirme Sistemi (v3)

## Masaüstündeki `MEKİK VİDEO` kayıtlarını çalıştırma (26 Ekim 2026)

Klasördeki her `Video N` alt klasöründe aynı koşunun iki telefon kaydı var: biri 0 m (başlangıç) çizgisinin arkasında, diğeri 20 m çizgisinin arkasında. Kamera rolleri, çizgi koordinatları, koşucu sayısı, çıkış bipi ve iki kamera arasındaki zaman farkı `mekik_sessions.json` dosyasında hazırdır.

```powershell
python run_sessions.py                     # menüden kayıt seç, görüntülü izle
python run_sessions.py --list              # kayıtları ve kalibrasyonu listele
python run_sessions.py -s 3 --hold-open    # Video 3'ü görüntülü analiz et
python run_sessions.py --all --no-display  # 7 kaydın hepsi + toplu özet
python run_sessions.py -s 3 --recalibrate  # çizgileri fareyle yeniden seç, dosyaya yaz
```

VS Code'da **Mekik - Masaustu Kayitlari (menu)** veya **Mekik - Tum Kayitlar (ekransiz)** ayarıyla F5. Çıktılar `data/outputs/sessions/video_N/` altına (video, CSV/Excel, `analiz_raporu.html`, `sonuc_paneli.jpg`), toplu özet `data/outputs/sessions/tum_kayitlar_ozet.csv` dosyasına yazılır.

Kalibrasyon nasıl yapıldı:
- **Çıkış bipi ve kamera senkronu**: Her kaydın sesi, salondaki bip kaydıyla (`data/inputs/reference_beep_audio.mp4`, Léger 20 m: 8,5 km/sa başlangıç) ilişkilendirildi. İki kameranın zaman farkı ayrıca iki kaydın sesi karşılaştırılarak doğrulandı. Koşucuların dönüş anları bip zamanlarıyla örtüşüyor.
- **Çizgiler**: Zemindeki 0 m / 20 m çizgileri kareler üzerinden ölçüldü ve YOLO ile çıkarılan dönüş noktalarıyla kontrol edildi.
- **Kamera kayması**: Telefonlar elde tutulduğu için görüntü 80 piksele kadar kayıyor. `camera_motion.py` her 3 karede bir kalibrasyon karesine göre homografi hesaplayıp çizgileri yeni konuma taşır (`--no-motion-compensation` ile kapatılabilir).
- **Çizgiye temas**: Ayak çizgiye bastığında mekik geçerli sayılır (`LINE_TOUCH_TOLERANCE_PX = 10`).

Bilinen sınırlar: **Video 7** standart bip testi değildir (koşucular ~31 s'de bir çalan bip ile gidip dönüyor ve aralarda bekliyor), bu yüzden puanlaması anlamlı değildir. Video 1'de 20 m kamerasının sesi zayıf olduğundan iki kamera arasındaki zaman farkı daha az kesindir. Sonuçlar otomatik değerlendirmedir ve insan hakem etiketleriyle karşılaştırılmamıştır.

## Doğrulanmış çalıştırma (23 Ekim 2026)

VS Code'da Run and Debug bölümünden **Mekik - Cift Kamera Goruntulu** ayarını seçip F5 ile başlatın. Bu ayar kökteki iki kamera videosunu, bu videolara ait çizgilerle açar. Çıkmak için görüntü penceresinde Q veya ESC kullanın.

Görüntü artık ayrı süre/hedef alanı, iki kamera paneli ve koşucu sonuç kartları içerir. Her analiz klasörüne video, CSV/Excel raporları, `sonuc_paneli.jpg` ve tarayıcıda açılabilen `analiz_raporu.html` yazılır. `--hold-open` son görüntüyü açık tutsa da raporlar ve video beklemeden kaydedilir.

Görüntülü ve ekransız mod varsayılan olarak bütün kareleri işler. Yavaş bilgisayarda görüntü gerçek zamandan yavaş akabilir. İstenirse `--realtime-preview` ile kare atlayan hızlı ön izleme açılabilir; bu modun yaklaşık sonuç verdiği panel ve raporda açıkça belirtilir. Çıktıyı bağımsız kontrol etmek için `python scripts/verify_analysis_output.py data/outputs/yeni_analiz` çalıştırılabilir.

Ekransız analiz örneği:

```powershell
python dual_main.py --no-display --no-audio --runner-count 5 --start-line '75,270;718,286' --far-line '170,450;905,443' --output-dir data/outputs/yeni_analiz
```

Çizgi koordinatları her kamera kaydı için ayrıca kalibre edilmelidir. `--runner-count` parkurdaki gerçek kişi sayısıdır; farklı videolara sabit 5 uygulanmamalıdır. `--no-display` çizgi koordinatları olmadan artık pencere açmak yerine açıklayıcı hata verir. `--no-audio` referans ses indirmesini de kapatır. `--cam2-offset` iki gerçek kaydın zaman farkını açıkça belirtebilir.

Matematiksel zamanlayıcı proje ayarındaki 7 km/sa başlangıç hızını ve `SHUTTLES_PER_LEVEL` tablosunu kullanır. Hız her seviye sonunda artar. Başlangıç bipi varsayılan 10. saniyedir; farklı kayıtlar için `--start-beep-time` belirtilmelidir. Bu değerler kayıt protokolüyle eşleştirilmeden puanlama doğruluğu varsayılamaz.

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/inspect_desktop_videos.py
python scripts/audit_videos.py
```

Son iki komut masaüstündeki `MEKİK VİDEO` klasörünü inceler. Denetim bütün kareleri okur, saniyede bir karede gerçek YOLO çıkarımı yapar ve ses kanalını analiz eder. Sonuçlar `data/outputs/verification/desktop_audit.json` dosyasındadır. Bu teknik denetim, insan tarafından etiketlenmiş koşucu/geçiş doğruluğu ölçümü değildir.

20m mekik koşusu testini (Beep Test) bilgisayarla görme ile otomatik puanlayan sistem.

## 🆕 v3.1 — Error Handling & Logging

- ✅ **Kapsamlı error handling** — hatalı girdilerde sistem çökmez
- ✅ **Logging sistemi** — tüm olaylar `data/logs/` klasörüne kaydedilir
- ✅ **Model doğrulama** — YOLO modeli yüklenmeden kontrol edilir
- ✅ **File validation** — video ve yapılandırma dosyaları kontrol edilir
- ✅ **Unit testler** — `pytest` ile otomatik testler
- ✅ **Exception handling** — model/kare işlemesi başarısızsa güvenilmez sonuç üretmek yerine açıklayıcı hatayla durur

## v4 — İki Gerçek Kamera + Dinamik Çizgi Takibi

- **0m ve 20m videoları**: Kök dizindeki `0metre.mp4` ve `20metre.mp4` varsayılan olarak iki ayrı kamera kabul edilir.
- **Dinamik çizgi takibi**: Kalibre edilen çizgiler her karede yeniden izlenir; çizgi görünmezse hafif kamera kayması kareler arası hareketten telafi edilir.
- **Bip/deadline değerlendirmesi**: Koşucu her bipte ilgili uç çizgiye temas/geçiş yapmak zorundadır.
- **Eleme mantığı**: Ardışık `MAX_CONSECUTIVE_LATE` gecikme/kaçırma sonrası koşucu elenir.
- **Ses veya matematiksel zamanlayıcı**: Video sesinden bip bulunursa kullanılır; bulunamazsa resmi hız tablosuna göre sanal bipler üretilir.

## Neden Tek Çizgi?

Kamera arkadan çekim yaptığında koşucular 20m ucunda çok küçülüyor ve
hiçbir model onları tespit edemiyor. Tek çizgi yaklaşımı, koşucuların
görülebildiği alanda çalışarak bu sorunu ortadan kaldırır.

## 📦 Kurulum

```bash
pip install -r requirements.txt
```

### Test Çalıştırma

```bash
# Tüm testleri çalıştır
pytest tests/

# Verbose mod
pytest tests/ -v

# Belirli test dosyasını çalıştır
pytest tests/test_validators.py
```

## 🚀 Kullanım

### Ana Program (Tek Çizgi)

```bash
python main.py                                  # YouTube'dan indir + işle
python main.py --no-display                     # Ekransız çalıştır
python main.py --video path/to/video.mp4        # Yerel video
python main.py --video path/to/video.mp4 --start-time 5.0  # Başlangıç zamanını belirt
```

### Çift Kamera Sistemi

```bash
python dual_main.py                             # 0metre.mp4 + 20metre.mp4
python dual_main.py --no-display                # Ekransız çalıştır
python dual_main.py --no-audio                  # Matematiksel bip zamanlayıcı
python dual_main.py --start-time 9.5            # Koşu başlangıç saniyesi
python dual_main.py --start-video a.mp4 --far-video b.mp4
python dual_main.py --use-config-lines          # Hazır config çizgilerini kullan
```

## 📂 Klasör Yapısı

```
mekikTestProje/
├── data/
│   ├── inputs/          ← Video dosyaları buraya koyun
│   ├── outputs/         ← Analiz videoları ve raporlar
│   └── logs/            ← İşlem logları (otomatik oluşturulur)
├── tests/               ← Unit testler
├── logger.py            ← Logging sistemi (YENİ)
├── validators.py        ← File ve sistem doğrulama (YENİ)
├── config.py            ← Merkezi yapılandırma
├── main.py              ← Ana program (güncellenmiş)
├── dual_main.py         ← Çift kamera programı
├── tracker.py           ← YOLOv8-Pose takibi (güncellenmiş)
├── analyser.py          ← Mekik değerlendirme
└── timer.py             ← Zamanlayıcı
```

## 📋 Loglar Nerede?

Her çalışma `data/logs/mekik_test_YYYYMMDD_HHMMSS.log` dosyasında kaydedilir.

```bash
# En yeni loga bak (Windows PowerShell)
Get-Content "data\logs\mekik_test_*.log" -Tail 50

# Hata satırlarını göster
Select-String -Path "data\logs\*.log" -Pattern "ERROR|EXCEPTION"
```

## 🔧 Sorun Giderme

### ❌ "YOLO model bulunamadı" hatası

```bash
python -c "from ultralytics import YOLO; YOLO('yolov8n-pose.pt')"
```

### ❌ "Video bulunamadı" hatası

- `data/inputs/` klasörüne video koyun, VEYA
- `--video /path/to/video.mp4` argümanını kullanın

### ❌ "yt-dlp kurulu değil" hatası

```bash
pip install yt-dlp
```

### ❌ Frame işlemesi başarısız

- Log dosyasını kontrol edin: `data/logs/`
- Video dosyasının bozuk olmadığını kontrol edin
- Modeli yeniden indirin: `python -c "from ultralytics import YOLO; YOLO('yolov8n-pose.pt')"`

## 📊 Çıktılar

- `*_analyzed.mp4` — Video overlay ile sonuçlar
- `results_TIMESTAMP.csv` — Koşucu sonuçları tablosu
- `mekik_test_*.log` — İşlem logları

### Kalibrasyon

`dual_main.py` varsayılan olarak her çalışmada iki kameranın ilk karesini açar ve kullanıcıdan çizgileri kendisinin seçmesini ister:

- Kamera 1: başlangıç / 0m çizgisi
- Kamera 2: 20m çizgisi

Her çizgi için soldan sağa iki nokta seçin. Hazır çizgi koordinatlarını kullanmak isterseniz `config.py` içindeki `DUAL_START_LINE_POINTS` ve `DUAL_FAR_LINE_POINTS` değerlerini doldurup programı `--use-config-lines` ile çalıştırın.
