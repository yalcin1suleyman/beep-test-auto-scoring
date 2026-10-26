"""
config.py — Otomatik Mekik Testi Değerlendirme Sistemi (v2)
Merkezi yapılandırma dosyası: sabitler, eşik değerleri ve veri yapıları.

v2 Değişiklikler:
  - Ses analizi kaldırıldı → Matematiksel zamanlayıcı
  - X ekseni → Y ekseni (kamera arkadan çekim, koşucular derinliğe koşuyor)
  - YouTube video indirme desteği
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ==============================================================================
# Proje Yolları
# ==============================================================================
PROJECT_ROOT = Path(__file__).parent
DATA_INPUTS = PROJECT_ROOT / "data" / "inputs"
DATA_OUTPUTS = PROJECT_ROOT / "data" / "outputs"
SAMPLE_INPUTS = DATA_INPUTS / "ornek_kayit"        # Eski tek/cift kamera ornek videolari
REFERENCE_INPUTS = DATA_INPUTS / "referans"         # Salonda calan bip kaydi

# Kullanici tarafindan yuklenen varsayilan cift kamera videolari.
# 0m kamerasi baslangic cizgisini, 20m kamerasi karsi uc cizgisini gorur.
DEFAULT_START_CAMERA_VIDEO = SAMPLE_INPUTS / "0metre.mp4"
DEFAULT_FAR_CAMERA_VIDEO = SAMPLE_INPUTS / "20metre.mp4"

# ==============================================================================
# YouTube Video İndirme
# ==============================================================================
DEFAULT_VIDEO_URL = "https://youtu.be/yUQAjRGAY0c?si=yCinebia1cDaRz7x"
DEFAULT_BEEP_AUDIO_URL = "https://youtu.be/wAISjikeyZU?si=gbJEyHtffnRTqFgd"

# ==============================================================================
# Video Başlangıç Zamanı (Senkronizasyon)
# ==============================================================================
# Koşunun videoda başladığı saniye. Video bu noktadan itibaren işlenir.
# Zamanlayıcı ve eleme mantığı bu anı "0. saniye" kabul eder.
VIDEO_START_TIME_SEC = 0.0

# Bu video setinde koşucular video 10. saniyedeki çıkış bipiyle başlar.
# Hedef bipleri bu andan itibaren 7 km/h mekik temposuyla üretilir.
DEFAULT_START_BEEP_TIME_SEC: float | None = 10.0

# ==============================================================================
# YOLOv8-Pose Ayarları
# ==============================================================================
# Nano model = en hızlı. Uzak mesafe tespiti İMKANSIZ olduğunda model
# büyütmek yerine ÇİZGİLERİ tespitın güvenilir olduğu bölgeye taşıyın.
# (Kalibrasyon sırasında çizgiyi ekranın en üstüne DEĞİL,
#  koşucuların hâlâ net göründüğü yere koyun.)
YOLO_MODEL = "models/yolov8n-pose.pt"

# Özel ByteTrack yapılandırması — uzak mesafe ID kurtarma optimize
TRACKER_CONFIG = "models/custom_bytetrack.yaml"

# Güven eşiği: 0.15 = uzak tespitlerde denge noktası
# Çok düşük (0.05) → yanlış pozitifler, çok yüksek (0.5) → uzak kayıplar
CONFIDENCE_THRESHOLD = 0.15

IOU_THRESHOLD = 0.45                    # NMS IoU eşiği

# Çıkarım çözünürlüğü: canlı/normal kamera akışı için düşük tutulur.
# Daha yüksek değer daha iyi tespit ama daha yavaş görüntü demektir.
# Uzak tespit sorunu çizgi konumuyla çözülür, model boyutuyla değil.
INFER_IMGSZ = 480

# ==============================================================================
# COCO Keypoint İndeksleri — Ayak Bileği
# ==============================================================================
LEFT_ANKLE_IDX = 15                     # Sol ayak bileği
RIGHT_ANKLE_IDX = 16                    # Sağ ayak bileği

# ==============================================================================
# Sanal Çizgi Ayarları — TEK ÇİZGİ (v3, eski mod)
# ==============================================================================
# v3 MİMARİ: İki çizgi yerine TEK çizgi kullanılır.
# None = ilk çalıştırmada fare ile kalibre edilecek
DETECTION_LINE_Y: int | None = None    # Tespit çizgisi Y koordinatı

LINE_COLOR_DETECT = (0, 255, 255)       # Sarı — tespit çizgisi
LINE_THICKNESS = 2                      # Çizgi kalınlığı (piksel)

# Çizgi geçiş tespiti — titreşim önleme marjı (piksel)
CROSSING_HYSTERESIS_PX = 15             # 15px = daha geniş marj (ID kayması önlenir)
# Kosucu cizgiye basarsa (gecmese de) mekik tamamlanmis sayilir. Ayak kutusunun
# alt kenari boyali cizginin bu kadar piksel onunde kalsa da temas kabul edilir.
LINE_TOUCH_TOLERANCE_PX = 10

# Kalibre edilen yatay cizgi her karede yeniden takip edilir. Kamera hafif
# kayarsa deger bu sinirlar icinde yumusak bicimde guncellenir.
ENABLE_AUTO_LINE_TRACKING = False
LINE_TRACK_SEARCH_MARGIN_PX = 70
LINE_TRACK_MIN_CONFIDENCE = 0.18
LINE_TRACK_SMOOTHING_ALPHA = 0.25
LINE_TRACK_MAX_STEP_PX = 8

# Elde tutulan telefon kameralari zamanla kayar/egilir. Acikken kalibrasyon
# karesine gore homografi hesaplanir ve cizgiler guncel kareye tasinir.
ENABLE_CAMERA_MOTION_COMPENSATION = True
MOTION_COMP_UPDATE_EVERY = 3            # Kac karede bir kamera hareketi hesaplanir

# ==============================================================================
# Çift Kamera Sistemi — İki Çizgi Ayarları (dual_main.py için)
# ==============================================================================
# None = ilk çalıştırmada fare ile kalibre edilecek (iki tıklama)
# Manuel piksel değeri atanabilir (test sonrası sabitlemek için)
#
# start_line_y: Başlangıç (0m) çizgisi — koşucuların kameraya yakın göründüğü yer
#               Büyük Y değeri (ekranın alt bölgesi)
# far_line_y  : 20m çizgisi — koşucuların uzakta/küçük göründüğü yer
#               Küçük Y değeri (ekranın üst bölgesi)
#
# ÖNEMLİ: far_line_y < start_line_y olmalı (piksel koordinatları)
DUAL_START_LINE_Y: int | None = None   # Başlangıç (0m) çizgisi Y pikseli
DUAL_FAR_LINE_Y: int | None = None     # 20m çizgisi Y pikseli

# Perspektifli cizgi noktaları. None = dual_main.py her calistiginda iki
# kamerada da kullanicidan 2 tiklamayla cizgiyi secmesini ister.
# Hazir noktalarla calismak isterseniz bu degerleri doldurup dual_main.py'yi
# --use-config-lines ile calistirin.
DUAL_START_LINE_POINTS: list[tuple[int, int]] | None = None
DUAL_FAR_LINE_POINTS: list[tuple[int, int]] | None = None

# ==============================================================================
# Dinamik Koni Tespit Sistemi — Kamera Hareketine Dayanıklı Çizgiler
# ==============================================================================
# Konileri otomatik tespit et (True) veya kullanicinin sectigi cizgiyi koru (False)
ENABLE_CONE_DETECTION: bool = False     # Varsayilan: manuel kalibrasyon cizgisi

# HSV renk aralığı — laranja koniler
CONE_HSV_LOWER: tuple[int, int, int] = (0, 80, 80)      # Laranja alt sınırı
CONE_HSV_UPPER: tuple[int, int, int] = (15, 255, 255)   # Laranja üst sınırı
CONE_HSV_SECONDARY_LOWER: tuple[int, int, int] = (170, 80, 80)    # Kırmızı alt sınırı
CONE_HSV_SECONDARY_UPPER: tuple[int, int, int] = (180, 255, 255)  # Kırmızı üst sınırı

# Koni boyutu filtresi (piksel²)
CONE_MIN_AREA_PX: int = 200             # Minimum koni alanı
CONE_MAX_AREA_PX: int = 50000           # Maximum koni alanı (yanlış pozitif engelle)
CONE_MIN_CIRCULARITY: float = 0.4       # Şekil çemberkiliği (0-1)

# Çizgi suavizasyon — kamera hareketi düzeltme
CONE_LINE_SMOOTHING_ALPHA: float = 0.7  # 0=çok suave, 1=hiç suave
CONE_DEBUG_DRAW: bool = True            # Konileri ekrana çiz (debug)

# ==============================================================================
# Ses Tabanlı Bip Tespiti (dual_main.py için)
# ==============================================================================
# Mekik testi bip sesi frekans aralığı (Hz)
# Standart beep test: ~1000 Hz sine wave
BEEP_FREQ_MIN_HZ: float = 450.0        # Bip frekans alt sınırı
BEEP_FREQ_MAX_HZ: float = 750.0        # Bip frekans üst sınırı

# Ardışık iki bip arasındaki minimum süre (saniye)
# Seviye 1 mekik süresi ~9s, bu değer çok düşük olmamalı
BEEP_MIN_GAP_SEC: float = 5.0          # Minimum bip arası (saniye)

# Bip enerjisi eşiği — kaç yüzdelik dilimdeki enerji eşik sayılır
# Düşük (60) = daha duyarlı ama gürültüye açık
# Yüksek (90) = daha seçici ama zayıf bipleri kaçırabilir
BEEP_ENERGY_THRESHOLD_PERCENTILE: float = 90.0

# Videodaki ses bipi zamanları tutarsızsa ilk güçlü start bipini kullanıp
# sonraki deadline'ları resmi mekik zamanlayıcıyla üret.
BEEP_STRONG_THRESHOLD_RATIO: float = 0.45
BEEP_MIN_VALID_SHUTTLE_SEC: float = 5.5

# ==============================================================================
# Çift Kamera Simülasyonu — Video Zaman Ofseti
# ==============================================================================
# Eski tek-video simulasyonunda Kamera 2 (20m), ana videoyu bu kadar saniye
# sonradan baslatir. Iki ayri video verildiginde varsayilan 0.0 kullanilir.
CAM2_OFFSET_SEC: float = 9.0

# Değerlendirmede ilk 20m deadline'ı. Kamera 2 video ofsetinden bağımsızdır:
# video 9s sonradan başlayabilir, ama koşucunun 20m'ye ulaşması için beklenen
# bip/deadline 10s kabul edilebilir.
FIRST_BEEP_DEADLINE_SEC: float = 10.0

# Tek video simülasyonunda iki tracker'ın aynı yarışmacı ID'lerini
# aynı kişi kabul etmesi gerekir. Gerçek iki fiziksel kamera kullanımında
# re-id/eşleştirme yapılana kadar False + CAM2_ID_OFFSET kullanılabilir.
CAM2_SHARE_TRACK_IDS: bool = True

# İki kameranın takip ID'lerinin çakışmaması için ofset
CAM2_ID_OFFSET: int = 1000

# ==============================================================================
# Matematiksel Mekik Zamanlayıcısı (Ses Yerine / Yedek)
# ==============================================================================
# Mekik koşusu formülü:
#   Hız (km/h) = 7.0 + (Seviye - 1) * 0.5
#   Bir mekik süresi (s) = 20 / (Hız * 1000 / 3600)
#
SHUTTLE_DISTANCE_M = 20.0               # Mekik mesafesi (metre)
INITIAL_SPEED_KMH = 7.0                 # Seviye 1 başlangıç hızı (km/h)
SPEED_INCREMENT_KMH = 0.5               # Her seviyede hız artışı (km/h)
SPEED_INCREMENT_EVERY_SHUTTLE = False   # Hiz SHUTTLES_PER_LEVEL tablosuna gore seviye sonunda artar

# Her seviyedeki mekik sayıları (resmi beep test tablosu)
# Seviye 1: 7 mekik, Seviye 2: 8, Seviye 3: 8, ... Seviye 21: 16
SHUTTLES_PER_LEVEL = [
    7,   # Seviye 1
    8,   # Seviye 2
    8,   # Seviye 3
    9,   # Seviye 4
    9,   # Seviye 5
    10,  # Seviye 6
    10,  # Seviye 7
    11,  # Seviye 8
    11,  # Seviye 9
    11,  # Seviye 10
    12,  # Seviye 11
    12,  # Seviye 12
    13,  # Seviye 13
    13,  # Seviye 14
    13,  # Seviye 15
    14,  # Seviye 16
    14,  # Seviye 17
    15,  # Seviye 18
    15,  # Seviye 19
    16,  # Seviye 20
    16,  # Seviye 21
]

# ==============================================================================
# Değerlendirme Mantığı
# ==============================================================================
LATE_TOLERANCE_SEC = 0.5                # Bipten sonra bu sure icinde cizgiye ulasan zamaninda sayilir (senkron/olcum belirsizligi payi)
MAX_CONSECUTIVE_LATE = 2                # Ardışık bu kadar gecikme/kaçırma sonrası eleme yapılır
MIN_SHUTTLE_INTERVAL_SEC = 2.0          # Aynı koşucu iki uç çizgiyi bundan hızlı tamamlayamaz
MASS_ELIMINATION_GUARD = False          # Resmi timer kullanılırken herkes kaçırırsa herkes elenir

# ==============================================================================
# Performans & Görüntüleme Optimizasyonu
# ==============================================================================
# Her N karede bir ekrana çizim yap (imshow FPS yükünü azaltır)
# 1 = her kare, 3 = her 3 karede bir görüntüle (çıktı video hâlâ her kareyi yazar)
DISPLAY_EVERY_N_FRAMES = 1

# Canlı pencerede videonun normal hızda akması için analiz yetişmediğinde
# kare atlanır. Tam kare kare analiz için --no-display kullanın.
REALTIME_PREVIEW = True
MAX_REALTIME_FRAME_SKIP = 12

# ==============================================================================
# Bölge İçi (ROI) Takip Kısıtlaması
# ==============================================================================
# Sadece parkur alanındaki tespitleri değerlendir.
# Seyircilere, kenardaki kişilere ID atanmasını engeller.
# None = kısıtlama yok (tüm ekran).
ROI_X_MIN: int | None = None           # Parkurun sol X sınırı (piksel)
ROI_X_MAX: int | None = None           # Parkurun sağ X sınırı (piksel)

# Kulvar tabanlı ID sabitleme. Yarışmacılar kulvar değiştirmiyorsa ByteTrack ID'si
# yerine bu sabit kulvar ID'si kullanılır. Bu videoda 5 yarışmacı vardır.
EXPECTED_RUNNER_COUNT: int = 5

# ==============================================================================
# Görselleştirme Ayarları
# ==============================================================================
FONT_SCALE = 0.6
FONT_THICKNESS = 2
ANKLE_CIRCLE_RADIUS = 5
ANKLE_CIRCLE_COLOR = (255, 165, 0)      # Turuncu — ayak bileği noktası

# Koşucu durum renkleri (BGR)
COLOR_ACTIVE = (0, 255, 0)              # Yeşil — aktif
COLOR_WARNING = (0, 255, 255)           # Sarı — 1 gecikme uyarısı
COLOR_ELIMINATED = (0, 0, 255)          # Kırmızı — elenmiş
COLOR_TEXT_BG = (0, 0, 0)               # Siyah — metin arka planı


# ==============================================================================
# Veri Yapıları (Data Classes)
# ==============================================================================
class RunnerState(Enum):
    """Koşucu durumu."""
    ACTIVE = "Aktif"
    WARNING = "Uyari"           # 1 ardışık gecikme
    ELIMINATED = "ELENDI"       # 2 ardışık gecikme


@dataclass
class RunnerData:
    """Tek bir karede bir koşucunun verisi."""
    track_id: int
    ankle_mid_x: float         # Ayak bileği ortalaması X
    ankle_mid_y: float         # Ayak bileği ortalaması Y (GEÇİŞ TESPİTİ İÇİN KULLANILIR)
    bbox: tuple                # (x1, y1, x2, y2) bounding box
    confidence: float          # Poz güvenilirlik skoru


@dataclass
class RunnerStatus:
    """Koşucunun kümülatif değerlendirme durumu."""
    track_id: int
    state: RunnerState = RunnerState.ACTIVE
    total_crossings: int = 0
    on_time_count: int = 0
    late_count: int = 0
    consecutive_late: int = 0
    last_crossing_time: float = 0.0
    last_direction: str = ""    # "to_far" (üst/20m'e doğru) veya "to_near" (alt/başlangıca doğru)
    elimination_time: float | None = None
    crossing_log: list = field(default_factory=list)
    # Crossing log entry: {"time": float, "direction": str, "status": str, "shuttle_no": int}
