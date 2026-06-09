# Otomatik Mekik Testi Değerlendirme Sistemi (v3)

20m mekik koşusu testini (Beep Test) bilgisayarla görme ile otomatik puanlayan sistem.

## 🆕 v3.1 — Error Handling & Logging

- ✅ **Kapsamlı error handling** — hatalı girdilerde sistem çökmez
- ✅ **Logging sistemi** — tüm olaylar `data/logs/` klasörüne kaydedilir
- ✅ **Model doğrulama** — YOLO modeli yüklenmeden kontrol edilir
- ✅ **File validation** — video ve yapılandırma dosyaları kontrol edilir
- ✅ **Unit testler** — `pytest` ile otomatik testler
- ✅ **Exception handling** — frame işlemeleri başarısız olsa bile devam eder

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
