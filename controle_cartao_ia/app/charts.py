"""
Criação de figuras matplotlib para embutir no Tkinter.
Cada função retorna uma Figure — a GUI decide onde colocar.
"""

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    matplotlib = None  # type: ignore
    plt = None  # type: ignore
    FigureCanvasTkAgg = None  # type: ignore
    MATPLOTLIB_AVAILABLE = False

def _br(value: float, cents: bool = False) -> str:
    """Formata número no padrão brasileiro. Ex: 10000.5 → R$ 10.000,50"""
    if cents:
        formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    else:
        formatted = f"{value:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


# Paleta de cores
COLORS_CATEGORY = [
    "#3498db", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6",
    "#1abc9c", "#e67e22", "#34495e", "#e91e63", "#00bcd4",
]
COLOR_OK = "#27ae60"
COLOR_WARN = "#f39c12"
COLOR_DANGER = "#e74c3c"
COLOR_PRIMARY = "#3498db"
COLOR_BG = "#ecf0f1"


def embed_figure(fig, parent_widget, side="left") -> object | None:
    """Embute uma Figure matplotlib num widget Tkinter e retorna o canvas."""
    if not MATPLOTLIB_AVAILABLE or fig is None:
        return None
    fig.tight_layout(pad=1.5)
    canvas = FigureCanvasTkAgg(fig, master=parent_widget)
    canvas.draw()
    canvas.get_tk_widget().pack(side=side, fill="both", expand=True, padx=3, pady=3)
    return canvas


def close_figure(fig) -> None:
    if MATPLOTLIB_AVAILABLE and fig is not None:
        plt.close(fig)


# ------------------------------------------------------------------
# Gráfico de pizza — categorias
# ------------------------------------------------------------------

def make_pie_chart(
    labels: list[str],
    values: list[float],
    title: str,
    figsize: tuple = (4.5, 3.2),
):
    if not MATPLOTLIB_AVAILABLE:
        return None

    fig = plt.Figure(figsize=figsize, dpi=95)
    ax = fig.add_subplot(111)
    filtered = [(l, v) for l, v in zip(labels, values) if v > 0]

    if filtered:
        lbls, vals = zip(*filtered)
        colors = COLORS_CATEGORY[: len(vals)]
        wedges, texts, autotexts = ax.pie(
            vals,
            labels=None,
            autopct="%1.1f%%",
            startangle=90,
            colors=colors,
            pctdistance=0.82,
        )
        for at in autotexts:
            at.set_fontsize(7)
        ax.legend(
            wedges,
            [f"{l} ({_br(v)})" for l, v in zip(lbls, vals)],
            loc="lower center",
            bbox_to_anchor=(0.5, -0.28),
            ncol=2,
            fontsize=7,
        )
    else:
        ax.text(0.5, 0.5, "Sem dados", ha="center", va="center", fontsize=11)

    ax.set_title(title, fontsize=10, fontweight="bold", pad=8)
    ax.axis("equal")
    return fig


# ------------------------------------------------------------------
# Gráfico meta vs gasto (donut / pizza bicolor)
# ------------------------------------------------------------------

def make_goal_chart(
    total: float,
    goal: float,
    title: str,
    figsize: tuple = (4.0, 3.2),
):
    if not MATPLOTLIB_AVAILABLE:
        return None

    fig = plt.Figure(figsize=figsize, dpi=95)
    ax = fig.add_subplot(111)

    percent = (total / goal * 100) if goal > 0 else 0
    color_used = COLOR_DANGER if percent >= 100 else (COLOR_WARN if percent >= 80 else COLOR_OK)
    remaining = max(goal - total, 0)

    if total > 0 or goal > 0:
        if remaining > 0:
            vals = [total, remaining]
            lbls = [f"Gasto  {_br(total, cents=True)}", f"Disponível  {_br(remaining, cents=True)}"]
            clrs = [color_used, COLOR_BG]
        else:
            vals = [total, 0.0001]
            lbls = [f"Gasto  {_br(total, cents=True)}", "Meta excedida"]
            clrs = [COLOR_DANGER, COLOR_BG]

        wedges, _, autotexts = ax.pie(
            vals,
            labels=None,
            colors=clrs,
            autopct="%1.1f%%",
            startangle=90,
            pctdistance=0.75,
            wedgeprops={"linewidth": 2, "edgecolor": "white"},
        )
        for at in autotexts:
            at.set_fontsize(8)
        ax.legend(wedges, lbls, loc="lower center", bbox_to_anchor=(0.5, -0.18), fontsize=8)
    else:
        ax.text(0.5, 0.5, "Sem dados", ha="center", va="center", fontsize=11)

    ax.set_title(f"{title}\n{percent:.1f}% da meta", fontsize=9, fontweight="bold")
    ax.axis("equal")
    return fig


# ------------------------------------------------------------------
# Gráfico de barras genérico
# ------------------------------------------------------------------

def make_bar_chart(
    labels: list[str],
    values: list[float],
    title: str,
    xlabel: str = "",
    ylabel: str = "R$",
    figsize: tuple = (5.0, 3.2),
    color: str = COLOR_PRIMARY,
    rotate: int = 35,
):
    if not MATPLOTLIB_AVAILABLE:
        return None

    fig = plt.Figure(figsize=figsize, dpi=95)
    ax = fig.add_subplot(111)

    if labels and values:
        x = range(len(labels))
        bars = ax.bar(x, values, color=color, edgecolor="white", linewidth=0.5)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=rotate, ha="right", fontsize=8)
        ax.set_xlabel(xlabel, fontsize=9)
        ax.set_ylabel(ylabel, fontsize=9)
        # rótulos nas barras
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.01,
                    _br(val),
                    ha="center",
                    va="bottom",
                    fontsize=7,
                )
    else:
        ax.text(0.5, 0.5, "Sem dados", ha="center", va="center", fontsize=11)

    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return fig


# ------------------------------------------------------------------
# Gráfico de linhas — evolução gasto vs meta
# ------------------------------------------------------------------

def make_line_chart(
    months: list[str],
    gastos: list[float],
    metas: list[float],
    title: str,
    figsize: tuple = (5.5, 3.2),
):
    if not MATPLOTLIB_AVAILABLE:
        return None

    fig = plt.Figure(figsize=figsize, dpi=95)
    ax = fig.add_subplot(111)

    if months and gastos:
        x = list(range(len(months)))
        ax.plot(x, gastos, "o-", color=COLOR_PRIMARY, linewidth=2, markersize=5, label="Gasto")
        ax.plot(x, metas,  "s--", color=COLOR_WARN,   linewidth=2, markersize=5, label="Meta")

        # Destaca meses em que o gasto ultrapassou a meta
        over_x = [xi for xi, g, m in zip(x, gastos, metas) if g > m]
        over_g = [g  for g, m in zip(gastos, metas) if g > m]
        if over_x:
            ax.scatter(over_x, over_g, color=COLOR_DANGER, zorder=5, s=60)

        ax.fill_between(x, gastos, metas,
                        where=[g > m for g, m in zip(gastos, metas)],
                        alpha=0.15, color=COLOR_DANGER)

        ax.set_xticks(x)
        ax.set_xticklabels(months, rotation=35, ha="right", fontsize=8)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: _br(v)))
        ax.legend(fontsize=8, loc="upper left")
    else:
        ax.text(0.5, 0.5, "Sem dados", ha="center", va="center", fontsize=11)

    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return fig


# ------------------------------------------------------------------
# Gráfico horizontal de maiores gastos
# ------------------------------------------------------------------

def make_top_expenses_chart(
    labels: list[str],
    values: list[float],
    title: str,
    figsize: tuple = (5.5, 3.2),
):
    if not MATPLOTLIB_AVAILABLE:
        return None

    fig = plt.Figure(figsize=figsize, dpi=95)
    ax = fig.add_subplot(111)

    if labels and values:
        # inverte para o maior ficar no topo
        lbls = labels[::-1]
        vals = values[::-1]
        y = range(len(lbls))
        colors = [COLOR_DANGER if v == max(values) else COLOR_PRIMARY for v in vals]
        bars = ax.barh(list(y), vals, color=colors, edgecolor="white")
        ax.set_yticks(list(y))
        ax.set_yticklabels(
            [l[:30] + "…" if len(l) > 30 else l for l in lbls],
            fontsize=8
        )
        for bar, val in zip(bars, vals):
            ax.text(
                bar.get_width() * 1.01,
                bar.get_y() + bar.get_height() / 2,
                _br(val, cents=True),
                va="center",
                fontsize=7,
            )
    else:
        ax.text(0.5, 0.5, "Sem dados", ha="center", va="center", fontsize=11)

    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return fig
