# Doğrulama raporu — 23 Ekim 2026

## Sonuçlar

- `python -m pytest -q`: **52 geçti**. Makine tarafından okunabilir sonuç: `data/outputs/verification/pytest-results.xml`.
- 34 Python dosyası sözdizimi kontrolünden geçti; `git diff --check` temiz.
- Masaüstündeki `MEKİK VİDEO` klasörünün 7 alt klasöründeki **14 video**, toplam **50.777 kare**, sonuna kadar çözümlendi. Bildirilen kare sayıları okunanlarla eşleşti.
- Bu kayıtların tamamına yayılan **1.527 karede** gerçek YOLO/ByteTrack çıkarımı çalıştı. Ses analizi de her video için çalıştırıldı. Ham ölçümler: `data/outputs/verification/desktop_audit.json`.
- Kök dizindeki iki kamerayla 3.841 karelik uzun analiz ve görüntülü uygulama denemeleri yapıldı. Çıktılar mevcut kullanıcı raporlarından ayrı `data/outputs/verification/` ve `data/outputs/vscode_preview*` klasörlerinde tutuldu.
- Son sürüm `data/outputs/quality_review/validated/` altında 3.841 karenin tamamını yeniden işledi (358,5 saniye). Bağımsız denetim, 1.284 × 634 boyutlu çıktı videosunun 3.841 karesini tekrar okudu; 5 koşucu, 56 detay satırı ve CSV/Excel eşitliği doğrulandı. Yinelenen başarılı mekik kaydı bulunmadı. Sonuç: `output_validation.json` içinde `ok: true`, `approximate: false`.
- İncelenebilir yeni çıktılar: `data/outputs/quality_review/validated/analiz_raporu.html`, `sonuc_paneli.jpg` ve `0metre_20metre_dual_camera.mp4`. Videodaki eleme kararları, kullanılan çizgi/bip ayarlarına göre hesaplanan otomatik değerlendirmelerdir; insan etiketlerine karşı doğruluk ölçümü değildir.

## Giderilen sorunlar

- Görüntülü analiz artık varsayılan olarak kare atlamaz. İsteğe bağlı `--realtime-preview` çıktıları yaklaşık olarak işaretlenir ve analiz edilen/yazılan kare sayıları ayrı kaydedilir.
- Video sonunda pencere açık tutulsa bile video kapatılır, CSV/Excel ve görsel raporlar beklemeden yazılır. Q ile ilk karede çıkışın kare sayımı da düzeltildi. Gerçek video yazıcısı ve taklit GUI ile regresyon testleri bu davranışı kontrol eder.
- Süre/hedef bilgisi ve koşucu kartları kamera görüntülerinin dışında ayrı alanlara taşındı. Her çalıştırmada sonuç paneli JPG ve yerel HTML raporu üretilir.
- Güven puanına göre sırayla yapılan kulvar ataması yakın koşucuların kimliklerini değiştirebiliyordu. Toplu minimum maliyetli eşleştirme ve uzamsal sıra koruması eklendi; eksik tespit ve ters kamera testleri geçti.
- Koşucu bulunmayan sonuçların CSV sütunları korunur ve HTML raporu puanlama verisinin olmadığını açıkça bildirir.

- Hız her mekikte artırılıyordu; yapılandırmadaki seviye tablosuyla uyumlu olarak seviye sonunda artırılması sağlandı. Başlangıç hızı mevcut proje ayarındaki 7 km/sa olarak kaldı.
- İlk gecikmenin aktif görünmesi, zaman atlamasında deadline'ların eksik işlenmesi ve kaçırılan karşı uçtan sonra aynı kameranın geçerli yeni geçişinin kilitlenmesi düzeltildi.
- Hedef çizgide hareketsiz kalmak yeni mekik olarak sayılamaz; tekrar geçiş için önce çizginin öteki tarafına dönülmesi gerekir.
- Tek çizgi modunda yavaş hareketin histerezis bandında kaybolması düzeltildi.
- Boş/kısa/sessiz ses verileri ve eşzamanlı ses işlemlerinde ortak geçici dosya sorunu giderildi.
- Kamera FPS farkları, farklı en/boy oranları ve kodlayıcının çift piksel boyutu gereksinimi ele alındı.
- Çift kamera kaynakları hata durumunda da kapatılır; açılamayan çıktı yazıcısı, bozuk video ve görüntü dışındaki çizgi koordinatları reddedilir.
- Model çalıştırma hataları boş tespit gibi gizlenmez. Modül günlükleri merkezi kayıt sistemine bağlandı.
- Ekransız mod eksik çizgilerle etkileşimli pencereye geçmez. `--no-audio` referans ses indirmesini kapatır.
- Koşucu sayısı, çizgi koordinatları ve çıktı klasörü komut satırından belirtilebilir. Model ve takip yapılandırması proje dışındaki çalışma dizininden de bulunur.
- VS Code için görüntülü çalıştırma ayarı eklendi. `--hold-open` video sonunda pencereyi açık tutar.

## Kullanım ve doğruluk sınırı

Yeni yatay ve dikey kayıt çıktıları `data/outputs/quality_review/` altında tutulur. `scripts/verify_analysis_output.py`, çıktı videosunun bütün karelerini yeniden okur; CSV ve Excel içeriklerini, sayaç toplamlarını ve yinelenen başarılı mekik kaydı olup olmadığını bağımsız olarak kontrol eder. 3 kişilik dikey kamera çiftinde ayrıca 60 karelik gerçek model denemesi ve çıktı doğrulaması yapıldı. Bu kısa kayıt testi puanlama doğruluğu ölçümü değildir.

VS Code'da **Mekik - Cift Kamera Goruntulu** ayarını F5 ile çalıştırın. Hazır çizgiler yalnızca kökteki `0metre.mp4` ve `20metre.mp4` içindir. Masaüstündeki diğer gruplar farklı kişi sayıları, kamera açıları ve başlangıç zamanları içerir; bu kayıtlar için çizgi, koşucu sayısı, kamera zaman farkı ve çıkış bipi ayrı kalibre edilmelidir.

Tam video çözümleme ve örneklenmiş model çıkarımı teknik çalışabilirliği doğrular. 14 videonun insan tarafından etiketlenmiş bütün mekiklerini, kişilerin kameralar arası kimlik eşleşmesini veya eleme kararlarının yüzde yüz doğruluğunu kanıtlamaz. Özellikle ses pikleri doğrudan güvenilir bip çizelgesi kabul edilmemelidir. Bu rapor, bütün olası girdiler için hatasızlık garantisi içermez.

## Tekrarlama

```powershell
python -m pytest -q
python scripts/inspect_desktop_videos.py
python scripts/audit_videos.py
python dual_main.py --no-display --no-audio --runner-count 5 --start-line '75,270;718,286' --far-line '170,450;905,443' --output-dir data/outputs/yeni_analiz
```
