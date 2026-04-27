# Controle de Cartão de Crédito com IA

Aplicativo desktop em Python + Tkinter para controle pessoal de gastos de cartão de crédito,
com classificação automática, previsão de parcelas, dashboard gráfico e assistente de IA.

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
| `pandas` | Análises futuras |

> Tkinter já vem com Python no Windows. No Linux: `sudo apt install python3-tk`  
> Python **3.11 ou superior** é necessário.

---

## Execução

```bash
python main.py
```

Na primeira execução, o sistema pedirá que você crie uma senha de acesso.

---

## Estrutura de pastas

```
controle cartao/
├── main.py                        ← ponto de entrada
├── README.md
├── STATUS.md                      ← não vai para o git
└── controle_cartao_ia/
    ├── requirements.txt
    ├── README.md                  ← documentação técnica detalhada
    ├── app/
    │   ├── __init__.py
    │   ├── utils.py               ← constantes, datas, moeda, classificação
    │   ├── database.py            ← banco SQLite
    │   ├── ai_advisor.py          ← integração com IA
    │   ├── pdf_importer.py        ← leitura de faturas PDF
    │   ├── charts.py              ← gráficos matplotlib
    │   └── gui.py                 ← interface Tkinter completa
    ├── data/                      ← reservado
    └── backups/                   ← backups manuais
```

### Onde ficam banco e configurações?

Fora do repositório, na pasta do usuário:

| Sistema | Caminho |
|---|---|
| Windows | `C:\Users\<usuario>\.controle_cartao_ia\` |
| Linux / macOS | `~/.controle_cartao_ia/` |

```
~/.controle_cartao_ia/
├── cartao.db        ← banco SQLite com todos os lançamentos
├── config.json      ← URL da IA, modelo, hash da senha
└── backups/         ← backups gerados pelo menu do app
```

---

## Funcionalidades

- Cadastro manual de gastos (com parcelas automáticas)
- Importação de fatura em PDF com revisão e correção pela IA
- Classificação automática por palavras-chave + IA para casos novos
- Categorias customizadas (a IA sugere palavras-chave)
- Meta mensal com barra de progresso e alertas
- Previsão de gastos futuros comprometidos (parcelas)
- Dashboard com 5 tipos de gráfico
- Chat lateral com assistente de IA (perguntas livres)
- Análise mensal e anual detalhada pela IA
- Edição de qualquer lançamento (duplo clique)
- Backup e restauração do banco com um clique
- Login com senha (SHA-256) — sem armazenamento de texto puro
- Funciona sem IA: fallback local sempre disponível

---

## Configuração da IA

Acesse **Configurações IA** dentro do app.

| Provedor | URL | Modelo de exemplo |
|---|---|---|
| Ollama (local) | `http://localhost:11434/api/chat` | `llama3.1:8b` |
| OpenRouter | `https://openrouter.ai/api/v1/chat/completions` | `openai/gpt-4o-mini` |
| OpenAI | `https://api.openai.com/v1/chat/completions` | `gpt-4o-mini` |

> Sem IA configurada, o sistema exibe análise local automática e funciona normalmente.

---

## Documentação técnica

Veja [controle_cartao_ia/README.md](controle_cartao_ia/README.md) para detalhes de cada módulo, changelog completo e instruções avançadas.
