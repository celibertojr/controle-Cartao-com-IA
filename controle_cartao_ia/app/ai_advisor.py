"""
Integração com IA via API compatível com Ollama / OpenAI / OpenRouter.
O sistema funciona sem IA — o fallback local sempre está disponível.
"""

import requests


class AIAdvisor:
    """
    Wrapper stateless para chamadas de IA.
    Detecta automaticamente o formato de resposta (Ollama vs OpenAI).
    """

    def __init__(self, config: dict):
        self.config = config
        self.available: bool = False  # atualizado após cada chamada

    # ------------------------------------------------------------------
    # Chamada principal
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_url(raw_url: str) -> str:
        """
        Aceita tanto a URL base quanto o endpoint completo.

        Formatos aceitos:
          • Ollama:          http://localhost:11434/api/chat          → usa como está
          • OpenAI completo: https://api.openai.com/v1/chat/completions → usa como está
          • Base OpenAI:     https://api.xxx.com/v1                  → adiciona /chat/completions
          • Base sem path:   https://api.xxx.com                     → adiciona /v1/chat/completions
        """
        url = raw_url.rstrip("/")
        if url.endswith("/chat/completions") or url.endswith("/api/chat"):
            return url
        if url.endswith("/v1"):
            return url + "/chat/completions"
        # fallback: assume base sem versão
        return url + "/v1/chat/completions"

    def analyze(self, prompt_text: str, system_msg: str | None = None) -> str:
        """
        Envia prompt para a API configurada.
        Detecta automaticamente o formato (Ollama ou OpenAI-compatible).
        Em caso de falha, retorna a análise local (fallback).
        """
        raw_url = self.config.get("api_base_url", "").strip()
        api_key = self.config.get("api_key", "").strip()
        model   = self.config.get("model", "llama3.1:8b").strip() or "llama3.1:8b"

        if not raw_url:
            self.available = False
            return self.local_fallback()

        api_url = self._resolve_url(raw_url)

        system = system_msg or (
            "Você é um assistente financeiro pessoal brasileiro. "
            "Seja objetivo, prático e amigável. Responda sempre em português do Brasil."
        )

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt_text},
            ],
            "stream": False,
        }

        try:
            resp = requests.post(api_url, headers=headers, json=payload, timeout=90)
            resp.raise_for_status()
            data = resp.json()
            self.available = True
            return self._extract_content(data)
        except requests.exceptions.ConnectionError:
            self.available = False
            return (
                "⚠️ Não foi possível conectar à IA.\n"
                "Verifique se o Ollama está rodando ou se a URL está correta.\n\n"
                + self.local_fallback()
            )
        except requests.exceptions.Timeout:
            self.available = False
            return (
                "⚠️ A IA demorou muito para responder (timeout).\n"
                "Tente novamente ou use um modelo menor.\n\n"
                + self.local_fallback()
            )
        except Exception as exc:
            self.available = False
            return f"⚠️ Erro ao consultar IA: {exc}\n\n{self.local_fallback()}"

    @staticmethod
    def _extract_content(data: dict) -> str:
        """Extrai o texto da resposta em formato Ollama ou OpenAI."""
        if isinstance(data, dict):
            # Formato Ollama: {"message": {"content": "..."}}
            if "message" in data and isinstance(data["message"], dict):
                return data["message"].get("content", str(data))
            # Formato OpenAI: {"choices": [{"message": {"content": "..."}}]}
            if "choices" in data and data["choices"]:
                msg = data["choices"][0].get("message", {})
                return msg.get("content", str(data))
        return str(data)

    # ------------------------------------------------------------------
    # Tarefas especializadas
    # ------------------------------------------------------------------

    def classify_expense(self, description: str, known_categories: list[str]) -> str:
        """
        Pede à IA para classificar um gasto e sugerir categoria.
        Retorna o nome da categoria (existente ou nova).
        """
        cat_list = ", ".join(known_categories)
        prompt = (
            f"Classifique o gasto abaixo em uma das categorias existentes "
            f"ou sugira uma nova categoria em português.\n"
            f"Categorias disponíveis: {cat_list}\n"
            f"Descrição do gasto: {description}\n\n"
            f"Responda APENAS com o nome da categoria. Nada mais."
        )
        result = self.analyze(prompt)
        # pega só a primeira linha, sem pontuação extra
        return result.strip().split("\n")[0].strip().rstrip(".")

    def suggest_category_keywords(self, category_name: str) -> list[str]:
        """Pede à IA palavras-chave para uma nova categoria."""
        prompt = (
            f"Liste palavras-chave em português para classificar automaticamente "
            f"gastos na categoria '{category_name}'.\n"
            f"Retorne apenas as palavras separadas por vírgula, sem explicações."
        )
        result = self.analyze(prompt)
        return [k.strip().lower() for k in result.split(",") if k.strip() and len(k.strip()) > 1]

    def review_pdf_expenses(self, raw_text: str, parsed_expenses: list[dict]) -> str:
        """
        Envia o texto bruto do PDF e os gastos parseados para a IA
        revisar e corrigir possíveis erros de leitura.
        """
        expenses_str = "\n".join(
            f"- {e['date']} | {e['description']} | R$ {e['amount']:.2f} | {e['category']}"
            for e in parsed_expenses[:30]  # limita para não estourar contexto
        )
        prompt = (
            f"Analisei uma fatura de cartão de crédito em PDF e extraí os gastos abaixo.\n"
            f"Revise se há erros de leitura, descrições incorretas ou categorias erradas.\n"
            f"Aponte problemas encontrados e sugira correções.\n\n"
            f"GASTOS EXTRAÍDOS:\n{expenses_str}\n\n"
            f"TEXTO ORIGINAL DO PDF (primeiros 2000 chars):\n{raw_text[:2000]}"
        )
        return self.analyze(prompt)

    def build_financial_summary_prompt(self, summary_text: str, question: str) -> str:
        """Monta o prompt final com contexto financeiro + pergunta do usuário."""
        return (
            "Use os dados financeiros abaixo para responder à pergunta do usuário.\n"
            "Responda em português do Brasil, de forma objetiva, prática e honesta.\n"
            "Quando fizer sentido, indique categorias, meses, valores e possíveis cortes.\n\n"
            f"DADOS FINANCEIROS DO USUÁRIO:\n{summary_text}\n\n"
            f"PERGUNTA:\n{question}"
        )

    # ------------------------------------------------------------------
    # Fallback local (sem IA)
    # ------------------------------------------------------------------

    @staticmethod
    def local_fallback() -> str:
        return (
            "📊 Análise local (IA não disponível):\n\n"
            "• Verifique as categorias com maior gasto no dashboard.\n"
            "• Se o total mensal ultrapassar 80% da meta antes do fim do mês, "
            "reduza gastos variáveis (lazer, compras, alimentação fora).\n"
            "• Atenção especial para compras parceladas — cada parcela "
            "compromete o orçamento dos próximos meses.\n"
            "• Priorize cortar assinaturas esquecidas e compras por impulso.\n"
            "• Configure a IA (Ollama local ou API) para obter análises personalizadas."
        )
