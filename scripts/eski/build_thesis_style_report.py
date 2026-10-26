from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from build_professional_report import (
    ASSET_DIR,
    GENERATED_DIR,
    LINE_CHECK_DIR,
    OUT_DIR,
    add_bullet,
    add_callout,
    add_caption,
    add_header_footer,
    add_heading,
    add_image,
    add_numbered,
    format_table,
    set_styles,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = OUT_DIR / "mekik_test_tez_tadinda_kapsamli_rapor.docx"


def add_title_page(doc: Document):
    for _ in range(2):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("OTOMATİK MEKİK TESTİ DEĞERLENDİRME SİSTEMİ")
    r.bold = True
    r.font.size = Pt(22)
    r.font.color.rgb = RGBColor(31, 77, 120)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(
        "Çift Kamera Görüntü İşleme, Kullanıcı Tanımlı Çizgi Kalibrasyonu ve Bip Tabanlı Performans Analizi"
    )
    r.font.size = Pt(13)
    r.font.color.rgb = RGBColor(80, 80, 80)

    for _ in range(4):
        doc.add_paragraph()

    meta = doc.add_table(rows=6, cols=2)
    rows = [
        ("Rapor Türü", "Tez / bitirme projesi formatında kapsamlı teknik rapor"),
        ("Çalışma Alanı", "Bilgisayarlı görme, spor performans analizi, otomatik karar destek sistemi"),
        ("Uygulama", "20 metre mekik koşusu değerlendirme sistemi"),
        ("Kullanılan Veri", "0m ve 20m kamera videoları, analiz çıktıları ve ekran görüntüleri"),
        ("Hazırlanma Tarihi", datetime.now().strftime("%d.%m.%Y")),
        ("Çıktı", "Microsoft Word DOCX"),
    ]
    for i, (left, right) in enumerate(rows):
        meta.cell(i, 0).text = left
        meta.cell(i, 1).text = right
    format_table(meta)

    for _ in range(3):
        doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Hazırlanan bu doküman, sistemin tasarımını, çalışma mantığını, uygulama ekranlarını ve değerlendirme sonuçlarını akademik bir akış içinde açıklamak amacıyla oluşturulmuştur.")
    r.italic = True
    r.font.size = Pt(10)
    doc.add_page_break()


def add_manual_toc(doc: Document):
    add_heading(doc, "İçindekiler", 1)
    entries = [
        "Özet",
        "1. Giriş",
        "2. Problem Tanımı ve Çalışmanın Gerekçesi",
        "3. Çalışmanın Amacı, Kapsamı ve Katkıları",
        "4. Kavramsal Arka Plan",
        "5. Sistem Gereksinimleri",
        "6. Sistem Mimarisi",
        "7. Yöntem",
        "8. Uygulama ve Yazılım Bileşenleri",
        "9. Kullanıcı Tanımlı Kalibrasyon Süreci",
        "10. Kulvar ID Takibi ve Geçiş Karar Mekanizması",
        "11. Deneysel Çalışma ve Ekran Görüntüleri",
        "12. Sonuçların Değerlendirilmesi",
        "13. Sınırlılıklar ve Riskler",
        "14. Sonuç ve Gelecek Çalışmalar",
        "Kaynakça",
        "Ekler",
    ]
    for entry in entries:
        p = doc.add_paragraph(entry)
        p.paragraph_format.left_indent = Inches(0.2)
        p.paragraph_format.space_after = Pt(2)
    doc.add_page_break()


def add_abstract(doc: Document):
    add_heading(doc, "Özet", 1)
    doc.add_paragraph(
        "Bu çalışma, 20 metre mekik koşusu testinin çift kamera görüntüleri kullanılarak otomatik biçimde değerlendirilmesini amaçlayan bir bilgisayarlı görme sistemini ele almaktadır. Geleneksel değerlendirme sürecinde hakem veya gözlemci, koşucuların hedef çizgilere bip zamanından önce ulaşıp ulaşmadığını anlık olarak takip etmek zorundadır. Bu süreç, çoklu koşucu takibi, hızlı tempo, uzak mesafe görünürlüğü ve insan dikkatinin sınırlı olması nedeniyle hataya açık hale gelebilmektedir."
    )
    doc.add_paragraph(
        "Geliştirilen sistemde başlangıç ve 20 metre noktaları iki ayrı kamera görüntüsüyle izlenmekte, kullanıcı her kamera için hedef çizgiyi iki noktalı perspektif kalibrasyon yöntemiyle belirlemekte ve koşucular kulvar ID mantığıyla takip edilmektedir. Koşucunun çizgiyi geçip geçmediği, takip kutusunun alt tabanının kullanıcı tarafından belirlenen çizginin altına geçmesi esas alınarak yorumlanmaktadır. Bip zamanları ise değerlendirme sürecinde deadline olarak kullanılmakta; çizgiyi zamanında geçen koşucu geçerli kabul edilmekte, geçemeyen koşucu için geç kalma sayacı güncellenmektedir."
    )
    doc.add_paragraph(
        "Bu rapor; sistemin problem tanımını, mimarisini, kullanılan teknolojileri, algoritmik karar mantığını, kalibrasyon sürecini, ekran görüntülerini, deneysel çıktıları ve geliştirme önerilerini tez formatına yakın bir bütünlük içinde sunmaktadır."
    )
    add_heading(doc, "Anahtar Kelimeler", 2)
    doc.add_paragraph("Mekik testi, bilgisayarlı görme, YOLOv8-Pose, çift kamera, çizgi kalibrasyonu, spor performans analizi, otomatik değerlendirme.")
    doc.add_page_break()


def add_results_table(doc: Document):
    csv_path = ROOT / "data" / "outputs" / "sonuc_ozet.csv"
    if not csv_path.exists():
        doc.add_paragraph("Sonuç özeti dosyası bulunamadığı için tablo eklenememiştir.")
        return

    df = pd.read_csv(csv_path)
    columns = [
        "Kosucu ID",
        "Durum",
        "Toplam Gecis",
        "20m Gecis",
        "Baslangic Gecis",
        "Zamaninda",
        "Gec",
        "Eleme Zamani (s)",
    ]
    labels = [
        "Koşucu ID",
        "Durum",
        "Toplam Geçiş",
        "20m Geçiş",
        "Başlangıç Geçiş",
        "Zamanında",
        "Geç",
        "Eleme Zamanı (s)",
    ]
    table = doc.add_table(rows=1, cols=len(columns))
    for i, label in enumerate(labels):
        table.cell(0, i).text = label
    for _, row in df.iterrows():
        cells = table.add_row().cells
        for i, column in enumerate(columns):
            cells[i].text = str(row.get(column, "-"))
    format_table(table)
    add_caption(doc, "Tablo 6.1. Sistem tarafından üretilen koşucu değerlendirme özeti.")


def add_chapters(doc: Document):
    add_heading(doc, "1. Giriş", 1)
    doc.add_paragraph(
        "Spor performans testleri, bireylerin dayanıklılık, hız, koordinasyon ve kondisyon düzeylerini ölçmek için yaygın olarak kullanılmaktadır. Bu testlerden biri olan 20 metre mekik koşusu, koşucunun iki uç nokta arasında bip sesleriyle belirlenen tempoya uygun şekilde gidip gelmesini gerektirir. Testin doğru değerlendirilebilmesi için koşucunun her bip zamanında ilgili hedef çizgiye ulaşıp ulaşmadığının güvenilir biçimde izlenmesi gerekir."
    )
    doc.add_paragraph(
        "Uygulamada bu değerlendirme çoğunlukla gözlemci tarafından yapılır. Ancak birden fazla koşucunun aynı anda test edildiği durumlarda her koşucunun çizgi geçişini, bip zamanını ve ardışık hata durumunu hatasız takip etmek zorlaşır. Bu nedenle video tabanlı otomatik değerlendirme sistemleri, spor ölçümlerinde nesnellik ve kayıt altına alınabilirlik açısından önemli bir katkı sağlar."
    )
    add_callout(
        doc,
        "Çalışmanın Odak Noktası",
        "Bu çalışma, mekik testi değerlendirmesinde çizgi geçişini kullanıcı tanımlı kamera çizgileri ve koşucu takip kutusunun alt tabanı üzerinden belirleyen çift kameralı bir analiz sistemi geliştirmeye odaklanmaktadır.",
    )

    add_heading(doc, "2. Problem Tanımı ve Çalışmanın Gerekçesi", 1)
    doc.add_paragraph(
        "Mekik testinde temel problem, koşucunun hedef çizgiyi doğru zamanda geçip geçmediğinin belirlenmesidir. Bu karar saniyelik zaman farklarına bağlı olabilir. Ayrıca koşucuların birbirine yakın hareket etmesi, kameraya uzaklaşınca küçülmesi, salon ışıklarının değişkenliği ve kamera perspektifi gibi etkenler otomatik algılamayı zorlaştırır."
    )
    add_bullet(doc, "Tek kamera kullanıldığında uzak uçtaki koşucular küçük görünür ve model güveni düşebilir.")
    add_bullet(doc, "Elle belirlenmeyen çizgiler farklı salonlarda veya kamera açılarında hatalı konumlanabilir.")
    add_bullet(doc, "Koşucu ID'lerinin takip boyunca kararlı kalmaması değerlendirme sonuçlarını bozabilir.")
    add_bullet(doc, "Bip anında çizgiye ulaşmamış koşucunun doğru biçimde geç kaldı veya elendi olarak işaretlenmesi gerekir.")

    add_heading(doc, "3. Çalışmanın Amacı, Kapsamı ve Katkıları", 1)
    add_heading(doc, "3.1 Amaç", 2)
    doc.add_paragraph(
        "Çalışmanın amacı, 20 metre mekik koşusu testinde koşucuların hedef çizgi geçişlerini video üzerinden otomatik olarak takip eden, bip zamanlarıyla karşılaştıran ve sonuçları raporlayan bir yazılım sistemi oluşturmaktır."
    )
    add_heading(doc, "3.2 Kapsam", 2)
    add_bullet(doc, "Başlangıç ve 20m çizgilerini gören iki kamera videosunun eş zamanlı analiz edilmesi.")
    add_bullet(doc, "Her iki kamerada çizginin kullanıcı tarafından belirlenmesi.")
    add_bullet(doc, "Koşucuların kulvar ID mantığıyla gösterilmesi.")
    add_bullet(doc, "Geçiş kararının takip kutusunun alt tabanına göre verilmesi.")
    add_bullet(doc, "Bip zamanlarına göre aktif, geçti, geç kaldı ve elendi durumlarının üretilmesi.")
    add_heading(doc, "3.3 Katkılar", 2)
    add_bullet(doc, "İnsan gözlemine dayalı değerlendirmedeki hata payını azaltır.")
    add_bullet(doc, "Kayıt altına alınabilir video çıktısı ve tablo raporları üretir.")
    add_bullet(doc, "Farklı kamera açılarına uyum sağlayabilen kullanıcı tanımlı kalibrasyon sunar.")
    add_bullet(doc, "Çift kamera yaklaşımıyla uzak mesafe tespit problemini azaltır.")

    add_heading(doc, "4. Kavramsal Arka Plan", 1)
    add_heading(doc, "4.1 20 Metre Mekik Koşusu", 2)
    doc.add_paragraph(
        "20 metre mekik koşusu, koşucunun iki çizgi arasında gidip gelerek bip seslerine uyum sağlamasını gerektiren artan tempolu bir dayanıklılık testidir. Her bip, koşucunun bir sonraki hedef çizgiye ulaşması gereken zamanı temsil eder. Koşucu hedefe zamanında ulaşamazsa uyarı veya eleme mekanizması uygulanır."
    )
    add_heading(doc, "4.2 Bilgisayarlı Görme ile Spor Analizi", 2)
    doc.add_paragraph(
        "Bilgisayarlı görme teknikleri, sporcuların hareketlerinin kamera görüntüleri üzerinden izlenmesine olanak tanır. Nesne tespiti, poz tahmini ve takip algoritmaları kullanılarak sporcunun konumu, hareket yönü ve belirli referans çizgilerine göre durumu analiz edilebilir."
    )
    add_heading(doc, "4.3 Poz Tespiti ve Takip", 2)
    doc.add_paragraph(
        "Bu projede YOLOv8-Pose yaklaşımı kullanılarak koşucuların görüntü içindeki konumu ve takip kutuları elde edilir. Takip kutusu, koşucunun sahnedeki kapladığı alanı temsil eder. Geçiş kararında bu kutunun alt tabanı kullanılır; çünkü çizgiye temas veya geçiş çoğunlukla koşucunun ayak/zemin hizasıyla ilişkilidir."
    )

    add_heading(doc, "5. Sistem Gereksinimleri", 1)
    req = doc.add_table(rows=1, cols=3)
    for i, h in enumerate(["Gereksinim", "Tür", "Açıklama"]):
        req.cell(0, i).text = h
    rows = [
        ("Çift kamera desteği", "İşlevsel", "0m ve 20m noktalarının ayrı video kaynaklarıyla izlenmesi."),
        ("Kullanıcı kalibrasyonu", "İşlevsel", "Her kamera için çizginin iki tıklamayla belirlenmesi."),
        ("Kulvar ID takibi", "İşlevsel", "Koşucuların takip kolaylığı için sabit kulvar numarasıyla gösterilmesi."),
        ("Bip değerlendirmesi", "İşlevsel", "Geçişlerin bip/deadline zamanlarıyla karşılaştırılması."),
        ("Görsel çıktı", "İşlevsel", "Analiz videosunda çizgi, kutu, ID ve durum bilgisinin gösterilmesi."),
        ("Raporlama", "İşlevsel", "Özet ve detay sonuçlarının CSV/Excel/DOCX olarak sunulması."),
        ("Okunabilir arayüz", "İşlevsel olmayan", "Çift kamera panelinin ve durum etiketlerinin anlaşılır olması."),
        ("Tekrarlanabilirlik", "İşlevsel olmayan", "Aynı video ve ayarlarla tutarlı sonuç üretmesi."),
    ]
    for row in rows:
        cells = req.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = value
    format_table(req)
    add_caption(doc, "Tablo 5.1. Sistem gereksinimleri.")

    add_heading(doc, "6. Sistem Mimarisi", 1)
    doc.add_paragraph(
        "Sistem modüler bir yapıya sahiptir. Video kaynakları açıldıktan sonra kalibrasyon işlemi yapılır. Ardından her karede koşucu tespiti, kulvar ID ataması, çizgi geçiş kontrolü, bip zamanlayıcı kontrolü ve görselleştirme adımları yürütülür."
    )
    arch = doc.add_table(rows=1, cols=4)
    for i, h in enumerate(["Modül", "Girdi", "İşlem", "Çıktı"]):
        arch.cell(0, i).text = h
    rows = [
        ("Video Giriş Modülü", "0m ve 20m videoları", "Kareleri zaman ekseninde okur", "Kamera kareleri"),
        ("Kalibrasyon Modülü", "İlk kamera kareleri", "Kullanıcıdan iki nokta alır", "PerspectiveLine"),
        ("Takip Modülü", "Video karesi", "Koşucu kutularını ve ID'leri üretir", "RunnerData listesi"),
        ("Değerlendirme Modülü", "Kutu tabanı, çizgi, bip", "Geçti/aktif/elendi kararlarını verir", "Koşucu durumu"),
        ("Raporlama Modülü", "Değerlendirme kayıtları", "CSV/Excel/DOCX çıktıları üretir", "Sonuç raporları"),
    ]
    for row in rows:
        cells = arch.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = value
    format_table(arch)
    add_caption(doc, "Tablo 6.1. Sistem mimarisi ve modüller.")

    add_heading(doc, "7. Yöntem", 1)
    add_heading(doc, "7.1 Kamera ve Çizgi Modeli", 2)
    doc.add_paragraph(
        "Her kamera görüntüsünde hedef çizgi, iki nokta ile tanımlanan perspektif çizgisi olarak modellenir. Kullanıcının seçtiği sol ve sağ noktalar doğrusal interpolasyonla birleştirilir. Böylece koşucunun görüntüdeki X konumuna göre çizginin karşılık gelen Y değeri hesaplanabilir."
    )
    add_heading(doc, "7.2 Geçiş Kararı", 2)
    doc.add_paragraph(
        "Geçiş kararı, koşucu takip kutusunun alt tabanına göre verilir. Bir koşucu, ilgili kameradaki hedef çizginin altına geçtiğinde 'GEÇTİ' olarak işaretlenir. Bu yaklaşım, ayak bileği noktasının bazı karelerde güvenilir algılanamaması durumunda daha kararlı bir karar mekanizması sağlar."
    )
    add_heading(doc, "7.3 Bip ve Deadline Mantığı", 2)
    doc.add_paragraph(
        "Bip sesleri, koşucunun ilgili çizgiye ulaşması gereken zamanları temsil eder. Sistem, geçiş ile bip zamanını karşılaştırır. Koşucu bipten önce çizgiyi geçmişse bu mekik başarılı kabul edilir. Bip geldiğinde koşucu hâlâ geçmemişse geç kalma sayacı artırılır. Ardışık geç kalma sayısı eşik değere ulaştığında koşucu elenir."
    )
    add_heading(doc, "7.4 Algoritmik Akış", 2)
    add_numbered(doc, "0m ve 20m kamera videoları açılır.")
    add_numbered(doc, "Kullanıcı her iki kamera için hedef çizgiyi iki nokta ile belirler.")
    add_numbered(doc, "Her karede koşucular tespit edilir ve kulvar ID'lerine atanır.")
    add_numbered(doc, "Her koşucu için takip kutusunun alt tabanı hesaplanır.")
    add_numbered(doc, "Alt tabanın çizginin altına geçip geçmediği kontrol edilir.")
    add_numbered(doc, "Bip zamanı geldiğinde geçiş yapmış koşucu aktif duruma döner; geçmemiş koşucu geç kalmış sayılır.")
    add_numbered(doc, "Sonuçlar ekrana, analiz videosuna ve tablo raporlarına yazılır.")

    add_heading(doc, "8. Uygulama ve Yazılım Bileşenleri", 1)
    comp = doc.add_table(rows=1, cols=3)
    for i, h in enumerate(["Dosya / Bileşen", "Görev", "Açıklama"]):
        comp.cell(0, i).text = h
    rows = [
        ("dual_main.py", "Ana çift kamera akışı", "Video okuma, kalibrasyon, takip, görselleştirme ve raporlama akışını yönetir."),
        ("dual_camera_analyser.py", "Değerlendirme motoru", "Geçiş, bip, aktif, geç kaldı ve elendi durumlarını hesaplar."),
        ("line_geometry.py", "Perspektif çizgi modeli", "İki noktalı çizgi üzerinden X konumuna göre Y değerini üretir."),
        ("tracker.py", "Poz ve koşucu takibi", "YOLOv8-Pose tabanlı koşucu tespiti ve takip verisini üretir."),
        ("timer.py", "Mekik zamanlayıcısı", "Resmi hız tablosuna göre deadline zamanlarını hesaplar."),
        ("config.py", "Merkezi ayarlar", "Model, tolerans, çizgi, bip, görselleştirme ve eşik ayarlarını içerir."),
    ]
    for row in rows:
        cells = comp.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = value
    format_table(comp)
    add_caption(doc, "Tablo 8.1. Uygulamanın temel yazılım bileşenleri.")

    add_heading(doc, "9. Kullanıcı Tanımlı Kalibrasyon Süreci", 1)
    doc.add_paragraph(
        "Kalibrasyon süreci, sistemin farklı kamera açılarına uyum sağlayabilmesi için kritik öneme sahiptir. Program çalıştığında önce Kamera 1, ardından Kamera 2 için kalibrasyon penceresi açılır. Kullanıcı çizginin sol ve sağ uçlarını seçer. Bu çizgiler, analiz boyunca geçiş kararında referans olarak kullanılır."
    )
    add_image(doc, ASSET_DIR / "01_0m_baslangic.jpg", "Şekil 9.1. Kamera 1 için başlangıç çizgisinin kullanıcı tarafından belirlenmesi.", 6.0)
    add_image(doc, ASSET_DIR / "02_20m_yaklasim.jpg", "Şekil 9.2. Kamera 2 için 20m çizgisinin kullanıcı tarafından belirlenmesi.", 6.0)
    add_image(doc, LINE_CHECK_DIR / "0metre.mp4_two_point_line.jpg", "Şekil 9.3. 0m kamerasında iki nokta çizgi kontrol çıktısı.", 6.0)
    add_image(doc, LINE_CHECK_DIR / "20metre.mp4_two_point_line.jpg", "Şekil 9.4. 20m kamerasında iki nokta çizgi kontrol çıktısı.", 6.0)

    add_heading(doc, "10. Kulvar ID Takibi ve Geçiş Karar Mekanizması", 1)
    doc.add_paragraph(
        "Koşucuların ID değerleri takip kolaylığı için kulvar mantığıyla gösterilir. Bu yaklaşım, kullanıcıya ekranda bir koşucunun hangi satır/konum üzerinden takip edildiğini daha anlaşılır biçimde gösterir. Her koşucunun etrafındaki kutu, sistemin geçiş kararında kullandığı temel görsel nesnedir."
    )
    add_callout(
        doc,
        "Karar Kuralı",
        "Koşucu kutusunun alt tabanı seçilen çizginin altına geçtiğinde sistem ilgili ID'yi GEÇTİ olarak işaretler. Bip geldiğinde bu geçiş onaylanır ve koşucu yeni mekik için Aktif durumuna alınır.",
    )
    add_image(doc, GENERATED_DIR / "dual_analysis_12s.jpg", "Şekil 10.1. Kulvar ID'leri ve aktif koşucu kutuları.", 6.5)
    add_image(doc, GENERATED_DIR / "dual_analysis_75s.jpg", "Şekil 10.2. 20m kamerasında ID bazlı geçiş takibi.", 6.5)

    add_heading(doc, "11. Deneysel Çalışma ve Ekran Görüntüleri", 1)
    doc.add_paragraph(
        "Deneysel çalışma, mevcut 0m ve 20m kamera videoları kullanılarak yürütülmüştür. Sistem, iki kamera görüntüsünü yan yana birleştirerek analiz ekranı üretir. Bu ekranda çizgiler, koşucu kutuları, ID etiketleri, aktif/geçti/elendi durumları ve bip zamanlayıcı bilgileri eş zamanlı olarak gösterilir."
    )
    add_image(doc, GENERATED_DIR / "dual_analysis_05s.jpg", "Şekil 11.1. Testin başlangıcına yakın çift kamera çalışma ekranı.", 6.5)
    add_image(doc, GENERATED_DIR / "dual_analysis_20s.jpg", "Şekil 11.2. Bip ve hedef çizgi takibinin birlikte gösterilmesi.", 6.5)
    add_image(doc, GENERATED_DIR / "dual_analysis_35s.jpg", "Şekil 11.3. Koşucuların iki kamera görüntüsünde hedef çizgilere yaklaşma süreci.", 6.5)
    add_image(doc, GENERATED_DIR / "dual_analysis_55s.jpg", "Şekil 11.4. İlerleyen süreçte aktif koşucu ve çizgi durumları.", 6.5)
    add_image(doc, ASSET_DIR / "03_0m_donus.jpg", "Şekil 11.5. Başlangıç kamerasında dönüş fazının izlenmesi.", 6.0)
    add_image(doc, ASSET_DIR / "04_20m_uzaklasma.jpg", "Şekil 11.6. 20m kamerasında uzaklaşma/yaklaşma fazı.", 6.0)

    add_heading(doc, "12. Sonuçların Değerlendirilmesi", 1)
    doc.add_paragraph(
        "Sistem çıktıları, her koşucu için toplam geçiş sayısı, 20m çizgisi geçişleri, başlangıç çizgisi geçişleri, zamanında geçişler, geç kalma sayısı ve eleme nedeni gibi alanları içerir. Bu yapı, yalnızca nihai sonucu değil, sonucun nasıl oluştuğunu da incelemeye olanak tanır."
    )
    add_results_table(doc)
    doc.add_paragraph(
        "Sonuç tablosu incelendiğinde sistemin her koşucu için bağımsız değerlendirme yaptığı görülmektedir. Koşucuların farklı zamanlarda elenmesi, geçişlerin ID bazında tutulduğunu ve bip/deadline mantığının her koşucuya ayrı uygulandığını göstermektedir."
    )
    add_heading(doc, "12.1 Yazılım Doğrulama", 2)
    add_bullet(doc, "Ana Python dosyaları derleme kontrolünden geçirilmiştir.")
    add_bullet(doc, "Mevcut otomatik test paketi çalıştırılmış ve testler başarılı sonuç vermiştir.")
    add_bullet(doc, "Rapor belgesinde ekran görüntülerinin Word nesnesi olarak yer aldığı yapısal olarak doğrulanmıştır.")

    add_heading(doc, "13. Sınırlılıklar ve Riskler", 1)
    add_bullet(doc, "Kamera açısı çok değişirse çizginin yeniden kalibre edilmesi gerekir.")
    add_bullet(doc, "Aşırı düşük ışık, hareket bulanıklığı veya koşucuların üst üste binmesi tespit kalitesini düşürebilir.")
    add_bullet(doc, "Kulvar ID mantığı, koşucuların kulvar değiştirmediği varsayımında daha kararlı çalışır.")
    add_bullet(doc, "Video ile bip sesi arasında senkronizasyon hatası varsa değerlendirme sonuçları etkilenebilir.")
    add_bullet(doc, "Canlı fiziksel kamera kullanımında gecikme ve kare senkronizasyonu ayrıca ölçülmelidir.")

    add_heading(doc, "14. Sonuç ve Gelecek Çalışmalar", 1)
    doc.add_paragraph(
        "Bu çalışma kapsamında geliştirilen sistem, 20 metre mekik koşusu testinin çift kamera görüntüsü üzerinden otomatik değerlendirilmesi için uygulanabilir bir çözüm sunmaktadır. Kullanıcı tanımlı çizgi kalibrasyonu, farklı çekim koşullarına uyum sağlamayı kolaylaştırmaktadır. Kulvar ID yaklaşımı ve kutu alt tabanına dayalı geçiş kararı, ekrandaki takip sürecini daha anlaşılır hale getirmektedir."
    )
    doc.add_paragraph(
        "Gelecek çalışmalarda canlı kamera entegrasyonu, otomatik kalibrasyon kaydı, daha gelişmiş ID sürekliliği, web tabanlı izleme paneli ve istatistiksel performans raporları sisteme eklenebilir. Ayrıca farklı salonlarda ve farklı koşucu sayılarında daha geniş testler yapılarak sistemin genellenebilirliği değerlendirilebilir."
    )

    add_heading(doc, "Kaynakça", 1)
    refs = [
        "Ultralytics YOLOv8-Pose dokümantasyonu ve model kullanım notları.",
        "OpenCV video işleme, çizim ve görüntü penceresi yönetimi dokümantasyonu.",
        "Python, Pandas ve OpenPyXL kütüphaneleri ile raporlama ve veri işleme yaklaşımı.",
        "20 metre mekik koşusu / beep test uygulama ilkeleri ve saha değerlendirme pratikleri.",
    ]
    for ref in refs:
        p = doc.add_paragraph(style="List Number")
        p.add_run(ref)

    add_heading(doc, "Ekler", 1)
    add_heading(doc, "Ek A. Üretilen Çıktılar", 2)
    add_bullet(doc, "Analiz videosu: data/outputs/0metre_20metre_dual_camera.mp4")
    add_bullet(doc, "Özet sonuç dosyası: data/outputs/sonuc_ozet.csv")
    add_bullet(doc, "Detay sonuç dosyası: data/outputs/sonuc_detay.csv")
    add_bullet(doc, "Excel raporu: data/outputs/sonuc_rapor.xlsx")
    add_heading(doc, "Ek B. Kullanım Komutları", 2)
    doc.add_paragraph("python dual_main.py")
    doc.add_paragraph("python dual_main.py --no-audio")
    doc.add_paragraph("python dual_main.py --start-video 0metre.mp4 --far-video 20metre.mp4")
    doc.add_paragraph("python dual_main.py --use-config-lines")


def build_report():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = Document()
    set_styles(doc)
    add_title_page(doc)
    add_manual_toc(doc)
    add_abstract(doc)
    add_chapters(doc)
    add_header_footer(doc)
    doc.save(REPORT_PATH)
    print(REPORT_PATH)


if __name__ == "__main__":
    build_report()
