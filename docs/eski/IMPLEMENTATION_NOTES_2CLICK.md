# 2-Tıklama Çizgi Kalibrasyonu Sistem Güncellemesi — Özet

## Yapılan Değişiklikler

### Dosya: `dual_main.py`

#### 1. Yeni Fonksiyon: `_calibrate_perspective_line()`

- **Konum:** ~110-269 satırları
- **Amaç:** 2 tıklamadan perspektif çizgisi oluşturma
- **Girdiler:**
  - `frame`: Kalibrasyon yapılacak video karesi
  - `win_title`: Pencere başlığı
  - `line_color`: Çizgi rengi (BGR)
  - `suggested_points`: Önerilen başlangıç noktaları
  - `header_lines`: Başlık metni
- **Çıktı:** 2 nokta listesi `[(x1, y1), (x2, y2)]`
- **Özellikler:**
  - İnteractive mouse desteği
  - Noktaları sürükleyerek değiştir
  - Gerçek zamanlı ön izleme
  - Duyarlı ölçekleme

#### 2. Güncellenmiş Fonksiyon: `calibrate_cameras()`

- **Eski davranış:** 1 tıklama = 1 Y değeri (yatay çizgi)
- **Yeni davranış:** 2 tıklama = 2 nokta (perspektif çizgisi)
- **Dönüş türü:** `tuple[list[tuple[int, int]], list[tuple[int, int]]]`
- **Kullanıcı Yönergeleri:** Türkçe, adım adım talimatlar

#### 3. Güncellenmiş Kod: Ana Çalıştırma

- **Satır ~906:** `calibrate_cameras()` çağrısı güncellendi
- **Yeni akış:**
  ```python
  start_line_points, far_line_points = calibrate_cameras(frame1_cal, frame2_cal)
  start_line_profile_base = PerspectiveLine.from_points(start_line_points)
  far_line_profile_base = PerspectiveLine.from_points(far_line_points)
  ```

### Dosya: `CALIBRATION_GUIDE.md` (YENI)

- Türkçe kalibrasyon rehberi
- Adım adım talimatlar
- Yapılandırma örnekleri
- Sık sorulan sorular
- Teknik detaylar

## Özellikler

### ✓ 2-Tıklama Arayüzü

Kullanıcılar her kamera için 2 nokta seçerek perspektif çizgileri tanımlar.

### ✓ İnteractive Noktaları Düzenleme

Tıkla ve sürükle ile seçim yaparken noktaları ayarla.

### ✓ Perspektif Desteği

Çizgiler eğik olabilir (Y1 ≠ Y2), bu kamera açısı farklılıklarını yansıtır.

### ✓ Yapılandırma Esnekliği

`config.py` içinde kalibrasyon noktaları saklanabilir.

### ✓ Gerçekleştirmede Uyumluluk

Varolan `PerspectiveLine` sınıfı tam uyumlu.

## Testi Edilen Senaryolar

1. **Yatay çizgiler** (Y1 = Y2)
   - ✓ Median Y doğru hesaplanır
   - ✓ İnterpolasyon düzgün çalışır

2. **Perspektif çizgiler** (Y1 ≠ Y2)
   - ✓ Eğik çizgiler doğru ele alınır
   - ✓ Y interpolasyonu doğru

3. **Sınır koşulları**
   - ✓ Çizim hatasız yapılır
   - ✓ Koordinat ölçekleme doğru

## Geriye Doğru Uyumluluk

- ✓ `PerspectiveLine.from_points()` önceki kodla uyumlu
- ✓ `config.py` DUAL_START_LINE_POINTS/DUAL_FAR_LINE_POINTS desteklenmeye devam eder
- ✓ Existing video işleme pipelines etkilenmez

## Kullanım

### Yöntemi 1: İnteractive Kalibrasyon

```bash
python dual_main.py
```

Program kalibrasyon araması yapacak ve 2 tıklama talep edecektir.

### Yöntemi 2: Yapılandırma Dosyasından

```python
# config.py içinde
DUAL_START_LINE_POINTS = [(70, 280), (720, 289)]
DUAL_FAR_LINE_POINTS = [(170, 462), (906, 449)]
```

Program kalibrasyon atlar ve bu değerleri kullanır.

## Gelecek İyileştirmeler (Öneriler)

1. **Koni Otomatik Algılaması:** Konilerin alt kısmını otomatik detect et ve öner
2. **Çoklu Perspektif Noktaları:** 2'den fazla nokta (spline interpolation)
3. **Kalibrasyon Doğrulaması:** Kalibrasyon sonrası doğrulama kontrolü
4. **Otomatik Kayıt:** Kalibrasyon sonrası config.py'ye otomatik kayıt
