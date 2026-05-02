"""
Camada de acesso ao banco SQLite.
Todas as queries ficam aqui — a GUI nunca acessa o banco diretamente.
"""

import sqlite3
import datetime as dt
import calendar
import re
from collections import defaultdict

from .utils import DB_PATH, add_months, invoice_month_for_date


class Database:
    def __init__(self, path=DB_PATH, config: dict | None = None):
        self.path = path
        self._config = config or {}
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.create_tables()

    def set_config(self, config: dict):
        """Atualiza referência ao config (chamar após salvar configurações)."""
        self._config = config

    def _closing_day(self, card: str | None) -> int:
        """Retorna o dia de fechamento do cartão informado, ou o padrão."""
        card_map = self._config.get("card_closing_days", {})
        default = int(self._config.get("default_closing_day", 25))
        if card and card in card_map:
            return int(card_map[card])
        return default

    def _invoice_month(self, date_str: str, card: str | None) -> str:
        """Calcula o mês da fatura (AAAA-MM) a partir da data e do cartão."""
        d = dt.date.fromisoformat(date_str)
        return invoice_month_for_date(d, self._closing_day(card))

    def _expenses_for_month(self, month: str):
        """
        Retorna todos os lançamentos cujo invoice_month calculado é igual a `month`.
        Usa filtro de datas no SQL para reduzir o volume antes de filtrar em Python.
        """
        year, m = int(month[:4]), int(month[5:7])
        # Intervalo generoso: mês anterior completo até o fim do mês alvo
        prev = dt.date(year, m, 1) - dt.timedelta(days=1)
        broad_start = dt.date(prev.year, prev.month, 1).isoformat()
        broad_end   = dt.date(year, m, calendar.monthrange(year, m)[1]).isoformat()
        rows = self.conn.execute(
            "SELECT * FROM expenses WHERE date >= ? AND date <= ? ORDER BY date DESC, id DESC",
            (broad_start, broad_end),
        ).fetchall()
        return [r for r in rows if self._invoice_month(r["date"], r["card"]) == month]

    # ------------------------------------------------------------------
    # Criação de tabelas
    # ------------------------------------------------------------------

    def create_tables(self):
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS expenses (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                date               TEXT    NOT NULL,
                description        TEXT    NOT NULL,
                amount             REAL    NOT NULL,
                category           TEXT    NOT NULL,
                card               TEXT,
                installments       INTEGER DEFAULT 1,
                installment_number INTEGER DEFAULT 1,
                parent_id          INTEGER,
                notes              TEXT,
                created_at         TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS monthly_goals (
                month TEXT PRIMARY KEY,
                goal  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS custom_categories (
                name     TEXT PRIMARY KEY,
                keywords TEXT NOT NULL
            );
        """)
        # Remove coluna invoice_month de bancos antigos (não é mais necessária)
        try:
            cur.execute("ALTER TABLE expenses DROP COLUMN invoice_month")
        except Exception:
            pass  # coluna já removida ou SQLite antigo sem suporte a DROP COLUMN
        self.conn.commit()

    # ------------------------------------------------------------------
    # Gastos
    # ------------------------------------------------------------------

    def add_expense(
        self,
        date: str,
        description: str,
        amount: float,
        category: str,
        card: str = "",
        installments: int = 1,
        notes: str = "",
    ):
        """Adiciona gasto. Para parcelados, insere apenas a parcela 1/N."""
        installments = max(1, installments)
        monthly_value = round(amount / installments, 2) if installments > 1 else amount
        self.add_expense_raw(date, description, monthly_value, category, card,
                             installments, 1, notes)

    def edit_expense(
        self,
        expense_id: int,
        date: str,
        description: str,
        amount: float,
        category: str,
        card: str = "",
        notes: str = "",
    ):
        """Edita um lançamento individual (não propaga para outras parcelas)."""
        self.conn.execute(
            """
            UPDATE expenses
            SET date=?, description=?, amount=?, category=?, card=?, notes=?
            WHERE id=?
            """,
            (date, description, amount, category, card, notes, expense_id),
        )
        self.conn.commit()

    def get_expense_by_id(self, expense_id: int):
        cur = self.conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,))
        return cur.fetchone()

    @staticmethod
    def _base_description(description: str) -> str:
        text = (description or "").strip().lower()
        text = re.sub(r"\s+\(\d+/\d+\)$", "", text)
        return text

    def list_expenses(self, month: str | None = None):
        """Lista gastos de uma fatura (AAAA-MM) ou todos os gastos."""
        if month:
            return self._expenses_for_month(month)
        return self.conn.execute(
            "SELECT * FROM expenses ORDER BY date DESC, id DESC"
        ).fetchall()

    def expense_exists(
        self,
        date: str,
        description: str,
        amount: float,
        card: str = "",
    ) -> bool:
        row = self.conn.execute(
            """
            SELECT 1
            FROM expenses
            WHERE date = ?
              AND lower(trim(description)) = lower(trim(?))
              AND ABS(amount - ?) < 0.005
              AND COALESCE(card, '') = COALESCE(?, '')
            LIMIT 1
            """,
            (date, description, amount, card),
        ).fetchone()
        return row is not None

    def delete_expense(self, expense_id: int):
        self.conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        self.conn.commit()

    def delete_all(self):
        """Apaga TODOS os lançamentos (com confirmação via GUI)."""
        self.conn.execute("DELETE FROM expenses")
        self.conn.execute("DELETE FROM monthly_goals")
        self.conn.commit()

    def add_expense_raw(
        self,
        date: str,
        description: str,
        amount: float,
        category: str,
        card: str = "",
        installments: int = 1,
        installment_number: int = 1,
        notes: str = "",
    ):
        """Insere um único lançamento sem expandir parcelas (usado na importação de PDF)."""
        created_at = dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """
            INSERT INTO expenses
                (date, description, amount, category, card,
                 installments, installment_number, parent_id, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (date, description, amount, category, card,
             installments, installment_number, notes, created_at),
        )
        self.conn.commit()

    def clear_expenses(self):
        self.conn.execute("DELETE FROM expenses")
        self.conn.commit()

    def clear_goals(self):
        self.conn.execute("DELETE FROM monthly_goals")
        self.conn.commit()

    def clear_custom_categories(self):
        self.conn.execute("DELETE FROM custom_categories")
        self.conn.commit()

    # ------------------------------------------------------------------
    # Totais e agregações
    # ------------------------------------------------------------------

    def get_month_total(self, month: str) -> float:
        rows = self._expenses_for_month(month)
        return round(sum(float(r["amount"]) for r in rows), 2)

    def get_category_totals(self, month: str):
        rows = self._expenses_for_month(month)
        totals: dict[str, float] = defaultdict(float)
        for r in rows:
            totals[r["category"]] += float(r["amount"])
        return sorted(
            [{"category": cat, "total": round(t, 2)} for cat, t in totals.items()],
            key=lambda x: -x["total"],
        )

    def get_year_category_totals(self, year: int):
        rows = self.conn.execute("SELECT date, card, category, amount FROM expenses").fetchall()
        totals: dict[str, float] = defaultdict(float)
        for r in rows:
            if self._invoice_month(r["date"], r["card"])[:4] == str(year):
                totals[r["category"]] += float(r["amount"])
        return sorted(
            [{"category": cat, "total": round(t, 2)} for cat, t in totals.items()],
            key=lambda x: -x["total"],
        )

    def get_all_month_totals(self):
        """Totais agrupados por fatura calculada, ordenados cronologicamente."""
        rows = self.conn.execute("SELECT date, card, amount FROM expenses").fetchall()
        totals: dict[str, float] = defaultdict(float)
        for r in rows:
            inv = self._invoice_month(r["date"], r["card"])
            totals[inv] += float(r["amount"])
        return [
            {"month": m, "total": round(t, 2)}
            for m, t in sorted(totals.items())
        ]

    def get_year_totals(self):
        rows = self.conn.execute("SELECT date, card, amount FROM expenses").fetchall()
        totals: dict[str, float] = defaultdict(float)
        for r in rows:
            year = self._invoice_month(r["date"], r["card"])[:4]
            totals[year] += float(r["amount"])
        return [
            {"year": y, "total": round(t, 2)}
            for y, t in sorted(totals.items())
        ]

    def get_future_commitments(self, start_month: str, months_ahead: int = 12):
        """
        Calcula comprometimentos futuros inferindo parcelas restantes.
        invoice_month é calculado dinamicamente a partir de date + card.
        """
        all_rows = self.conn.execute(
            "SELECT description, amount, installments, installment_number, date, card "
            "FROM expenses ORDER BY date ASC"
        ).fetchall()

        recorded: set[tuple] = {
            (
                (r["description"] or "").strip().lower(),
                r["installments"] or 1,
                r["installment_number"] or 1,
                self._invoice_month(r["date"], r["card"]),
            )
            for r in all_rows
        }

        totals: dict[str, float] = defaultdict(float)

        for row in all_rows:
            inv = self._invoice_month(row["date"], row["card"])
            totals[inv] += float(row["amount"])

            n_total   = row["installments"] or 1
            n_current = row["installment_number"] or 1
            remaining = n_total - n_current
            if remaining <= 0:
                continue

            desc_lower = (row["description"] or "").strip().lower()
            base = dt.datetime.strptime(inv + "-01", "%Y-%m-%d").date()

            next_inv = add_months(base, 1).strftime("%Y-%m")
            if (desc_lower, n_total, n_current + 1, next_inv) in recorded:
                continue

            for offset in range(1, remaining + 1):
                future_inv      = add_months(base, offset).strftime("%Y-%m")
                future_inst_num = n_current + offset
                if (desc_lower, n_total, future_inst_num, future_inv) not in recorded:
                    totals[future_inv] += float(row["amount"])

        result = sorted(
            [{"month": m, "total": round(t, 2)} for m, t in totals.items() if m >= start_month],
            key=lambda x: x["month"],
        )
        return result[:months_ahead]

    def get_recurring_expenses(self, min_months: int = 2, limit: int = 8):
        rows = self.conn.execute(
            """
            SELECT date, description, amount, category
            FROM expenses
            ORDER BY date ASC, id ASC
            """
        ).fetchall()

        grouped: dict[str, dict] = defaultdict(
            lambda: {
                "description": "",
                "category": "Outros",
                "months": set(),
                "count": 0,
                "total": 0.0,
                "last_date": "",
            }
        )

        for row in rows:
            base_desc = self._base_description(row["description"])
            if not base_desc:
                continue
            item = grouped[base_desc]
            item["description"] = item["description"] or row["description"]
            item["category"] = row["category"]
            item["months"].add(row["date"][:7])
            item["count"] += 1
            item["total"] += float(row["amount"])
            item["last_date"] = row["date"]

        result = []
        for item in grouped.values():
            month_count = len(item["months"])
            if month_count < min_months:
                continue
            avg_per_month = item["total"] / month_count if month_count else 0.0
            result.append({
                "description": item["description"],
                "category": item["category"],
                "months": month_count,
                "count": item["count"],
                "avg_per_month": avg_per_month,
                "last_date": item["last_date"],
            })

        result.sort(key=lambda x: (-x["months"], -x["avg_per_month"], x["description"].lower()))
        return result[:limit]

    def get_top_expenses(self, month: str | None = None, limit: int = 8):
        if month:
            rows = self._expenses_for_month(month)
            rows = sorted(rows, key=lambda r: -float(r["amount"]))
            return rows[:limit]
        return self.conn.execute(
            "SELECT * FROM expenses ORDER BY amount DESC LIMIT ?", (limit,)
        ).fetchall()

    def count_expenses(self, month: str | None = None) -> int:
        if month:
            return len(self._expenses_for_month(month))
        row = self.conn.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()
        return int(row["n"])

    # ------------------------------------------------------------------
    # Metas mensais
    # ------------------------------------------------------------------

    def set_goal(self, month: str, goal: float):
        self.conn.execute(
            """
            INSERT INTO monthly_goals(month, goal) VALUES(?,?)
            ON CONFLICT(month) DO UPDATE SET goal = excluded.goal
            """,
            (month, goal),
        )
        self.conn.commit()

    def get_goal(self, month: str, default_goal: float) -> float:
        row = self.conn.execute(
            "SELECT goal FROM monthly_goals WHERE month=?", (month,)
        ).fetchone()
        if row:
            return float(row["goal"])
        return float(default_goal)

    # ------------------------------------------------------------------
    # Categorias customizadas
    # ------------------------------------------------------------------

    def get_custom_categories(self) -> dict:
        rows = self.conn.execute(
            "SELECT name, keywords FROM custom_categories"
        ).fetchall()
        return {
            row["name"]: [k.strip() for k in row["keywords"].split(",") if k.strip()]
            for row in rows
        }

    def save_custom_category(self, name: str, keywords: list[str]):
        kw_str = ", ".join(k.lower().strip() for k in keywords if k.strip())
        self.conn.execute(
            """
            INSERT INTO custom_categories(name, keywords) VALUES(?,?)
            ON CONFLICT(name) DO UPDATE SET keywords = excluded.keywords
            """,
            (name, kw_str),
        )
        self.conn.commit()

    def delete_custom_category(self, name: str):
        self.conn.execute("DELETE FROM custom_categories WHERE name=?", (name,))
        self.conn.commit()

    # ------------------------------------------------------------------
    # Utilitários
    # ------------------------------------------------------------------

    def close(self):
        self.conn.close()
