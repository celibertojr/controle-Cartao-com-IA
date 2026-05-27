"""
Importação de faturas em PDF.
Tenta extrair gastos automaticamente; retorna texto bruto para revisão da IA.

Formatos reconhecidos:
- Bradesco (Visa/Master): transações nacionais, internacionais (USD + cotação),
  parcelados com XX/YY embutido na descrição, múltiplos portadores.
- Nubank, Inter, Itaú e outros: padrão genérico DD/MM DESCRIÇÃO VALOR.
"""

import re
import datetime as dt

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    pdfplumber = None  # type: ignore
    PDFPLUMBER_AVAILABLE = False

from .utils import classify_expense


# ---------------------------------------------------------------------------
# Padrões genéricos
# ---------------------------------------------------------------------------

# Parcelamento no sufixo da descrição: "1/3", "(2/5)"
_INSTALLMENT_SUFFIX_RE = re.compile(r'\s*\(?\b(\d+)/(\d+)\)?\s*$')

# Estorno por palavras-chave
_ESTORNO_RE = re.compile(
    r"\bestorno\b|\bcrédito\b|\bcredito\b|\bcancelado\b|\bdevol",
    re.IGNORECASE,
)

# Linhas de pagamento/quitação — NÃO são gastos
_PAYMENT_RE = re.compile(
    r"PAGTO\.?\s+(POR\s+DEB|RECEBIDO|EFETUADO)"
    r"|PAGAMENTO\s+(RECEBIDO|EFETUADO)"
    r"|CREDITO\s+(EM\s+CONTA|FINANCEIRO)",
    re.IGNORECASE,
)

# Taxas IOF e encargos de câmbio
_IOF_RE = re.compile(
    r"\bIOF\b|\bCUSTO\s+TRANS\.?\s+EXTERIOR\b",
    re.IGNORECASE,
)

# Presença de moeda estrangeira na linha
_FOREIGN_CURRENCY_RE = re.compile(r"\b(USD|EUR|GBP|ARS|CLP|UYU)\b")

# Padrões genéricos: DD/MM [/ano] DESCRIÇÃO VALOR
_PATTERNS = [
    # Padrão principal: 12/03 MERCADO EXEMPLO 123,45
    re.compile(
        r"(?P<date>\d{2}/\d{2}(?:/\d{2,4})?)\s+"
        r"(?P<desc>.+?)\s+"
        r"(?:R\$\s*)?(?P<neg>-)?(?P<value>\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})"
        r"(?P<cr>\s+CR)?\s*$"
    ),
    # Variante com traço: 12/03 - MERCADO - 123,45
    re.compile(
        r"(?P<date>\d{2}/\d{2}(?:/\d{2,4})?)\s*[-–]\s*"
        r"(?P<desc>.+?)\s*[-–]\s*"
        r"(?:R\$\s*)?(?P<neg>-)?(?P<value>\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})"
        r"(?P<cr>\s+CR)?\s*$"
    ),
]

# ---------------------------------------------------------------------------
# Bradesco — portador adicional
# Ex: "KELLY P SANTOS Cartão 4066 XXXX XXXX 4786"
# ---------------------------------------------------------------------------
_CARDHOLDER_RE = re.compile(
    r"^([A-ZÁÉÍÓÚÃÕÂÊÎÔÛÀÇ][A-ZÁÉÍÓÚÃÕÂÊÎÔÛÀÇ\s]{2,}?)\s+"
    r"Cart[aã]o\s+\d{4}\s+XXXX\s+XXXX\s+(\d{4})\s*$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Bradesco — parcelamento embutido na descrição
# Detecta XX/YY onde 1 ≤ X ≤ Y ≤ 72 (parcelas plausíveis, não datas)
# Ex: "BMA CENTRO TREINA02/12"  →  parcela 2 de 12
#     "WISH FOZ DO IGUAC 04/05 FOZ DO IGUACU"  →  parcela 4 de 5
# ---------------------------------------------------------------------------
_BRADESCO_INST_RE = re.compile(r'(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)')


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def _clean_foreign_description(desc: str) -> tuple[str, bool]:
    """
    Remove dados de câmbio/site da descrição de transações internacionais.
    Retorna (desc_limpa, é_internacional).

    Caso 1 — símbolo de moeda explícito (USD, EUR...):
        "W *Xiaomi MiMo USD 12,32 platform.xiao 12,32 5,2700"
        → ("W *Xiaomi MiMo", True)

    Caso 2 — padrão MERCHANT valor SITE (sem símbolo de moeda):
        "CLAUDE.AI SUBSCRIPTION 110,00 ANTHROPIC.COM"
        → ("CLAUDE.AI SUBSCRIPTION", True)
    """
    m = _FOREIGN_CURRENCY_RE.search(desc)
    if m:
        cleaned = desc[:m.start()].strip()
        return (cleaned if cleaned else desc), True

    # Padrão: "MERCHANT decimal SITE_IDENTIFIER" no final da descrição
    m2 = re.search(r'\s+[\d,.]+\s+\S+\s*$', desc)
    if m2:
        cleaned = desc[:m2.start()].strip()
        if cleaned:
            return cleaned, True

    return desc, False


def _extract_bradesco_installment(desc: str) -> tuple[str, int, int]:
    """
    Detecta parcelamento estilo Bradesco embutido na descrição.
    Retorna (desc_limpa, parcela_atual, total_parcelas).
    """
    for m in _BRADESCO_INST_RE.finditer(desc):
        n, total = int(m.group(1)), int(m.group(2))
        # Parcela plausível: 1 ≤ n ≤ total ≤ 72, total > 1
        if 1 <= n <= total and 1 < total <= 72:
            clean = (desc[:m.start()].rstrip() + " " + desc[m.end():].lstrip()).strip()
            return clean, n, total
    return desc, 1, 1


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def extract_raw_text(file_path: str) -> str:
    """Extrai todo o texto do PDF, página por página."""
    if not PDFPLUMBER_AVAILABLE:
        raise RuntimeError("Instale pdfplumber: pip install pdfplumber")
    parts = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            parts.append(f"--- Página {i + 1} ---\n{text}")
    return "\n\n".join(parts)


def parse_pdf_invoice(
    file_path: str,
    custom_categories: dict | None = None,
    reference_year: int | None = None,
    reference_month: int | None = None,
) -> tuple[list[dict], str]:
    """
    Extrai gastos de um PDF de fatura de cartão de crédito.

    reference_month (1-12): mês de fechamento da fatura. Datas sem ano explícito
    cujo mês é posterior ao de referência são atribuídas ao ano anterior
    (ex: 28/12 numa fatura de janeiro → dezembro do ano passado).

    Retorna:
        (expenses, raw_text)

    Cada expense é um dict com:
        date, description, amount, category,
        installment_number, installments,
        is_foreign, cardholder, raw_line
    """
    if not PDFPLUMBER_AVAILABLE:
        raise RuntimeError("Instale pdfplumber: pip install pdfplumber")

    raw_text = extract_raw_text(file_path)
    year = reference_year or dt.date.today().year
    expenses: list[dict] = []
    current_cardholder: str | None = None

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Detecta troca de portador (cartão adicional Bradesco e similares)
        ch_match = _CARDHOLDER_RE.match(line)
        if ch_match:
            current_cardholder = ch_match.group(1).strip().title()
            continue

        expense = _try_parse_line(
            line, year, custom_categories, reference_month, current_cardholder
        )
        if expense:
            expenses.append(expense)

    return expenses, raw_text


# ---------------------------------------------------------------------------
# Parsing de linha individual
# ---------------------------------------------------------------------------

def _try_parse_line(
    line: str,
    year: int,
    custom_categories: dict | None,
    ref_month: int | None,
    cardholder: str | None,
) -> dict | None:
    """Tenta casar a linha com os padrões conhecidos. Retorna None se não for gasto."""

    # Pagamento/crédito: ignora
    if _PAYMENT_RE.search(line):
        return None

    for pattern in _PATTERNS:
        match = pattern.search(line)
        if not match:
            continue

        date_raw = match.group("date")
        desc = match.group("desc").strip()
        value_raw = match.group("value").replace(".", "").replace(",", ".")
        is_negative = bool(match.group("neg")) or bool((match.group("cr") or "").strip())

        try:
            amount = float(value_raw)
            if is_negative or _ESTORNO_RE.search(desc):
                amount = -amount
            if amount == 0:
                continue
            date_obj = _parse_date(date_raw, year, ref_month)
        except (ValueError, TypeError):
            continue

        # Ignora valores absurdos (lixo de OCR)
        if abs(amount) > 999_999:
            continue

        # IOF e encargos de câmbio → Tarifas
        if _IOF_RE.search(desc) or _IOF_RE.search(line):
            return _build_expense(
                date_obj, desc, amount, "Tarifas",
                1, 1, False, cardholder, line
            )

        # Limpeza de transações internacionais (remove USD/EUR/site/cotação da descrição)
        desc, is_foreign = _clean_foreign_description(desc)

        # Parcelamento: primeiro tenta sufixo genérico, depois formato Bradesco
        inst_match = _INSTALLMENT_SUFFIX_RE.search(desc)
        if inst_match:
            inst_num = int(inst_match.group(1))
            inst_total = int(inst_match.group(2))
            desc = desc[:inst_match.start()].strip()
        else:
            desc, inst_num, inst_total = _extract_bradesco_installment(desc)

        # Estornos: categoria fixa, sem parcelamento
        if amount < 0:
            category = "Estorno"
            inst_num, inst_total = 1, 1
        else:
            category = classify_expense(desc, custom_categories)

        return _build_expense(
            date_obj, desc, amount, category,
            inst_num, inst_total, is_foreign, cardholder, line
        )

    return None


def _build_expense(
    date_obj: dt.date,
    description: str,
    amount: float,
    category: str,
    inst_num: int,
    inst_total: int,
    is_foreign: bool,
    cardholder: str | None,
    raw_line: str,
) -> dict:
    return {
        "date": date_obj.strftime("%Y-%m-%d"),
        "description": description,
        "amount": amount,
        "category": category,
        "raw_line": raw_line,
        "installment_number": inst_num,
        "installments": inst_total,
        "is_foreign": is_foreign,
        "cardholder": cardholder,
    }


def _parse_date(date_raw: str, default_year: int, ref_month: int | None = None) -> dt.date:
    """
    Aceita DD/MM, DD/MM/AA ou DD/MM/AAAA.
    Com ref_month: datas sem ano cujo mês é posterior ao de referência
    são atribuídas ao ano anterior (útil para faturas que fecham no início do mês).
    """
    parts = date_raw.split("/")
    if len(parts) == 2:
        day, month = int(parts[0]), int(parts[1])
        year = default_year
        if ref_month is not None and month > ref_month:
            year -= 1
        return dt.date(year, month, day)
    elif len(parts) == 3:
        day, month = int(parts[0]), int(parts[1])
        y = int(parts[2])
        year = 2000 + y if y < 100 else y
        return dt.date(year, month, day)
    raise ValueError(f"Data inválida: {date_raw}")
