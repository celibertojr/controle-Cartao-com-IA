"""
Gera 6 PDFs de fatura (Nubank) no formato compatível com o importador.
Saída: faturas_teste/fatura_nubank_AAAA-MM.pdf
"""

import sys
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

OUTPUT_DIR = Path(__file__).parent / "faturas_teste"
OUTPUT_DIR.mkdir(exist_ok=True)

# Cada fatura: (invoice_month, vencimento, fechamento, [(data_dd_mm, descrição, valor)])
# valor negativo → será formatado com sufixo CR (estorno)
FATURAS = [
    {
        "month":       "2025-12",
        "title":       "FATURA NUBANK - DEZEMBRO/2025",
        "vencimento":  "05/01/2026",
        "fechamento":  "25/12/2025",
        "lancamentos": [
            ("05/12", 'Samsung TV 65" QLED (1/6)',   1100.00),
            ("01/12", "Netflix",                       55.90),
            ("08/12", "Uber",                          87.50),
            ("10/12", "Supermercado Pao de Acucar",   650.00),
            ("15/12", "Restaurante Madero",            230.00),
            ("20/12", "Presente de Natal",             480.00),
        ],
    },
    {
        "month":       "2026-01",
        "title":       "FATURA NUBANK - JANEIRO/2026",
        "vencimento":  "05/02/2026",
        "fechamento":  "25/01/2026",
        "lancamentos": [
            ("05/01", 'Samsung TV 65" QLED (2/6)',   1100.00),
            ("10/01", "iPhone 15 Pro 512GB (1/3)",   1800.00),
            ("02/01", "Spotify",                       21.90),
            ("15/01", "Supermercado Carrefour",        720.00),
            ("20/01", "Aluguel de Carro Localiza",     380.00),
            ("22/01", "Farmacia Drogasil",             145.00),
        ],
    },
    {
        "month":       "2026-02",
        "title":       "FATURA NUBANK - FEVEREIRO/2026",
        "vencimento":  "05/03/2026",
        "fechamento":  "25/02/2026",
        "lancamentos": [
            ("05/02", 'Samsung TV 65" QLED (3/6)',   1100.00),
            ("10/02", "iPhone 15 Pro 512GB (2/3)",   1800.00),
            ("01/02", "Passagens Aereas LATAM",       4500.00),
            ("03/02", "Hotel Grand Hyatt 3 diarias",  2800.00),
            ("15/02", "Supermercado Extra",           1200.00),
            ("20/02", "Restaurante Fogo de Chao",      450.00),
        ],
    },
    {
        "month":       "2026-03",
        "title":       "FATURA NUBANK - MARCO/2026",
        "vencimento":  "05/04/2026",
        "fechamento":  "25/03/2026",
        "lancamentos": [
            ("05/03", 'Samsung TV 65" QLED (4/6)',   1100.00),
            ("10/03", "iPhone 15 Pro 512GB (3/3)",   1800.00),
            ("05/03", "AirPods Pro 2a geracao",       1900.00),
            ("12/03", "EXTORNO AirPods Pro 2a ger",  -1900.00),  # extorno
            ("18/03", "Supermercado Pao de Acucar",    880.00),
            ("22/03", "Restaurante Coco Bambu",         340.00),
            ("01/03", "Netflix",                        55.90),
        ],
    },
    {
        "month":       "2026-04",
        "title":       "FATURA NUBANK - ABRIL/2026",
        "vencimento":  "05/05/2026",
        "fechamento":  "25/04/2026",
        "lancamentos": [
            ("05/04", 'Samsung TV 65" QLED (5/6)',   1100.00),
            ("01/04", "Spotify",                       21.90),
            ("10/04", "Supermercado Carrefour",        950.00),
            ("15/04", "Farmacia Ultrafarma",            230.00),
            ("20/04", "Cinemark",                       85.00),
            ("22/04", "Restaurante Outback",            420.00),
            ("24/04", "iFood",                          145.00),
        ],
    },
    {
        "month":       "2026-05",
        "title":       "FATURA NUBANK - MAIO/2026",
        "vencimento":  "05/06/2026",
        "fechamento":  "25/05/2026",
        "lancamentos": [
            ("05/05", 'Samsung TV 65" QLED (6/6)',   1100.00),
            ("01/05", "Netflix",                        55.90),
            ("10/05", "Supermercado Pao de Acucar",   1100.00),
            ("15/05", "Combustivel Ipiranga",           320.00),
            ("20/05", "Restaurante Japones Ky",         290.00),
            ("22/05", "Farmacia Drogasil",              175.00),
        ],
    },
]


def formatar_valor(v: float) -> str:
    """Formata valor no padrão brasileiro: 1.234,56 ou 1.234,56 CR para negativos."""
    abs_v = abs(v)
    inteiro = int(abs_v)
    centavos = round((abs_v - inteiro) * 100)
    partes = []
    s = str(inteiro)
    while len(s) > 3:
        partes.append(s[-3:])
        s = s[:-3]
    partes.append(s)
    inteiro_fmt = ".".join(reversed(partes))
    valor_fmt = f"{inteiro_fmt},{centavos:02d}"
    return f"{valor_fmt} CR" if v < 0 else valor_fmt


def gerar_pdf(fatura: dict):
    fname = OUTPUT_DIR / f"fatura_nubank_{fatura['month']}.pdf"
    c = canvas.Canvas(str(fname), pagesize=A4)
    w, h = A4

    # Cabeçalho roxo
    c.setFillColorRGB(0.42, 0.0, 0.75)
    c.rect(0, h - 55*mm, w, 55*mm, fill=1, stroke=0)

    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(15*mm, h - 22*mm, "nubank")

    c.setFont("Helvetica-Bold", 13)
    c.drawString(15*mm, h - 36*mm, fatura["title"])

    c.setFont("Helvetica", 9)
    c.drawString(15*mm, h - 46*mm,
                 f"Vencimento: {fatura['vencimento']}    "
                 f"Fechamento: {fatura['fechamento']}")

    # Subtítulo da seção
    y = h - 65*mm
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(15*mm, y, "LANÇAMENTOS NACIONAIS")
    y -= 6*mm

    # Linha separadora
    c.setStrokeColorRGB(0.8, 0.8, 0.8)
    c.line(15*mm, y, w - 15*mm, y)
    y -= 7*mm

    # Cabeçalho da tabela
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(15*mm, y, "DATA")
    c.drawString(35*mm, y, "DESCRIÇÃO")
    c.drawRightString(w - 15*mm, y, "VALOR (R$)")
    y -= 5*mm
    c.line(15*mm, y, w - 15*mm, y)
    y -= 7*mm

    # Lançamentos
    total = 0.0
    for data, desc, valor in fatura["lancamentos"]:
        total += valor
        valor_fmt = formatar_valor(valor)
        is_extorno = valor < 0

        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.15, 0.15, 0.15)
        c.drawString(15*mm, y, data)

        if is_extorno:
            c.setFillColorRGB(0.8, 0.1, 0.1)
        c.drawString(35*mm, y, desc)

        c.setFillColorRGB(0.8, 0.1, 0.1) if is_extorno else c.setFillColorRGB(0.15, 0.15, 0.15)
        c.drawRightString(w - 15*mm, y, valor_fmt)

        y -= 7*mm

    # Linha total
    y -= 3*mm
    c.setStrokeColorRGB(0.42, 0.0, 0.75)
    c.setLineWidth(1.2)
    c.line(15*mm, y, w - 15*mm, y)
    y -= 7*mm

    c.setFont("Helvetica-Bold", 10)
    c.setFillColorRGB(0.42, 0.0, 0.75)
    c.drawString(15*mm, y, "TOTAL DA FATURA")
    c.drawRightString(w - 15*mm, y, formatar_valor(total))

    # Rodapé
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    c.drawCentredString(w / 2, 10*mm, "Documento gerado para fins de teste — Controle Cartão IA")

    c.save()
    return fname


def main():
    print(f"Gerando PDFs em: {OUTPUT_DIR}\n")
    for fatura in FATURAS:
        path = gerar_pdf(fatura)
        total = sum(v for _, _, v in fatura["lancamentos"])
        print(f"  {path.name}  —  Total: {formatar_valor(total)}")
    print(f"\n{len(FATURAS)} PDFs gerados com sucesso!")


if __name__ == "__main__":
    main()
