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

## Son doğrulama - 18 Kasım 2026

- **72 otomatik test geçti.** 14 kaynak videonun 50.777 karesi okundu ve masaüstündeki asıllarla dosya hash değerleri eşleşti.
- **7 kamera çiftinin ortak aralıklarında 24.298 kare** atlanmadan analiz edildi. Çıktı videoları tekrar okundu; CSV ve Excel eşitliği ile mekik kayıtlarının tekilliği doğrulandı.
- Video 1-6 otomatik puanlandı. Standart ritme uymayan Video 7 gözlem olarak tamamlandı ve puanlanmadı.
- Bu teknik doğrulamadır; hakem etiketlerine karşı doğruluk oranı ölçülmedi. Video 1'in tahmini başlangıç zamanı ve Video 6'nın kadraj sınırı özellikle gözden geçirilmelidir.

[PDF teslim raporu](docs/reports/2026-11-18/MEKIK_DOGRULAMA_RAPORU.pdf) · [Toplu Excel](docs/reports/2026-11-18/TUM_SONUCLAR.xlsx) · [Teknik rapor](docs/reports/2026-11-18/RAPOR.md) · [Makine doğrulama kaydı](docs/reports/2026-11-18/dogrulama.json)

Yerel görüntülü sonuçların başlangıç sayfası: `data/outputs/sonuclar/SONUCLAR.html`. Büyük kaynak ve çıktı videoları bu teslim commitine eklenmez.

---

## 1. Hızlı başlangıç

**VS Code:** Sol menüde *Run and Debug* (▶) → açılır listeden bir ayar seçin → ▶ / F5.

İlk kurulumda **Python: Select Interpreter** komutuyla bağımlılıkları kurduğunuz Python ortamını seçin. Çalıştırma ayarları sabit bir kullanıcı klasörüne değil, seçili yorumlayıcıya bağlanır.

| Ayar | Ne yapar |
|---|---|
| `Mekik - Video N (goruntulu)` | N. kaydı pencerede, videonun kendi hızında izletir |
| `Mekik - Masaustu Kayitlari (menu)` | Terminalde kayıt numarası sorar |
| `Mekik - Tum Kayitlar (ekransiz)` | 7 kaydın hepsini kare atlamadan analiz eder |

**Terminal:**

```powershell
python run_sessions.py --list               # kayıtları ve ayarlarını listele
python run_sessions.py -s 2                 # Video 2'yi izle (kendi hızında)
python run_sessions.py -s 2 --no-display    # Video 2, ekransız, her kare
python run_sessions.py --all --no-display   # hepsi + toplu özet
python run_sessions.py -s 2 --recalibrate   # çizgileri fareyle yeniden seç
```

> **Görüntülü mod** videoyu kendi hızında oynatır. İşlemci her kareye yetişemediği için
> saniyede birkaç kare analiz edilir; izlemek ve kontrol etmek içindir.
> **Ekransız mod** her kareyi işler; kare atlamayan otomatik değerlendirme için bunu kullanın.
> Tam kare analizi, insan/hakem etiketlerine karşı yüzde yüz doğruluk garantisi değildir.

Pencerede **Q / ESC** durdurur. Video bitince pencere açık kalır; bir tuşa basınca kapanır.

## 2. Sonuçlar nereye yazılır?

```
data/outputs/sonuclar/
├── SONUCLAR.html        ← analizi yapılmış tüm kayıtlar tek sayfada (buradan başlayın)
├── TUM_SONUCLAR.xlsx    ← aynısı Excel olarak
└── video_N/
    ├── SONUC.html       ← bu kaydın raporu
    ├── SONUC.xlsx       ← "Sonuç" ve "Mekik mekik" sayfaları (renkli)
    ├── sonuc_ozet.csv   ← koşucu başına bir satır
    ├── sonuc_mekikler.csv ← koşucu ve mekik başına bir satır
    ├── son_durum.jpg    ← videonun son ekranı
    ├── analiz_videosu.mp4 ← iki kamera yan yana, işaretlenmiş
    └── teknik/          ← ham veriler ve ayarlar (geliştirici için)
```

**Sonuç tablosu** (`sonuc_ozet.csv`), her koşucu için:

| Sütun | Anlamı |
|---|---|
| Sonuç | *Devam etti* (kayıt bitene kadar) ya da *Elendi* |
| Tamamlanan mekik / Koşulan mesafe | Zamanında tamamlanan 20 m'lik mekik sayısı ve toplam metre |
| Ulaştığı seviye | Son tamamlanan mekik, ör. *Seviye 2 – 5. mekik* |
| Son hız | O mekiğin temposu (km/sa) |
| Uyarı | Bip çaldığında çizgiye ulaşamadığı mekik sayısı |
| Elendiği an / Açıklama | Ne zaman ve hangi çizgide elendiği |

**Mekik mekik tablosu**, her mekik için bip zamanını, koşucunun çizgiye ulaştığı anı ve
kararı gösterir: *Zamanında*, *Geç kaldı (uyarı)*, *Geç ulaştı (uyarı)*, *Ulaşamadı → elendi*.

Koşucu numaraları başlangıç kamerasından bakınca soldan sağa sıralıdır. Raporun doğruluğunu
bağımsız kontrol etmek için: `python scripts/verify_analysis_output.py data/outputs/sonuclar/video_2`

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
├── video_dashboard.py       ← Video üzerindeki panel (süre, koşucu kartları)
├── result_report.py         ← Okunur sonuç tabloları ve HTML/Excel raporlar
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
   4. Sonunda:        SONUC.html, SONUC.xlsx, analiz videosu; tüm kayıtlar SONUCLAR.html
```

Kurallar (`config.py`):

- Ayak çizgiye **basarsa** yeterli (`LINE_TOUCH_TOLERANCE_PX = 10`).
- Kulvar kimliği ve geçiş değerlendirmesi yalnızca hedef çizgi çevresindeki tespitlerde uygulanır (kare yüksekliğinin %14'ü, en az 40 piksel). Bu alan ve kulvar uçları kamera hareketinde çizgiyle birlikte taşınır. Uzakta kutu/kimlik görünmemesi bu nedenle beklenen davranıştır; bütün kareler yine modelden geçirilir.
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
- Bu nedenle Video 7'de puanlama kapalıdır (`scoring_eligible: false`): raporda “Puanlanmadı” gösterilir, standart mesafe/seviye/eleme kararı yayımlanmaz.
- **Video 1**'de salon bipi neredeyse duyulmuyor; çıkış zamanı ±1 s belirsizdir. Bu yüzden 3. mekikte herkese "geç" uyarısı çıkabilir.
- Sonuçlar otomatik değerlendirmedir; hakem kayıtlarıyla karşılaştırılmamıştır.

## 7. Kurulum ve test

Python 3.11 veya daha yeni bir sürüm kullanın. Girdi videoları ve model dosyaları yerel diskte bulunmalıdır; örnek veri ve model yolları `config.py` içindedir.

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

18 Kasım 2026'da kullanılan Windows/Python 3.14.3 paket sürümleri `requirements-tested.txt` içindedir. Aynı sürümleri kurmak için `python -m pip install -r requirements-dev.txt -c requirements-tested.txt` kullanılabilir. Bu dosya yalnızca test edilen ortamı kaydeder; başka işletim sistemleri ayrıca test edilmemiştir. ByteTrack'in `lap` bağımlılığı kurulum listesine dahildir; ilk analiz sırasında ayrıca indirilmesi gerekmez.

Eski sürüm notları: `docs/GECMIS_NOTLAR.md` · Kalibrasyon: `docs/CALIBRATION_GUIDE.md`

## 8. Toplu doğrulama ve teslim raporu

```powershell
python scripts/start_full_batch.py
python scripts/audit_session_sources.py
python -m pytest -q --junitxml=data/outputs/hazirlik_2026-11-18/testler.xml
python scripts/prepare_release.py
```

İlk komut analiz öncesi kod/ayar parmak izini ve başlangıç zamanını kaydeder. Son komut yalnızca bütün kayıtların yeni tam kare analizi tamamlanmış, beklenen koşucu sayıları bulunmuş ve kaynak kontrolleri geçmişse rapor üretir. Çıktı videolarını tekrar okur; CSV/Excel eşitliğini ve tekrarlanan mekik kaydı olmadığını denetler. Video ve metadata hash değerleri kontrol kayıtlarına eklenir; eski bir kontrol dosyası yeni çıktının doğrulanması sayılmaz.

Teslim raporu `docs/reports/2026-11-18/RAPOR.md`, makine kaydı `dogrulama.json` ve koşucu sonuçları `kosucu_sonuclari.csv` dosyalarıdır. PDF için isteğe bağlı `reportlab` kurulu ortamda `python scripts/build_release_pdf.py` çalıştırılabilir. Yeni kaynak ve analiz videoları GitHub'a eklenmez; yerel sonuç klasöründe kalır.
