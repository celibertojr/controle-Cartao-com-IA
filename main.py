"""
Controle de Cartão de Crédito com IA
======================================
Ponto de entrada do aplicativo.

Execução:
    python main.py

Estrutura:
    app/utils.py       → constantes, configuração, datas, moeda
    app/database.py    → banco SQLite
    app/ai_advisor.py  → integração com IA (Ollama / OpenAI / OpenRouter)
    app/pdf_importer.py → leitura de faturas PDF
    app/charts.py      → gráficos matplotlib
    app/gui.py         → interface Tkinter (login, dashboard, chat IA)
"""

import sys
from pathlib import Path

# Adiciona controle_cartao_ia/ ao path para que 'app' seja encontrado
sys.path.insert(0, str(Path(__file__).parent / "controle_cartao_ia"))


def main():
    if sys.version_info < (3, 11):
        print("Python 3.11 ou superior é necessário.")
        sys.exit(1)

    from app.gui import run
    run()


if __name__ == "__main__":
    main()
