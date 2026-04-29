"""
Utilitários gerais: constantes, configuração, formatação, datas e classificação.
"""

import json
import hashlib
import datetime as dt
from pathlib import Path

# Diretório de dados do usuário (fora do repositório)
APP_DIR = Path.home() / ".controle_cartao_ia"
APP_DIR.mkdir(exist_ok=True)
DB_PATH = APP_DIR / "cartao.db"
CONFIG_PATH = APP_DIR / "config.json"
BACKUP_DIR = APP_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

CURRENCY = "R$"

DEFAULT_CONFIG = {
    "api_base_url": "http://localhost:11434/api/chat",
    "api_key": "",
    "model": "llama3.1:8b",
    "monthly_goal": 3000.00,
    "user_name": "",
    "user_email": "",
    "user_phone": "",
    "password_hash": "",
    "recovery_hash": "",
    "default_closing_day": 25,
    "card_closing_days": {},
}

# Categorias padrão com palavras-chave em português
CATEGORIES: dict[str, list[str]] = {
    "Alimentação": [
        "mercado", "supermercado", "ifood", "restaurante", "padaria",
        "burger", "pizza", "cafe", "açougue", "lanchonete", "sushi",
        "delivery", "refeicao", "refeição", "hortifruti", "atacadao",
        "atacadão", "breads", "mcdonalds", "subway", "habib",
    ],
    "Transporte": [
        "uber", "99", "posto", "gasolina", "estacionamento", "pedagio",
        "pedágio", "sem parar", "metro", "metrô", "ônibus", "onibus",
        "taxi", "táxi", "combustivel", "combustível", "autopass", "bpk",
        "ipva", "dpvat", "veiculo", "veículo",
    ],
    "Casa": [
        "energia", "sabesp", "condominio", "condomínio", "aluguel",
        "internet", "vivo", "claro", "tim", "enel", "agua", "água",
        "gas", "gás", "comgas", "celesc", "cemig", "cpfl", "eletropaulo",
        "net", "oi ", "sky", "reforma",
    ],
    "Saúde": [
        "farmacia", "farmácia", "drogaria", "hospital", "clinica",
        "clínica", "laboratorio", "laboratório", "medico", "médico",
        "dentista", "remedio", "remédio", "consulta", "exame",
        "convenio", "convênio", "plano de saude", "unimed", "amil",
    ],
    "Educação": [
        "curso", "udemy", "alura", "livro", "faculdade", "escola",
        "universidade", "apostila", "material", "mensalidade", "colegio",
        "colégio", "treinamento", "workshop", "linkedin learning",
    ],
    "Lazer": [
        "cinema", "netflix", "spotify", "disney", "amazon prime",
        "hbo", "show", "ingresso", "teatro", "parque", "jogo",
        "steam", "xbox", "playstation", "nintendo", "streaming",
        "clube", "academia", "esporte",
    ],
    "Compras": [
        "amazon", "mercado livre", "magazine", "shopee", "aliexpress",
        "loja", "shopping", "roupa", "calcado", "calçado", "roupas",
        "moda", "c&a", "renner", "riachuelo", "zara", "hering",
        "americanas", "casas bahia", "extra", "submarino",
    ],
    "Assinaturas/Software": [
        "openai", "chatgpt", "github", "google", "microsoft", "adobe",
        "apple", "notion", "canva", "dropbox", "icloud", "office",
        "antivirus", "vpn", "lastpass", "figma", "slack", "zoom",
    ],
    "Viagem": [
        "hotel", "airbnb", "latam", "azul", "gol", "booking", "decolar",
        "rentcars", "passagem", "aeroporto", "hostel", "resort",
        "excursao", "excursão", "turismo", "viagem",
    ],
}


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULT_CONFIG, **data}
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Autenticação simples (hash SHA-256) + código de recuperação
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def check_password(password: str, stored_hash: str) -> bool:
    return hash_password(password) == stored_hash


def generate_recovery_key() -> str:
    """Gera um código de recuperação legível no formato XXXX-XXXX-XXXX-XXXX."""
    import secrets
    parts = [secrets.token_hex(2).upper() for _ in range(4)]
    return "-".join(parts)


# ---------------------------------------------------------------------------
# Datas
# ---------------------------------------------------------------------------

def _clamp_day(year: int, month: int, day: int) -> dt.date:
    """Retorna a data com o dia dado, reduzindo até ser válido (ex: 31 em fevereiro → 28/29)."""
    while day > 0:
        try:
            return dt.date(year, month, day)
        except ValueError:
            day -= 1
    raise ValueError(f"Data inválida: {year}-{month}-??")


def invoice_month_for_date(date: dt.date, closing_day: int) -> str:
    """
    Retorna o mês da fatura (AAAA-MM) de uma transação dado o dia de fechamento.
    Ex: closing_day=25, date=28/04 → '2026-05'  (vai para a fatura de maio)
        closing_day=25, date=20/05 → '2026-05'  (fica na fatura de maio)
        closing_day=25, date=25/05 → '2026-05'  (dia do fechamento ainda é deste mês)
    """
    if date.day > closing_day:
        return add_months(date, 1).strftime("%Y-%m")
    return date.strftime("%Y-%m")


def invoice_period(year: int, month: int, closing_day: int) -> tuple[dt.date, dt.date]:
    """
    Retorna (data_início, data_fim) do ciclo de fatura.
    Ex: year=2026, month=5, closing_day=25 → (2026-04-26, 2026-05-25)
    """
    end   = _clamp_day(year, month, closing_day)
    prev  = add_months(dt.date(year, month, 1), -1)
    start = _clamp_day(prev.year, prev.month, closing_day) + dt.timedelta(days=1)
    return start, end


def add_months(date_obj: dt.date, months: int) -> dt.date:
    """Avança N meses numa data, respeitando o último dia do mês."""
    month = date_obj.month - 1 + months
    year = date_obj.year + month // 12
    month = month % 12 + 1
    day = min(date_obj.day, [
        31,
        29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31
    ][month - 1])
    return dt.date(year, month, day)


def current_month() -> str:
    """Retorna o mês atual no formato brasileiro MM/AAAA."""
    return dt.date.today().strftime("%m/%Y")


def current_year() -> int:
    return dt.date.today().year


def month_br_to_db(month_br: str) -> str:
    """Converte MM/AAAA → AAAA-MM (formato interno do banco)."""
    month_br = month_br.strip()
    try:
        return dt.datetime.strptime(month_br, "%m/%Y").strftime("%Y-%m")
    except ValueError:
        raise ValueError("Informe o mês no formato MM/AAAA. Exemplo: 04/2026")


def month_db_to_br(month_db: str) -> str:
    """Converte AAAA-MM → MM/AAAA."""
    try:
        return dt.datetime.strptime(month_db, "%Y-%m").strftime("%m/%Y")
    except ValueError:
        return month_db


# ---------------------------------------------------------------------------
# Moeda
# ---------------------------------------------------------------------------

def money(value: float) -> str:
    """Formata valor em Real brasileiro: R$ 1.234,56"""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_money(text: str) -> float:
    """Converte string em float, aceitando formatos 1.234,56 ou 1234.56"""
    text = text.strip().replace("R$", "").strip()
    if "," in text and "." in text:
        # formato brasileiro 1.234,56
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    return float(text)


# ---------------------------------------------------------------------------
# Classificação de gastos
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    return text.lower().strip()


def classify_expense(description: str, custom_categories: dict | None = None) -> str:
    """
    Classifica um gasto por palavras-chave.
    custom_categories permite categorias dinâmicas criadas pelo usuário ou pela IA.
    """
    text = normalize(description)
    all_categories = {**CATEGORIES}
    if custom_categories:
        all_categories.update(custom_categories)
    for category, keywords in all_categories.items():
        for keyword in keywords:
            if normalize(keyword) in text:
                return category
    return "Outros"


def get_all_category_names(custom_categories: dict | None = None) -> list[str]:
    """Retorna lista completa de categorias (padrão + customizadas)."""
    names = list(CATEGORIES.keys())
    if custom_categories:
        for name in custom_categories:
            if name not in names:
                names.append(name)
    if "Outros" not in names:
        names.append("Outros")
    return names
