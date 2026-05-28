"""
Importação de faturas em PDF.

Formatos reconhecidos:
  • Bradesco App: PDF gerado pelo app/site Bradesco.
      Datas separadas em linhas: número do dia → expenses → abreviatura do mês.
      Parcelamentos no formato "( 01/02 )".
  • Bradesco Papel / Genérico: fatura física escaneada ou Nubank/Itaú.
      Formato clássico: DD/MM DESCRIÇÃO VALOR por linha.
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


# ===========================================================================
# Extração de texto bruto
# ===========================================================================

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


# ===========================================================================
# Detecção de formato
# ===========================================================================

def _is_bradesco_app_format(raw_text: str) -> bool:
    """Detecta PDF do app/site Bradesco (datas em linhas separadas)."""
    sample = raw_text[:1200]
    return bool(
        re.search(r"Fatura Data \d{2}/\d{2}/\d{4}", sample, re.IGNORECASE)
        or re.search(r"Data de vencimento:", sample, re.IGNORECASE)
        or re.search(r"Data Lan.amentos\s+Moeda de Origem", sample, re.IGNORECASE)
    )


# ===========================================================================
# Metadados da fatura (total, vencimento, banco…)
# ===========================================================================

# Padrões para metadados — cobrem papel e app
_META_TOTAL_RE   = re.compile(r"Total\s+da\s+fatura[:\s]+R\$\s*([\d.]+,\d{2})", re.IGNORECASE)
_META_VENC_RE    = re.compile(r"(?:Data de vencimento|Vencimento)[:\s]+(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
_META_FECHA_RE   = re.compile(r"fechamento\s+(?:da\s+pr[oó]xima\s+fatura)?[:\s]+(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
_META_MINIMO_RE  = re.compile(r"Pagamento\s+m[ií]nimo[:\s]+R?\$?\s*([\d.]+,\d{2})", re.IGNORECASE)
_META_LIMITE_RE  = re.compile(r"Limite\s+de\s+compras[:\s]+R\$\s*([\d.]+,\d{2})", re.IGNORECASE)
_META_FATURA_ANT = re.compile(r"(?:Valor da fatura anterior|Saldo anterior)[:\s]+R?\$?\s*([\d.]+,\d{2})", re.IGNORECASE)

_BANKS = {
    "bradesco": "Bradesco", "nubank": "Nubank",
    "itau": "Itaú",   "itaú": "Itaú",
    "santander": "Santander", "inter": "Banco Inter",
    "c6": "C6 Bank",  "xp ": "XP",
    "caixa": "Caixa", "banco do brasil": "Banco do Brasil",
    "next": "Next",   "neon": "Neon", "pan": "Banco Pan",
}


def extract_invoice_metadata(file_path: str) -> dict:
    """
    Extrai metadados da fatura: total, vencimento, fechamento, banco.
    Retorna dict: total, due_date, closing_date, min_payment, limit,
                  previous_total, bank.
    Valores ausentes são None.
    """
    raw = extract_raw_text(file_path)
    fname = str(file_path).lower()
    head  = raw[:1500].lower()

    def first_money(pat):
        m = pat.search(raw)
        if m:
            return float(m.group(1).replace(".", "").replace(",", "."))
        return None

    def first_date(pat):
        m = pat.search(raw)
        return m.group(1) if m else None

    bank = None
    for key, name in _BANKS.items():
        if key in head[:600] or key in fname:
            bank = name
            break

    return {
        "bank":           bank,
        "total":          first_money(_META_TOTAL_RE),
        "due_date":       first_date(_META_VENC_RE),
        "closing_date":   first_date(_META_FECHA_RE),
        "min_payment":    first_money(_META_MINIMO_RE),
        "limit":          first_money(_META_LIMITE_RE),
        "previous_total": first_money(_META_FATURA_ANT),
    }


# ===========================================================================
# API pública — parse
# ===========================================================================

def parse_pdf_invoice(
    file_path: str,
    custom_categories: dict | None = None,
    reference_year: int | None = None,
    reference_month: int | None = None,
) -> tuple[list[dict], str]:
    """
    Extrai gastos de um PDF de fatura.

    reference_year  (int)  : ano base para datas sem ano explícito.
    reference_month (1-12) : mês de fechamento. Datas cujo mês é posterior
                             ao de referência recebem o ano anterior.

    Retorna (expenses, raw_text).
    Cada expense: date, description, amount, category,
                  installment_number, installments, is_foreign, cardholder, raw_line.
    """
    if not PDFPLUMBER_AVAILABLE:
        raise RuntimeError("Instale pdfplumber: pip install pdfplumber")

    raw_text = extract_raw_text(file_path)
    year = reference_year or dt.date.today().year

    if _is_bradesco_app_format(raw_text):
        expenses = _parse_bradesco_app(raw_text, year, custom_categories)
    else:
        expenses = _parse_generic(raw_text, year, custom_categories, reference_month)

    return expenses, raw_text


# ===========================================================================
# Parser 1 — Bradesco App (stateful: dia → expenses → mês)
# ===========================================================================

_MONTHS_PT = {
    "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4,
    "MAI": 5, "JUN": 6, "JUL": 7, "AGO": 8,
    "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12,
}

_APP_MONTH_RE = re.compile(
    r"^(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)$", re.IGNORECASE
)
_APP_DAY_RE = re.compile(r"^\d{1,2}$")

# Parcelamento no formato app: "( 01/02 )"
_APP_INST_RE = re.compile(r"\(\s*(\d+)/(\d+)\s*\)")

# Transação internacional no formato app:
# "DESC USD valor_brl valor_usd cotacao valor_r$"
# O valor R$ (final) é o que nos interessa.
_APP_INTL_RE = re.compile(
    r"^(?P<desc>.+?)\s+USD\s+[\d,]+\s+[\d.]+\s+[\d.]+\s+(?P<value>[\d.]+,\d{2})\s*$"
)

# Linhas a ignorar completamente no formato app
_APP_SKIP_RE = re.compile(
    r"SALDO ANTERIOR"
    r"|TOTAL DA FATURA.*FINAL"
    r"|TOTAL DOS LAN"
    r"|EXTRATO EM ABERTO"
    r"|SUJEITO A ALTERA"
    r"|RESUMO DAS DESPESAS"
    r"|PAGAMENTOS.CR.DITOS"
    r"|DESPESAS LOCAIS"
    r"|DESPESAS NO EXTERIOR"
    r"|PAGAMENTO M.NIMO"
    r"|DATA LAN.AMENTOS"
    r"|TAXAS MENSAIS"
    r"|GASTOS REFERENTES AO CART"
    r"|VALOR DA FATURA ANTERIOR"
    r"|PARCELAMENTO DE FATURA"
    r"|COMPRAS PARCELADAS"
    r"|MELHOR DATA DE COMPRA"
    r"|FORMA DE PAGAMENTO"
    r"|VALIDADE"
    r"|CARTAO SELECIONADO"
    r"|FATURA DATA"
    r"|DATA DE VENCIMENTO"
    r"|A FALTA DE PAGAMENTO"
    r"|IOF.*JUROS DE MORA"
    r"|DO CR.DITO ROTATIVO"
    r"|\*+\s+\*+\s+\*+\s+\d{4}"   # "**** **** **** 9913"
    r"|LUIZ.*FORMA DE PAGAMENTO"
    r"|PAGAMENTO DE CONTAS"
    r"|SAQUE.*VISTA"
    r"|CREDI.RIO"
    r"|ROTATIVO"
    r"|\(=\)"                       # linha "(=)Total da fatura: ..." no resumo
    r"|PAGTO\.?\s+(POR\s+DEB|RECEBIDO|EFETUADO)"  # pagamento/débito em conta
    r"|PAGAMENTO\s+(RECEBIDO|EFETUADO)"
    r"|CREDITO\s+(EM\s+CONTA|FINANCEIRO)",
    re.IGNORECASE,
)

_IOF_RE = re.compile(r"\bIOF\b|\bCUSTO\s+TRANS\.?\s+EXTERIOR\b", re.IGNORECASE)
_ESTORNO_RE = re.compile(
    r"\bestorno\b|\bcrédito\b|\bcredito\b|\bcancelado\b|\bdevol", re.IGNORECASE
)


def _parse_bradesco_app(
    raw_text: str,
    year: int,
    custom_categories: dict | None,
) -> list[dict]:
    """
    Parser stateful para o formato Bradesco App.
    Cada grupo de transações tem: DAY(standalone) → expenses → MONTH(standalone).
    O mês pode aparecer no meio ou no final do grupo; aplica-se a TODAS as
    expenses do grupo (não só às anteriores a ele).
    """
    expenses: list[dict] = []
    current_day: int | None = None
    current_month: int | None = None
    pending: list[dict] = []   # expenses aguardando atribuição de mês
    in_programados = False     # seção "Lançamentos programados" → ignorar

    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("---"):
            continue

        # Detecta início da seção de "lançamentos programados" (parcelas futuras)
        if re.search(r"LAN.AMENTOS PROGRAMADOS", line, re.IGNORECASE):
            in_programados = True
            continue
        if in_programados:
            # Volta à seção principal no "Resumo das Despesas"
            if re.search(r"RESUMO DAS DESPESAS", line, re.IGNORECASE):
                in_programados = False
            continue

        if _APP_SKIP_RE.search(line):
            continue

        # ── Número de dia (ex: "25") ───────────────────────────────────────
        if _APP_DAY_RE.match(line):
            # Descarrega pending do dia anterior (se tiver mês)
            if current_month is not None and pending:
                for exp in pending:
                    d = exp.pop("_day", current_day)
                    date = _make_date(year, current_month, d)
                    if date:
                        exp["date"] = date
                        expenses.append(exp)
            pending = []
            current_day = int(line)
            current_month = None   # mês reset para novo dia
            continue

        # ── Abreviatura de mês (ex: "MAI") ───────────────────────────────
        m_month = _APP_MONTH_RE.match(line)
        if m_month:
            current_month = _MONTHS_PT[m_month.group(1).upper()]
            # Atribui este mês às expenses pendentes (que vieram antes do mês)
            if pending:
                for exp in pending:
                    d = exp.pop("_day", current_day)
                    date = _make_date(year, current_month, d)
                    if date:
                        exp["date"] = date
                        expenses.append(exp)
                pending = []
            continue

        # ── Linha de gasto ────────────────────────────────────────────────
        if current_day is None:
            continue

        exp = _parse_app_line(line, custom_categories)
        if exp is None:
            continue

        if current_month is not None:
            # Mês já conhecido: define data agora
            date = _make_date(year, current_month, current_day)
            if date:
                exp["date"] = date
                expenses.append(exp)
        else:
            # Mês ainda não visto: guarda em pending
            exp["_day"] = current_day
            pending.append(exp)

    # Descarrega pendentes do último grupo (sem novo dia após)
    if current_month is not None and pending:
        for exp in pending:
            d = exp.pop("_day", current_day)
            date = _make_date(year, current_month, d)
            if date:
                exp["date"] = date
                expenses.append(exp)

    return expenses


def _make_date(year: int, month: int, day: int) -> str | None:
    """Cria AAAA-MM-DD; tenta ano anterior se inválido (ex: fev com 31)."""
    for y in (year, year - 1):
        try:
            return dt.date(y, month, day).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_app_line(line: str, custom_categories: dict | None) -> dict | None:
    """Tenta parsear uma linha de gasto no formato Bradesco App."""
    line = line.strip()
    if not line:
        return None
    if _APP_SKIP_RE.search(line):
        return None

    # Internacional: DESC USD val_brl val_usd cotacao val_r$
    intl = _APP_INTL_RE.match(line)
    if intl:
        desc = intl.group("desc").strip()
        value = _parse_brl(intl.group("value"))
        if value is None or value == 0:
            return None
        desc, inst_num, inst_total = _extract_app_installment(desc)
        return _build(desc, value, True, inst_num, inst_total, custom_categories, line)

    # Genérico: DESC [-]VALOR_R$  (aceita negativo para estornos)
    gen = re.search(
        r"^(?P<desc>.+?)\s+(?P<neg>-)?(?P<val>\d{1,3}(?:\.\d{3})*,\d{2})\s*$",
        line,
    )
    if not gen:
        return None

    desc = gen.group("desc").strip()
    value = _parse_brl(gen.group("val"))
    if value is None or value == 0:
        return None
    if gen.group("neg") or _ESTORNO_RE.search(desc):
        value = -abs(value)

    if abs(value) > 999_999:
        return None

    # IOF
    if _IOF_RE.search(desc) or _IOF_RE.search(line):
        return _build(desc, value, False, 1, 1, custom_categories, line, force_cat="Tarifas")

    desc, inst_num, inst_total = _extract_app_installment(desc)

    if value < 0:
        return _build(desc, value, False, 1, 1, custom_categories, line, force_cat="Estorno")

    return _build(desc, value, False, inst_num, inst_total, custom_categories, line)


def _extract_app_installment(desc: str) -> tuple[str, int, int]:
    """Remove '( XX/YY )' da descrição e retorna (desc_limpa, n, total)."""
    m = _APP_INST_RE.search(desc)
    if m:
        n, total = int(m.group(1)), int(m.group(2))
        if 1 <= n <= total <= 72:
            desc = _APP_INST_RE.sub("", desc).strip()
            return desc, n, total
    return desc, 1, 1


def _parse_brl(s: str) -> float | None:
    try:
        return float(s.replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _build(
    desc: str,
    amount: float,
    is_foreign: bool,
    inst_num: int,
    inst_total: int,
    custom_categories: dict | None,
    raw_line: str,
    force_cat: str | None = None,
) -> dict:
    if force_cat:
        category = force_cat
    elif amount < 0:
        category = "Estorno"
    else:
        category = classify_expense(desc, custom_categories)
    return {
        "description":        desc,
        "amount":             amount,
        "category":           category,
        "raw_line":           raw_line,
        "installment_number": inst_num,
        "installments":       inst_total,
        "is_foreign":         is_foreign,
        "cardholder":         None,
    }


# ===========================================================================
# Parser 2 — Genérico / Bradesco Papel (regex por linha)
# ===========================================================================

_INSTALLMENT_SUFFIX_RE = re.compile(r"\s*\(?\b(\d+)/(\d+)\)?\s*$")
_PAYMENT_RE = re.compile(
    r"PAGTO\.?\s+(POR\s+DEB|RECEBIDO|EFETUADO)"
    r"|PAGAMENTO\s+(RECEBIDO|EFETUADO)"
    r"|CREDITO\s+(EM\s+CONTA|FINANCEIRO)",
    re.IGNORECASE,
)
_FOREIGN_CURRENCY_RE = re.compile(r"\b(USD|EUR|GBP|ARS|CLP|UYU)\b")
_BRADESCO_INST_RE = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)")
_CARDHOLDER_RE = re.compile(
    r"^([A-ZÁÉÍÓÚÃÕÂÊÎÔÛÀÇ][A-ZÁÉÍÓÚÃÕÂÊÎÔÛÀÇ\s]{2,}?)\s+"
    r"Cart[aã]o\s+\d{4}\s+XXXX\s+XXXX\s+(\d{4})\s*$",
    re.IGNORECASE,
)

_GENERIC_PATTERNS = [
    re.compile(
        r"(?P<date>\d{2}/\d{2}(?:/\d{2,4})?)\s+"
        r"(?P<desc>.+?)\s+"
        r"(?:R\$\s*)?(?P<neg>-)?(?P<value>\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})"
        r"(?P<cr>\s+CR)?\s*$"
    ),
    re.compile(
        r"(?P<date>\d{2}/\d{2}(?:/\d{2,4})?)\s*[-–]\s*"
        r"(?P<desc>.+?)\s*[-–]\s*"
        r"(?:R\$\s*)?(?P<neg>-)?(?P<value>\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})"
        r"(?P<cr>\s+CR)?\s*$"
    ),
]


def _parse_generic(
    raw_text: str,
    year: int,
    custom_categories: dict | None,
    ref_month: int | None,
) -> list[dict]:
    expenses: list[dict] = []
    current_cardholder: str | None = None

    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue

        ch = _CARDHOLDER_RE.match(line)
        if ch:
            current_cardholder = ch.group(1).strip().title()
            continue

        exp = _parse_generic_line(line, year, custom_categories, ref_month, current_cardholder)
        if exp:
            expenses.append(exp)

    return expenses


def _parse_generic_line(
    line: str, year: int, custom_categories: dict | None,
    ref_month: int | None, cardholder: str | None,
) -> dict | None:
    if _PAYMENT_RE.search(line):
        return None

    for pattern in _GENERIC_PATTERNS:
        match = pattern.search(line)
        if not match:
            continue

        date_raw  = match.group("date")
        desc      = match.group("desc").strip()
        value_raw = match.group("value").replace(".", "").replace(",", ".")
        is_neg    = bool(match.group("neg")) or bool((match.group("cr") or "").strip())

        try:
            amount = float(value_raw)
            if is_neg or _ESTORNO_RE.search(desc):
                amount = -amount
            if amount == 0:
                continue
            date_obj = _parse_date(date_raw, year, ref_month)
        except (ValueError, TypeError):
            continue

        if abs(amount) > 999_999:
            continue

        # IOF
        if _IOF_RE.search(desc) or _IOF_RE.search(line):
            return _build(desc, amount, False, 1, 1, custom_categories, line, force_cat="Tarifas")

        # Internacional
        desc, is_foreign = _clean_foreign_desc(desc)

        # Parcelamento: sufixo genérico
        inst = _INSTALLMENT_SUFFIX_RE.search(desc)
        if inst:
            n, t = int(inst.group(1)), int(inst.group(2))
            desc = desc[:inst.start()].strip()
        else:
            desc, n, t = _extract_bradesco_paper_installment(desc)

        if amount < 0:
            cat = "Estorno"; n = t = 1
        else:
            cat = classify_expense(desc, custom_categories)

        exp = _build(desc, amount, is_foreign, n, t, custom_categories, line, force_cat=cat if amount < 0 else None)
        exp["cardholder"] = cardholder
        exp["date"] = date_obj.strftime("%Y-%m-%d")
        return exp

    return None


def _clean_foreign_desc(desc: str) -> tuple[str, bool]:
    m = _FOREIGN_CURRENCY_RE.search(desc)
    if m:
        return desc[:m.start()].strip() or desc, True
    m2 = re.search(r"\s+[\d,.]+\s+\S+\s*$", desc)
    if m2:
        cleaned = desc[:m2.start()].strip()
        if cleaned:
            return cleaned, True
    return desc, False


def _extract_bradesco_paper_installment(desc: str) -> tuple[str, int, int]:
    for m in _BRADESCO_INST_RE.finditer(desc):
        n, total = int(m.group(1)), int(m.group(2))
        if 1 <= n <= total and 1 < total <= 72:
            clean = (desc[:m.start()].rstrip() + " " + desc[m.end():].lstrip()).strip()
            return clean, n, total
    return desc, 1, 1


def _parse_date(date_raw: str, default_year: int, ref_month: int | None = None) -> dt.date:
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
        return dt.date(2000 + y if y < 100 else y, month, day)
    raise ValueError(f"Data inválida: {date_raw}")
