from __future__ import annotations

from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "outputs" / "reports"
ASSET_DIR = ROOT / "data" / "outputs" / "report_assets"
OUT_PATH = OUT_DIR / "mekik_test_sistem_raporu.docx"


BLUE = RGBColor(46, 116, 181)
DARK_BLUE = RGBColor(31, 77, 120)
GRAY_FILL = "F2F4F7"
LIGHT_BLUE_FILL = "E8EEF5"
INK = RGBColor(31, 31, 31)


def set_cell_shading(cell, fill: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_text(cell, text: str, bold: bool = False):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(text)
    run.bold = bold
    run.font.name = "Calibri"
    run.font.size = Pt(10)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def set_table_borders(table):
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = "w:" + edge
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "D9DEE7")


def add_heading(doc: Document, text: str, level: int = 1):
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        run.font.name = "Calibri"
        run.font.color.rgb = BLUE if level <= 2 else DARK_BLUE
    return p


def add_body(doc: Document, text: str):
    p = doc.add_paragraph(text)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.10
    for run in p.runs:
        run.font.name = "Calibri"
        run.font.size = Pt(11)
        run.font.color.rgb = INK
    return p


def add_bullet(doc: Document, text: str):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(10.5)
    return p


def add_caption(doc: Document, text: str):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(text)
    run.italic = True
    run.font.name = "Calibri"
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(90, 90, 90)


def add_kv_table(doc: Document, rows: list[tuple[str, str]], widths=(2.2, 4.1)):
    table = doc.add_table(rows=0, cols=2)
    table.autofit = False
    for key, val in rows:
        cells = table.add_row().cells
        cells[0].width = Inches(widths[0])
        cells[1].width = Inches(widths[1])
        set_cell_text(cells[0], key, bold=True)
        set_cell_text(cells[1], val)
        set_cell_shading(cells[0], GRAY_FILL)
    set_table_borders(table)
    doc.add_paragraph()
    return table


def add_data_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float]):
    table = doc.add_table(rows=1, cols=len(headers))
    table.autofit = False
    for i, header in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.width = Inches(widths[i])
        set_cell_text(cell, header, bold=True)
        set_cell_shading(cell, LIGHT_BLUE_FILL)
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].width = Inches(widths[i])
            set_cell_text(cells[i], value)
    set_table_borders(table)
    doc.add_paragraph()
    return table


def add_figure(doc: Document, image_name: str, caption: str, width_in: float = 6.2):
    path = ASSET_DIR / image_name
    if not path.exists():
        add_body(doc, f"Gorsel bulunamadi: {path}")
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(str(path), width=Inches(width_in))
    add_caption(doc, caption)


def set_styles(doc: Document):
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.10

    for name, size, color in [
        ("Heading 1", 16, BLUE),
        ("Heading 2", 13, BLUE),
        ("Heading 3", 12, DARK_BLUE),
    ]:
        style = doc.styles[name]
        style.font.name = "Calibri"
        style.font.size = Pt(size)
        style.font.color.rgb = color
        style.font.bold = True
        style.paragraph_format.space_before = Pt(10 if name != "Heading 1" else 14)
        style.paragraph_format.space_after = Pt(6)


def add_footer(doc: Document):
    for section in doc.sections:
        footer = section.footer
        p = footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("Otomatik Mekik Testi Degerlendirme Sistemi - Teknik Rapor")
        run.font.name = "Calibri"
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(100, 100, 100)


def build():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = Document()
    set_styles(doc)

    # Cover
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run("Otomatik Mekik Testi Değerlendirme Sistemi")
    run.font.name = "Calibri"
    run.font.size = Pt(24)
    run.font.bold = True
    run.font.color.rgb = BLUE

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("Çift Kamera, Perspektif Çizgi Takibi ve Resmi Kademe Zamanlayıcısı")
    run.font.name = "Calibri"
    run.font.size = Pt(13)
    run.font.color.rgb = DARK_BLUE

    add_kv_table(
        doc,
        [
            ("Proje klasörü", str(ROOT)),
            ("Kamera videoları", "0metre.mp4 ve 20metre.mp4"),
            ("Rapor tarihi", date.today().strftime("%d.%m.%Y")),
            ("Rapor kapsamı", "Mevcut sistem durumu, çalışma mantığı, ekran örnekleri, riskler ve öneriler"),
        ],
    )

    add_body(
        doc,
        "Bu rapor, mekik koşusu testinin iki ayrı kamera videosu kullanılarak otomatik "
        "değerlendirilmesi için geliştirilen mevcut yazılımın durumunu ve çalışma "
        "mantığını açıklar. Odak noktası; çıkış zamanının doğru kurulması, çizgi geçişlerinin "
        "güvenilir yakalanması, koşucuların durumlarının ekranda anlaşılır gösterilmesi ve "
        "eleme kararının resmi mekik testi kademelerine göre verilmesidir."
    )
    doc.add_page_break()

    add_heading(doc, "1. Yönetici Özeti")
    add_body(
        doc,
        "Sistem şu anda 0 metre ve 20 metre çizgilerini ayrı kamera görüntülerinden takip eden "
        "bir çift kamera mimarisine sahiptir. Çıkış zamanı bu video seti için 10. saniyeye "
        "sabitlenmiştir. Çıkıştan sonra süreler videodaki ortam sesine değil, resmi mekik "
        "testi temposuna göre hesaplanır. Bu yaklaşım, videodaki eksik veya gürültülü bip "
        "seslerinin hatalı toplu eleme oluşturmasını engeller."
    )
    add_bullet(doc, "Koşucu beklenen çizgiyi bipten önce geçerse ekranda GECTI Mx etiketi görünür.")
    add_bullet(doc, "İlgili bip zamanı geldiğinde geçiş onaylanmış kabul edilir ve sistem bir sonraki hedef çizgiyi bekler.")
    add_bullet(doc, "Beklenen çizgi bip/deadline öncesi geçilmezse koşucu elenir.")
    add_bullet(doc, "Çizgi, yatay tek Y değeri yerine iki uç koninin alt noktasını birleştiren perspektif çizgi olarak hesaplanır.")

    add_heading(doc, "2. Amaç ve Kapsam")
    add_body(
        doc,
        "Amaç, mekik koşusu testinde yarışmacıların 0 m ve 20 m çizgilerine zamanında ulaşıp "
        "ulaşmadığını otomatik olarak kontrol etmektir. Sistem, her koşucuya takip ID'si atar, "
        "beklenen hedef çizgide geçişi yakalar ve resmi kademe zaman çizelgesine göre "
        "zamanında/geç/elenmiş durumunu üretir."
    )
    add_data_table(
        doc,
        ["Kapsam Kalemi", "Mevcut Durum", "Not"],
        [
            ["Video girişi", "0m ve 20m olmak üzere iki ayrı MP4", "Varsayılan dosyalar proje kökündedir."],
            ["Çıkış zamanı", "10.0 s sabit", "CLI ile --start-beep-time kullanılarak değiştirilebilir."],
            ["Zamanlayıcı", "Resmi kademe formülü", "Seviye arttıkça hız artar, mekik süresi azalır."],
            ["Çizgi modeli", "İki noktalı perspektif çizgi", "Koni alt noktaları temel alınır."],
            ["Durum etiketi", "Aktif / GECTI Mx / ELENDI", "GECTI etiketi ilgili bip gelene kadar görünür."],
        ],
        [1.55, 2.05, 2.55],
    )

    add_heading(doc, "3. Sistem Mimarisi")
    add_body(
        doc,
        "Uygulama Python, OpenCV ve YOLOv8-Pose/ByteTrack akışı üzerine kuruludur. İki video "
        "akışı paralel biçimde okunur; her kameradaki koşucu tespitleri ortak koşucu ID düzenine "
        "aktarılır. Değerlendirme motoru, hangi mekiğin hangi çizgide tamamlanması gerektiğini "
        "resmi zamanlayıcıdan alır."
    )
    add_data_table(
        doc,
        ["Bileşen", "Görev"],
        [
            ["dual_main.py", "Video akışları, çizim, HUD, çıktı videosu ve ana çalışma döngüsü."],
            ["dual_camera_analyser.py", "Çizgi geçişi, GECTI durumu, deadline kontrolü ve eleme kararı."],
            ["tracker.py", "YOLOv8-Pose ve ByteTrack ile koşucu/ayak bileği takibi."],
            ["timer.py", "Resmi mekik testi kademe ve süre çizelgesinin hesaplanması."],
            ["line_geometry.py", "Perspektif çizgi üzerinde X konumuna karşılık gelen Y değerinin hesaplanması."],
            ["audio_detector.py", "Gerekirse video sesinden bip adayı çıkarma altyapısı."],
        ],
        [2.0, 4.15],
    )

    add_heading(doc, "4. Video Görselleri ve Çizgi Tanımı")
    add_body(
        doc,
        "Aşağıdaki görüntüler videolardan alınmıştır. Renkli çizgiler, sistemin çizgi geçişini "
        "hesaplarken kullandığı perspektif çizgiyi gösterir. Bu çizgiler düz yatay bir piksel "
        "satırı değildir; her koşucunun X konumuna göre çizgi üzerindeki karşılık gelen Y değeri "
        "hesaplanır."
    )
    add_figure(doc, "01_0m_baslangic.jpg", "Şekil 1. 0m kamerası: başlangıç çizgisi ve koşucuların çıkış konumu.")
    add_figure(doc, "02_20m_yaklasim.jpg", "Şekil 2. 20m kamerası: koşucuların 20m çizgisine yaklaşma durumu.")
    add_figure(doc, "03_0m_donus.jpg", "Şekil 3. 0m kamerası: dönüş yönünde başlangıç çizgisine yaklaşma örneği.")
    add_figure(doc, "04_20m_uzaklasma.jpg", "Şekil 4. 20m kamerası: çizgi sonrası uzaklaşma/hareket yönü örneği.")

    add_heading(doc, "5. Çizgi Geçiş Mantığı")
    add_body(
        doc,
        "Koşucunun ayak bileği orta noktası, ilgili kameradaki perspektif çizgiyle karşılaştırılır. "
        "Çizgiye temas bandına girilmesi veya hedef tarafına geçilmesi, o hedef çizginin geçildiği "
        "anlamına gelir. Hedef tarafı, gerçek çift kamera modunda her iki kamera için çizginin "
        "kameraya yakın tarafıdır."
    )
    add_bullet(doc, "1. mekik hedefi: 20m çizgisi.")
    add_bullet(doc, "2. mekik hedefi: 0m çizgisi.")
    add_bullet(doc, "Yönler sırayla 20m, 0m, 20m, 0m olarak devam eder.")
    add_bullet(doc, "Aynı koşucunun fiziksel olarak imkansız kısa sürede iki çizgiyi birden geçmiş sayılmaması için minimum aralık filtresi vardır.")

    add_heading(doc, "6. Zamanlayıcı ve Kademe Sistemi")
    add_body(
        doc,
        "Çıkış anı bu video seti için 10.0 saniyedir. Ekranda bu anda CIKIS BIPI! gösterilir "
        "ve yarış saati sıfırlanır. Sonraki hedef zamanları resmi mekik testi formülüne göre "
        "üretilir: hız = 8.0 + (kademe - 1) x 0.5 km/h; mekik süresi = 20 m / hız."
    )
    add_data_table(
        doc,
        ["Kademe", "Hız", "Mekik Sayısı", "Örnek Deadline"],
        [
            ["1", "8.0 km/h", "7", "9.000, 18.000, 27.000, ... s"],
            ["2", "8.5 km/h", "8", "71.471 s sonrasında 8.471 s aralıklarla"],
            ["3", "9.0 km/h", "8", "Seviye 2 tamamlandıktan sonra daha kısa aralıklarla"],
        ],
        [1.0, 1.4, 1.3, 2.5],
    )

    add_heading(doc, "7. Koşucu Durumları")
    add_body(
        doc,
        "Ekrandaki koşucu etiketi, değerlendirme motorunun o anki kararını anlaşılır hale getirir. "
        "Özellikle yeni eklenen GECTI Mx etiketi, koşucunun beklenen çizgiyi geçtiğini ve ilgili "
        "bip gelene kadar güvenli olduğunu gösterir."
    )
    add_data_table(
        doc,
        ["Ekran Etiketi", "Anlamı", "Sonraki Davranış"],
        [
            ["Aktif", "Koşucu testtedir ve sıradaki hedef çizgiyi beklemektedir.", "Beklenen çizgiyi geçerse GECTI olur."],
            ["GECTI Mx", "Koşucu x numaralı mekiğin hedef çizgisini bipten önce geçmiştir.", "İlgili bip gelince etiket tekrar Aktif olur."],
            ["ELENDI", "Koşucu beklenen çizgiyi deadline öncesinde geçmemiştir.", "Raporlarda eleme zamanı ve nedeni yazılır."],
        ],
        [1.4, 2.7, 2.0],
    )

    add_heading(doc, "8. Mevcut Test Bulguları")
    add_body(
        doc,
        "Kısa testlerde sistem, 10. saniye çıkış ayarıyla ilk 20m hedefini çıkıştan 9 saniye "
        "sonra değerlendirmiştir. İlk hedef çizgi geçişinde 5 koşucunun 20m çizgisini zamanında "
        "tamamladığı görülmüştür. Ayrıca yapay senaryoda GECTI etiketinin ilgili bip zamanına "
        "kadar kaldığı ve bipten sonra Aktif durumuna döndüğü doğrulanmıştır."
    )
    add_data_table(
        doc,
        ["Test", "Beklenen", "Gözlenen"],
        [
            ["Çıkış ayarı", "Video 10.0s yarış başlangıcı", "Yarış saati 10.0s'de sıfırlanıyor."],
            ["İlk hedef", "Çıkıştan 9.0s sonra 20m", "İlk 20m geçişleri zamanında sayıldı."],
            ["GECTI etiketi", "Geçişten deadline'a kadar görünmeli", "Yapay testte GECTI M1 -> Aktif geçişi doğrulandı."],
            ["Perspektif çizgi", "İki uç koni altını birleştirmeli", "0m ve 20m için iki noktalı çizgi tanımlandı."],
        ],
        [1.5, 2.25, 2.35],
    )

    add_heading(doc, "9. Riskler ve Dikkat Edilecek Noktalar")
    add_bullet(doc, "Kamera açısı değişirse çizgi uç noktaları yeniden kalibre edilmelidir.")
    add_bullet(doc, "Koşucular birbirini kapattığında YOLO/ByteTrack ID değişimi yaşanabilir.")
    add_bullet(doc, "Videodaki ortam sesi güvenilir olmadığından, sadece çıkış zamanı için kullanılmalı; kademe süreleri resmi timer ile devam etmelidir.")
    add_bullet(doc, "Koni yerleri değişirse iki noktalı perspektif çizgi tekrar ayarlanmalıdır.")
    add_bullet(doc, "Final kabul testi, tam video üzerinden ve mümkünse manuel gözlemle karşılaştırılarak yapılmalıdır.")

    add_heading(doc, "10. Önerilen Sonraki Geliştirmeler")
    add_data_table(
        doc,
        ["Öneri", "Amaç", "Öncelik"],
        [
            ["Ekran üzerinden iki uç nokta seçimi", "Koni altlarını fareyle kolayca kalibre etmek", "Yüksek"],
            ["Koşucu ID stabilizasyonu", "Kamera değişiminde aynı koşucunun aynı ID ile sürmesi", "Yüksek"],
            ["Tam video kabul raporu", "Her koşucunun mekik bazlı durumunu ayrı ayrı doğrulamak", "Orta"],
            ["Kamera bazlı ROI ayarı", "Seyirci/kenar tespitlerini filtrelemek", "Orta"],
            ["PDF/Excel rapor genişletme", "Sonuçları antrenör veya hakem için okunur hale getirmek", "Düşük"],
        ],
        [2.25, 2.8, 1.0],
    )

    add_heading(doc, "11. Sonuç")
    add_body(
        doc,
        "Proje, çift kamera üzerinden mekik testi değerlendirmesi yapabilecek çalışan bir temel "
        "mimariye ulaşmıştır. Mevcut karar mantığı; çıkış anı, resmi kademe zamanlayıcısı, "
        "perspektif çizgi geçişi, GECTI durumu ve eleme kuralını birleştirir. Bir sonraki kritik "
        "adım, çizgi uç noktalarının kullanıcı arayüzünden kolay kalibre edilmesi ve tam video "
        "kabul testinin yapılmasıdır."
    )

    add_footer(doc)
    doc.save(OUT_PATH)
    print(OUT_PATH)


if __name__ == "__main__":
    build()
