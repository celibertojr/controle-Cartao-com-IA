"""
Gera 5 faturas PDF de teste (Janeiro a Maio de 2026).
Fechamento no dia 25 de cada mês.
Inclui parcelamentos em 3x, 6x e 12x, e um estorno em Abril.
"""

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as rl_canvas

OUTPUT_DIR = Path(__file__).parent

FATURAS = {
    "janeiro_2026": {
        "titulo": "FATURA JANEIRO 2026",
        "vencimento": "05/02/2026",
        "fechamento": "25/01/2026",
        "linhas": [
            "28/12  Supermercado Pao de Acucar                     320,00",
            "05/01  Supermercado Extra                             450,00",
            "08/01  Posto Shell Combustivel                        180,00",
            "10/01  Netflix Assinatura Mensal                       55,90",
            "12/01  Farmacia Sao Paulo                              89,50",
            "15/01  Restaurante Madero                             156,00",
            "18/01  Notebook Samsung Galaxy 1/12                   300,00",
            "20/01  Academia FitLife Mensalidade                   120,00",
            "22/01  iFood Pedido Delivery                           67,30",
            "24/01  Cinemark Ingresso                               45,00",
        ],
    },
    "fevereiro_2026": {
        "titulo": "FATURA FEVEREIRO 2026",
        "vencimento": "05/03/2026",
        "fechamento": "25/02/2026",
        "linhas": [
            "27/01  Mercado Livre Produto Eletronico                95,00",
            "02/02  Supermercado Extra                             380,00",
            "05/02  Netflix Assinatura Mensal                       55,90",
            "07/02  Posto Ipiranga Combustivel                     210,00",
            "10/02  Sofa Tok e Stok Sala 1/6                       400,00",
            "12/02  Farmacia Droga Raia                             45,00",
            "14/02  Restaurante Outback Jantar                     280,00",
            "15/02  Academia FitLife Mensalidade                   120,00",
            "18/02  Notebook Samsung Galaxy 2/12                   300,00",
            "20/02  iFood Pedido Delivery                           89,00",
            "22/02  Spotify Assinatura Mensal                       21,90",
            "25/02  Mercado Livre Acessorios                       135,00",
        ],
    },
    "marco_2026": {
        "titulo": "FATURA MARCO 2026",
        "vencimento": "05/04/2026",
        "fechamento": "25/03/2026",
        "linhas": [
            "26/02  Mercado Livre Livros                            95,00",
            "03/03  Supermercado Carrefour                         420,00",
            "05/03  Netflix Assinatura Mensal                       55,90",
            "07/03  Posto Shell Combustivel                        195,00",
            "08/03  Geladeira Consul Frost Free 1/3                300,00",
            "10/03  Sofa Tok e Stok Sala 2/6                       400,00",
            "12/03  Notebook Samsung Galaxy 3/12                   300,00",
            "15/03  Academia FitLife Mensalidade                   120,00",
            "17/03  Restaurante Fogo de Chao                       340,00",
            "20/03  iFood Pedido Delivery                           54,00",
            "22/03  Farmacia CVS Medicamentos                       67,00",
            "24/03  Amazon Produto Importado                       189,90",
        ],
    },
    "abril_2026": {
        "titulo": "FATURA ABRIL 2026",
        "vencimento": "05/05/2026",
        "fechamento": "25/04/2026",
        "linhas": [
            "26/03  Mercado Livre Eletronico                       145,00",
            "02/04  Supermercado Extra Compras Semanais            395,00",
            "05/04  Netflix Assinatura Mensal                       55,90",
            "07/04  Posto BR Combustivel                           220,00",
            "10/04  Geladeira Consul Frost Free 2/3                300,00",
            "12/04  Sofa Tok e Stok Sala 3/6                       400,00",
            "14/04  Notebook Samsung Galaxy 4/12                   300,00",
            "15/04  Academia FitLife Mensalidade                   120,00",
            "17/04  Amazon Produto Importado                      -189,90",
            "19/04  Restaurante Coco Bambu                         215,00",
            "21/04  iFood Pedido Delivery                           78,50",
            "23/04  Spotify Assinatura Mensal                       21,90",
            "25/04  Magazine Luiza Eletrodomestico                 450,00",
        ],
    },
    "maio_2026": {
        "titulo": "FATURA MAIO 2026",
        "vencimento": "05/06/2026",
        "fechamento": "25/05/2026",
        "linhas": [
            "27/04  Mercado Livre Produto Casa                     110,00",
            "03/05  Supermercado Pao de Acucar                    410,00",
            "05/05  Netflix Assinatura Mensal                       55,90",
            "08/05  Posto Shell Combustivel                        185,00",
            "10/05  Geladeira Consul Frost Free 3/3                300,00",
            "12/05  Sofa Tok e Stok Sala 4/6                       400,00",
            "14/05  Notebook Samsung Galaxy 5/12                   300,00",
            "15/05  Academia FitLife Mensalidade                   120,00",
            "18/05  Restaurante Quintal Sabor                      178,00",
            "20/05  iFood Pedido Delivery                           92,00",
            "22/05  Mercado Livre Roupas                           145,00",
            "24/05  Farmacia Sao Paulo Remedios                     56,00",
        ],
    },
}


def gerar_pdf(nome_arquivo: str, dados: dict):
    caminho = OUTPUT_DIR / f"fatura_{nome_arquivo}.pdf"
    c = rl_canvas.Canvas(str(caminho), pagesize=A4)
    largura, altura = A4

    # Cabeçalho
    c.setFillColorRGB(0.20, 0.47, 0.75)
    c.rect(0, altura - 3.5 * cm, largura, 3.5 * cm, fill=True, stroke=False)

    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(1.5 * cm, altura - 1.8 * cm, dados["titulo"])
    c.setFont("Helvetica", 10)
    c.drawString(1.5 * cm, altura - 2.8 * cm,
                 f"Fechamento: {dados['fechamento']}    Vencimento: {dados['vencimento']}")

    # Linha separadora do corpo
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.setFont("Helvetica-Bold", 9)
    y = altura - 4.5 * cm
    c.drawString(1.5 * cm, y, "DATA")
    c.drawString(3.5 * cm, y, "DESCRIÇÃO")
    c.drawRightString(largura - 1.5 * cm, y, "VALOR (R$)")

    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(1.5 * cm, y - 0.2 * cm, largura - 1.5 * cm, y - 0.2 * cm)

    # Lançamentos
    c.setFont("Courier", 9)
    y -= 0.8 * cm
    total = 0.0

    for linha in dados["linhas"]:
        partes = linha.split()
        data  = partes[0]
        valor_str = partes[-1]
        desc  = " ".join(partes[1:-1])

        # Converte para float para somar
        negativo = valor_str.startswith("-")
        v = float(valor_str.replace("-", "").replace(".", "").replace(",", "."))
        if negativo:
            v = -v
        total += v

        # Cor: estorno em verde, normal em preto
        if negativo:
            c.setFillColorRGB(0.05, 0.55, 0.20)
            valor_display = f"-{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            c.setFillColorRGB(0.1, 0.1, 0.1)
            valor_display = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        c.drawString(1.5 * cm, y, data)
        c.drawString(3.5 * cm, y, desc[:60])
        c.drawRightString(largura - 1.5 * cm, y, valor_display)

        y -= 0.55 * cm
        if y < 3 * cm:
            c.showPage()
            y = altura - 2 * cm
            c.setFont("Courier", 9)

    # Total
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.line(1.5 * cm, y, largura - 1.5 * cm, y)
    y -= 0.6 * cm
    c.setFont("Helvetica-Bold", 10)
    cor = (0.83, 0.15, 0.15) if total > 0 else (0.05, 0.55, 0.20)
    c.setFillColorRGB(*cor)
    total_display = f"{total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    c.drawString(1.5 * cm, y, "TOTAL DA FATURA")
    c.drawRightString(largura - 1.5 * cm, y, f"R$ {total_display}")

    c.save()
    print(f"Gerado: {caminho.name}  (total R$ {total_display})")


if __name__ == "__main__":
    for nome, dados in FATURAS.items():
        gerar_pdf(nome, dados)
    print("\nTodos os arquivos gerados em:", OUTPUT_DIR)
