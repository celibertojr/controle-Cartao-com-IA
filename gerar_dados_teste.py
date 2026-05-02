"""
Script de geração de dados de teste — 6 meses de movimentação realista.

Cenários cobertos:
  - Compra parcelada em 6x (Samsung TV 65")  → parcelas em dez/25 a mai/26
  - Compra parcelada em 3x (iPhone 15 Pro)   → parcelas em jan/26 a mar/26
  - Fatura de fevereiro/26 acima de R$ 10.000
  - Extorno de compra em março/26
  - Dois cartões com dias de fechamento distintos (Nubank=25, Itaú=10)

Execute APENAS em ambiente de teste. Apaga todos os dados existentes antes de inserir.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "controle_cartao_ia"))

from app.database import Database
from app.utils import DB_PATH

CONFIG = {
    "default_closing_day": 25,
    "card_closing_days": {"Nubank": 25, "Itaú": 10},
}

# --------------------------------------------------------------------------
# Dados organizados por (data, descrição, valor, categoria, cartão, inst, inst_num)
# --------------------------------------------------------------------------

DESPESAS = [

    # ══════════════════════════════════════════════════════════════
    # FATURA DEZEMBRO 2025  (Nubank: 26/nov–25/dez | Itaú: 11/nov–10/dez)
    # ══════════════════════════════════════════════════════════════

    # --- parcelado 6x: Samsung TV 65" QLED ---
    ("2025-12-05", "Samsung TV 65\" QLED (1/6)",  1100.00, "Eletrônicos",   "Nubank", 6, 1),
    # cotidiano Nubank dez
    ("2025-12-01", "Netflix",                        55.90, "Streaming",     "Nubank", 1, 1),
    ("2025-12-08", "Uber",                           87.50, "Transporte",    "Nubank", 1, 1),
    ("2025-12-10", "Supermercado Pão de Açúcar",    650.00, "Alimentação",   "Nubank", 1, 1),
    ("2025-12-15", "Restaurante Madero",             230.00, "Alimentação",   "Nubank", 1, 1),
    ("2025-12-20", "Presente de Natal",              480.00, "Outros",        "Nubank", 1, 1),
    # cotidiano Itaú dez
    ("2025-11-15", "Academia Smart Fit",             120.00, "Saúde",         "Itaú",   1, 1),
    ("2025-12-01", "Farmácia Ultrafarma",            340.00, "Saúde",         "Itaú",   1, 1),
    ("2025-12-05", "Combustível Shell",              280.00, "Transporte",    "Itaú",   1, 1),

    # ══════════════════════════════════════════════════════════════
    # FATURA JANEIRO 2026  (Nubank: 26/dez–25/jan | Itaú: 11/dez–10/jan)
    # ══════════════════════════════════════════════════════════════

    # TV parcelado 2/6
    ("2026-01-05", "Samsung TV 65\" QLED (2/6)",   1100.00, "Eletrônicos",   "Nubank", 6, 2),
    # parcelado 3x: iPhone 15 Pro
    ("2026-01-10", "iPhone 15 Pro 512GB (1/3)",    1800.00, "Eletrônicos",   "Nubank", 3, 1),
    # cotidiano Nubank jan
    ("2026-01-02", "Spotify",                        21.90, "Streaming",     "Nubank", 1, 1),
    ("2026-01-15", "Supermercado Carrefour",         720.00, "Alimentação",   "Nubank", 1, 1),
    ("2026-01-20", "Aluguel de Carro Localiza",      380.00, "Transporte",    "Nubank", 1, 1),
    ("2026-01-22", "Farmácia Drogasil",              145.00, "Saúde",         "Nubank", 1, 1),
    # cotidiano Itaú jan
    ("2025-12-28", "Restaurante Outback",            175.00, "Alimentação",   "Itaú",   1, 1),
    ("2026-01-05", "Farmácia Ultrafarma",            190.00, "Saúde",         "Itaú",   1, 1),
    ("2026-01-08", "Combustível Ipiranga",           310.00, "Transporte",    "Itaú",   1, 1),

    # ══════════════════════════════════════════════════════════════
    # FATURA FEVEREIRO 2026  — ACIMA DE R$ 10.000
    # (Nubank: 26/jan–25/fev | Itaú: 11/jan–10/fev)
    # ══════════════════════════════════════════════════════════════

    # TV parcelado 3/6
    ("2026-02-05", "Samsung TV 65\" QLED (3/6)",   1100.00, "Eletrônicos",   "Nubank", 6, 3),
    # iPhone parcelado 2/3
    ("2026-02-10", "iPhone 15 Pro 512GB (2/3)",    1800.00, "Eletrônicos",   "Nubank", 3, 2),
    # Viagem — faz o mês estourar R$ 10.000
    ("2026-02-01", "Passagens Aéreas LATAM",       4500.00, "Viagem",        "Nubank", 1, 1),
    ("2026-02-03", "Hotel Grand Hyatt 3 diárias",  2800.00, "Viagem",        "Nubank", 1, 1),
    ("2026-02-15", "Supermercado Extra",           1200.00, "Alimentação",   "Nubank", 1, 1),
    ("2026-02-20", "Restaurante Fogo de Chão",      450.00, "Alimentação",   "Nubank", 1, 1),
    # subtotal Nubank fev = 1100+1800+4500+2800+1200+450 = 11.850 ✓
    # cotidiano Itaú fev
    ("2026-01-15", "Academia Smart Fit",             120.00, "Saúde",         "Itaú",   1, 1),
    ("2026-01-20", "Farmácia Ultrafarma",            250.00, "Saúde",         "Itaú",   1, 1),
    ("2026-02-08", "Combustível Shell",              295.00, "Transporte",    "Itaú",   1, 1),

    # ══════════════════════════════════════════════════════════════
    # FATURA MARÇO 2026  — COM EXTORNO
    # (Nubank: 26/fev–25/mar | Itaú: 11/fev–10/mar)
    # ══════════════════════════════════════════════════════════════

    # TV parcelado 4/6
    ("2026-03-05", "Samsung TV 65\" QLED (4/6)",   1100.00, "Eletrônicos",   "Nubank", 6, 4),
    # iPhone parcelado 3/3
    ("2026-03-10", "iPhone 15 Pro 512GB (3/3)",    1800.00, "Eletrônicos",   "Nubank", 3, 3),
    # Compra + extorno
    ("2026-03-05", "AirPods Pro 2ª geração",       1900.00, "Eletrônicos",   "Nubank", 1, 1),
    ("2026-03-12", "EXTORNO - AirPods Pro 2ª ger",-1900.00, "Extorno",       "Nubank", 1, 1),
    # cotidiano Nubank mar
    ("2026-03-18", "Supermercado Pão de Açúcar",    880.00, "Alimentação",   "Nubank", 1, 1),
    ("2026-03-22", "Restaurante Coco Bambu",         340.00, "Alimentação",   "Nubank", 1, 1),
    ("2026-03-01", "Netflix",                         55.90, "Streaming",     "Nubank", 1, 1),
    # cotidiano Itaú mar
    ("2026-02-15", "Academia Smart Fit",             120.00, "Saúde",         "Itaú",   1, 1),
    ("2026-03-08", "Combustível Ipiranga",           310.00, "Transporte",    "Itaú",   1, 1),
    ("2026-03-05", "Farmácia Drogasil",              180.00, "Saúde",         "Itaú",   1, 1),

    # ══════════════════════════════════════════════════════════════
    # FATURA ABRIL 2026
    # (Nubank: 26/mar–25/abr | Itaú: 11/mar–10/abr)
    # ══════════════════════════════════════════════════════════════

    # TV parcelado 5/6
    ("2026-04-05", "Samsung TV 65\" QLED (5/6)",   1100.00, "Eletrônicos",   "Nubank", 6, 5),
    # cotidiano Nubank abr
    ("2026-04-01", "Spotify",                        21.90, "Streaming",     "Nubank", 1, 1),
    ("2026-04-10", "Supermercado Carrefour",         950.00, "Alimentação",   "Nubank", 1, 1),
    ("2026-04-15", "Farmácia Ultrafarma",            230.00, "Saúde",         "Nubank", 1, 1),
    ("2026-04-20", "Cinemark",                        85.00, "Lazer",         "Nubank", 1, 1),
    ("2026-04-22", "Restaurante Outback",             420.00, "Alimentação",   "Nubank", 1, 1),
    ("2026-04-24", "iFood",                          145.00, "Alimentação",   "Nubank", 1, 1),
    # cotidiano Itaú abr
    ("2026-03-15", "Academia Smart Fit",             120.00, "Saúde",         "Itaú",   1, 1),
    ("2026-04-08", "Combustível Shell",              265.00, "Transporte",    "Itaú",   1, 1),
    ("2026-04-02", "Supermercado Extra",             430.00, "Alimentação",   "Itaú",   1, 1),

    # ══════════════════════════════════════════════════════════════
    # FATURA MAIO 2026
    # (Nubank: 26/abr–25/mai | Itaú: 11/abr–10/mai)
    # ══════════════════════════════════════════════════════════════

    # TV parcelado 6/6 — última parcela!
    ("2026-05-05", "Samsung TV 65\" QLED (6/6)",   1100.00, "Eletrônicos",   "Nubank", 6, 6),
    # cotidiano Nubank mai
    ("2026-05-01", "Netflix",                         55.90, "Streaming",     "Nubank", 1, 1),
    ("2026-05-10", "Supermercado Pão de Açúcar",   1100.00, "Alimentação",   "Nubank", 1, 1),
    ("2026-05-15", "Combustível Ipiranga",           320.00, "Transporte",    "Nubank", 1, 1),
    ("2026-05-20", "Restaurante japonês Ky",         290.00, "Alimentação",   "Nubank", 1, 1),
    ("2026-05-22", "Farmácia Drogasil",              175.00, "Saúde",         "Nubank", 1, 1),
    # cotidiano Itaú mai
    ("2026-04-15", "Academia Smart Fit",             120.00, "Saúde",         "Itaú",   1, 1),
    ("2026-05-08", "Combustível Shell",              285.00, "Transporte",    "Itaú",   1, 1),
    ("2026-05-03", "Supermercado Carrefour",         560.00, "Alimentação",   "Itaú",   1, 1),
    ("2026-04-28", "Farmácia Ultrafarma",            210.00, "Saúde",         "Itaú",   1, 1),
]


def main():
    db = Database(path=DB_PATH, config=CONFIG)

    print("⚠  Apagando todos os dados existentes…")
    db.clear_expenses()
    db.clear_goals()

    print(f"Inserindo {len(DESPESAS)} lançamentos…\n")
    for date, desc, amount, cat, card, inst, inst_num in DESPESAS:
        db.add_expense_raw(
            date=date,
            description=desc,
            amount=amount,
            category=cat,
            card=card,
            installments=inst,
            installment_number=inst_num,
        )

    db.close()

    # Resumo por fatura
    db2 = Database(path=DB_PATH, config=CONFIG)
    print("═" * 52)
    print(f"{'Fatura':<12} {'Total':>12}  Destaques")
    print("═" * 52)
    for row in db2.get_all_month_totals():
        month = row["month"]
        total = row["total"]
        flag = ""
        if total > 10_000:
            flag = "  ⚠ ACIMA DE R$ 10.000"
        print(f"{month:<12} R$ {total:>9,.2f}{flag}")
    print("═" * 52)

    # Confere extorno
    extornos = [r for r in db2.list_expenses("2026-03") if float(r["amount"]) < 0]
    print(f"\nExtornos em mar/26: {len(extornos)}")
    for e in extornos:
        print(f"  {e['date']}  {e['description']}  R$ {e['amount']:.2f}")

    # Confere parcelados
    all_tv = db2.conn.execute(
        "SELECT * FROM expenses WHERE description LIKE '%Samsung TV%' ORDER BY date"
    ).fetchall()
    print(f"\nParcelas Samsung TV 65\": {len(all_tv)}/6")

    all_iphone = db2.conn.execute(
        "SELECT * FROM expenses WHERE description LIKE '%iPhone%' ORDER BY date"
    ).fetchall()
    print(f"Parcelas iPhone 15 Pro: {len(all_iphone)}/3")

    db2.close()
    print("\nDados de teste gerados com sucesso!")


if __name__ == "__main__":
    main()
