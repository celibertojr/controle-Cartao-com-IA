# Controle de Cartão de Crédito com IA

Aplicativo desktop em Python + Tkinter para controle pessoal de gastos de cartão de crédito,
com classificação automática, importação de fatura PDF, previsão de parcelas, dashboard gráfico
e assistente de IA integrado.

---

## Requisitos

- Python **3.11 ou superior**
- Tkinter (já incluso no Python para Windows; no Linux: `sudo apt install python3-tk`)

---

## Instalação

```bash
pip install -r controle_cartao_ia/requirements.txt
```

| Pacote | Uso |
|---|---|
| `requests` | Chamadas à API de IA |
| `pdfplumber` | Leitura de faturas PDF |
| `matplotlib` | Gráficos do dashboard |
| `openpyxl` | Exportação para Excel |

---

## Execução

```bash
python main.py
```

Na primeira execução, o sistema pedirá que você crie uma senha de acesso e gerará automaticamente
um código de recuperação — anote-o em local seguro.

---

## Onde ficam os dados?

Todos os dados pessoais ficam **fora do repositório**, na pasta do usuário:

| Sistema | Caminho |
|---|---|
| Windows | `C:\Users\<usuario>\.controle_cartao_ia\` |
| Linux / macOS | `~/.controle_cartao_ia/` |

```
~/.controle_cartao_ia/
├── cartao.db        ← banco SQLite com todos os lançamentos
├── config.json      ← URL da IA, modelo, hash da senha (nunca texto puro)
└── backups/         ← backups gerados pelo app
```

Isso garante que **nenhum dado pessoal vai para o repositório** — nem API keys, nem senha, nem histórico de gastos.

---

## Estrutura do projeto

```
controle-Cartao-com-IA/
├── main.py                        ← ponto de entrada
├── README.md
└── controle_cartao_ia/
    ├── requirements.txt
    └── app/
        ├── utils.py               ← constantes, datas, moeda, classificação
        ├── database.py            ← banco SQLite
        ├── ai_advisor.py          ← integração com IA
        ├── pdf_importer.py        ← leitura de faturas PDF
        ├── charts.py              ← gráficos matplotlib
        └── gui.py                 ← interface Tkinter completa
```

---

## Funcionalidades

- Cadastro manual de gastos com suporte a parcelamento automático
- Importação de fatura em PDF com revisão e sugestão de correção pela IA
- Classificação automática por palavras-chave + IA para categorias desconhecidas
- Categorias personalizadas (a IA sugere palavras-chave)
- Meta mensal com barra de progresso, alertas e herança automática do mês anterior
- Projeção dos próximos 12 meses com base em parcelas e gastos recorrentes
- Dashboard com 5 tipos de gráfico (pizza, barras, linha, progresso, horizontal)
- Chat lateral com assistente de IA — perguntas livres e análise detalhada
- Edição de qualquer lançamento via duplo clique
- Exportação para Excel — mês atual ou histórico completo
- Backup e restauração do banco com um clique
- Login com senha (SHA-256) + código de recuperação
- Painel de Manutenção para limpeza seletiva do banco de dados
- Funciona completamente sem IA: fallback local sempre disponível

---

## Configuração da IA

Acesse **Configurações → IA** dentro do app.

| Provedor | URL | Modelo de exemplo |
|---|---|---|
| Ollama (local) | `http://localhost:11434/api/chat` | `llama3.1:8b` |
| Xiaomi MiMo | `https://api.xiaomimimo.com/v1` | `mimo-v2.5-pro` |
| OpenRouter | `https://openrouter.ai/api/v1` | `openai/gpt-4o-mini` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |

A URL pode ser a base (`/v1`) ou o endpoint completo — o sistema detecta e completa automaticamente.

> Sem IA configurada, o sistema exibe análise local automática e funciona normalmente.

---

## Licença

Uso pessoal.
