# Çift Kamera Kalibrasyonu — 2-Tıklama Perspektif Çizgisi Rehberi

## Genel Bakış

Yeni kalibrasyom sistemi her kamera için **2 tıklamayla** perspektif çizgileri tanımlayabilir. Bu, konilerin alt kısmından geçen gerçek bir çizgiyi tanımlamaya olanak sağlar ve kamera açısı (perspektif) farklılıklarını düzeltir.

## Kalibrasyonun Yapılması

### Aşama 1: Kamera 1 (Başlangıç / 0m)

Program çalıştırıldığında, ilk kalibrasyon penceresi açılır:

```
KALIBRASYON 1/2 — KAMERA 1: Başlangıç (0m) çizgisi (2 TIKLAMA)
```

**Yapılacaklar:**

1. **1. Tıklama (Solda):** Konilerin alt kısmının **solundaki** noktaya tıklayın
2. **2. Tıklama (Sağda):** Konilerin alt kısmının **sağındaki** noktaya tıklayın
3. **ENTER tuşuna basın** veya çizgi otomatik olarak onaylanır

**İpuçları:**

- Konilerin alt kenarından geçen çizgi seçin
- Çizginin perspektifini (solda/sağda farklı yükseklikler) dikkate alın
- Noktaları taşımak için tıklayıp sürükleyebilirsiniz

### Aşama 2: Kamera 2 (20m)

İkinci kalibrasyon penceresi açılır:

```
KALIBRASYON 2/2 — KAMERA 2: 20m çizgisi (2 TIKLAMA)
```

**Aynı işlemi tekrarlayın:**

1. Konilerin solundaki noktaya tıklayın
2. Konilerin sağındaki noktaya tıklayın
3. ENTER tuşuna basın

## Çıktı

Kalibrasyondan sonra sistem şunu gösterecektir:

```
Başlangıç çizgisi = [(70, 280), (720, 289)]
20m çizgisi = [(170, 462), (906, 449)]
```

Bu noktalar şu şekilde yorumlanır:

| Değer        | Anlamı                                     |
| ------------ | ------------------------------------------ |
| `(70, 280)`  | Soldaki nokta (X=70 piksel, Y=280 piksel)  |
| `(720, 289)` | Sağdaki nokta (X=720 piksel, Y=289 piksel) |

**Önemli:** Y değerleri farklıysa, çizgi perspektiftir (eğik). Bu normal ve beklenendir.

## Yapılandırma Dosyasında Kaydetme

Kalibrasyondan sonra, sonuçları `config.py` dosyasında sabitleyebilirsiniz:

```python
# config.py
DUAL_START_LINE_POINTS = [
    (70, 280),
    (720, 289),
]

DUAL_FAR_LINE_POINTS = [
    (170, 462),
    (906, 449),
]
```

Böylelikle isterseniz programı şu komutla çalıştırıp kalibrasyon adımını atlayabilirsiniz:

```bash
python dual_main.py --use-config-lines
```

`--use-config-lines` verilmezse program her çalışmada iki kamera için çizgiyi kullanıcıya seçtirir.

## Perspektif Çizgileri Nasıl Çalışır?

Sistem iki noktayı doğrusal interpolasyon ile birleştirir. Herhangi bir X konumundaki Y değeri:

```
Y(X) = Y1 + (X - X1) * (Y2 - Y1) / (X2 - X1)
```

**Örnek:**

- Nokta 1: (70, 280)
- Nokta 2: (720, 289)
- X=400 konumundaki Y değeri:
  ```
  Y(400) = 280 + (400 - 70) * (289 - 280) / (720 - 70)
         = 280 + 330 * 9 / 650
         = 280 + 4.57
         = 284.57
  ```

## Sık Sorulan Sorular

### P: Neden 2 nokta?

**C:** İki nokta, kameranın perspektif açısından kaynaklanan eğik çizgileri doğru şekilde modellemeye izin verir. Bu, uzak bölgelerde daha doğru ölçüm sağlar.

### P: Kalibrasyon her çalışmada tekrarlanması gerekir mi?

**C:** Varsayılan akışta evet; kullanıcı iki kameranın çizgisini kendisi belirler. Sabit kamera düzeninde tekrar seçmek istemezseniz değerleri `config.py` dosyasına kaydedip `--use-config-lines` ile çalıştırın.

### P: Çizginin konumu doğru değilse?

**C:** Kalibrasyon sırasında, konilerin **tam alt kenarından** geçen noktaları seçtiğinizden emin olun. Atletlerin gözünü değil, konilerin kenarını hedef alın.

### P: Farklı video çözünürlükleri için ne yapmalı?

**C:** Her video çözünürlüğü için ayrı kalibrasyonlar gerekebilir. Yeni bir çözünürlüğe geçerseniz kalibrasyon yapın ve noktaları kaydedin.

## Teknik Detaylar

- **Çizgi sınıfı:** `PerspectiveLine` (line_geometry.py)
- **Kalibrasyon fonksiyonları:** `_calibrate_perspective_line()` ve `calibrate_cameras()` (dual_main.py)
- **Çizgi koordinatları:** Görüntü piksel koordinatları (0,0 = üst-sol köşe)

## İlgili Dosyalar

- `dual_main.py` — Ana kalibrasyom ve çalıştırma scripti
- `line_geometry.py` — PerspectiveLine sınıfı tanımı
- `config.py` — Kalibrasyon noktalarının kaydedildiği yer
