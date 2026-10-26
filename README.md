# Otomatik Mekik Testi (20 m Beep Test) Değerlendirme Sistemi

İki telefonla çekilen mekik koşusu videolarını izler. Koşucuların her bipte ilgili
çizgiye ulaşıp ulaşmadığını yapay zekâ ile (YOLOv8-Pose) kontrol eder; geç kalanları
uyarır, üst üste iki kez kaçıranları eler ve rapor üretir.

```
   [0 m telefonu]  →  koşucular  ⇄  20 m  ←  [20 m telefonu]
   baslangic_0m.mp4                          bitis_20m.mp4
```

Her telefon kendi çizgisinin arkasında durur ve koşucular ona doğru koşarken o çizgiyi
denetler.

---

## 1. Hızlı başlangıç

**VS Code:** Sol menüde *Run and Debug* (▶) → açılır listeden bir ayar seçin → ▶ / F5.

| Ayar | Ne yapar |
|---|---|
| `Mekik - Video N (goruntulu)` | N. kaydı pencerede, videonun kendi hızında izletir |
| `Mekik - Masaustu Kayitlari (menu)` | Terminalde kayıt numarası sorar |
| `Mekik - Tum Kayitlar (ekransiz)` | 7 kaydın hepsini her kareyi işleyerek analiz eder (kesin sonuç) |

**Terminal:**

```powershell
python run_sessions.py --list               # kayıtları ve ayarlarını listele
python run_sessions.py -s 2                 # Video 2'yi izle (kendi hızında)
python run_sessions.py -s 2 --no-display    # Video 2, ekransız, her kare (kesin sonuç)
python run_sessions.py --all --no-display   # hepsi + toplu özet
python run_sessions.py -s 2 --recalibrate   # çizgileri fareyle yeniden seç
```

> **Görüntülü mod** videoyu kendi hızında oynatır. İşlemci her kareye yetişemediği için
> saniyede birkaç kare analiz edilir; izlemek ve kontrol etmek içindir.
> **Ekransız mod** her kareyi işler; kesin puanlar için bunu kullanın.

Pencerede **Q / ESC** durdurur. Video bitince pencere açık kalır; bir tuşa basınca kapanır.

## 2. Sonuçlar nereye yazılır?

`data/outputs/sonuclar/video_N/`

| Dosya | İçerik |
|---|---|
| `analiz_raporu.html` | Tarayıcıda açılan özet rapor |
| `sonuc_ozet.csv` / `sonuc_rapor.xlsx` | Koşucu başına durum, geçiş, geç, eleme |
| `sonuc_detay.csv` | Her çizgi geçişi ve bip kararı |
| `sonuc_paneli.jpg` | Son durum ekranı |
| `*_dual_camera.mp4` | İki kamera yan yana, işaretlenmiş analiz videosu |
| `run_metadata.json` | Kullanılan ayarlar, kamera kayması istatistikleri |

Hepsi birlikte çalıştırılırsa: `data/outputs/sonuclar/tum_kayitlar_ozet.csv`

## 3. Klasör yapısı

```
mekikTestProje/
├── run_sessions.py          ← ANA PROGRAM: kayıtları seçip çalıştırır
├── mekik_sessions.json      ← 7 kaydın ayarları (çizgiler, koşucu sayısı, bip, senkron)
├── config.py                ← Genel ayarlar (toleranslar, eleme kuralı, model yolu…)
│
├── dual_main.py             ← Analiz döngüsü: iki videoyu senkron okur, çizer, raporlar
├── dual_camera_analyser.py  ← Puanlama kuralları (zamanında / geç / elendi)
├── tracker.py               ← YOLOv8-Pose ile kişi ve ayak tespiti
├── camera_motion.py         ← Elde tutulan telefonun kaymasını telafi eder
├── run_start.py             ← Ses yoksa çıkış anını koşucuların kalkışından bulur
├── audio_detector.py        ← Bip sesi tespiti
├── timer.py                 ← Resmi mekik temposu (seviye / hız tablosu)
├── line_geometry.py         ← Perspektifli çizgi hesabı
├── video_dashboard.py       ← Ekran paneli ve HTML rapor
├── line_calibrator.py       ← Fareyle çizgi seçme penceresi
├── validators.py, logger.py ← Dosya doğrulama ve günlük kaydı
├── main.py                  ← (Eski) tek kameralı sürüm
├── line_tracker.py, cone_*.py, video_splitter.py ← (Eski) yardımcılar; dual_main içinden isteğe bağlı
│
├── models/                  ← yolov8n-pose.pt, yolov8s-pose.pt, custom_bytetrack.yaml
├── data/
│   ├── inputs/
│   │   ├── mekik_video/video_1 … video_7/   ← baslangic_0m.mp4 + bitis_20m.mp4 (+ kaynak.txt)
│   │   ├── referans/reference_beep_audio.mp4 ← salonda çalan bip kaydı (Léger 20 m)
│   │   └── ornek_kayit/                     ← eski örnekler (0metre.mp4, 20metre.mp4…)
│   ├── outputs/
│   │   ├── sonuclar/video_N/                ← güncel analiz çıktıları
│   │   └── _eski/                           ← önceki denemelerin çıktıları
│   └── logs/                                ← çalışma günlükleri
├── tests/                   ← otomatik testler (python -m pytest -q)
├── scripts/                 ← denetim araçları (eski rapor betikleri: scripts/eski/)
└── docs/                    ← kalibrasyon rehberi, doğrulama raporu, geçmiş notlar
```

`data/inputs/mekik_video/` masaüstündeki **MEKİK VİDEO** klasörünün kopyasıdır. Her
klasördeki `kaynak.txt` hangi WhatsApp dosyasından geldiğini yazar. Bu klasör büyük
olduğu için `.gitignore` ile git dışında tutulur.

## 4. Nasıl çalışır?

```
mekik_sessions.json ──► run_sessions.py ──► dual_main.process_dual_camera()
                                              │
   1. Bip çizelgesi:  referans bip kaydı → bipler arası resmi aralıklar
                      (8,47 s × 7, 8,0 s × 8, 7,58 s × 8 …), çıkış bipinden başlar
   2. Her kare:       0 m videosu + 20 m videosu (cam2_offset ile eşlenir)
                      ├─ camera_motion: telefon kaydıysa çizgiyi yeni yerine taşı
                      ├─ tracker: kişileri ve ayak noktalarını bul
                      ├─ kulvar ataması: soldan sağa koşucu 1, 2, 3…
                      └─ analyser: ayak çizgiye bastı mı? Bip geldi mi?
   3. Bip anında:     hedef çizgiye ulaşmayan → GEÇ; üst üste 2 kez → ELENDİ
   4. Sonunda:        CSV, Excel, HTML rapor, analiz videosu
```

Kurallar (`config.py`):

- Ayak çizgiye **basarsa** yeterli (`LINE_TOUCH_TOLERANCE_PX = 10`).
- Bipten sonraki **0,5 s** içinde ulaşan zamanında sayılır (`LATE_TOLERANCE_SEC`). Bu pay, iki telefon arasındaki senkron ve ölçüm belirsizliği içindir.
- Üst üste **2** gecikme ya da kaçırma eleme sebebidir (`MAX_CONSECUTIVE_LATE`).

## 5. Kayıtların ayarları nasıl bulundu?

| Ayar | Yöntem |
|---|---|
| Hangi video 0 m / 20 m | Karelere bakılarak (koşucular kameraya yaklaşıp hangi çizgide dönüyor) |
| Çıkış bipi | Kaydın sesi referans bip kaydıyla eşleştirildi (672 Hz bip) |
| İki kamera arası fark | İki kaydın sesi karşılaştırıldı; Video 1'de dönüşlerdeki ayakkabı gıcırtıları kullanıldı |
| Çizgiler | Zemindeki çizgiler kareler üzerinde ölçüldü, koşucuların dönüş noktalarıyla doğrulandı |
| Koşucu sayısı | Başlangıç karesinden sayıldı |

Yeni bir kayıt eklemek için `mekik_sessions.json` dosyasına yeni bir bölüm ekleyin.
Çizgileri `--recalibrate` ile fareyle seçebilirsiniz. Ses yoksa `"start_beep_time": "kalkis"`
yazın; çıkış anı koşucuların kalkışından bulunur.

## 6. Bilinen sınırlar

- **Video 7** standart bip testi değildir: koşucular ~31 s'de bir gidip dönüyor, arada bekliyor. Puanlaması anlamlı değildir.
- **Video 1**'de salon bipi neredeyse duyulmuyor; çıkış zamanı ±1 s belirsizdir. Bu yüzden 3. mekikte herkese "geç" uyarısı çıkabilir.
- Sonuçlar otomatik değerlendirmedir; hakem kayıtlarıyla karşılaştırılmamıştır.

## 7. Kurulum ve test

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Eski sürüm notları: `docs/GECMIS_NOTLAR.md` · Kalibrasyon: `docs/CALIBRATION_GUIDE.md`
