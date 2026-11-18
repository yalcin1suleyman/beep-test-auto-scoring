"""Build the delivery PDF from the independently validated release manifest.

Optional dependency: reportlab (python -m pip install reportlab).
Run after scripts/prepare_release.py.
"""
import json
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'docs/reports/2026-11-18'


def build():
    data = json.loads((OUT/'dogrulama.json').read_text(encoding='utf-8'))
    import csv
    with (OUT/'kosucu_sonuclari.csv').open(encoding='utf-8-sig', newline='') as source:
        participants = list(csv.DictReader(source))
    pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
    pdfmetrics.registerFont(TTFont('ArialBold', 'C:/Windows/Fonts/arialbd.ttf'))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('BodyTR',fontName='Arial',fontSize=10,leading=15,spaceAfter=8,textColor=colors.HexColor('#293847')))
    styles.add(ParagraphStyle('TitleTR',fontName='ArialBold',fontSize=26,leading=31,spaceAfter=14,textColor=colors.HexColor('#102638')))
    styles.add(ParagraphStyle('HeadingTR',fontName='ArialBold',fontSize=14,leading=19,spaceBefore=10,spaceAfter=9,textColor=colors.HexColor('#102638')))
    styles.add(ParagraphStyle('SmallTR',fontName='Arial',fontSize=8,leading=11,spaceAfter=6))
    styles.add(ParagraphStyle('CellTR',fontName='Arial',fontSize=8,leading=11))
    styles.add(ParagraphStyle('CellHeadTR',fontName='ArialBold',fontSize=8,leading=11,textColor=colors.white))
    def p(value,style='BodyTR'):
        label=str(value).translate(str.maketrans({'\u2011':'-','\u2013':'-','\u2014':'-'}))
        return Paragraph(escape(label), styles[style])
    def count_label(value):
        return f'{value:,}'.replace(',','.')
    def table(headers,rows,widths):
        content = [[p(c,'CellHeadTR') for c in headers]]+[[p(c,'CellTR') for c in row] for row in rows]
        result = Table(content,colWidths=widths,repeatRows=1,hAlign='LEFT')
        result.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#163b50')),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),7),
            ('BOTTOMPADDING',(0,0),(-1,-1),7),('LEFTPADDING',(0,0),(-1,-1),7),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f0f5f8'),colors.white]),
            ('LINEBELOW',(0,0),(-1,0),.6,colors.HexColor('#163b50')),
            ('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#d7e0e6'))]))
        return result
    def footer(canvas,doc):
        canvas.setStrokeColor(colors.HexColor('#d7e0e6'))
        canvas.line(20*mm,18*mm,190*mm,18*mm)
        canvas.setFont('Arial',8)
        canvas.setFillColor(colors.HexColor('#586a78'))
        canvas.drawString(20*mm,13*mm,'MEKİK TESTİ | 18 Kasım 2026 | Teknik doğrulama ve otomatik sonuçlar')
        canvas.drawRightString(190*mm,13*mm,str(doc.page))
    story = [p('MEKİK TESTİ','HeadingTR'),p('Proje ve sonuçlar\nTeslim raporu'.replace('\n',' - '),'TitleTR'),
        p('18 Kasım 2026 | İki telefon kamerasıyla 20 m mekik koşusu analizi'),
        p('Teknik sonuç','HeadingTR'),
        p(f"{data['tests_passed']} otomatik test geçti. Yedi kamera çiftinin ortak kayıt aralığı, kare atlanmadan işlendi. "
          f"14 kaynak dosyanın {count_label(data['source_frames'])} karesi çözümlendi ve masaüstündeki asıllarla SHA-256 eşleşmesi doğrulandı."),
        p(f"Toplam {count_label(data['analyzed_timeline_frames'])} analiz karesi için çıktı videoları yeniden okundu; CSV ve Excel içerikleri, sayaçlar ve başarılı mekik kayıtlarının tekilliği denetlendi."),
        p('Puanlama kapsamı','HeadingTR'),
        p('Video 1-6 yapılandırılmış bip çizelgesine göre otomatik değerlendirildi. Video 7 standart bip testi ritmine uymadığından gözlem olarak işlendi; puan, mesafe, seviye ve eleme kararı yayımlanmadı.'),
        table(['Kayıt','Kare','Koşucu','Devam','Elendi','Puan yok'],
              [[r['name'],r['frames'],r['runners'],r['continued'],r['eliminated'],r['unscored']] for r in data['sessions']],
              [30*mm,31*mm,26*mm,27*mm,27*mm,29*mm]),
        Spacer(1,12*mm),p('Sonuçların anlamı','HeadingTR'),
        p('Bu tablo yazılımın otomatik kararlarını gösterir. Hakem kayıtlarına karşı doğruluk oranı ölçülmemiştir. Teknik testlerin geçmesi, her koşucunun kimlik ve çizgi temasının kusursuz tanındığı anlamına gelmez.'),PageBreak(),
        p('Koşucu sonuçları','TitleTR'),
        p('Koşucu numarası her kayıt içinde başlangıç kamerasından soldan sağa atanır. Aynı numara farklı kayıtlarda aynı kişiyi ifade etmez. Mesafe, raporda tamamlanmış sayılan mekik adedinin 20 m ile çarpımıdır.','SmallTR')]
    standard = [r for r in participants if r['Sonuç'] != 'Puanlanmadı']
    story += [table(['Kayıt / Koşucu','Sonuç','Mekik','Mesafe (m)','Ulaştığı seviye'],
        [[r['Kayıt']+' / '+r['Koşucu'],r['Sonuç'],r['Tamamlanan mekik'],r['Koşulan mesafe (m)'],r['Ulaştığı seviye']] for r in standard],
        [45*mm,30*mm,20*mm,25*mm,50*mm]),Spacer(1,7*mm),
        p('Video 7’deki beş koşucu puanlama dışında tutulmuştur. Ayrıntılı mekik zamanları kayıt başına SONUC.xlsx ve SONUC.html dosyalarındadır.','SmallTR'),PageBreak(),
        p('Yöntem ve sınırlamalar','TitleTR'),
        p('Kamera eşleme ve analiz','HeadingTR'),
        p('Birinci kameranın her karesi analiz edilir. İkinci kamera, kayıtlar arasındaki zaman farkı uygulanarak eşlenir. FPS değerleri farklı olduğunda ikinci kameradaki her kaynak kareye ayrıca model uygulanması anlamına gelmez. Kamera hareketi, referans çizgiye göre homografiyle telafi edilir.'),
        p(f"Ayarlar: Bip sonrası tolerans {data['rules']['late_tolerance_seconds']} s; çizgi temas payı {data['rules']['line_touch_tolerance_pixels']} piksel; eleme eşiği {data['rules']['consecutive_late_limit']} ardışık gecikme. Model ve ByteTrack dosyalarının SHA-256 değerleri doğrulama kaydındadır.",'SmallTR'),
        table(['Kayıt','Çıkış bipi (s)','Kamera farkı (s)','Puanlama'],
            [[r['name'],f"{r['start_beep_time']:.2f}",f"{r['cam2_offset']:+.2f}",'Otomatik' if r['scoring_eligible'] else 'Uygun değil'] for r in data['sessions']],
            [35*mm,44*mm,45*mm,46*mm]),
        p('Ölçüm belirsizlikleri','HeadingTR'),
        p('Video 1: Salon bipi zayıftır; başlangıç zamanı tahminidir. Yaklaşık +/-1 saniyelik belirsizlik uyarı ve eleme sonuçlarını etkileyebilir. Video 6: Kadraj kenarındaki koşucunun görünürlüğü sınırlıdır. Video 7: Farklı ritim ve beklemeler standart puanlamayı geçersiz kılar.'),
        p('İzlenebilirlik ve teslim','HeadingTR'),
        p('Yerel başlangıç sayfası: data/outputs/sonuclar/SONUCLAR.html. Her video klasöründe okunur HTML/Excel raporu, CSV tabloları, analiz videosu ve son durum görseli bulunur. teknik/output_validation.json çıktının ve metadatanın hash değerlerini içerir.'),
        p('Kod ve raporlar depoya alınır; yeni kaynak ve analiz videoları yerel diskte kalır.','SmallTR'),
        p('Tekrar çalıştırma','HeadingTR'),
        Paragraph('<br/>'.join(escape(command) for command in [
            'python scripts/start_full_batch.py', 'python scripts/audit_session_sources.py',
            'python -m pytest -q --junitxml=data/outputs/hazirlik_2026-11-18/testler.xml',
            'python scripts/prepare_release.py']),styles['SmallTR']),
        p('Kaynaklar: mekik_sessions.json; kaynak.txt dosyaları; her kaydın teknik/run_metadata.json, ham_gecisler.csv ve çıktı doğrulama kaydı. İnsan tarafından etiketlenmiş bir doğruluk veri seti kullanılmamıştır.','SmallTR')]
    target = OUT/'MEKIK_DOGRULAMA_RAPORU.pdf'
    doc = SimpleDocTemplate(str(target),pagesize=A4,leftMargin=20*mm,rightMargin=20*mm,topMargin=20*mm,bottomMargin=24*mm,
        title='Mekik sistemi - teslim ve doğrulama raporu',author='Mekik Test Projesi')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print(target)


if __name__ == '__main__':
    build()
