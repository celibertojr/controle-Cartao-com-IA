"""
Importação de faturas em PDF.
Tenta extrair gastos automaticamente; retorna texto bruto para revisão da IA.
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


# Detecta parcelamento no final da descrição: "1/3", "(2/5)", etc.
_INSTALLMENT_RE = re.compile(r'\s*\(?\b(\d+)/(\d+)\)?\s*$')

# Padrões de data/valor comuns em faturas brasileiras
# Captura opcionalmente sinal negativo antes do valor e sufixo CR (crédito/estorno)
_PATTERNS = [
    # 12/03 MERCADO EXEMPLO 123,45  ou  12/03 ESTORNO COMPRA -123,45  ou  123,45 CR
    re.compile(
        r"(?P<date>\d{2}/\d{2}(?:/\d{2,4})?)\s+"
        r"(?P<desc>.+?)\s+"
        r"(?:R\$\s*)?(?P<neg>-)?(?P<value>\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})(?P<cr>\s+CR)?\s*$"
    ),
    # Variante com traço separador: 12/03 - MERCADO EXEMPLO - 123,45
    re.compile(
        r"(?P<date>\d{2}/\d{2}(?:/\d{2,4})?)\s*[-–]\s*"
        r"(?P<desc>.+?)\s*[-–]\s*"
        r"(?:R\$\s*)?(?P<neg>-)?(?P<value>\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})(?P<cr>\s+CR)?\s*$"
    ),
]

# Palavras na descrição que indicam estorno mesmo sem valor negativo
_ESTORNO_RE = re.compile(r"\bestorno\b|\bcrédito\b|\bcredito\b|\bcancelado\b|\bdevol", re.IGNORECASE)


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
    Tenta extrair gastos automaticamente de um PDF de fatura.

    reference_month (1-12): mês de fechamento da fatura. Quando informado,
    datas sem ano explícito cujo mês é posterior ao mês de referência são
    atribuídas ao ano anterior (ex: 28/12 em fatura de janeiro → dezembro do
    ano passado).

    Retorna:
        (expenses, raw_text)
        - expenses: lista de dicts com date, description, amount, category
        - raw_text: texto bruto do PDF para revisão ou envio à IA
    """
    if not PDFPLUMBER_AVAILABLE:
        raise RuntimeError("Instale pdfplumber: pip install pdfplumber")

    raw_text = extract_raw_text(file_path)
    year = reference_year or dt.date.today().year
    expenses = []

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue

        expense = _try_parse_line(line, year, custom_categories, reference_month)
        if expense:
            expenses.append(expense)

    return expenses, raw_text


def _try_parse_line(
    line: str,
    year: int,
    custom_categories: dict | None,
    ref_month: int | None = None,
) -> dict | None:
    """Tenta casar a linha com os padrões conhecidos."""
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

        # Ignora valores absurdos (provável lixo de OCR)
        if abs(amount) > 999_999:
            continue

        # Extrai parcelamento do final da descrição: "1/3", "(2/5)", etc.
        inst_match = _INSTALLMENT_RE.search(desc)
        if inst_match:
            inst_num = int(inst_match.group(1))
            inst_total = int(inst_match.group(2))
            desc = desc[:inst_match.start()].strip()
        else:
            inst_num = 1
            inst_total = 1

        # Estornos: categoria fixa, sem parcelamento
        if amount < 0:
            category = "Estorno"
            inst_num = 1
            inst_total = 1
        else:
            category = classify_expense(desc, custom_categories)

        return {
            "date": date_obj.strftime("%Y-%m-%d"),
            "description": desc,
            "amount": amount,
            "category": category,
            "raw_line": line,
            "installment_number": inst_num,
            "installments": inst_total,
        }

    return None


def _parse_date(date_raw: str, default_year: int, ref_month: int | None = None) -> dt.date:
    """
    Aceita DD/MM, DD/MM/AA ou DD/MM/AAAA.
    Quando ref_month é fornecido e a data não tem ano explícito, datas cujo
    mês é posterior ao mês de referência da fatura são atribuídas ao ano
    anterior (ex: 28/12 numa fatura de janeiro usa default_year - 1).
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
