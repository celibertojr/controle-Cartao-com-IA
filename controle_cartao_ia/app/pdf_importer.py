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


# Padrões de data/valor comuns em faturas brasileiras
_PATTERNS = [
    # 12/03 MERCADO EXEMPLO 123,45
    # 12/03/2026 MERCADO EXEMPLO R$ 1.234,56
    re.compile(
        r"(?P<date>\d{2}/\d{2}(?:/\d{2,4})?)\s+"
        r"(?P<desc>.+?)\s+"
        r"(?:R\$\s*)?(?P<value>\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s*$"
    ),
    # Variante com traço separador: 12/03 - MERCADO EXEMPLO - 123,45
    re.compile(
        r"(?P<date>\d{2}/\d{2}(?:/\d{2,4})?)\s*[-–]\s*"
        r"(?P<desc>.+?)\s*[-–]\s*"
        r"(?:R\$\s*)?(?P<value>\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s*$"
    ),
]


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
) -> tuple[list[dict], str]:
    """
    Tenta extrair gastos automaticamente de um PDF de fatura.

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

        expense = _try_parse_line(line, year, custom_categories)
        if expense:
            expenses.append(expense)

    return expenses, raw_text


def _try_parse_line(
    line: str,
    year: int,
    custom_categories: dict | None,
) -> dict | None:
    """Tenta casar a linha com os padrões conhecidos."""
    for pattern in _PATTERNS:
        match = pattern.search(line)
        if not match:
            continue

        date_raw = match.group("date")
        desc = match.group("desc").strip()
        value_raw = match.group("value").replace(".", "").replace(",", ".")

        try:
            amount = float(value_raw)
            if amount <= 0:
                continue
            date_obj = _parse_date(date_raw, year)
        except (ValueError, TypeError):
            continue

        # Ignora valores muito baixos ou muito altos (provável lixo de OCR)
        if amount < 0.01 or amount > 999_999:
            continue

        return {
            "date": date_obj.strftime("%Y-%m-%d"),
            "description": desc,
            "amount": amount,
            "category": classify_expense(desc, custom_categories),
            "raw_line": line,
        }

    return None


def _parse_date(date_raw: str, default_year: int) -> dt.date:
    """Aceita DD/MM, DD/MM/AA ou DD/MM/AAAA."""
    parts = date_raw.split("/")
    if len(parts) == 2:
        day, month = int(parts[0]), int(parts[1])
        return dt.date(default_year, month, day)
    elif len(parts) == 3:
        day, month = int(parts[0]), int(parts[1])
        y = int(parts[2])
        year = 2000 + y if y < 100 else y
        return dt.date(year, month, day)
    raise ValueError(f"Data inválida: {date_raw}")
