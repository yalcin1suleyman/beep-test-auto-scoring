# Mekik sistemi - teslim ve dogrulama raporu

Tarih: 18 Kasim 2026

- Otomatik test: 72 gecti; 0 hata.
- Kaynak kontrolu: 14 video, 50.777 kare; masaustu asillariyla SHA-256 eslesmesi saglandi.
- Analiz: 7 kamera cifti, 24.298 birinci kamera zaman cizelgesi karesi; kare atlama yok.
- Standart puanlama: 6 kayit. Video 7 protokol disi gozlem olarak tamamlandi ve puanlanmadi.

| Kayit | Analiz karesi | Kosucu | Devam etti | Elendi | Puanlanmadi | Sure (s) |
|---|---:|---:|---:|---:|---:|---:|
| Video 1 | 3966 | 4 | 2 | 2 | 0 | 580.0 |
| Video 2 | 3176 | 3 | 2 | 1 | 0 | 398.0 |
| Video 3 | 4154 | 3 | 2 | 1 | 0 | 528.7 |
| Video 4 | 4370 | 3 | 2 | 1 | 0 | 532.8 |
| Video 5 | 2004 | 3 | 2 | 1 | 0 | 350.1 |
| Video 6 | 3123 | 4 | 2 | 2 | 0 | 433.7 |
| Video 7 | 3505 | 5 | 0 | 0 | 5 | 463.1 |

## Dogrulamanin kapsami

14 kaynak dosyanin tum kareleri okundu. Kamera cifti analizinde birinci kameranin her karesi islenir; ikinci kamera zaman damgasina gore eslenir. Farkli FPS kayitlarinda ikinci kameranin her kaynak karesine model uygulanmasi anlamina gelmez. Sadece iki kameranin ortak zaman araligi puanlanir.

Goruntu kontrolunde kenardaki bir nesnenin kosucu kimligi alabildigi goruldu. Kulvar atamasi hedef cizginin yakinindaki tespitlerle sinirlandirildi; kamera hareketinde bu alan ve kulvar uclari cizgiyle birlikte tasinir. Referans sesli calismalarda hedef etiketinin bekleme durumunda kalmasi duzeltildi. Mevcut ciktilarin sadece bilgi basligi yeniden olusturuldu; puanlama ve kamera eslestirmesi degistirilmedi.

Cikti videolari tekrar sonuna kadar cozuldu. CSV ve Excel verileri, toplamlar, basarili mekik kayitlarinin tekilligi, kosucu sayilari, cizgi ayarlari ve cikis bipi bilgisi kontrol edildi. Her videonun ve metadatanin SHA-256 degeri dogrulama kaydinda saklandi.

## Sonuclarin yorumu

Teknik analiz ve raporlama akisi dogrulanmistir. Sonuclar otomatik model kararlaridir; hakem/insan etiketleriyle bir dogruluk yuzdesi olculmemistir. Bu rapor kusursuz kisi kimligi, temas tespiti veya eleme dogrulugu iddiasi tasimaz.

Video 1: Cikis bipi zayif oldugu icin baslangic zamani tahminidir. Notlardaki yaklasik +/-1 saniye belirsizlik eleme kararlarini etkileyebilir.
Video 6: Kadraj kenarindaki kosucunun gorunurlugu sinirlidir.
Video 7: Standart bip testi ritmine uymadigindan puan/mesafe/seviye ve eleme karari yayimlanmaz.

## Dosyalar ve tekrar calistirma

- Yerel tum sonuclar: `data/outputs/sonuclar/SONUCLAR.html` ve `TUM_SONUCLAR.xlsx`.
- Kayit raporlari: `data/outputs/sonuclar/video_N/SONUC.html`, `SONUC.xlsx`, `analiz_videosu.mp4`.
- Bu raporun makine kaydi: `dogrulama.json`; kosucu sonuclari: `kosucu_sonuclari.csv` ve `TUM_SONUCLAR.xlsx`.
- Buyuk/ozel kaynak ve cikti videolari yeni GitHub commitine eklenmez. Rapor ve kod depoya dahil edilir.

```powershell
python scripts/start_full_batch.py
python scripts/audit_session_sources.py
python -m pytest -q --junitxml=data/outputs/hazirlik_2026-11-18/testler.xml
python scripts/prepare_release.py
```
