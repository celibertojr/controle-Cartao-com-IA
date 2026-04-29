"""
Camada de acesso ao banco SQLite.
Todas as queries ficam aqui — a GUI nunca acessa o banco diretamente.
"""

import sqlite3
import datetime as dt
import re
from collections import defaultdict

from .utils import DB_PATH, add_months, invoice_month_for_date


class Database:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")  # melhor concorrência
        self.create_tables()

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
                created_at         TEXT    NOT NULL,
                invoice_month      TEXT
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
        # Migração: adiciona invoice_month se o banco já existia sem a coluna
        try:
            cur.execute("ALTER TABLE expenses ADD COLUMN invoice_month TEXT")
        except Exception:
            pass  # coluna já existe
        # Popula invoice_month para registros antigos (usa mês da data da transação)
        cur.execute(
            "UPDATE expenses SET invoice_month = substr(date, 1, 7) WHERE invoice_month IS NULL"
        )
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
        invoice_month: str | None = None,
    ):
        """Adiciona gasto. Para parcelados, insere apenas a parcela atual (1/N); parcelas futuras são inferidas."""
        installments = max(1, installments)
        monthly_value = round(amount / installments, 2) if installments > 1 else amount
        inv = invoice_month or date[:7]
        self.add_expense_raw(date, description, monthly_value, category, card,
                             installments, 1, inv, notes)

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
            cur = self.conn.execute(
                "SELECT * FROM expenses WHERE invoice_month=? ORDER BY date DESC, id DESC",
                (month,),
            )
        else:
            cur = self.conn.execute(
                "SELECT * FROM expenses ORDER BY invoice_month DESC, date DESC, id DESC"
            )
        return cur.fetchall()

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
        invoice_month: str | None = None,
        notes: str = "",
    ):
        """Insere um único lançamento sem expandir parcelas (usado na importação de PDF)."""
        created_at = dt.datetime.now().isoformat(timespec="seconds")
        inv = invoice_month or date[:7]
        self.conn.execute(
            """
            INSERT INTO expenses
                (date, description, amount, category, card,
                 installments, installment_number, parent_id, notes, created_at, invoice_month)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (date, description, amount, category, card,
             installments, installment_number, notes, created_at, inv),
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
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM expenses WHERE invoice_month=?",
            (month,),
        ).fetchone()
        return float(row["t"])

    def get_category_totals(self, month: str):
        return self.conn.execute(
            """
            SELECT category, COALESCE(SUM(amount),0) AS total
            FROM expenses WHERE invoice_month=?
            GROUP BY category ORDER BY total DESC
            """,
            (month,),
        ).fetchall()

    def get_year_category_totals(self, year: int):
        return self.conn.execute(
            """
            SELECT category, COALESCE(SUM(amount),0) AS total
            FROM expenses WHERE substr(invoice_month,1,4)=?
            GROUP BY category ORDER BY total DESC
            """,
            (str(year),),
        ).fetchall()

    def get_all_month_totals(self):
        """Totais agrupados por fatura (invoice_month), ordenados cronologicamente."""
        return self.conn.execute(
            """
            SELECT invoice_month AS month, COALESCE(SUM(amount),0) AS total
            FROM expenses GROUP BY invoice_month ORDER BY invoice_month ASC
            """
        ).fetchall()

    def get_year_totals(self):
        return self.conn.execute(
            """
            SELECT substr(invoice_month,1,4) AS year, COALESCE(SUM(amount),0) AS total
            FROM expenses GROUP BY substr(invoice_month,1,4) ORDER BY year ASC
            """
        ).fetchall()

    def get_future_commitments(self, start_month: str, months_ahead: int = 12):
        """
        Calcula comprometimentos futuros usando invoice_month como unidade.
        Infere parcelas restantes sem duplicar entradas já registradas.
        Retorna lista de dicts {"month": "AAAA-MM", "total": float}.
        """
        all_rows = self.conn.execute(
            "SELECT description, amount, installments, installment_number, invoice_month "
            "FROM expenses ORDER BY invoice_month ASC"
        ).fetchall()

        # Chave (desc_lower, total_parc, num_parc, invoice_month)
        recorded: set[tuple] = {
            (
                (r["description"] or "").strip().lower(),
                r["installments"] or 1,
                r["installment_number"] or 1,
                r["invoice_month"] or "",
            )
            for r in all_rows
        }

        totals: dict[str, float] = defaultdict(float)

        for row in all_rows:
            inv = row["invoice_month"] or ""
            totals[inv] += float(row["amount"])

            n_total = row["installments"] or 1
            n_current = row["installment_number"] or 1
            remaining = n_total - n_current
            if remaining <= 0:
                continue

            desc_lower = (row["description"] or "").strip().lower()
            base = dt.datetime.strptime(inv + "-01", "%Y-%m-%d").date()

            # Não projeta se o próximo da cadeia já está registrado
            next_inv = add_months(base, 1).strftime("%Y-%m")
            if (desc_lower, n_total, n_current + 1, next_inv) in recorded:
                continue

            for offset in range(1, remaining + 1):
                future_inv = add_months(base, offset).strftime("%Y-%m")
                future_inst_num = n_current + offset
                if (desc_lower, n_total, future_inst_num, future_inv) not in recorded:
                    totals[future_inv] += float(row["amount"])

        result = sorted(
            [{"month": m, "total": t} for m, t in totals.items() if m >= start_month],
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
            return self.conn.execute(
                "SELECT * FROM expenses WHERE invoice_month=? ORDER BY amount DESC LIMIT ?",
                (month, limit),
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM expenses ORDER BY amount DESC LIMIT ?", (limit,)
        ).fetchall()

    def count_expenses(self, month: str | None = None) -> int:
        if month:
            row = self.conn.execute(
                "SELECT COUNT(*) AS n FROM expenses WHERE invoice_month=?", (month,)
            ).fetchone()
        else:
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
        """
        Retorna a meta do mês informado.
        Se houver meta salva para o mês, ela prevalece.
        Caso contrário, usa a meta atual padrão informada pela interface.
        """
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
