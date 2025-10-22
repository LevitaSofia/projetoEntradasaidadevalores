"""
Parser de linguagem natural usando OpenAI.
Extrai informações estruturadas de mensagens livres do usuário.
"""
import json
import logging
from typing import Dict, Any
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from openai import OpenAI
from openai.types.chat import ChatCompletion

from .config import config
from .models import LancamentoFinanceiro, RespostaIA

logger = logging.getLogger(__name__)


class OpenAIParseError(Exception):
    """Erro específico do parser OpenAI."""
    pass


class FinanceAIParser:
    """
    Parser que usa OpenAI para extrair dados financeiros de texto livre.
    """

    def __init__(self):
        """Inicializa o parser com cliente OpenAI."""
        self.client = OpenAI(api_key=config.openai_api_key)
        self.model = config.openai_model

    @property
    def system_prompt(self) -> str:
        """Prompt do sistema para instruir a IA."""
        return """Você é um extrator de dados financeiros pessoais para lançamentos em planilha.

A mensagem do usuário descreve uma ENTRADA (recebimento de dinheiro) ou SAÍDA (pagamento/gasto).

Seu trabalho é converter o texto em JSON estruturado seguindo estas regras:

1. TIPO: Determine se é "entrada" (recebeu dinheiro) ou "saida" (gastou/pagou dinheiro)
   - Palavras para ENTRADA: recebi, entrou, venda, pagaram, recebimento, pix recebido, transferência recebida
   - Palavras para SAÍDA: paguei, gastei, comprei, saída, despesa, conta, frete, combustível

2. VALOR: Extraia o valor numérico e normalize para decimal com ponto
   - Aceite formatos: 35,90 ou 35.90 ou 35
   - Remova símbolos: R$, reais, etc.

3. DESCRIÇÃO: Resuma o que foi o lançamento em até 3-5 palavras
   - Exemplos: "frete sedex", "venda produto", "combustível", "pix João"

4. CATEGORIA: Inferir categoria quando possível
   - Exemplos: transporte, alimentação, vendas, serviços, combustível, frete

5. DATA: Use "today" se não especificada, "yesterday" para ontem, ou YYYY-MM-DD

RESPONDA APENAS COM JSON VÁLIDO seguindo o schema exato.

Exemplos:
"paguei 35,90 de frete hoje" → {"tipo":"saida","valor":35.9,"descricao":"frete","categoria":"logística","data":"today"}
"entrou 500 pix do Carlos" → {"tipo":"entrada","valor":500,"descricao":"pix Carlos","categoria":"transferência","data":"today"}
"comprei combustível 89,50" → {"tipo":"saida","valor":89.5,"descricao":"combustível","categoria":"transporte","data":"today"}"""

    @property
    def json_schema(self) -> Dict[str, Any]:
        """Schema JSON para resposta estruturada."""
        return {
            "type": "object",
            "properties": {
                "tipo": {
                    "type": "string",
                    "enum": ["entrada", "saida"],
                    "description": "Tipo do lançamento: entrada ou saida"
                },
                "valor": {
                    "type": "number",
                    "minimum": 0.01,
                    "description": "Valor em decimal (usar ponto)"
                },
                "descricao": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 100,
                    "description": "Descrição resumida do lançamento"
                },
                "categoria": {
                    "type": "string",
                    "maxLength": 50,
                    "description": "Categoria inferida (opcional)",
                    "default": ""
                },
                "data": {
                    "type": "string",
                    "description": "Data: 'today', 'yesterday' ou YYYY-MM-DD",
                    "default": "today"
                }
            },
            "required": ["tipo", "valor", "descricao", "categoria", "data"],
            "additionalProperties": False
        }

    @retry(
        retry=retry_if_exception_type((Exception,)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        before_sleep=lambda retry_state: logger.warning(
            f"Tentativa {retry_state.attempt_number} falhou, tentando novamente..."
        )
    )
    def parse_message(self, message: str) -> LancamentoFinanceiro:
        """
        Analisa uma mensagem e retorna um lançamento financeiro estruturado.

        Args:
            message: Mensagem do usuário em linguagem natural

        Returns:
            LancamentoFinanceiro: Dados estruturados extraídos

        Raises:
            OpenAIParseError: Erro ao processar com OpenAI
            ValueError: Erro de validação dos dados
        """
        if not message or not message.strip():
            raise ValueError("Mensagem não pode estar vazia")

        message = message.strip()
        logger.info(f"Analisando mensagem: '{message[:50]}...'")

        try:
            # Chama a API OpenAI com resposta estruturada
            response: ChatCompletion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": message}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "LancamentoFinanceiro",
                        "schema": self.json_schema,
                        "strict": True
                    }
                },
                temperature=0.1,  # Baixa variabilidade para mais consistência
                max_tokens=200    # Limite para resposta concisa
            )

            # Extrai conteúdo da resposta
            content = response.choices[0].message.content
            if not content:
                raise OpenAIParseError("OpenAI retornou resposta vazia")

            logger.debug(f"Resposta OpenAI: {content}")

            # Parse do JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                raise OpenAIParseError(
                    f"Resposta OpenAI não é JSON válido: {e}")

            # Valida com Pydantic
            resposta_ia = RespostaIA(**data)
            lancamento = resposta_ia.to_lancamento()

            logger.info(
                f"Parsing bem-sucedido: {lancamento.tipo} R$ {lancamento.valor} - {lancamento.descricao}"
            )

            return lancamento

        except json.JSONDecodeError as e:
            error_msg = f"Erro ao decodificar JSON da OpenAI: {e}"
            logger.error(error_msg)
            raise OpenAIParseError(error_msg)

        except Exception as e:
            error_msg = f"Erro na API OpenAI: {str(e)}"
            logger.error(error_msg)
            raise OpenAIParseError(error_msg)

    def parse_direct_command(self, command: str, text: str) -> LancamentoFinanceiro:
        """
        Analisa comandos diretos como /entrada ou /saida.

        Args:
            command: Comando (/entrada ou /saida)
            text: Texto completo da mensagem

        Returns:
            LancamentoFinanceiro: Dados estruturados

        Raises:
            ValueError: Erro de parsing ou validação
        """
        # Remove o comando do início
        text = text.replace(command, "").strip()

        if not text:
            raise ValueError(
                f"Informe ao menos o valor. Exemplo: {command} 100 descrição")

        # Separa em partes: valor e descrição
        parts = text.split(maxsplit=1)

        if len(parts) < 1:
            raise ValueError(
                f"Informe o valor. Exemplo: {command} 100 descrição")

        valor_str = parts[0]
        descricao = parts[1] if len(parts) > 1 else "sem descrição"

        # Determina tipo baseado no comando
        tipo = "entrada" if command == "/entrada" else "saida"

        # Cria lançamento
        lancamento = LancamentoFinanceiro(
            tipo=tipo,
            valor=valor_str,
            descricao=descricao,
            categoria="",
            data="today"
        )

        logger.info(
            f"Comando direto processado: {lancamento.tipo} R$ {lancamento.valor} - {lancamento.descricao}"
        )

        return lancamento

    async def test_connection(self) -> bool:
        """
        Testa conectividade com a API OpenAI.

        Returns:
            bool: True se conexão ok, False caso contrário
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Teste de conexão"}],
                max_tokens=10
            )
            return bool(response.choices)
        except Exception as e:
            logger.error(f"Erro no teste de conexão OpenAI: {e}")
            return False


# Instância global do parser
ai_parser = FinanceAIParser()
