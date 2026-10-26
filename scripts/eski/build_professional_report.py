from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "outputs" / "reports"
ASSET_DIR = ROOT / "data" / "outputs" / "report_assets"
GENERATED_DIR = ASSET_DIR / "generated"
LINE_CHECK_DIR = ROOT / "data" / "outputs" / "line_check"
REPORT_PATH = OUT_DIR / "mekik_test_profesyonel_rapor.docx"


BLUE = RGBColor(46, 116, 181)
DARK_BLUE = RGBColor(31, 77, 120)
INK = RGBColor(20, 30, 40)
MUTED = RGBColor(90, 90, 90)


TR_REPLACEMENTS = {
    "OTOMATIK MEKIK TESTI": "OTOMATİK MEKİK TESTİ",
    "DEGERLENDIRME SISTEMI": "DEĞERLENDİRME SİSTEMİ",
    "Cift": "Çift",
    "cift": "çift",
    "Kullanici": "Kullanıcı",
    "kullanici": "kullanıcı",
    "Tanimli": "Tanımlı",
    "tanimli": "tanımlı",
    "Cizgi": "Çizgi",
    "cizgi": "çizgi",
    "Kosucu": "Koşucu",
    "kosucu": "koşucu",
    "Degerlendirme": "Değerlendirme",
    "degerlendirme": "değerlendirme",
    "Sistemi": "Sistemi",
    "sistemi": "sistemi",
    "Raporun Amaci": "Raporun Amacı",
    "amaci": "amacı",
    "Amaci": "Amacı",
    "calisma": "çalışma",
    "Calisma": "Çalışma",
    "gelistirilen": "geliştirilen",
    "gelistirme": "geliştirme",
    "Gelistirme": "Geliştirme",
    "goruntu": "görüntü",
    "goruntusu": "görüntüsü",
    "goruntuleri": "görüntüleri",
    "Goruntuleri": "Görüntüleri",
    "gorsel": "görsel",
    "Gorsel": "Görsel",
    "akademik": "akademik",
    "teknik": "teknik",
    "Hazirlanma": "Hazırlanma",
    "Cikti": "Çıktı",
    "Ciktilari": "Çıktıları",
    "Çıktılari": "Çıktıları",
    "Formati": "Formatı",
    "Icindekiler": "İçindekiler",
    "Giris": "Giriş",
    "Kapsami": "Kapsamı",
    "Tanimi": "Tanımı",
    "Kullanilan": "Kullanılan",
    "Teknolojiler": "Teknolojiler",
    "Belirleme": "Belirleme",
    "Takibi": "Takibi",
    "Tabanli": "Tabanlı",
    "Diskalifiye Mantigi": "Diskalifiye Mantığı",
    "Test ve Dogrulama": "Test ve Doğrulama",
    "Dogrulama": "Doğrulama",
    "Sonuc": "Sonuç",
    "Onerileri": "Önerileri",
    "amaca": "amaca",
    "uzerinden": "üzerinden",
    "hedefleyen": "hedefleyen",
    "yazilim": "yazılım",
    "Yazilim": "Yazılım",
    "kapsamaktadir": "kapsamaktadır",
    "baslangic": "başlangıç",
    "Baslangic": "Başlangıç",
    "ayri": "ayrı",
    "Ayri": "Ayrı",
    "takip eder": "takip eder",
    "zamanlarina": "zamanlarına",
    "yorumlar": "yorumlar",
    "gecis": "geçiş",
    "Gecis": "Geçiş",
    "GECTI": "GEÇTİ",
    "gecti": "geçti",
    "aktif": "aktif",
    "cizilen": "çizilen",
    "alt tabaninin": "alt tabanının",
    "altina": "altına",
    "gore": "göre",
    "olusturmak": "oluşturmak",
    "azaltmak": "azaltmak",
    "gorundugunden": "göründüğünden",
    "zayiflayabilir": "zayıflayabilir",
    "mimarisini": "mimarisini",
    "kullanir": "kullanır",
    "asamasinda": "aşamasında",
    "icin": "için",
    "noktasi": "noktası",
    "donusturulur": "dönüştürülür",
    "uretir": "üretir",
    "uretilen": "üretilen",
    "olusturur": "oluşturur",
    "goruntulenir": "görüntülenir",
    "yaklasma": "yaklaşma",
    "sureci": "süreci",
    "sonuclari": "sonuçları",
    "tamamlandi": "tamamlandı",
    "basariyla": "başarıyla",
    "Guncel": "Güncel",
    "Onerilen": "Önerilen",
    "Kanitlar": "Kanıtlar",
    "on isleme": "ön işleme",
    "kaydedilip": "kaydedilip",
    "yuklenmesi": "yüklenmesi",
    "iyilestirebilir": "iyileştirebilir",
    "olcumu": "ölçümü",
}


def tr_text(text: str) -> str:
    for src, dst in TR_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text


def localize_turkish(doc: Document):
    containers = list(doc.paragraphs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                containers.extend(cell.paragraphs)
    for paragraph in containers:
        for run in paragraph.runs:
            # Runs that contain pictures often have empty text. Reassigning
            # run.text on those runs can remove the drawing from the document.
            if run.text:
                run.text = tr_text(run.text)


def set_cell_shading(cell, fill: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_borders(cell, color="D9E2EC"):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right"):
        tag = OxmlElement(f"w:{edge}")
        tag.set(qn("w:val"), "single")
        tag.set(qn("w:sz"), "4")
        tag.set(qn("w:space"), "0")
        tag.set(qn("w:color"), color)
        borders.append(tag)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def format_table(table, header_fill="F2F4F7"):
    table.autofit = False
    for i, row in enumerate(table.rows):
        for cell in row.cells:
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_borders(cell)
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                for run in p.runs:
                    run.font.name = "Calibri"
                    run.font.size = Pt(9)
        if i == 0:
            set_repeat_table_header(row)
            for cell in row.cells:
                set_cell_shading(cell, header_fill)
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.bold = True
                        run.font.color.rgb = DARK_BLUE


def add_caption(doc: Document, text: str):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(10)
    r = p.add_run(text)
    r.italic = True
    r.font.size = Pt(9)
    r.font.color.rgb = MUTED


def add_image(doc: Document, path: Path, caption: str, width: float = 6.2):
    if not path.exists():
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Inches(width))
    add_caption(doc, caption)


def add_bullet(doc: Document, text: str):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(4)
    p.add_run(text)


def add_numbered(doc: Document, text: str):
    p = doc.add_paragraph(style="List Number")
    p.paragraph_format.space_after = Pt(4)
    p.add_run(text)


def add_callout(doc: Document, title: str, body: str):
    table = doc.add_table(rows=1, cols=1)
    table.autofit = False
    cell = table.cell(0, 0)
    set_cell_shading(cell, "F4F6F9")
    set_cell_borders(cell, "CAD6E3")
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(title)
    r.bold = True
    r.font.color.rgb = DARK_BLUE
    r.font.size = Pt(10)
    p2 = cell.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    p2.add_run(body)
    doc.add_paragraph()


def add_heading(doc: Document, text: str, level: int):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.keep_with_next = True
    return p


def set_styles(doc: Document):
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.font.color.rgb = INK
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.10

    for name, size, color, before, after in [
        ("Heading 1", 16, BLUE, 16, 8),
        ("Heading 2", 13, BLUE, 12, 6),
        ("Heading 3", 12, DARK_BLUE, 8, 4),
    ]:
        style = styles[name]
        style.font.name = "Calibri"
        style.font.size = Pt(size)
        style.font.color.rgb = color
        style.font.bold = True
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    for name in ("List Bullet", "List Number"):
        style = styles[name]
        style.font.name = "Calibri"
        style.font.size = Pt(11)
        style.paragraph_format.space_after = Pt(4)
        style.paragraph_format.line_spacing = 1.167


def add_header_footer(doc: Document):
    for section in doc.sections:
        header = section.header
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hr = hp.add_run("Otomatik Mekik Testi Degerlendirme Sistemi")
        hr.font.size = Pt(9)
        hr.font.color.rgb = MUTED

        footer = section.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fr = fp.add_run("Profesyonel Teknik Rapor")
        fr.font.size = Pt(9)
        fr.font.color.rgb = MUTED


def add_cover(doc: Document):
    for _ in range(3):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("OTOMATIK MEKIK TESTI\nDEGERLENDIRME SISTEMI")
    r.bold = True
    r.font.size = Pt(24)
    r.font.color.rgb = DARK_BLUE

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Cift Kamera, Kullanici Tanimli Cizgi Kalibrasyonu ve Bip Tabanli Performans Analizi")
    r.font.size = Pt(13)
    r.font.color.rgb = MUTED

    doc.add_paragraph()
    add_callout(
        doc,
        "Raporun Amaci",
        "Bu rapor, 20 metre mekik kosusu icin gelistirilen bilgisayarli gorme tabanli degerlendirme sisteminin amacini, mimarisini, calisma mantigini, ekran goruntulerini ve test sonuclarini akademik ve teknik bir formatta aciklar.",
    )

    table = doc.add_table(rows=5, cols=2)
    rows = [
        ("Proje", "Otomatik Mekik Testi Degerlendirme Sistemi"),
        ("Kapsam", "Cift kamera analizi, kulvar ID takibi, cizgi gecis tespiti, bip/deadline kontrolu"),
        ("Hazirlanma Tarihi", datetime.now().strftime("%d.%m.%Y")),
        ("Cikti Formati", "Microsoft Word DOCX"),
        ("Gorsel Kaynaklar", "Kalibrasyon kareleri, analiz video kareleri ve sonuc raporlari"),
    ]
    for i, (k, v) in enumerate(rows):
        table.cell(i, 0).text = k
        table.cell(i, 1).text = v
    format_table(table)
    doc.add_page_break()


def add_contents(doc: Document):
    add_heading(doc, "Icindekiler", 1)
    entries = [
        "1. Giris",
        "2. Projenin Amaci ve Kapsami",
        "3. Problem Tanimi",
        "4. Sistem Mimarisi",
        "5. Kullanilan Teknolojiler",
        "6. Kalibrasyon ve Cizgi Belirleme",
        "7. Kosucu Tespiti ve Kulvar ID Takibi",
        "8. Bip Tabanli Degerlendirme ve Diskalifiye Mantigi",
        "9. Calisma Ekran Goruntuleri",
        "10. Test ve Dogrulama",
        "11. Sonuc ve Gelistirme Onerileri",
    ]
    for entry in entries:
        p = doc.add_paragraph(entry)
        p.paragraph_format.left_indent = Inches(0.2)
        p.paragraph_format.space_after = Pt(3)
    doc.add_page_break()


def add_summary_table(doc: Document):
    csv_path = ROOT / "data" / "outputs" / "sonuc_ozet.csv"
    if not csv_path.exists():
        return
    df = pd.read_csv(csv_path)
    cols = ["Kosucu ID", "Durum", "Toplam Gecis", "20m Gecis", "Baslangic Gecis", "Zamaninda", "Gec", "Eleme Zamani (s)"]
    table = doc.add_table(rows=1, cols=len(cols))
    for j, col in enumerate(cols):
        table.cell(0, j).text = col
    for _, row in df.iterrows():
        cells = table.add_row().cells
        for j, col in enumerate(cols):
            cells[j].text = str(row.get(col, "-"))
    format_table(table)


def build_report():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = Document()
    set_styles(doc)

    add_cover(doc)
    add_contents(doc)
    add_header_footer(doc)

    add_heading(doc, "1. Giris", 1)
    doc.add_paragraph(
        "Bu calisma, 20 metre mekik kosusu testinin video verileri uzerinden otomatik olarak degerlendirilmesini hedefleyen bir yazilim sistemini kapsamaktadir. Sistem; iki kamera goruntusunu birlikte kullanarak baslangic ve 20 metre cizgilerini ayri ayri takip eder, kosuculari kulvar ID'leriyle izler ve bip zamanlarina gore gecis durumlarini yorumlar."
    )
    doc.add_paragraph(
        "Rapor, uygulamanin guncel calisma mantigini esas alir: kullanici her iki kamerada hedef cizgiyi kendisi belirler; kosucu gecisi, kosucunun etrafinda cizilen kutunun alt tabaninin secilen cizginin altina gecmesine gore kabul edilir."
    )

    add_heading(doc, "2. Projenin Amaci ve Kapsami", 1)
    add_bullet(doc, "Mekik testi esnasinda insan hatasini azaltan, tekrarlanabilir ve kayit altina alinabilir bir degerlendirme akisi olusturmak.")
    add_bullet(doc, "0m ve 20m noktalarini iki ayri kamera goruntusuyle izleyerek uzak mesafe tespit sorununu azaltmak.")
    add_bullet(doc, "Her kosucuyu kulvar ID'si ile takip ederek ekrandaki degerlendirmeyi okunabilir hale getirmek.")
    add_bullet(doc, "Bip zamanlariyla cizgi gecislerini eslestirerek aktif, gecti ve elendi durumlarini otomatik uretmek.")

    add_heading(doc, "3. Problem Tanimi", 1)
    doc.add_paragraph(
        "Mekik testlerinde temel zorluk, kosucunun hedef cizgiye bipten once ulasip ulasmadiginin anlik olarak ve nesnel bicimde belirlenmesidir. Tek kamera kullaniminda uzak uctaki kosucular kucuk gorundugunden poz tespiti zayiflayabilir. Bu nedenle sistem, baslangic ve 20m noktalarini ayri kamera goruntuleriyle izleyen cift kamera mimarisini kullanir."
    )
    add_callout(
        doc,
        "Guncel Gecis Kurali",
        "Bir kosucu sadece takip kutusunun alt tabani kullanici tarafindan belirlenen cizginin altina indigi zaman 'GECTI' durumuna alinir. Cizgiye yakin olmak veya temas bandinda bulunmak tek basina gecis sayilmaz.",
    )

    add_heading(doc, "4. Sistem Mimarisi", 1)
    doc.add_paragraph(
        "Sistem boru hatti video alma, kalibrasyon, poz/takip, cizgi gecis degerlendirmesi, bip zamanlayici kontrolu, ekran ustu gorsellestirme ve raporlama modullerinden olusur."
    )
    flow = doc.add_table(rows=1, cols=5)
    headers = ["Video Girisi", "Kalibrasyon", "Kosucu Takibi", "Bip Kontrolu", "Raporlama"]
    details = [
        "0m ve 20m kamera videolari",
        "Kullanici 2 noktayla cizgi secer",
        "YOLOv8-Pose + kulvar ID",
        "Deadline ve gecis eslestirme",
        "CSV, Excel ve video ciktilari",
    ]
    for i, h in enumerate(headers):
        flow.cell(0, i).text = h + "\n" + details[i]
    format_table(flow, "E8EEF5")

    add_heading(doc, "5. Kullanilan Teknolojiler", 1)
    tech = doc.add_table(rows=1, cols=3)
    for i, h in enumerate(["Bilesen", "Kullanim", "Aciklama"]):
        tech.cell(0, i).text = h
    rows = [
        ("Python", "Ana uygulama dili", "Video isleme, analiz ve raporlama akislarini yonetir."),
        ("OpenCV", "Video isleme ve arayuz", "Kare okuma, pencere gosterimi, cizgi ve kutu cizimi icin kullanilir."),
        ("YOLOv8-Pose", "Kosucu tespiti", "Kosucularin beden noktalarini ve takip kutularini uretir."),
        ("ByteTrack / Kulvar ID", "Kimlik surekliligi", "Takibi kolaylastirmak icin kosucular kulvar ID mantigiyla gosterilir."),
        ("Pandas / OpenPyXL", "Raporlama", "Ozet ve detay sonuclari CSV/Excel olarak kaydeder."),
    ]
    for row in rows:
        cells = tech.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = value
    format_table(tech)

    add_heading(doc, "6. Kalibrasyon ve Cizgi Belirleme", 1)
    doc.add_paragraph(
        "Kalibrasyon asamasinda kullanici, her kamera icin cizginin sol ve sag ucunu iki tiklama ile belirler. Bu yontem, kamera perspektifinden kaynaklanan egik cizgi gorunumunu daha dogru temsil eder."
    )
    add_numbered(doc, "Kamera 1 penceresinde baslangic / 0m cizgisinin sol ve sag noktasi secilir.")
    add_numbered(doc, "Kamera 2 penceresinde 20m cizgisinin sol ve sag noktasi secilir.")
    add_numbered(doc, "Secilen noktalar PerspectiveLine modeline donusturulur ve her kosucunun X konumuna karsilik gelen cizgi Y degeri hesaplanir.")
    add_image(doc, ASSET_DIR / "01_0m_baslangic.jpg", "Sekil 1. Kamera 1 icin kullanici tarafindan belirlenen baslangic cizgisi.", 5.8)
    add_image(doc, ASSET_DIR / "02_20m_yaklasim.jpg", "Sekil 2. Kamera 2 icin kullanici tarafindan belirlenen 20m cizgisi.", 5.8)

    add_heading(doc, "7. Kosucu Tespiti ve Kulvar ID Takibi", 1)
    doc.add_paragraph(
        "Kosucular ekranda takip kutulari ile gosterilir. ID numaralari takip kolayligi icin kulvar mantigina gore atanir. Bu sayede her kosucunun aktif, gecti veya elendi durumu kamera penceresinde dogrudan okunabilir."
    )
    add_bullet(doc, "Kutu rengi kosucunun durumunu gorsel olarak ayirt etmeye yardim eder.")
    add_bullet(doc, "Kutu alt tabani gecis kararinda esas alinan referans noktadir.")
    add_bullet(doc, "Sistem, ayak bilegi noktasindan kaynaklanabilecek kararsizliklari azaltmak icin gecis kararini kutu tabanina dayandirir.")

    add_heading(doc, "8. Bip Tabanli Degerlendirme ve Diskalifiye Mantigi", 1)
    doc.add_paragraph(
        "Bip zamanlari, kosucunun ilgili hedef cizgiyi hangi zamanda gecmesi gerektigini belirleyen deadline olarak kullanilir. Kosucu cizgiyi bipten once gecerse 'GECTI' olarak isaretlenir. Bip geldiginde bu gecis onaylanir ve kosucu sonraki mekik icin tekrar 'Aktif' durumuna doner."
    )
    add_bullet(doc, "Kosucu bip anina kadar cizgiyi gecmediyse gec kalmis sayilir.")
    add_bullet(doc, "Ardisik gec kalma sayaci sistemdeki esik degerine ulasinca kosucu diskalifiye edilir.")
    add_bullet(doc, "Mevcut konfigurasyonda MAX_CONSECUTIVE_LATE = 2 olarak kullanilmaktadir.")

    add_heading(doc, "9. Calisma Ekran Goruntuleri", 1)
    doc.add_paragraph(
        "Bu bolumde sistemin gercek calisma ekranlari verilmektedir. Gorseller; kullanici tarafindan belirlenen cizgileri, cift kamera panelini, kosucu ID kutularini, aktif/gecis durumlarini ve bip zamanlayici bilgisini gostermektedir."
    )
    add_image(doc, GENERATED_DIR / "dual_analysis_12s.jpg", "Sekil 3. Cift kamera panelinde kulvar ID'leri ve aktif kosucu durumlari.", 6.5)
    add_image(doc, GENERATED_DIR / "dual_analysis_35s.jpg", "Sekil 4. Kosucularin iki kamera goruntusunde hedef cizgilere yaklasma sureci.", 6.5)
    add_image(doc, GENERATED_DIR / "dual_analysis_75s.jpg", "Sekil 5. Gecis takibinin 20m kamerasinda ID bazli gosterimi.", 6.5)
    add_image(doc, ASSET_DIR / "03_0m_donus.jpg", "Sekil 6. Baslangic kamerasinda donus fazi ve cizgi referansi.", 5.8)
    add_image(doc, ASSET_DIR / "04_20m_uzaklasma.jpg", "Sekil 7. 20m kamerasinda uzaklasma/yaklasma fazinin izlenmesi.", 5.8)

    add_heading(doc, "10. Test ve Dogrulama", 1)
    doc.add_paragraph(
        "Uygulama ciktilari hem gorsel hem de tablo tabanli olarak dogrulanmistir. Analiz sonucunda her kosucu icin toplam gecis, 20m gecisi, baslangic gecisi, zamaninda gecis, gec kalma sayisi ve eleme nedeni raporlanir."
    )
    add_summary_table(doc)
    add_caption(doc, "Tablo 1. Sistem tarafindan uretilen kosucu ozet sonuclari.")
    add_heading(doc, "10.1 Yazilim Dogrulama", 2)
    add_bullet(doc, "Python derleme kontrolu ile ana dosyalarda sozdizimi dogrulandi.")
    add_bullet(doc, "Mevcut otomatik test paketi calistirildi ve testler basariyla tamamlandi.")
    add_bullet(doc, "Kalibrasyon penceresi, kullanici secimli iki nokta mantigina uygun hale getirildi.")

    add_heading(doc, "11. Sonuc ve Gelistirme Onerileri", 1)
    doc.add_paragraph(
        "Gelistirilen sistem, mekik testi degerlendirmesinde cift kamera goruntusunu, kullanici tanimli cizgi kalibrasyonunu ve bip tabanli deadline mantigini birlestirerek uygulanabilir bir otomatik analiz cozumu sunmaktadir. Kulvar ID gosterimi ve kutu alt tabanina dayali gecis karari, ekrandaki takibi daha anlasilir ve denetlenebilir hale getirir."
    )
    add_heading(doc, "11.1 Onerilen Gelistirmeler", 2)
    add_bullet(doc, "Farkli salon isik kosullari icin otomatik pozlama ve renk duzeltme on isleme eklenebilir.")
    add_bullet(doc, "Kulvar ID eslestirmesi icin uzun sureli re-identification modeliyle daha kararli takip saglanabilir.")
    add_bullet(doc, "Kalibrasyon noktalarinin JSON olarak kaydedilip istenirse yeniden yuklenmesi kullanici deneyimini iyilestirebilir.")
    add_bullet(doc, "Canli kamera kullanimi icin senkronizasyon ve gecikme olcumu modulu eklenebilir.")

    doc.add_page_break()
    add_heading(doc, "Ek A. Gorsel Kanitlar ve Ekran Ciktilari", 1)
    doc.add_paragraph(
        "Bu ekte raporda kullanilan calisma ekranlarinin daha genis bir secimi sunulmustur. Gorseller, sistemin yalnizca teorik olarak degil, video uzerinde calisan bir analiz araci olarak isledigini gostermek amaciyla eklenmistir."
    )
    add_image(doc, LINE_CHECK_DIR / "0metre.mp4_two_point_line.jpg", "Ek Sekil A1. 0m kamerasinda iki nokta ile belirlenen perspektif cizgisi.", 6.2)
    add_image(doc, LINE_CHECK_DIR / "20metre.mp4_two_point_line.jpg", "Ek Sekil A2. 20m kamerasinda iki nokta ile belirlenen perspektif cizgisi.", 6.2)
    add_image(doc, GENERATED_DIR / "dual_analysis_05s.jpg", "Ek Sekil A3. Test baslangicina yakin cift kamera calisma ekrani.", 6.5)
    add_image(doc, GENERATED_DIR / "dual_analysis_20s.jpg", "Ek Sekil A4. Bip ve hedef cizgi takibi sirasinda cift kamera gorunumu.", 6.5)
    add_image(doc, GENERATED_DIR / "dual_analysis_55s.jpg", "Ek Sekil A5. Ilerleyen surecte aktif kosucu ve cizgi durumlari.", 6.5)

    localize_turkish(doc)
    doc.save(REPORT_PATH)
    print(REPORT_PATH)


if __name__ == "__main__":
    build_report()
