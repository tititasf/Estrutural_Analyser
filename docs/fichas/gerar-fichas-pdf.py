"""
Gerador de PDFs das Fichas de Compreensão dos Robôs
====================================================
Converte os arquivos .md em PDF usando reportlab (sem dependências de browser).

Uso:
    python gerar-fichas-pdf.py
    python gerar-fichas-pdf.py --robo bolt
    python gerar-fichas-pdf.py --robo crane
    python gerar-fichas-pdf.py --robo slab
"""

import sys
import argparse
from pathlib import Path

FICHAS_DIR = Path(__file__).parent

FICHAS = {
    'bolt': FICHAS_DIR / 'bolt-pilar-ficha.md',
    'crane': FICHAS_DIR / 'crane-viga-ficha.md',
    'slab': FICHAS_DIR / 'slab-laje-ficha.md',
}


def gerar_pdf_reportlab(md_path: Path, pdf_path: Path):
    """Gera PDF a partir de Markdown usando reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Preformatted, Table, TableStyle,
            Image as RLImage
        )
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
    except ImportError:
        print("reportlab nao instalado. Execute: pip install reportlab")
        return False

    text = md_path.read_text(encoding='utf-8')
    lines = text.split('\n')

    styles = getSampleStyleSheet()

    # Estilos customizados
    h1_style = ParagraphStyle('H1', parent=styles['Heading1'],
                               fontSize=16, textColor=colors.HexColor('#1a3a5c'),
                               spaceAfter=12)
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'],
                               fontSize=13, textColor=colors.HexColor('#2c5f8a'),
                               spaceAfter=8, spaceBefore=12)
    h3_style = ParagraphStyle('H3', parent=styles['Heading3'],
                               fontSize=11, textColor=colors.HexColor('#3a7ab8'),
                               spaceAfter=6, spaceBefore=8)
    body_style = ParagraphStyle('Body', parent=styles['Normal'],
                                 fontSize=9, leading=14)
    code_style = ParagraphStyle('Code', parent=styles['Code'],
                                 fontSize=8, fontName='Courier',
                                 backColor=colors.HexColor('#f5f5f5'),
                                 borderColor=colors.HexColor('#dddddd'),
                                 borderWidth=1, borderPadding=6)

    caption_style = ParagraphStyle('Caption', parent=styles['Normal'],
                                    fontSize=8, textColor=colors.HexColor('#555555'),
                                    alignment=TA_CENTER, spaceBefore=2, spaceAfter=8)

    story = []
    in_code_block = False
    code_lines = []
    table_lines = []
    in_table = False
    import re
    _img_re = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

    def flush_code():
        if code_lines:
            code_text = '\n'.join(code_lines)
            story.append(Preformatted(code_text, code_style))
            story.append(Spacer(1, 6))
            code_lines.clear()

    def flush_table():
        if table_lines:
            # Parse table
            rows = []
            for tl in table_lines:
                if set(tl.replace('|', '').replace('-', '').replace(' ', '')) == set():
                    continue  # separator row
                cells = [c.strip() for c in tl.split('|') if c.strip()]
                if cells:
                    rows.append(cells)

            if rows:
                max_cols = max(len(r) for r in rows)
                # Pad rows
                rows = [r + [''] * (max_cols - len(r)) for r in rows]

                col_width = (A4[0] - 4*cm) / max_cols
                t = Table(rows, colWidths=[col_width] * max_cols)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5f8a')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1),
                     [colors.white, colors.HexColor('#f0f4f8')]),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('PADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(t)
                story.append(Spacer(1, 8))
            table_lines.clear()

    for line in lines:
        # Code blocks
        if line.startswith('```'):
            if in_code_block:
                flush_code()
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Table rows
        if line.startswith('|'):
            if in_table:
                table_lines.append(line)
            else:
                flush_code()
                in_table = True
                table_lines.append(line)
            continue
        else:
            if in_table:
                flush_table()
                in_table = False

        # Images: ![caption](path)
        m = _img_re.match(line.strip())
        if m:
            caption, img_path = m.group(1), m.group(2)
            # Resolve relative to md_path directory
            p = Path(img_path) if Path(img_path).is_absolute() else md_path.parent / img_path
            if p.exists():
                max_w = A4[0] - 4*cm
                max_h = A4[1] * 0.55  # max 55% da altura da página
                try:
                    # Get actual dimensions to compute aspect ratio
                    try:
                        from PIL import Image as PILImage
                        with PILImage.open(str(p)) as pil:
                            iw, ih = pil.size
                    except Exception:
                        iw, ih = 1200, 800  # fallback ratio
                    # Scale to fit max_w, then check height
                    scale = max_w / iw
                    draw_w = max_w
                    draw_h = ih * scale
                    if draw_h > max_h:
                        scale = max_h / ih
                        draw_w = iw * scale
                        draw_h = max_h
                    img = RLImage(str(p), width=draw_w, height=draw_h)
                    img.hAlign = 'CENTER'
                    story.append(img)
                    if caption:
                        story.append(Paragraph(caption, caption_style))
                    story.append(Spacer(1, 8))
                except Exception as e:
                    story.append(Paragraph(f'[Imagem: {p.name} — erro: {e}]', caption_style))
            else:
                story.append(Paragraph(f'[Imagem nao encontrada: {img_path}]', caption_style))
            continue

        # Headers
        if line.startswith('# ') and not line.startswith('## '):
            title = line[2:].strip()
            story.append(Paragraph(title, h1_style))
            continue
        if line.startswith('## '):
            story.append(Paragraph(line[3:].strip(), h2_style))
            continue
        if line.startswith('### '):
            story.append(Paragraph(line[4:].strip(), h3_style))
            continue

        # Horizontal rule
        if line.startswith('---'):
            story.append(Spacer(1, 4))
            continue

        # Bold lines (**)
        if line.strip():
            # Simple markdown-to-reportlab: replace ** with <b>
            text_line = line.replace('**', '<b>', 1).replace('**', '</b>', 1)
            text_line = text_line.replace('`', '').replace('*', '')
            # Bullets
            if line.startswith('- ') or line.startswith('  - '):
                bullet = '&bull; ' + text_line.lstrip('- ').strip()
                story.append(Paragraph(bullet, body_style))
            else:
                story.append(Paragraph(text_line, body_style))
        else:
            story.append(Spacer(1, 4))

    flush_code()
    flush_table()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title=md_path.stem,
    )
    doc.build(story)
    return True


def gerar_pdf_markdown_fallback(md_path: Path, pdf_path: Path):
    """Fallback: gera PDF usando markdown2 + weasyprint se disponivel."""
    try:
        import markdown2
        from weasyprint import HTML
        html = markdown2.markdown(md_path.read_text(encoding='utf-8'),
                                   extras=['tables', 'fenced-code-blocks'])
        styled = f"""
        <html><head><style>
        body {{ font-family: Arial; font-size: 10px; margin: 20px; }}
        h1 {{ color: #1a3a5c; }} h2 {{ color: #2c5f8a; }} h3 {{ color: #3a7ab8; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th {{ background: #2c5f8a; color: white; padding: 4px; }}
        td {{ border: 1px solid #ccc; padding: 4px; font-size: 9px; }}
        pre {{ background: #f5f5f5; padding: 8px; font-size: 8px; }}
        </style></head><body>{html}</body></html>
        """
        HTML(string=styled).write_pdf(str(pdf_path))
        return True
    except ImportError:
        return False


def main():
    parser = argparse.ArgumentParser(description='Gera PDFs das fichas dos robôs')
    parser.add_argument('--robo', choices=['bolt', 'crane', 'slab', 'all'],
                        default='all', help='Qual robô gerar (default: all)')
    args = parser.parse_args()

    robos = FICHAS.keys() if args.robo == 'all' else [args.robo]

    for robo in robos:
        md_path = FICHAS[robo]
        pdf_path = md_path.with_suffix('.pdf')

        print(f"\n[{robo.upper()}] Gerando PDF: {pdf_path.name}")

        if not md_path.exists():
            print(f"  ERRO: {md_path} nao encontrado")
            continue

        # Tentar reportlab primeiro
        ok = gerar_pdf_reportlab(md_path, pdf_path)
        if not ok:
            # Fallback: weasyprint
            ok = gerar_pdf_markdown_fallback(md_path, pdf_path)

        if ok and pdf_path.exists():
            size_kb = pdf_path.stat().st_size / 1024
            print(f"  OK: {pdf_path} ({size_kb:.0f}KB)")
        else:
            print(f"  FALHA: Instale reportlab (pip install reportlab) e tente novamente")


if __name__ == '__main__':
    main()
