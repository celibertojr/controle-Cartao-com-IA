"""
Interface gráfica principal do Controle de Cartão de Crédito com IA.
- Um único Tk() na raiz; janelas secundárias usam Toplevel()
- Chamadas de IA executam em thread separada para não travar a UI
- Login/senha protege o acesso ao sistema
"""

import json
import shutil
import threading
import datetime as dt
from tkinter import (
    Tk, Toplevel, Frame, Label, Button, Entry, Text, StringVar, DoubleVar,
    IntVar, BooleanVar, filedialog, messagebox, END, BOTH, LEFT, RIGHT, X,
    Y, TOP, BOTTOM, WORD, DISABLED, NORMAL, W, scrolledtext,
)
from tkinter import ttk

from .utils import (
    load_config, save_config, hash_password, check_password,
    generate_recovery_key,
    add_months, current_month, month_br_to_db, month_db_to_br,
    classify_expense, get_all_category_names, money, parse_money,
    current_year, DB_PATH, BACKUP_DIR,
)
from .database import Database
from .ai_advisor import AIAdvisor
from .pdf_importer import parse_pdf_invoice, extract_raw_text, PDFPLUMBER_AVAILABLE
from . import charts


# ---------------------------------------------------------------------------
# Constantes visuais
# ---------------------------------------------------------------------------
FONT_TITLE   = ("Segoe UI", 15, "bold")
FONT_HEADER  = ("Segoe UI", 11, "bold")
FONT_NORMAL  = ("Segoe UI", 10)
FONT_SMALL   = ("Segoe UI", 9)
FONT_MONO    = ("Consolas", 9)

CLR_BG       = "#f0f2f5"
CLR_CARD     = "#ffffff"
CLR_PRIMARY  = "#2c3e50"
CLR_ACCENT   = "#3498db"
CLR_OK       = "#27ae60"
CLR_WARN     = "#f39c12"
CLR_DANGER   = "#e74c3c"
CLR_LIGHT    = "#ecf0f1"
CLR_TEXT     = "#2c3e50"
CLR_MUTED    = "#7f8c8d"


# ===========================================================================
# Ponto de entrada chamado por main.py
# ===========================================================================

def run():
    root = Tk()
    root.withdraw()                        # esconde até o login ser aprovado
    root.title("Controle de Cartão de Crédito com IA")
    root.configure(bg=CLR_BG)

    config = load_config()

    # --- login ---
    if not _do_login(root, config):
        root.destroy()
        return

    # --- aplica estilo global ---
    _apply_style(root)

    # --- inicia app ---
    app = CreditCardApp(root, config)
    root.deiconify()
    root.geometry("1280x820")
    root.minsize(1000, 680)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


# ===========================================================================
# Login / criação de senha
# ===========================================================================

def _do_login(root: Tk, config: dict) -> bool:
    """Mostra diálogo de login e retorna True se aprovado."""
    stored_hash = config.get("password_hash", "")
    first_time  = not stored_hash
    result      = [False]
    reset_state = {"performed": False}

    dlg = Toplevel(root)
    dlg.title("Controle de Cartão")
    dlg.resizable(True, True)   # redimensionável — evita corte de conteúdo
    dlg.grab_set()
    dlg.configure(bg=CLR_CARD)

    # Centraliza com tamanho suficiente para todos os botões
    w = 420
    h = 540 if first_time else 500
    dlg.update_idletasks()
    sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
    dlg.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
    dlg.minsize(380, 460)

    # ---- Cabeçalho ----
    header = Frame(dlg, bg=CLR_PRIMARY, height=60)
    header.pack(fill=X)
    header.pack_propagate(False)
    Label(header, text="💳  Controle de Cartão",
          font=("Segoe UI", 14, "bold"), bg=CLR_PRIMARY, fg="white").pack(expand=True)

    # ---- Corpo com scroll implícito via pack natural ----
    body = Frame(dlg, bg=CLR_CARD)
    body.pack(fill=BOTH, expand=True, padx=32, pady=16)

    if first_time:
        Label(body, text="Primeira vez? Crie uma senha de acesso.",
              font=("Segoe UI", 10), bg=CLR_CARD, fg=CLR_MUTED).pack(anchor=W, pady=(0, 12))
    else:
        Label(body, text="Digite sua senha para continuar.",
              font=("Segoe UI", 10), bg=CLR_CARD, fg=CLR_MUTED).pack(anchor=W, pady=(0, 12))

    Label(body, text="Senha:", font=("Segoe UI", 10, "bold"), bg=CLR_CARD, fg=CLR_TEXT).pack(anchor=W)
    pw_var   = StringVar()
    pw_entry = Entry(body, textvariable=pw_var, show="●",
                     font=("Segoe UI", 12), relief="solid", bd=1)
    pw_entry.pack(fill=X, pady=(2, 10))
    pw_entry.focus_set()

    pw2_var = StringVar()
    if first_time:
        Label(body, text="Confirme a senha:", font=("Segoe UI", 10, "bold"),
              bg=CLR_CARD, fg=CLR_TEXT).pack(anchor=W)
        Entry(body, textvariable=pw2_var, show="●",
              font=("Segoe UI", 12), relief="solid", bd=1).pack(fill=X, pady=(2, 10))

    # Mensagem de erro (sempre visível, só muda o texto)
    msg_var = StringVar()
    Label(body, textvariable=msg_var, fg=CLR_DANGER,
          font=("Segoe UI", 9), bg=CLR_CARD, wraplength=340).pack(fill=X, pady=(0, 8))

    # ---- Botão principal ----
    Button(body, text="→  Entrar", command=lambda: attempt(),
           bg=CLR_ACCENT, fg="white", relief="flat",
           font=("Segoe UI", 11, "bold"), pady=10, cursor="hand2").pack(fill=X)

    # Separador visual
    Frame(body, bg=CLR_LIGHT, height=1).pack(fill=X, pady=12)

    # ---- Opções de recuperação (sempre visíveis quando há senha) ----
    if stored_hash:
        Label(body, text="Problemas para entrar?",
              font=("Segoe UI", 9, "bold"), bg=CLR_CARD, fg=CLR_MUTED).pack(anchor=W, pady=(0, 4))
        Button(body, text="🔑  Esqueci a senha (usar código de recuperação)",
               command=lambda: _forgot_password_dialog(dlg, config),
               bg=CLR_LIGHT, fg=CLR_ACCENT, relief="flat",
               font=("Segoe UI", 9), pady=6, cursor="hand2", anchor=W).pack(fill=X, pady=2)
        Button(body, text="🗑  Resetar acesso e apagar dados",
               command=lambda: reset_all(),
               bg=CLR_LIGHT, fg=CLR_DANGER, relief="flat",
               font=("Segoe UI", 9), pady=6, cursor="hand2", anchor=W).pack(fill=X, pady=2)

    # Separador
    Frame(body, bg=CLR_LIGHT, height=1).pack(fill=X, pady=8)

    Button(body, text="✕  Sair do aplicativo",
           command=dlg.destroy,
           bg="#fdecea", fg=CLR_DANGER, relief="flat",
           font=("Segoe UI", 10, "bold"), pady=8, cursor="hand2").pack(fill=X)

    # ---- Funções internas ----
    def attempt(event=None):
        pw = pw_var.get()
        if first_time:
            if len(pw) < 4:
                msg_var.set("A senha deve ter pelo menos 4 caracteres.")
                return
            if pw != pw2_var.get():
                msg_var.set("As senhas não conferem.")
                return
            recovery_key = generate_recovery_key()
            config["password_hash"] = hash_password(pw)
            config["recovery_hash"] = hash_password(recovery_key)
            save_config(config)
            result[0] = True
            dlg.destroy()
            _show_recovery_key(root, recovery_key)
        else:
            if check_password(pw, stored_hash):
                result[0] = True
                dlg.destroy()
            else:
                msg_var.set("Senha incorreta. Tente novamente ou use uma das opções abaixo.")
                pw_var.set("")
                pw_entry.focus_set()

    def reset_all():
        if messagebox.askyesno(
            "Resetar acesso e apagar dados",
            "⚠️ Se você não consegue recuperar a senha, este é o último recurso.\n\n"
            "Isso apagará usuário, senha, código de recuperação e TODOS os lançamentos.\n"
            "Um backup do banco será criado antes para restauração futura.\n\n"
            "Deseja continuar?",
            parent=dlg,
        ) and messagebox.askyesno(
            "Confirmação final",
            "Tem certeza absoluta? O acesso atual será removido e o banco será apagado.",
            parent=dlg,
        ):
            # faz backup antes de apagar
            import shutil, datetime as _dt
            ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            BACKUP_DIR.mkdir(exist_ok=True)
            if DB_PATH.exists():
                backup_path = BACKUP_DIR / f"cartao_emergencia_{ts}.db"
                shutil.copy2(DB_PATH, backup_path)
                _write_backup_metadata(backup_path, config, "reset_login")
            config["password_hash"] = ""
            config["recovery_hash"] = ""
            config["user_name"] = ""
            config["user_email"] = ""
            config["user_phone"] = ""
            save_config(config)
            if DB_PATH.exists():
                DB_PATH.unlink()
            reset_state["performed"] = True
            messagebox.showinfo(
                "Reset concluído",
                "Seus dados locais foram apagados e o backup foi preservado.\n"
                "Abra o aplicativo novamente para criar uma nova senha.",
                parent=dlg,
            )
            dlg.destroy()

    pw_entry.bind("<Return>", attempt)
    dlg.wait_window()
    if reset_state["performed"]:
        return False
    return result[0]


def _show_recovery_key(parent, recovery_key: str):
    """Exibe o código de recuperação após criar a senha. O usuário deve anotar."""
    dlg = Toplevel(parent)
    dlg.title("Código de recuperação")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.configure(bg=CLR_CARD)

    w, h = 440, 280
    dlg.update_idletasks()
    sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
    dlg.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    Frame(dlg, bg=CLR_WARN, height=5).pack(fill=X)
    Label(dlg, text="⚠️  Guarde este código de recuperação",
          font=("Segoe UI", 12, "bold"), bg=CLR_CARD, fg=CLR_WARN).pack(pady=(16, 4))
    Label(dlg, text="Se esquecer a senha, use este código para redefiní-la.\n"
                    "Anote em local seguro. Ele não será mostrado novamente.",
          font=("Segoe UI", 9), bg=CLR_CARD, fg=CLR_MUTED, justify="center").pack(padx=20)

    # Exibe o código em destaque
    code_frame = Frame(dlg, bg=CLR_LIGHT, relief="groove", bd=1)
    code_frame.pack(padx=32, pady=16, fill=X)
    Label(code_frame, text=recovery_key,
          font=("Consolas", 18, "bold"), bg=CLR_LIGHT, fg=CLR_PRIMARY,
          pady=10).pack()

    def copy_and_close():
        dlg.clipboard_clear()
        dlg.clipboard_append(recovery_key)
        dlg.destroy()

    Button(dlg, text="Copiei e anotei — Fechar", command=copy_and_close,
           bg=CLR_OK, fg="white", relief="flat",
           font=("Segoe UI", 10, "bold"), pady=8, cursor="hand2").pack(padx=32, fill=X)
    Label(dlg, text="O código também foi copiado para a área de transferência.",
          font=("Segoe UI", 8), bg=CLR_CARD, fg=CLR_MUTED).pack(pady=(6, 0))

    dlg.wait_window()


def _write_backup_metadata(backup_path, config: dict, reason: str):
    """Salva um pequeno manifesto ao lado do backup para identificação futura."""
    metadata = {
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "reason": reason,
        "db_backup_file": backup_path.name,
        "user": {
            "name": config.get("user_name", "").strip(),
            "email": config.get("user_email", "").strip(),
            "phone": config.get("user_phone", "").strip(),
        },
        "ai": {
            "api_base_url": config.get("api_base_url", "").strip(),
            "model": config.get("model", "").strip(),
        },
    }
    metadata_path = backup_path.with_suffix(".json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)


def _forgot_password_dialog(parent, config: dict):
    """Permite redefinir a senha usando o código de recuperação."""
    recovery_hash = config.get("recovery_hash", "")

    dlg = Toplevel(parent)
    dlg.title("Recuperar acesso")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.configure(bg=CLR_CARD)

    w, h = 400, 300
    dlg.update_idletasks()
    sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
    dlg.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    Frame(dlg, bg=CLR_ACCENT, height=5).pack(fill=X)
    Label(dlg, text="Recuperar acesso", font=("Segoe UI", 13, "bold"),
          bg=CLR_CARD, fg=CLR_TEXT).pack(pady=(16, 4))

    if not recovery_hash:
        Label(dlg, text="Nenhum código de recuperação foi gerado para esta conta.\n\n"
                         "Sem esse código, não é possível redefinir a senha com segurança.\n"
                         "Nesse caso, volte à tela de login e use a opção:\n"
                         "• 'Resetar acesso e apagar dados'\n\n"
                         "O app criará um backup do banco antes de apagar, para que\n"
                         "você possa restaurar as informações depois.",
              font=("Segoe UI", 9), bg=CLR_CARD, fg=CLR_MUTED, justify=LEFT).pack(padx=24, pady=8)
        Button(dlg, text="Fechar", command=dlg.destroy, relief="flat",
               font=("Segoe UI", 10), pady=6).pack(pady=10)
        return

    Label(dlg, text="Digite o código de recuperação que você anotou:",
          font=("Segoe UI", 9), bg=CLR_CARD, fg=CLR_MUTED).pack(padx=24)

    code_var = StringVar()
    Entry(dlg, textvariable=code_var, font=("Consolas", 13), width=22,
          relief="solid", bd=1, justify="center").pack(padx=32, pady=10, fill=X)

    Label(dlg, text="Nova senha:", font=("Segoe UI", 10, "bold"), bg=CLR_CARD, fg=CLR_TEXT).pack(anchor=W, padx=32)
    new_pw_var = StringVar()
    Entry(dlg, textvariable=new_pw_var, show="●", font=("Segoe UI", 11),
          relief="solid", bd=1).pack(padx=32, pady=(2, 6), fill=X)

    msg_var = StringVar()
    Label(dlg, textvariable=msg_var, font=("Segoe UI", 9), bg=CLR_CARD, fg=CLR_DANGER).pack()

    def reset():
        code = code_var.get().strip().upper()
        new_pw = new_pw_var.get().strip()
        if hash_password(code) != recovery_hash:
            msg_var.set("Código de recuperação incorreto.")
            return
        if len(new_pw) < 4:
            msg_var.set("A nova senha deve ter pelo menos 4 caracteres.")
            return
        # Redefine senha e gera novo código de recuperação
        new_recovery = generate_recovery_key()
        config["password_hash"] = hash_password(new_pw)
        config["recovery_hash"] = hash_password(new_recovery)
        save_config(config)
        dlg.destroy()
        _show_recovery_key(parent, new_recovery)
        messagebox.showinfo("Senha redefinida",
                            "Senha redefinida com sucesso! Faça login com a nova senha.")

    Button(dlg, text="Redefinir senha", command=reset,
           bg=CLR_ACCENT, fg="white", relief="flat",
           font=("Segoe UI", 10, "bold"), pady=7, cursor="hand2").pack(padx=32, fill=X, pady=(4, 0))
    Button(dlg, text="Cancelar", command=dlg.destroy, relief="flat",
           font=("Segoe UI", 9), pady=4).pack(pady=(6, 0))


# ===========================================================================
# Estilo ttk
# ===========================================================================

def _apply_style(root: Tk):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    style.configure("TNotebook", background=CLR_BG, borderwidth=0)
    style.configure("TNotebook.Tab", font=FONT_NORMAL, padding=[12, 6])
    style.map("TNotebook.Tab", background=[("selected", CLR_ACCENT)],
              foreground=[("selected", "white")])

    style.configure("Treeview", font=FONT_SMALL, rowheight=24, background=CLR_CARD,
                    fieldbackground=CLR_CARD, foreground=CLR_TEXT)
    style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background=CLR_PRIMARY,
                    foreground="white")
    style.map("Treeview", background=[("selected", CLR_ACCENT)])

    style.configure("TPanedwindow", background=CLR_BG)
    style.configure("TCombobox", font=FONT_NORMAL)
    style.configure("TProgressbar", troughcolor=CLR_LIGHT, background=CLR_OK, thickness=14)


# ===========================================================================
# Aplicativo principal
# ===========================================================================

class CreditCardApp:
    def __init__(self, root: Tk, config: dict):
        self.root = root
        self.config = config
        self.db = Database()
        self.ai = AIAdvisor(config)
        self._ai_thread: threading.Thread | None = None

        self.month_var = StringVar(value=current_month())
        self.goal_var  = DoubleVar(value=float(config.get("monthly_goal", 3000.00)))
        self.expense_month_var = StringVar(value=current_month())
        self.expense_scope_var = StringVar(value="")

        self._build_ui()
        self.refresh_all()

    # ------------------------------------------------------------------
    # Layout principal
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.root.configure(bg=CLR_BG)

        # Barra superior
        top = Frame(self.root, bg=CLR_PRIMARY, height=48)
        top.pack(fill=X, side=TOP)
        top.pack_propagate(False)
        self._build_topbar(top)

        # Corpo principal: notebook à esquerda, sidebar IA à direita
        body = Frame(self.root, bg=CLR_BG)
        body.pack(fill=BOTH, expand=True, padx=8, pady=6)

        paned = ttk.PanedWindow(body, orient="horizontal")
        paned.pack(fill=BOTH, expand=True)

        left_frame  = Frame(paned, bg=CLR_BG)
        right_frame = Frame(paned, bg=CLR_CARD, relief="groove", bd=1, width=360)

        paned.add(left_frame,  weight=5)
        paned.add(right_frame, weight=1)

        # Notebook com abas
        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill=BOTH, expand=True)

        self.tab_dash    = Frame(self.notebook, bg=CLR_BG)
        self.tab_exp     = Frame(self.notebook, bg=CLR_BG)
        self.tab_future  = Frame(self.notebook, bg=CLR_BG)
        self.tab_ai      = Frame(self.notebook, bg=CLR_BG)

        self.notebook.add(self.tab_dash,   text="  Dashboard  ")
        self.notebook.add(self.tab_exp,    text="  Gastos  ")
        self.notebook.add(self.tab_future, text="  Próximos meses  ")
        self.notebook.add(self.tab_ai,     text="  Análise IA  ")

        self._build_dashboard_tab()
        self._build_expenses_tab()
        self._build_future_tab()
        self._build_ai_tab()
        self._build_ai_sidebar(right_frame)

    def _build_topbar(self, parent: Frame):
        """Barra superior com mês, meta, ações."""
        # Lado esquerdo
        left = Frame(parent, bg=CLR_PRIMARY)
        left.pack(side=LEFT, padx=8, pady=6)

        Label(left, text="💳", font=("Segoe UI", 16), bg=CLR_PRIMARY, fg="white").pack(side=LEFT)
        Label(left, text="Controle de Cartão com IA", font=("Segoe UI", 12, "bold"),
              bg=CLR_PRIMARY, fg="white").pack(side=LEFT, padx=6)

        sep = Frame(parent, bg="#4a6fa5", width=1)
        sep.pack(side=LEFT, fill=Y, pady=8, padx=6)

        Label(left, text="Mês:", bg=CLR_PRIMARY, fg="white", font=FONT_SMALL).pack(side=LEFT, padx=(12, 2))
        month_entry = Entry(left, textvariable=self.month_var, width=9, font=FONT_NORMAL)
        month_entry.pack(side=LEFT)
        month_entry.bind("<Return>", lambda _: self.refresh_all())

        Button(left, text="Atualizar", command=self.refresh_all,
               bg=CLR_ACCENT, fg="white", relief="flat", font=FONT_SMALL,
               padx=6).pack(side=LEFT, padx=4)

        Label(left, text="Meta:", bg=CLR_PRIMARY, fg="white", font=FONT_SMALL).pack(side=LEFT, padx=(12, 2))
        Entry(left, textvariable=self.goal_var, width=10, font=FONT_NORMAL).pack(side=LEFT)
        Button(left, text="Salvar", command=self.save_goal,
               bg=CLR_OK, fg="white", relief="flat", font=FONT_SMALL,
               padx=6).pack(side=LEFT, padx=4)

        # Lado direito
        right = Frame(parent, bg=CLR_PRIMARY)
        right.pack(side=RIGHT, padx=8, pady=6)

        for label, cmd in [
            ("⚙ Configurações", self.open_settings),
            ("🏷 Categorias", self.open_category_manager),
            ("📊 Exportar Excel", self.export_to_excel),
            ("💾 Backup", self.backup_db),
            ("♻ Restaurar", self.restore_db),
        ]:
            Button(right, text=label, command=cmd,
                   bg=CLR_PRIMARY, fg="white", relief="flat",
                   activebackground="#3d5a80", activeforeground="white",
                   font=FONT_SMALL, padx=6, pady=0).pack(side=LEFT, padx=2)

        # Botão Sair — separado visualmente
        Frame(right, bg="#4a6fa5", width=1).pack(side=LEFT, fill=Y, pady=6, padx=6)
        Button(right, text="✕ Sair", command=self.on_close,
               bg=CLR_DANGER, fg="white", relief="flat",
               activebackground="#c0392b", activeforeground="white",
               font=FONT_SMALL, padx=8, pady=0).pack(side=LEFT, padx=2)

    # ------------------------------------------------------------------
    # Tab Dashboard
    # ------------------------------------------------------------------

    def _build_dashboard_tab(self):
        header = Frame(self.tab_dash, bg=CLR_BG)
        header.pack(fill=X, padx=10, pady=(10, 4))
        Label(header, text="Resumo financeiro", font=FONT_TITLE, bg=CLR_BG, fg=CLR_TEXT).pack(side=LEFT)
        Button(header, text="↺ Atualizar", command=self.refresh_all,
               relief="flat", bg=CLR_ACCENT, fg="white", font=FONT_SMALL,
               padx=8).pack(side=RIGHT)

        # Cartões de indicadores
        self.cards_frame = Frame(self.tab_dash, bg=CLR_BG)
        self.cards_frame.pack(fill=X, padx=10, pady=(0, 4))

        self.card_total        = self._make_card(self.cards_frame, "Gasto no mês",     "R$ 0,00",  CLR_DANGER)
        self.card_goal         = self._make_card(self.cards_frame, "Meta mensal",       "R$ 0,00",  CLR_ACCENT)
        self.card_remaining    = self._make_card(self.cards_frame, "Disponível",        "R$ 0,00",  CLR_OK)
        self.card_percent      = self._make_card(self.cards_frame, "Uso da meta",       "0%",       CLR_WARN)
        self.card_transactions = self._make_card(self.cards_frame, "Lançamentos",       "0",        CLR_PRIMARY)

        # Barra de progresso da meta
        prog_frame = Frame(self.tab_dash, bg=CLR_BG, padx=10)
        prog_frame.pack(fill=X, pady=(0, 4))
        Label(prog_frame, text="Progresso da meta:", font=FONT_SMALL, bg=CLR_BG, fg=CLR_MUTED).pack(anchor=W)
        self.progress_bar = ttk.Progressbar(prog_frame, mode="determinate", maximum=100, length=600)
        self.progress_bar.pack(fill=X, pady=2)

        # Insight textual
        self.insight_var = StringVar(value="")
        self.insight_label = Label(
            self.tab_dash, textvariable=self.insight_var,
            font=FONT_SMALL, bg=CLR_LIGHT, fg=CLR_TEXT,
            anchor=W, justify=LEFT, relief="flat",
            padx=12, pady=8, wraplength=860,
        )
        self.insight_label.pack(fill=X, padx=10, pady=(0, 6))

        # Área de gráficos (será recriada a cada refresh)
        self.chart_frame = Frame(self.tab_dash, bg=CLR_BG)
        self.chart_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 6))

    def _make_card(self, parent: Frame, title: str, value: str, color: str) -> Label:
        card = Frame(parent, bg=CLR_CARD, relief="groove", bd=1, padx=12, pady=10)
        card.pack(side=LEFT, fill=X, expand=True, padx=4, pady=2)

        bar = Frame(card, bg=color, height=4)
        bar.pack(fill=X, side=TOP)

        Label(card, text=title, font=FONT_SMALL, bg=CLR_CARD, fg=CLR_MUTED).pack(anchor=W, pady=(4, 0))
        val_label = Label(card, text=value, font=("Segoe UI", 14, "bold"), bg=CLR_CARD, fg=color)
        val_label.pack(anchor=W)
        return val_label

    # ------------------------------------------------------------------
    # Tab Gastos
    # ------------------------------------------------------------------

    def _build_expenses_tab(self):
        info_frame = Frame(self.tab_exp, bg=CLR_LIGHT, padx=12, pady=10)
        info_frame.pack(fill=X, padx=10, pady=(10, 0))
        Label(
            info_frame,
            text="Fluxo recomendado: atualize os dados importando a fatura em PDF sempre que ela mudar. "
                 "Você também pode importar faturas antigas para enriquecer o histórico e encontrar gastos rotineiros.",
            font=FONT_SMALL,
            bg=CLR_LIGHT,
            fg=CLR_TEXT,
            justify=LEFT,
            wraplength=960,
        ).pack(anchor=W)

        # Formulário de cadastro
        form_frame = Frame(self.tab_exp, bg=CLR_CARD, relief="groove", bd=1, padx=10, pady=8)
        form_frame.pack(fill=X, padx=10, pady=8)
        Label(form_frame, text="Novo lançamento", font=FONT_HEADER, bg=CLR_CARD, fg=CLR_TEXT).pack(anchor=W, pady=(0, 6))

        row1 = Frame(form_frame, bg=CLR_CARD)
        row1.pack(fill=X)

        self.f_date  = self._form_entry(row1, "Data (AAAA-MM-DD)", dt.date.today().strftime("%Y-%m-%d"), 12)
        self.f_desc  = self._form_entry(row1, "Descrição", "", 38)
        self.f_value = self._form_entry(row1, "Valor (R$)", "", 12)

        row2 = Frame(form_frame, bg=CLR_CARD)
        row2.pack(fill=X, pady=(6, 0))

        # Combobox de categoria
        Label(row2, text="Categoria", font=FONT_SMALL, bg=CLR_CARD, fg=CLR_MUTED).pack(side=LEFT, padx=(0, 4))
        self.f_cat_var = StringVar(value="Outros")
        self.f_cat_combo = ttk.Combobox(row2, textvariable=self.f_cat_var, width=22, font=FONT_NORMAL)
        self.f_cat_combo.pack(side=LEFT, padx=(0, 12))

        self.f_card    = self._form_entry(row2, "Cartão", "", 14)
        self.f_install = self._form_entry(row2, "Parcelas", "1", 5)
        self.f_notes   = self._form_entry(row2, "Notas", "", 20)

        btn_row = Frame(form_frame, bg=CLR_CARD)
        btn_row.pack(anchor=W, pady=(8, 0))
        Button(btn_row, text="+ Adicionar", command=self.add_manual_expense,
               bg=CLR_OK, fg="white", relief="flat", font=FONT_NORMAL, padx=10).pack(side=LEFT, padx=(0, 6))
        Button(btn_row, text="🔍 Classificar com IA", command=self.ai_classify_form,
               bg=CLR_ACCENT, fg="white", relief="flat", font=FONT_NORMAL, padx=10).pack(side=LEFT, padx=(0, 6))

        # Treeview de gastos
        tree_frame = Frame(self.tab_exp, bg=CLR_BG)
        tree_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 6))

        tree_toolbar = Frame(tree_frame, bg=CLR_BG)
        tree_toolbar.pack(fill=X, pady=(0, 4))
        Button(tree_toolbar, text="📄 Importar fatura PDF", command=self.import_pdf,
               relief="flat", bg=CLR_ACCENT, fg="white", font=FONT_SMALL, padx=8).pack(side=LEFT, padx=(0, 6))
        Button(tree_toolbar, text="✏ Editar selecionado", command=self.edit_selected_expense,
               relief="flat", bg=CLR_WARN, fg="white", font=FONT_SMALL, padx=8).pack(side=LEFT, padx=(0, 6))
        Button(tree_toolbar, text="🗑 Excluir selecionado", command=self.delete_selected_expense,
               relief="flat", bg=CLR_DANGER, fg="white", font=FONT_SMALL, padx=8).pack(side=LEFT)
        Label(tree_toolbar, text="Ver mês:", font=FONT_SMALL, bg=CLR_BG, fg=CLR_MUTED).pack(side=RIGHT, padx=(8, 4))
        self.expense_month_combo = ttk.Combobox(
            tree_toolbar,
            textvariable=self.expense_month_var,
            width=10,
            state="readonly",
            font=FONT_NORMAL,
        )
        self.expense_month_combo.pack(side=RIGHT)
        self.expense_month_combo.bind("<<ComboboxSelected>>", lambda _: self.refresh_expenses())
        Label(tree_frame, textvariable=self.expense_scope_var,
              font=FONT_SMALL, bg=CLR_BG, fg=CLR_MUTED).pack(anchor=W, pady=(0, 4))

        cols = ("id", "date", "description", "amount", "category", "card", "parcela")
        self.expense_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        col_cfg = {
            "id":          ("ID",       50,  False),
            "date":        ("Data",     90,  True),
            "description": ("Descrição",340, True),
            "amount":      ("Valor",    100, True),
            "category":    ("Categoria",140, True),
            "card":        ("Cartão",   100, True),
            "parcela":     ("Parcela",  70,  True),
        }
        for col, (heading, width, stretch) in col_cfg.items():
            self.expense_tree.heading(col, text=heading, anchor=W,
                                      command=lambda c=col: self._sort_tree(c))
            self.expense_tree.column(col, width=width, stretch=stretch)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",   command=self.expense_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.expense_tree.xview)
        self.expense_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.expense_tree.pack(side=LEFT, fill=BOTH, expand=True)
        vsb.pack(side=RIGHT, fill=Y)

        self.expense_tree.bind("<Double-1>", lambda _: self.edit_selected_expense())
        self._tree_sort_col = "date"
        self._tree_sort_asc = False

    def _form_entry(self, parent: Frame, label: str, default: str, width: int) -> Entry:
        Label(parent, text=label, font=FONT_SMALL, bg=parent.cget("bg"), fg=CLR_MUTED).pack(side=LEFT, padx=(0, 3))
        e = Entry(parent, width=width, font=FONT_NORMAL)
        e.insert(0, default)
        e.pack(side=LEFT, padx=(0, 10))
        return e

    def _sort_tree(self, col: str):
        """Ordena a treeview pela coluna clicada."""
        rows = [(self.expense_tree.set(r, col), r) for r in self.expense_tree.get_children()]
        rows.sort(reverse=(col == self._tree_sort_col and not self._tree_sort_asc))
        self._tree_sort_asc = not (col == self._tree_sort_col and not self._tree_sort_asc)
        self._tree_sort_col = col
        for i, (_, row) in enumerate(rows):
            self.expense_tree.move(row, "", i)

    # ------------------------------------------------------------------
    # Tab Próximos meses
    # ------------------------------------------------------------------

    def _build_future_tab(self):
        Label(self.tab_future, text="Compromissos futuros (parcelas e lançamentos)",
              font=FONT_HEADER, bg=CLR_BG, fg=CLR_TEXT).pack(anchor=W, padx=12, pady=(10, 4))
        Label(
            self.tab_future,
            text="Cada mês abaixo usa sua própria meta. Meses passados ficam congelados; "
                 "meses atual e futuros seguem a meta atual, salvo quando você definir uma meta específica.",
            font=FONT_SMALL,
            bg=CLR_BG,
            fg=CLR_MUTED,
            justify=LEFT,
            wraplength=980,
        ).pack(anchor=W, padx=12, pady=(0, 6))
        self.future_text = Text(self.tab_future, wrap=WORD, font=FONT_MONO,
                                bg=CLR_CARD, fg=CLR_TEXT, relief="groove", bd=1, padx=8, pady=6)
        self.future_text.pack(fill=BOTH, expand=True, padx=10, pady=(0, 8))

    # ------------------------------------------------------------------
    # Tab Análise IA
    # ------------------------------------------------------------------

    def _build_ai_tab(self):
        ctrl = Frame(self.tab_ai, bg=CLR_BG)
        ctrl.pack(fill=X, padx=10, pady=8)
        Label(ctrl, text="Análise detalhada pela IA", font=FONT_HEADER, bg=CLR_BG, fg=CLR_TEXT).pack(side=LEFT)
        Button(ctrl, text="▶ Gerar análise do mês", command=self.generate_ai_analysis,
               bg=CLR_ACCENT, fg="white", relief="flat", font=FONT_NORMAL, padx=10).pack(side=LEFT, padx=8)
        Button(ctrl, text="📅 Análise anual", command=self.generate_yearly_analysis,
               bg=CLR_PRIMARY, fg="white", relief="flat", font=FONT_NORMAL, padx=10).pack(side=LEFT)

        self.ai_status_var = StringVar(value="")
        Label(self.tab_ai, textvariable=self.ai_status_var, font=FONT_SMALL,
              bg=CLR_BG, fg=CLR_WARN).pack(anchor=W, padx=10)

        self.ai_text = Text(self.tab_ai, wrap=WORD, font=FONT_NORMAL,
                            bg=CLR_CARD, fg=CLR_TEXT, relief="groove", bd=1, padx=8, pady=6)
        self.ai_text.pack(fill=BOTH, expand=True, padx=10, pady=(4, 8))

    # ------------------------------------------------------------------
    # Sidebar IA (chat lateral)
    # ------------------------------------------------------------------

    def _build_ai_sidebar(self, parent: Frame):
        parent.configure(bg=CLR_CARD)
        container = Frame(parent, bg=CLR_CARD, padx=8, pady=8)
        container.pack(fill=BOTH, expand=True)

        # Cabeçalho
        header = Frame(container, bg=CLR_CARD)
        header.pack(fill=X)
        Label(header, text="🤖 Assistente IA", font=FONT_HEADER, bg=CLR_CARD, fg=CLR_TEXT).pack(side=LEFT)
        Button(header, text="Limpar", command=self.clear_chat,
               relief="flat", bg=CLR_LIGHT, fg=CLR_MUTED, font=FONT_SMALL).pack(side=RIGHT)

        self.ai_status_sidebar = Label(container, text="", font=FONT_SMALL,
                                       bg=CLR_CARD, fg=CLR_WARN, anchor=W)
        self.ai_status_sidebar.pack(fill=X, pady=(2, 0))

        # Área de chat
        self.ai_chat_text = Text(
            container, wrap=WORD, font=("Segoe UI", 9),
            bg="#fafafa", fg=CLR_TEXT, relief="groove", bd=1,
            state=NORMAL, padx=6, pady=4,
        )
        self.ai_chat_text.pack(fill=BOTH, expand=True, pady=(6, 0))
        self.ai_chat_text.tag_configure("sender",   font=("Segoe UI", 9, "bold"), foreground=CLR_PRIMARY)
        self.ai_chat_text.tag_configure("ai",       font=("Segoe UI", 9),         foreground="#1a252f")
        self.ai_chat_text.tag_configure("user",     font=("Segoe UI", 9),         foreground="#2980b9")
        self.ai_chat_text.tag_configure("system",   font=("Segoe UI", 9, "italic"), foreground=CLR_MUTED)
        self.ai_chat_text.tag_configure("warn",     font=("Segoe UI", 9),         foreground=CLR_DANGER)

        # Campo de entrada
        input_frame = Frame(container, bg=CLR_CARD)
        input_frame.pack(fill=X, pady=(6, 0))

        self.ai_question_var = StringVar()
        self.chat_entry = Entry(input_frame, textvariable=self.ai_question_var,
                                font=FONT_NORMAL, relief="groove", bd=1)
        self.chat_entry.pack(side=LEFT, fill=X, expand=True)
        self.chat_entry.bind("<Return>", lambda _: self.ask_ai_question())

        self.send_btn = Button(input_frame, text="Enviar", command=self.ask_ai_question,
                               bg=CLR_ACCENT, fg="white", relief="flat", font=FONT_SMALL, padx=8)
        self.send_btn.pack(side=RIGHT, padx=(4, 0))

        # Botões rápidos
        quick = Frame(container, bg=CLR_CARD)
        quick.pack(fill=X, pady=(6, 0))
        for label, question in [
            ("📊 Resumo do mês",    "Analise meu mês atual, aponte onde posso economizar e compare com o histórico."),
            ("📅 Análise anual",    "Mostre uma análise dos meus gastos anuais e tendências mês a mês."),
            ("🏷 Por categoria",    "Quais categorias consomem mais do meu orçamento? Dê dicas para reduzir."),
            ("📉 Maiores gastos",   "Quais foram os maiores gastos do mês e são justificáveis?"),
        ]:
            Button(quick, text=label, font=FONT_SMALL, relief="flat",
                   bg=CLR_LIGHT, fg=CLR_TEXT, anchor=W,
                   command=lambda q=question: self.ask_ai_question(q)).pack(fill=X, pady=1)

        # Mensagem inicial
        self._add_chat("IA", "Olá! Sou seu assistente financeiro. Faça uma pergunta sobre seus gastos "
                              "ou use um dos botões rápidos acima. Tenho acesso a todos os seus dados cadastrados.")

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh_all(self):
        try:
            month = month_br_to_db(self.month_var.get())
            goal  = self.db.get_goal(month, self.config.get("monthly_goal", 3000.0))
            self.goal_var.set(goal)
            self._update_category_combo()
            self._update_expense_month_options()
            self.refresh_dashboard()
            self.refresh_expenses()
            self.refresh_future()
        except ValueError as exc:
            messagebox.showerror("Erro de formato", str(exc))

    def _update_category_combo(self):
        cats = get_all_category_names(self.db.get_custom_categories())
        self.f_cat_combo["values"] = cats

    def _update_expense_month_options(self):
        current = self.month_var.get().strip()
        months = [current]
        for row in reversed(self.db.get_all_month_totals()):
            month_br = month_db_to_br(row["month"])
            if month_br not in months:
                months.append(month_br)
        self.expense_month_combo["values"] = months
        if self.expense_month_var.get().strip() not in months:
            self.expense_month_var.set(current)

    def refresh_dashboard(self):
        month_br = self.month_var.get().strip()
        month    = month_br_to_db(month_br)
        goal     = self.db.get_goal(month, self.config.get("monthly_goal", 3000.0))
        total    = self.db.get_month_total(month)
        remaining  = goal - total
        percent    = (total / goal * 100) if goal > 0 else 0
        n_trans    = self.db.count_expenses(month)

        # Atualiza cartões
        self.card_total.config(text=money(total), fg=CLR_DANGER if percent >= 100 else CLR_DANGER)
        self.card_goal.config(text=money(goal))
        self.card_remaining.config(text=money(remaining),
                                   fg=CLR_DANGER if remaining < 0 else CLR_OK)
        self.card_percent.config(text=f"{percent:.1f}%",
                                 fg=CLR_DANGER if percent >= 100 else (CLR_WARN if percent >= 80 else CLR_OK))
        self.card_transactions.config(text=str(n_trans))

        # Barra de progresso
        self.progress_bar["value"] = min(percent, 100)
        bar_style = "danger.TProgressbar" if percent >= 100 else ("warn.TProgressbar" if percent >= 80 else "TProgressbar")
        ttk.Style().configure("danger.TProgressbar", background=CLR_DANGER)
        ttk.Style().configure("warn.TProgressbar",   background=CLR_WARN)

        # Insight
        cat_rows = self.db.get_category_totals(month)
        if cat_rows:
            top_cat = cat_rows[0]
            status  = "✅ Situação dentro da meta." if percent < 80 else (
                      "⚠️ Atenção: perto da meta!" if percent < 100 else "🚨 Meta ultrapassada!")
            self.insight_var.set(
                f"Mês: {month_br}  |  Maior categoria: {top_cat['category']} ({money(top_cat['total'])})  |  "
                f"Uso da meta: {percent:.1f}%  |  {status}"
            )
        else:
            self.insight_var.set(f"Mês: {month_br}  |  Sem lançamentos. Importe uma fatura ou cadastre gastos manualmente.")

        # Limpa e reconstrói gráficos
        for w in self.chart_frame.winfo_children():
            w.destroy()

        if not charts.MATPLOTLIB_AVAILABLE:
            Label(self.chart_frame, text="Instale matplotlib para ver gráficos: pip install matplotlib",
                  bg=CLR_BG, fg=CLR_MUTED, font=FONT_NORMAL).pack(pady=20)
            return

        month_rows = self.db.get_all_month_totals()
        year_rows  = self.db.get_year_totals()
        top_rows   = self.db.get_top_expenses(month, limit=8)

        row1 = Frame(self.chart_frame, bg=CLR_BG)
        row1.pack(fill=BOTH, expand=True)
        row2 = Frame(self.chart_frame, bg=CLR_BG)
        row2.pack(fill=BOTH, expand=True)

        if cat_rows:
            labels = [r["category"] for r in cat_rows]
            totals = [float(r["total"]) for r in cat_rows]
            charts.embed_figure(charts.make_pie_chart(labels, totals, f"Categorias — {month_br}"), row1)
            charts.embed_figure(charts.make_goal_chart(total, goal, f"Meta x Gasto — {month_br}"), row1)

        if top_rows:
            t_labels = [f"{r['description'][:25]}" for r in top_rows]
            t_values = [float(r["amount"]) for r in top_rows]
            charts.embed_figure(charts.make_top_expenses_chart(t_labels, t_values, "Maiores gastos do mês"), row1)

        if month_rows:
            m_labels = [month_db_to_br(r["month"]) for r in month_rows]
            m_values = [float(r["total"]) for r in month_rows]
            charts.embed_figure(charts.make_bar_chart(m_labels, m_values, "Evolução mês a mês", "Mês"), row2)

        if year_rows:
            y_labels = [r["year"] for r in year_rows]
            y_values = [float(r["total"]) for r in year_rows]
            charts.embed_figure(charts.make_bar_chart(y_labels, y_values, "Gastos por ano", "Ano",
                                                      color="#9b59b6"), row2)

    def refresh_expenses(self):
        for item in self.expense_tree.get_children():
            self.expense_tree.delete(item)

        month_br = self.expense_month_var.get().strip() or self.month_var.get().strip()
        month = month_br_to_db(month_br)
        rows = self.db.list_expenses(month)
        total = self.db.get_month_total(month)
        goal = self.db.get_goal(month, self.config.get("monthly_goal", 3000.0))
        percent = (total / goal * 100) if goal > 0 else 0.0
        current_month_db = dt.date.today().strftime("%Y-%m")
        if month < current_month_db:
            status = "meta ultrapassada" if percent > 100 else "meta dentro do limite"
            self.expense_scope_var.set(
                f"{month_br}: {len(rows)} lançamentos | total {money(total)} | meta {money(goal)} | "
                f"{percent:.1f}% da meta | mês fechado: {status}."
            )
        else:
            self.expense_scope_var.set(
                f"{month_br}: {len(rows)} lançamentos | total {money(total)} | meta {money(goal)} | "
                f"{percent:.1f}% da meta."
            )
        for row in rows:
            parcela = f"{row['installment_number']}/{row['installments']}"
            self.expense_tree.insert("", END, iid=str(row["id"]), values=(
                row["id"],
                row["date"],
                row["description"],
                money(row["amount"]),
                row["category"],
                row["card"] or "",
                parcela,
            ))

    def refresh_future(self):
        month = month_br_to_db(self.month_var.get())
        months_ahead = 12
        rows = {
            row["month"]: float(row["total"])
            for row in self.db.get_future_commitments(month, months_ahead=18)
        }
        base_month = dt.datetime.strptime(month + "-01", "%Y-%m-%d").date()
        recurring = self.db.get_recurring_expenses(min_months=2, limit=8)

        self.future_text.config(state=NORMAL)
        self.future_text.delete("1.0", END)
        self.future_text.insert(END, "Projeção dos próximos meses com base na meta vigente de cada mês:\n\n")

        for i in range(months_ahead):
            month_date = add_months(base_month, i)
            month_key = month_date.strftime("%Y-%m")
            month_goal = self.db.get_goal(month_key, self.config.get("monthly_goal", 3000.0))
            committed = rows.get(month_key, 0.0)
            available = month_goal - committed
            percent = (committed / month_goal * 100) if month_goal > 0 else 0.0
            status = "🚨" if percent >= 100 else ("⚠️" if percent >= 80 else "✅")
            self.future_text.insert(
                END,
                f"{status} {month_db_to_br(month_key)}\n"
                f"   Meta do mês        : {money(month_goal)}\n"
                f"   Já comprometido    : {money(committed)} ({percent:.1f}% da meta)\n"
                f"   Ainda pode gastar  : {money(available)}\n\n"
            )

        self.future_text.insert(END, "Possíveis gastos rotineiros detectados no histórico:\n\n")
        if recurring:
            for row in recurring:
                self.future_text.insert(
                    END,
                    f"• {row['description']} | {row['category']} | "
                    f"apareceu em {row['months']} meses | média {money(row['avg_per_month'])}/mês | "
                    f"último registro {row['last_date']}\n"
                )
        else:
            self.future_text.insert(END, "Nenhum padrão recorrente forte identificado ainda.\n")

        self.future_text.config(state=DISABLED)

    # ------------------------------------------------------------------
    # Ações — gastos
    # ------------------------------------------------------------------

    def add_manual_expense(self):
        try:
            date         = self.f_date.get().strip()
            dt.datetime.strptime(date, "%Y-%m-%d")
            description  = self.f_desc.get().strip()
            amount       = parse_money(self.f_value.get())
            category     = self.f_cat_var.get().strip() or classify_expense(description, self.db.get_custom_categories())
            card         = self.f_card.get().strip()
            installments = int(self.f_install.get().strip() or "1")
            notes        = self.f_notes.get().strip()

            if not description:
                raise ValueError("Informe a descrição do gasto.")
            if amount <= 0:
                raise ValueError("O valor deve ser positivo.")
            if installments < 1:
                raise ValueError("Número de parcelas inválido.")

            self.db.add_expense(date, description, amount, category, card, installments, notes)

            # limpa só os campos de valor e descrição
            self.f_desc.delete(0, END)
            self.f_value.delete(0, END)
            self.f_install.delete(0, END)
            self.f_install.insert(0, "1")
            self.f_notes.delete(0, END)
            self.refresh_all()

        except ValueError as exc:
            messagebox.showerror("Erro de validação", str(exc))
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))

    def ai_classify_form(self):
        """Usa a IA para sugerir categoria com base na descrição do formulário."""
        desc = self.f_desc.get().strip()
        if not desc:
            messagebox.showinfo("IA", "Digite a descrição do gasto primeiro.")
            return
        all_cats = get_all_category_names(self.db.get_custom_categories())

        def worker():
            cat = self.ai.classify_expense(desc, all_cats)
            self.root.after(0, lambda: self._apply_ai_category(cat, all_cats))

        threading.Thread(target=worker, daemon=True).start()
        self.f_cat_var.set("Classificando...")

    def _apply_ai_category(self, category: str, all_cats: list[str]):
        # Se for nova categoria, oferece salvar
        if category not in all_cats:
            if messagebox.askyesno(
                "Nova categoria",
                f"A IA sugeriu a categoria '{category}', que não existe ainda.\n"
                f"Deseja criá-la automaticamente com palavras-chave sugeridas?",
            ):
                kws = self.ai.suggest_category_keywords(category)
                self.db.save_custom_category(category, kws)
        self.f_cat_var.set(category)
        self._update_category_combo()

    def edit_selected_expense(self):
        selected = self.expense_tree.selection()
        if not selected:
            messagebox.showinfo("Editar", "Selecione um lançamento para editar.")
            return
        expense_id = int(self.expense_tree.item(selected[0])["values"][0])
        row = self.db.get_expense_by_id(expense_id)
        if not row:
            return
        _EditExpenseDialog(self.root, self.db, row, self.db.get_custom_categories(), self.refresh_all)

    def delete_selected_expense(self):
        selected = self.expense_tree.selection()
        if not selected:
            messagebox.showinfo("Excluir", "Selecione um lançamento para excluir.")
            return
        expense_id = int(self.expense_tree.item(selected[0])["values"][0])
        if messagebox.askyesno("Confirmar exclusão", f"Excluir lançamento ID {expense_id}?"):
            self.db.delete_expense(expense_id)
            self.refresh_all()

    def save_goal(self):
        try:
            month = month_br_to_db(self.month_var.get())
            goal  = float(self.goal_var.get())
            if goal <= 0:
                raise ValueError("Meta deve ser maior que zero.")
            self.db.set_goal(month, goal)
            if month >= dt.date.today().strftime("%Y-%m"):
                self.config["monthly_goal"] = goal
            save_config(self.config)
            self.refresh_all()
            messagebox.showinfo("Meta", f"Meta de {money(goal)} salva para {month_db_to_br(month)}.")
        except ValueError as exc:
            messagebox.showerror("Erro", str(exc))

    # ------------------------------------------------------------------
    # Importação de PDF
    # ------------------------------------------------------------------

    def import_pdf(self):
        if not PDFPLUMBER_AVAILABLE:
            messagebox.showerror("Dependência ausente",
                                 "Instale pdfplumber para importar PDFs:\npip install pdfplumber")
            return

        file_path = filedialog.askopenfilename(
            title="Selecione a fatura em PDF",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")],
        )
        if not file_path:
            return

        try:
            ref_month = month_br_to_db(self.month_var.get())
            ref_year = int(ref_month[:4])
            expenses, raw_text = parse_pdf_invoice(
                file_path,
                self.db.get_custom_categories(),
                reference_year=ref_year,
            )

            if not expenses:
                if messagebox.askyesno(
                    "Sem resultados automáticos",
                    "Nenhum gasto foi identificado automaticamente.\n"
                    "Deseja enviar o texto do PDF para a IA tentar extrair os gastos?",
                ):
                    self._ask_ai_to_parse_pdf(raw_text)
                return

            # Mostra janela de revisão antes de salvar
            _PDFReviewDialog(
                self.root, expenses, raw_text, self.db,
                self.db.get_custom_categories(), self.ai, self.refresh_all
            )

        except Exception as exc:
            messagebox.showerror("Erro ao importar PDF", str(exc))

    def _ask_ai_to_parse_pdf(self, raw_text: str):
        self._set_ai_busy("Analisando PDF com IA...")

        def worker():
            answer = self.ai.review_pdf_expenses(raw_text, [])
            self.root.after(0, lambda: self._on_ai_done_generic(answer))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # IA — análise em tabs
    # ------------------------------------------------------------------

    def generate_ai_analysis(self):
        self._set_ai_tab_busy("Gerando análise do mês...")
        summary = self._make_summary()

        def worker():
            prompt = (
                "Analise os dados financeiros abaixo e:\n"
                "1. Aponte os maiores problemas de gasto.\n"
                "2. Identifique categorias preocupantes.\n"
                "3. Diga se a pessoa está próxima ou acima da meta mensal.\n"
                "4. Sugira cortes realistas e práticos.\n"
                "5. Alerte sobre parcelas que comprometem meses futuros.\n\n"
                f"{summary}"
            )
            result = self.ai.analyze(prompt)
            self.root.after(0, lambda: self._on_ai_tab_done(summary, result))

        threading.Thread(target=worker, daemon=True).start()

    def generate_yearly_analysis(self):
        self._set_ai_tab_busy("Gerando análise anual...")
        year = current_year()
        year_cats  = self.db.get_year_category_totals(year)
        month_rows = self.db.get_all_month_totals()
        year_rows  = self.db.get_year_totals()

        cats_str = "\n".join(f"- {r['category']}: {money(r['total'])}" for r in year_cats)
        months_str = "\n".join(f"- {month_db_to_br(r['month'])}: {money(r['total'])}" for r in month_rows)
        years_str  = "\n".join(f"- {r['year']}: {money(r['total'])}" for r in year_rows)

        context = (
            f"ANÁLISE ANUAL — {year}\n\n"
            f"Gastos por categoria no ano:\n{cats_str}\n\n"
            f"Evolução mês a mês:\n{months_str}\n\n"
            f"Totais por ano:\n{years_str}"
        )

        def worker():
            prompt = (
                f"Faça uma análise anual detalhada dos gastos abaixo.\n"
                f"Aponte tendências, meses problemáticos, categorias que mais cresceram e sugestões de melhoria.\n\n"
                f"{context}"
            )
            result = self.ai.analyze(prompt)
            self.root.after(0, lambda: self._on_ai_tab_done(context, result))

        threading.Thread(target=worker, daemon=True).start()

    def _set_ai_tab_busy(self, msg: str):
        self.ai_status_var.set(f"⏳ {msg}")
        self.ai_text.config(state=NORMAL)
        self.ai_text.delete("1.0", END)
        self.ai_text.insert(END, f"{msg}\n")
        self.ai_text.config(state=DISABLED)
        self.root.update_idletasks()

    def _on_ai_tab_done(self, summary: str, result: str):
        self.ai_status_var.set("")
        self.ai_text.config(state=NORMAL)
        self.ai_text.delete("1.0", END)
        self.ai_text.insert(END, "DADOS ENVIADOS PARA A IA:\n")
        self.ai_text.insert(END, summary + "\n\n")
        self.ai_text.insert(END, "─" * 60 + "\nRESPOSTA DA IA:\n\n")
        self.ai_text.insert(END, result)
        self.ai_text.config(state=DISABLED)

    # ------------------------------------------------------------------
    # IA — chat lateral
    # ------------------------------------------------------------------

    def ask_ai_question(self, preset: str | None = None):
        question = preset or self.ai_question_var.get().strip()
        if not question:
            return
        self.ai_question_var.set("")

        self._add_chat("Você", question, tag="user")
        self._set_ai_busy("Consultando IA...")

        summary = self._make_summary()
        prompt  = self.ai.build_financial_summary_prompt(summary, question)

        def worker():
            answer = self.ai.analyze(prompt)
            self.root.after(0, lambda: self._on_ai_response(answer))

        threading.Thread(target=worker, daemon=True).start()

    def _set_ai_busy(self, msg: str):
        self.ai_status_sidebar.config(text=f"⏳ {msg}")
        self.send_btn.config(state=DISABLED)
        self.root.update_idletasks()

    def _on_ai_response(self, answer: str):
        self.ai_status_sidebar.config(text="")
        self.send_btn.config(state=NORMAL)
        tag = "warn" if answer.startswith("⚠️") else "ai"
        self._add_chat("IA", answer, tag=tag)

    def _on_ai_done_generic(self, answer: str):
        self.ai_status_sidebar.config(text="")
        self.send_btn.config(state=NORMAL)
        self._add_chat("IA", answer, tag="ai")

    def _add_chat(self, sender: str, message: str, tag: str = "ai"):
        self.ai_chat_text.config(state=NORMAL)
        self.ai_chat_text.insert(END, f"\n{sender}:\n", "sender")
        self.ai_chat_text.insert(END, message + "\n", tag)
        self.ai_chat_text.see(END)
        self.ai_chat_text.config(state=DISABLED)

    def clear_chat(self):
        self.ai_chat_text.config(state=NORMAL)
        self.ai_chat_text.delete("1.0", END)
        self.ai_chat_text.config(state=DISABLED)
        self._add_chat("IA", "Chat limpo. Como posso ajudar?")

    # ------------------------------------------------------------------
    # Resumo financeiro para a IA
    # ------------------------------------------------------------------

    def _make_summary(self) -> str:
        month_br   = self.month_var.get().strip()
        month      = month_br_to_db(month_br)
        year       = current_year()
        goal       = self.db.get_goal(month, self.config.get("monthly_goal", 3000.0))
        total      = self.db.get_month_total(month)
        cat_rows   = self.db.get_category_totals(month)
        future     = self.db.get_future_commitments(month, 12)
        year_cats  = self.db.get_year_category_totals(year)
        month_rows = self.db.get_all_month_totals()
        top_rows   = self.db.get_top_expenses(month, limit=15)
        recurring  = self.db.get_recurring_expenses(min_months=2, limit=10)
        percent    = (total / goal * 100) if goal > 0 else 0

        lines = [
            f"=== DADOS FINANCEIROS ===",
            f"Mês analisado : {month_br}",
            f"Meta mensal   : {money(goal)}",
            f"Total gasto   : {money(total)}  ({percent:.1f}% da meta)",
            f"Disponível    : {money(goal - total)}",
            "",
            "Gastos por categoria no mês:",
        ]
        for r in cat_rows:
            pct = float(r["total"]) / total * 100 if total else 0
            lines.append(f"  {r['category']}: {money(r['total'])} ({pct:.1f}%)")

        lines.append("\nGastos por categoria no ano:")
        for r in year_cats:
            lines.append(f"  {r['category']}: {money(r['total'])}")

        lines.append("\nEvolução mês a mês (histórico):")
        for r in month_rows:
            lines.append(f"  {month_db_to_br(r['month'])}: {money(r['total'])}")

        lines.append("\nCompromissos futuros (parcelas):")
        for r in future:
            lines.append(f"  {month_db_to_br(r['month'])}: {money(r['total'])}")

        lines.append("\nPossíveis gastos rotineiros no histórico:")
        for r in recurring:
            lines.append(
                f"  {r['description']} | {r['category']} | "
                f"{r['months']} meses | média {money(r['avg_per_month'])}/mês"
            )

        lines.append(f"\nMaiores gastos do mês ({month_br}):")
        for r in top_rows:
            lines.append(f"  {r['date']} | {r['description']} | {r['category']} | {money(r['amount'])}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Exportação Excel
    # ------------------------------------------------------------------

    def export_to_excel(self):
        try:
            import pandas as pd
        except ImportError:
            messagebox.showerror("Dependência ausente",
                                 "Instale pandas e openpyxl para exportar:\npip install pandas openpyxl")
            return

        month_br = self.month_var.get().strip()
        escolha = messagebox.askyesnocancel(
            "Exportar Excel",
            f"Exportar apenas o mês atual ({month_br})?\n\n"
            "Sim → só o mês atual\nNão → todo o histórico\nCancelar → cancelar",
        )
        if escolha is None:
            return

        if escolha:
            rows = self.db.list_expenses(month_br_to_db(month_br))
            sugestao = f"gastos_{month_br.replace('/', '-')}.xlsx"
        else:
            rows = self.db.list_expenses()
            sugestao = "gastos_completo.xlsx"

        if not rows:
            messagebox.showinfo("Exportar", "Não há lançamentos para exportar.")
            return

        dest = filedialog.asksaveasfilename(
            title="Salvar Excel",
            initialfile=sugestao,
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")],
        )
        if not dest:
            return

        data = []
        for r in rows:
            data.append({
                "ID":           r["id"],
                "Data":         r["date"],
                "Descrição":    r["description"],
                "Valor (R$)":   round(float(r["amount"]), 2),
                "Categoria":    r["category"],
                "Cartão":       r["card"] or "",
                "Parcelas":     r["installments"],
                "Nº Parcela":   r["installment_number"],
                "Notas":        r["notes"] or "",
                "Criado em":    r["created_at"],
            })

        df = pd.DataFrame(data)

        try:
            with pd.ExcelWriter(dest, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Lançamentos")
                ws = writer.sheets["Lançamentos"]

                # Ajusta largura das colunas automaticamente
                for col_cells in ws.columns:
                    max_len = max(len(str(c.value or "")) for c in col_cells)
                    ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 60)

            messagebox.showinfo("Exportar Excel", f"Arquivo salvo em:\n{dest}")
        except Exception as exc:
            messagebox.showerror("Erro ao exportar", str(exc))

    # ------------------------------------------------------------------
    # Backup e restauração
    # ------------------------------------------------------------------

    def backup_db(self):
        ts   = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = BACKUP_DIR / f"cartao_backup_{ts}.db"
        shutil.copy2(DB_PATH, dest)
        _write_backup_metadata(dest, self.config, "backup_manual")
        messagebox.showinfo("Backup", f"Backup criado em:\n{dest}")

    def restore_db(self):
        path = filedialog.askopenfilename(
            title="Selecione um backup .db",
            initialdir=BACKUP_DIR,
            filetypes=[("SQLite DB", "*.db"), ("Todos", "*.*")],
        )
        if not path:
            return
        if messagebox.askyesno("Restaurar", "Isso substituirá o banco de dados atual. Continuar?"):
            self.db.close()
            shutil.copy2(path, DB_PATH)
            self.db = Database()
            self.refresh_all()
            messagebox.showinfo("Restaurar", "Backup restaurado com sucesso.")

    def delete_all_data(self):
        if messagebox.askyesno(
            "Apagar TODOS os dados",
            "⚠️ Isso apagará TODOS os lançamentos e metas. Esta ação não pode ser desfeita!\n\n"
            "Deseja continuar?",
        ):
            confirm = messagebox.askyesno("Confirmação final", "Tem certeza absoluta? TODOS os dados serão perdidos.")
            if confirm:
                self.db.delete_all()
                self.refresh_all()
                messagebox.showinfo("Dados apagados", "Todos os dados foram removidos.")

    # ------------------------------------------------------------------
    # Configurações
    # ------------------------------------------------------------------

    def open_settings(self):
        dlg = Toplevel(self.root)
        dlg.title("Configurações")
        dlg.geometry("720x500")
        dlg.minsize(660, 460)
        dlg.grab_set()

        pad = {"padx": 14, "pady": 4}
        Label(dlg, text="Configurações", font=FONT_TITLE).pack(anchor=W, **pad)

        notebook = ttk.Notebook(dlg)
        notebook.pack(fill=BOTH, expand=True, padx=14, pady=(0, 10))

        tab_ai = Frame(notebook, bg=CLR_CARD)
        tab_user = Frame(notebook, bg=CLR_CARD)
        tab_manut = Frame(notebook, bg=CLR_CARD)
        notebook.add(tab_ai, text="  IA  ")
        notebook.add(tab_user, text="  Usuário  ")
        notebook.add(tab_manut, text="  Manutenção  ")

        ai_vars = {}
        for label, key, secret in [
            ("URL da API:", "api_base_url", False),
            ("API Key:", "api_key", True),
            ("Modelo:", "model", False),
        ]:
            Label(tab_ai, text=label, font=FONT_SMALL, fg=CLR_MUTED, bg=CLR_CARD).pack(anchor=W, **pad)
            v = StringVar(value=self.config.get(key, ""))
            Entry(tab_ai, textvariable=v, width=70, show="●" if secret else "").pack(
                anchor=W, padx=14, pady=2
            )
            ai_vars[key] = v

        info = (
            "A URL pode ser a base (ex: https://api.xxx.com/v1) ou o endpoint completo.\n"
            "O sistema detecta automaticamente e completa se necessário.\n\n"
            "• Ollama local:   http://localhost:11434/api/chat        modelo: llama3.1:8b\n"
            "• Xiaomi MiMo:    https://api.xiaomimimo.com/v1          modelo: mimo-v2.5-pro\n"
            "• OpenRouter:     https://openrouter.ai/api/v1           modelo: openai/gpt-4o\n"
            "• OpenAI:         https://api.openai.com/v1              modelo: gpt-4o-mini"
        )
        Label(tab_ai, text=info, justify=LEFT, font=FONT_SMALL, fg=CLR_MUTED,
              bg=CLR_LIGHT, padx=10, pady=8).pack(fill=X, padx=14, pady=8)

        user_vars = {
            "user_name": StringVar(value=self.config.get("user_name", "")),
            "user_email": StringVar(value=self.config.get("user_email", "")),
            "user_phone": StringVar(value=self.config.get("user_phone", "")),
        }
        Label(tab_user, text="Dados básicos", font=FONT_HEADER, bg=CLR_CARD, fg=CLR_TEXT).pack(anchor=W, **pad)
        for label, key in [
            ("Nome:", "user_name"),
            ("E-mail:", "user_email"),
            ("Telefone:", "user_phone"),
        ]:
            Label(tab_user, text=label, font=FONT_SMALL, fg=CLR_MUTED, bg=CLR_CARD).pack(anchor=W, **pad)
            Entry(tab_user, textvariable=user_vars[key], width=55).pack(anchor=W, padx=14, pady=2)

        Label(
            tab_user,
            text="Esses dados ficam salvos apenas neste computador. Eles ajudam a identificar backups e\n"
                 "restaurações futuras, mas não recuperam a senha automaticamente sem um serviço externo.",
            justify=LEFT,
            font=FONT_SMALL,
            fg=CLR_MUTED,
            bg=CLR_LIGHT,
            padx=10,
            pady=8,
        ).pack(fill=X, padx=14, pady=8)

        Label(tab_user, text="Alterar senha de acesso:", font=FONT_SMALL, fg=CLR_MUTED, bg=CLR_CARD).pack(
            anchor=W, padx=14, pady=(2, 4)
        )
        pw_var = StringVar()
        Entry(tab_user, textvariable=pw_var, show="●", width=30).pack(anchor=W, padx=14, pady=2)

        recovery_status_var = StringVar(
            value="Código de recuperação configurado."
            if self.config.get("recovery_hash")
            else "Nenhum código de recuperação ativo. Gere um novo abaixo."
        )
        Label(tab_user, textvariable=recovery_status_var, font=FONT_SMALL, fg=CLR_TEXT, bg=CLR_CARD).pack(
            anchor=W, padx=14, pady=(10, 4)
        )

        pending_recovery_key = {"value": None}
        recovery_key_var = StringVar(value="")

        def generate_new_recovery_key():
            new_key = generate_recovery_key()
            pending_recovery_key["value"] = new_key
            recovery_key_var.set(new_key)
            recovery_status_var.set("Novo código gerado. Salve as configurações para concluir.")

        def copy_pending_recovery_key():
            code = recovery_key_var.get().strip()
            if not code:
                messagebox.showinfo(
                    "Código de recuperação",
                    "Gere um novo código primeiro.",
                    parent=dlg,
                )
                return
            dlg.clipboard_clear()
            dlg.clipboard_append(code)
            messagebox.showinfo(
                "Código copiado",
                "O código de recuperação foi copiado para a área de transferência.",
                parent=dlg,
            )

        Button(
            tab_user,
            text="Gerar novo código de recuperação",
            command=generate_new_recovery_key,
            bg=CLR_ACCENT,
            fg="white",
            relief="flat",
            font=FONT_SMALL,
            padx=10,
            pady=4,
        ).pack(anchor=W, padx=14, pady=(0, 8))

        Label(
            tab_user,
            text="Novo código gerado:",
            font=FONT_SMALL,
            fg=CLR_MUTED,
            bg=CLR_CARD,
        ).pack(anchor=W, padx=14, pady=(2, 2))
        Entry(
            tab_user,
            textvariable=recovery_key_var,
            font=("Consolas", 12),
            width=30,
            state="readonly",
            readonlybackground=CLR_LIGHT,
        ).pack(anchor=W, padx=14, pady=(0, 6))
        Button(
            tab_user,
            text="Copiar código",
            command=copy_pending_recovery_key,
            bg=CLR_LIGHT,
            fg=CLR_PRIMARY,
            relief="flat",
            font=FONT_SMALL,
            padx=10,
            pady=4,
        ).pack(anchor=W, padx=14, pady=(0, 10))

        # --- aba Manutenção ---
        Label(tab_manut, text="Manutenção do banco de dados", font=FONT_HEADER,
              bg=CLR_CARD, fg=CLR_TEXT).pack(anchor=W, padx=14, pady=(12, 2))
        Label(
            tab_manut,
            text="As operações abaixo apagam dados permanentemente.\nFaça um backup antes de prosseguir.",
            justify=LEFT, font=FONT_SMALL, fg=CLR_DANGER,
            bg=CLR_LIGHT, padx=10, pady=8,
        ).pack(fill=X, padx=14, pady=(0, 12))

        def _make_clear_btn(parent, label, descricao, action):
            row = Frame(parent, bg=CLR_CARD)
            row.pack(fill=X, padx=14, pady=4)
            Label(row, text=descricao, font=FONT_SMALL, fg=CLR_MUTED,
                  bg=CLR_CARD, width=38, anchor=W).pack(side=LEFT)
            def _confirmar(lbl=label, fn=action):
                if messagebox.askyesno(
                    "Confirmar exclusão",
                    f"Tem certeza que deseja apagar {lbl}?\n\nEssa ação não pode ser desfeita.",
                    icon="warning", parent=dlg,
                ):
                    fn()
                    self.refresh_all()
                    messagebox.showinfo("Manutenção", f"{lbl} apagado(s) com sucesso.", parent=dlg)
            Button(row, text=f"Apagar", command=_confirmar,
                   bg=CLR_DANGER, fg="white", relief="flat",
                   font=FONT_SMALL, padx=10, pady=3).pack(side=RIGHT)

        _make_clear_btn(tab_manut, "todos os lançamentos",
                        "Lançamentos (expenses):", self.db.clear_expenses)
        _make_clear_btn(tab_manut, "todas as metas mensais",
                        "Metas mensais (monthly_goals):", self.db.clear_goals)
        _make_clear_btn(tab_manut, "todas as categorias personalizadas",
                        "Categorias personalizadas:", self.db.clear_custom_categories)

        ttk.Separator(tab_manut, orient="horizontal").pack(fill=X, padx=14, pady=12)

        def _apagar_tudo_manut():
            if messagebox.askyesno(
                "Apagar tudo",
                "Isso irá apagar TODOS os lançamentos, metas e categorias personalizadas.\n\nDeseja continuar?",
                icon="warning", parent=dlg,
            ):
                self.db.clear_expenses()
                self.db.clear_goals()
                self.db.clear_custom_categories()
                self.refresh_all()
                messagebox.showinfo("Manutenção", "Todos os dados do banco foram apagados.", parent=dlg)

        Button(tab_manut, text="🗑 Apagar TUDO (lançamentos + metas + categorias)",
               command=_apagar_tudo_manut,
               bg=CLR_DANGER, fg="white", relief="flat",
               font=FONT_SMALL, padx=12, pady=5).pack(anchor=W, padx=14)

        btn_frame = Frame(dlg, bg=CLR_BG)
        btn_frame.pack(fill=X, padx=14, pady=(0, 12))

        def save():
            for key, var in ai_vars.items():
                self.config[key] = var.get().strip()

            name = user_vars["user_name"].get().strip()
            email = user_vars["user_email"].get().strip()
            phone = user_vars["user_phone"].get().strip()

            if email and "@" not in email:
                messagebox.showerror("Usuário", "Informe um e-mail válido.", parent=dlg)
                return

            self.config["user_name"] = name
            self.config["user_email"] = email
            self.config["user_phone"] = phone

            if pw_var.get().strip():
                if len(pw_var.get().strip()) < 4:
                    messagebox.showerror("Senha", "A senha deve ter pelo menos 4 caracteres.", parent=dlg)
                    return
                self.config["password_hash"] = hash_password(pw_var.get().strip())

            generated_key = pending_recovery_key["value"]
            if generated_key:
                self.config["recovery_hash"] = hash_password(generated_key)
            elif not self.config.get("recovery_hash") and self.config.get("password_hash"):
                generated_key = generate_recovery_key()
                self.config["recovery_hash"] = hash_password(generated_key)

            save_config(self.config)
            self.ai = AIAdvisor(self.config)
            dlg.destroy()

            if generated_key:
                _show_recovery_key(self.root, generated_key)
            messagebox.showinfo("Configurações", "Configurações salvas com sucesso.", parent=self.root)

        Button(btn_frame, text="Salvar", command=save,
               bg=CLR_OK, fg="white", relief="flat", font=FONT_NORMAL, padx=12).pack(side=LEFT, padx=6)
        Button(btn_frame, text="Cancelar", command=dlg.destroy,
               relief="flat", font=FONT_NORMAL, padx=12).pack(side=LEFT)
        Button(btn_frame, text="🗑 Apagar TODOS os dados", command=self.delete_all_data,
               bg=CLR_DANGER, fg="white", relief="flat", font=FONT_SMALL, padx=10).pack(side=RIGHT)

    def open_category_manager(self):
        _CategoryManagerDialog(self.root, self.db, self.ai, self.refresh_all)

    # ------------------------------------------------------------------
    # Encerramento
    # ------------------------------------------------------------------

    def on_close(self):
        self.db.close()
        self.root.destroy()


# ===========================================================================
# Diálogo de edição de lançamento
# ===========================================================================

class _EditExpenseDialog:
    def __init__(self, root, db: Database, row, custom_cats: dict, on_save):
        self.db = db
        self.expense_id = row["id"]
        self.on_save = on_save

        dlg = Toplevel(root)
        dlg.title(f"Editar lançamento #{row['id']}")
        dlg.geometry("520x340")
        dlg.grab_set()
        self.dlg = dlg

        pad = {"padx": 14, "pady": 4}
        Label(dlg, text="Editar lançamento", font=FONT_HEADER).pack(anchor=W, **pad)

        self.v_date  = StringVar(value=row["date"])
        self.v_desc  = StringVar(value=row["description"])
        self.v_amt   = StringVar(value=f"{row['amount']:.2f}")
        self.v_cat   = StringVar(value=row["category"])
        self.v_card  = StringVar(value=row["card"] or "")
        self.v_notes = StringVar(value=row["notes"] or "")

        fields = [
            ("Data (AAAA-MM-DD):", self.v_date),
            ("Descrição:",         self.v_desc),
            ("Valor (R$):",        self.v_amt),
            ("Cartão:",            self.v_card),
            ("Notas:",             self.v_notes),
        ]
        for label, var in fields:
            Label(dlg, text=label, font=FONT_SMALL, fg=CLR_MUTED).pack(anchor=W, **pad)
            Entry(dlg, textvariable=var, width=55, font=FONT_NORMAL).pack(anchor=W, padx=14, pady=1)

        Label(dlg, text="Categoria:", font=FONT_SMALL, fg=CLR_MUTED).pack(anchor=W, **pad)
        cat_combo = ttk.Combobox(dlg, textvariable=self.v_cat, width=30, font=FONT_NORMAL,
                                 values=get_all_category_names(custom_cats))
        cat_combo.pack(anchor=W, padx=14, pady=1)

        btn = Frame(dlg)
        btn.pack(pady=12)
        Button(btn, text="Salvar", command=self._save, bg=CLR_OK, fg="white",
               relief="flat", font=FONT_NORMAL, padx=12).pack(side=LEFT, padx=6)
        Button(btn, text="Cancelar", command=dlg.destroy,
               relief="flat", font=FONT_NORMAL, padx=12).pack(side=LEFT)

    def _save(self):
        try:
            date  = self.v_date.get().strip()
            dt.datetime.strptime(date, "%Y-%m-%d")
            desc  = self.v_desc.get().strip()
            amt   = parse_money(self.v_amt.get())
            cat   = self.v_cat.get().strip()
            card  = self.v_card.get().strip()
            notes = self.v_notes.get().strip()

            if not desc:
                raise ValueError("Descrição não pode ser vazia.")
            if amt <= 0:
                raise ValueError("Valor deve ser positivo.")

            self.db.edit_expense(self.expense_id, date, desc, amt, cat, card, notes)
            self.on_save()
            self.dlg.destroy()

        except ValueError as exc:
            messagebox.showerror("Erro", str(exc), parent=self.dlg)


# ===========================================================================
# Diálogo de revisão de PDF
# ===========================================================================

class _PDFReviewDialog:
    """Mostra os gastos extraídos do PDF para revisão antes de salvar."""

    def __init__(self, root, expenses: list[dict], raw_text: str,
                 db: Database, custom_cats: dict, ai: AIAdvisor, on_save):
        self.db = db
        self.expenses = expenses
        self.on_save = on_save
        self.ai = ai
        self.raw_text = raw_text
        self.custom_cats = custom_cats

        dlg = Toplevel(root)
        dlg.title(f"Revisão de importação PDF — {len(expenses)} gastos encontrados")
        dlg.geometry("920x560")
        dlg.grab_set()
        self.dlg = dlg

        Label(dlg, text=f"PDF importado: {len(expenses)} lançamentos identificados",
              font=FONT_HEADER).pack(anchor=W, padx=10, pady=8)
        Label(dlg, text="Revise abaixo. Duplo clique para editar. Depois clique em Salvar tudo.",
              font=FONT_SMALL, fg=CLR_MUTED).pack(anchor=W, padx=10)

        # Treeview de revisão
        cols = ("date", "description", "amount", "category")
        tree = ttk.Treeview(dlg, columns=cols, show="headings", height=16)
        for col, heading, width in [
            ("date", "Data", 100), ("description", "Descrição", 380),
            ("amount", "Valor", 100), ("category", "Categoria", 160),
        ]:
            tree.heading(col, text=heading)
            tree.column(col, width=width)
        tree.pack(fill=BOTH, expand=True, padx=10, pady=6)
        self.tree = tree

        for i, exp in enumerate(expenses):
            tree.insert("", END, iid=str(i), values=(
                exp["date"], exp["description"],
                money(exp["amount"]), exp["category"],
            ))

        tree.bind("<Double-1>", self._on_double_click)

        btn_frame = Frame(dlg)
        btn_frame.pack(fill=X, padx=10, pady=8)

        Button(btn_frame, text="🤖 Revisar com IA", command=self._ai_review,
               bg=CLR_ACCENT, fg="white", relief="flat", font=FONT_NORMAL, padx=10).pack(side=LEFT, padx=4)
        Button(btn_frame, text="✅ Salvar tudo", command=self._save_all,
               bg=CLR_OK, fg="white", relief="flat", font=FONT_NORMAL, padx=10).pack(side=LEFT, padx=4)
        Button(btn_frame, text="Cancelar", command=dlg.destroy,
               relief="flat", font=FONT_NORMAL, padx=10).pack(side=LEFT)

        self.status_var = StringVar()
        Label(dlg, textvariable=self.status_var, font=FONT_SMALL, fg=CLR_WARN).pack(anchor=W, padx=10)

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        exp = self.expenses[idx]
        # Mini diálogo inline de edição
        dlg2 = Toplevel(self.dlg)
        dlg2.title("Editar linha do PDF")
        dlg2.geometry("480x260")
        dlg2.grab_set()

        vars_ = {
            "date":        StringVar(value=exp["date"]),
            "description": StringVar(value=exp["description"]),
            "amount":      StringVar(value=f"{exp['amount']:.2f}"),
            "category":    StringVar(value=exp["category"]),
        }
        for label, key in [("Data:", "date"), ("Descrição:", "description"),
                            ("Valor:", "amount")]:
            Label(dlg2, text=label, font=FONT_SMALL).pack(anchor=W, padx=14, pady=3)
            Entry(dlg2, textvariable=vars_[key], width=55).pack(anchor=W, padx=14)
        Label(dlg2, text="Categoria:", font=FONT_SMALL).pack(anchor=W, padx=14, pady=3)
        ttk.Combobox(dlg2, textvariable=vars_["category"], width=30,
                     values=get_all_category_names(self.custom_cats)).pack(anchor=W, padx=14)

        def apply():
            try:
                exp["date"]        = vars_["date"].get().strip()
                exp["description"] = vars_["description"].get().strip()
                exp["amount"]      = parse_money(vars_["amount"].get())
                exp["category"]    = vars_["category"].get().strip()
                self.tree.item(str(idx), values=(
                    exp["date"], exp["description"],
                    money(exp["amount"]), exp["category"],
                ))
                dlg2.destroy()
            except ValueError as e:
                messagebox.showerror("Erro", str(e), parent=dlg2)

        Button(dlg2, text="Aplicar", command=apply,
               bg=CLR_OK, fg="white", relief="flat").pack(pady=10)

    def _ai_review(self):
        self.status_var.set("⏳ Enviando para a IA revisar...")
        self.dlg.update_idletasks()

        def worker():
            answer = self.ai.review_pdf_expenses(self.raw_text, self.expenses)
            self.dlg.after(0, lambda: self._show_ai_review(answer))

        threading.Thread(target=worker, daemon=True).start()

    def _show_ai_review(self, answer: str):
        self.status_var.set("")
        dlg3 = Toplevel(self.dlg)
        dlg3.title("Revisão da IA")
        dlg3.geometry("700x420")
        t = Text(dlg3, wrap=WORD, font=FONT_NORMAL, padx=8, pady=8)
        t.pack(fill=BOTH, expand=True, padx=10, pady=10)
        t.insert(END, answer)
        t.config(state=DISABLED)
        Button(dlg3, text="Fechar", command=dlg3.destroy, relief="flat").pack(pady=8)

    def _save_all(self):
        imported = 0
        skipped = 0
        for exp in self.expenses:
            if self.db.expense_exists(
                exp["date"],
                exp["description"],
                exp["amount"],
                card="PDF",
            ):
                skipped += 1
                continue
            self.db.add_expense(
                exp["date"], exp["description"], exp["amount"],
                exp["category"], card="PDF", installments=1,
            )
            imported += 1
        self.on_save()
        self.dlg.destroy()
        if skipped:
            messagebox.showinfo(
                "Importação concluída",
                f"{imported} lançamentos importados com sucesso.\n"
                f"{skipped} já existiam e foram ignorados.",
            )
        else:
            messagebox.showinfo("Importação concluída", f"{imported} lançamentos importados com sucesso.")


# ===========================================================================
# Gerenciador de categorias
# ===========================================================================

class _CategoryManagerDialog:
    def __init__(self, root, db: Database, ai: AIAdvisor, on_save):
        self.db = db
        self.ai = ai
        self.on_save = on_save

        dlg = Toplevel(root)
        dlg.title("Gerenciar categorias")
        dlg.geometry("680x480")
        dlg.grab_set()
        self.dlg = dlg

        Label(dlg, text="Categorias customizadas", font=FONT_HEADER).pack(anchor=W, padx=10, pady=8)
        Label(dlg, text="Categorias padrão do sistema não podem ser removidas, mas as abaixo sim.",
              font=FONT_SMALL, fg=CLR_MUTED).pack(anchor=W, padx=10)

        cols = ("name", "keywords")
        tree = ttk.Treeview(dlg, columns=cols, show="headings", height=12)
        tree.heading("name",     text="Categoria")
        tree.heading("keywords", text="Palavras-chave")
        tree.column("name",     width=180)
        tree.column("keywords", width=460)
        tree.pack(fill=BOTH, expand=True, padx=10, pady=8)
        self.tree = tree
        self._reload_tree()

        add_frame = Frame(dlg, padx=10)
        add_frame.pack(fill=X, pady=4)
        Label(add_frame, text="Nova categoria:", font=FONT_SMALL).pack(side=LEFT, padx=(0, 4))
        self.v_name = StringVar()
        Entry(add_frame, textvariable=self.v_name, width=20).pack(side=LEFT, padx=(0, 8))
        Label(add_frame, text="Palavras-chave (vírgula):", font=FONT_SMALL).pack(side=LEFT, padx=(0, 4))
        self.v_kw = StringVar()
        Entry(add_frame, textvariable=self.v_kw, width=30).pack(side=LEFT, padx=(0, 8))
        Button(add_frame, text="Adicionar", command=self._add_category,
               bg=CLR_OK, fg="white", relief="flat").pack(side=LEFT, padx=(0, 4))
        Button(add_frame, text="🤖 Sugerir com IA", command=self._ai_suggest,
               bg=CLR_ACCENT, fg="white", relief="flat").pack(side=LEFT)

        btn_frame = Frame(dlg, padx=10)
        btn_frame.pack(fill=X, pady=8)
        Button(btn_frame, text="Remover selecionada", command=self._remove_category,
               bg=CLR_DANGER, fg="white", relief="flat").pack(side=LEFT, padx=(0, 8))
        Button(btn_frame, text="Fechar", command=dlg.destroy, relief="flat").pack(side=LEFT)

    def _reload_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for name, kws in self.db.get_custom_categories().items():
            self.tree.insert("", END, iid=name, values=(name, ", ".join(kws)))

    def _add_category(self):
        name = self.v_name.get().strip()
        kws  = [k.strip() for k in self.v_kw.get().split(",") if k.strip()]
        if not name:
            messagebox.showerror("Erro", "Informe o nome da categoria.", parent=self.dlg)
            return
        self.db.save_custom_category(name, kws)
        self._reload_tree()
        self.on_save()
        self.v_name.set("")
        self.v_kw.set("")

    def _remove_category(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Remover", "Selecione uma categoria.", parent=self.dlg)
            return
        name = sel[0]
        if messagebox.askyesno("Remover", f"Remover categoria '{name}'?", parent=self.dlg):
            self.db.delete_custom_category(name)
            self._reload_tree()
            self.on_save()

    def _ai_suggest(self):
        name = self.v_name.get().strip()
        if not name:
            messagebox.showinfo("IA", "Digite o nome da categoria primeiro.", parent=self.dlg)
            return

        def worker():
            kws = self.ai.suggest_category_keywords(name)
            self.dlg.after(0, lambda: self.v_kw.set(", ".join(kws)))

        threading.Thread(target=worker, daemon=True).start()
        self.v_kw.set("Aguardando IA...")
