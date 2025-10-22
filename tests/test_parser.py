"""
Testes para o parser de IA financeira.
Testa extração de dados de mensagens livres.
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock

from app.ai_parser import FinanceAIParser, OpenAIParseError
from app.models import LancamentoFinanceiro


class TestFinanceAIParser:
    """Testes para o parser OpenAI."""

    @pytest.fixture
    def parser(self):
        """Fixture para criar parser."""
        return FinanceAIParser()

    def test_parse_direct_command_entrada(self, parser):
        """Testa parsing de comando /entrada."""
        lancamento = parser.parse_direct_command(
            "/entrada", "/entrada 150 venda produto")

        assert lancamento.tipo == "entrada"
        assert lancamento.valor == Decimal("150")
        assert lancamento.descricao == "venda produto"
        assert lancamento.data == "today"

    def test_parse_direct_command_saida(self, parser):
        """Testa parsing de comando /saida."""
        lancamento = parser.parse_direct_command(
            "/saida", "/saida 35,90 frete sedex")

        assert lancamento.tipo == "saida"
        assert lancamento.valor == Decimal("35.90")
        assert lancamento.descricao == "frete sedex"

    def test_parse_direct_command_valor_apenas(self, parser):
        """Testa comando com apenas valor."""
        lancamento = parser.parse_direct_command("/entrada", "/entrada 100")

        assert lancamento.tipo == "entrada"
        assert lancamento.valor == Decimal("100")
        assert lancamento.descricao == "sem descrição"

    def test_parse_direct_command_erro_vazio(self, parser):
        """Testa erro quando comando está vazio."""
        with pytest.raises(ValueError, match="Informe ao menos o valor"):
            parser.parse_direct_command("/entrada", "/entrada")

    def test_parse_direct_command_valor_invalido(self, parser):
        """Testa erro com valor inválido."""
        with pytest.raises(ValueError):
            parser.parse_direct_command("/entrada", "/entrada abc venda")

    @patch('app.ai_parser.OpenAI')
    def test_parse_message_sucesso(self, mock_openai, parser):
        """Testa parsing com IA bem-sucedido."""
        # Mock da resposta OpenAI
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = '''
        {
            "tipo": "saida",
            "valor": 35.9,
            "descricao": "frete",
            "categoria": "logística",
            "data": "today"
        }
        '''

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Recria parser com mock
        parser.client = mock_client

        lancamento = parser.parse_message("paguei 35,90 de frete hoje")

        assert lancamento.tipo == "saida"
        assert lancamento.valor == Decimal("35.9")
        assert lancamento.descricao == "frete"
        assert lancamento.categoria == "logística"

    @patch('app.ai_parser.OpenAI')
    def test_parse_message_json_invalido(self, mock_openai, parser):
        """Testa erro com JSON inválido da OpenAI."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "json inválido {"

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        parser.client = mock_client

        with pytest.raises(OpenAIParseError, match="JSON válido"):
            parser.parse_message("paguei 100 de algo")

    @patch('app.ai_parser.OpenAI')
    def test_parse_message_resposta_vazia(self, mock_openai, parser):
        """Testa erro com resposta vazia da OpenAI."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        parser.client = mock_client

        with pytest.raises(OpenAIParseError, match="resposta vazia"):
            parser.parse_message("teste")

    def test_parse_message_vazio(self, parser):
        """Testa erro com mensagem vazia."""
        with pytest.raises(ValueError, match="não pode estar vazia"):
            parser.parse_message("")

        with pytest.raises(ValueError, match="não pode estar vazia"):
            parser.parse_message("   ")

    @patch('app.ai_parser.OpenAI')
    def test_parse_message_erro_api(self, mock_openai, parser):
        """Testa erro na API OpenAI."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception(
            "API Error")
        mock_openai.return_value = mock_client

        parser.client = mock_client

        with pytest.raises(OpenAIParseError, match="Erro na API OpenAI"):
            parser.parse_message("teste")

    def test_system_prompt(self, parser):
        """Testa se o system prompt está configurado."""
        prompt = parser.system_prompt

        assert "extrator de dados financeiros" in prompt.lower()
        assert "entrada" in prompt.lower()
        assert "saida" in prompt.lower()
        assert "json" in prompt.lower()

    def test_json_schema(self, parser):
        """Testa se o schema JSON está correto."""
        schema = parser.json_schema

        assert "tipo" in schema["properties"]
        assert "valor" in schema["properties"]
        assert "descricao" in schema["properties"]
        assert schema["properties"]["tipo"]["enum"] == ["entrada", "saida"]
        assert "required" in schema
        assert "tipo" in schema["required"]
        assert "valor" in schema["required"]
        assert "descricao" in schema["required"]


@pytest.mark.asyncio
class TestAsyncMethods:
    """Testes para métodos assíncronos."""

    @pytest.fixture
    def parser(self):
        return FinanceAIParser()

    @patch('app.ai_parser.OpenAI')
    async def test_test_connection_sucesso(self, mock_openai, parser):
        """Testa teste de conexão bem-sucedido."""
        mock_response = Mock()
        mock_response.choices = [Mock()]

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        parser.client = mock_client

        result = await parser.test_connection()
        assert result is True

    @patch('app.ai_parser.OpenAI')
    async def test_test_connection_falha(self, mock_openai, parser):
        """Testa teste de conexão com falha."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception(
            "Connection failed")
        mock_openai.return_value = mock_client

        parser.client = mock_client

        result = await parser.test_connection()
        assert result is False


class TestCasosReais:
    """Testes com casos reais de uso."""

    @pytest.fixture
    def parser(self):
        return FinanceAIParser()

    def test_casos_comando_direto(self, parser):
        """Testa casos reais de comandos diretos."""
        casos = [
            ("/entrada 1500 salário", "entrada", Decimal("1500"), "salário"),
            ("/saida 89,50 combustível", "saida", Decimal("89.50"), "combustível"),
            ("/entrada 25 vale transporte", "entrada",
             Decimal("25"), "vale transporte"),
            ("/saida 199,99 mercado", "saida", Decimal("199.99"), "mercado"),
        ]

        for comando_texto, tipo_esperado, valor_esperado, descricao_esperada in casos:
            comando = comando_texto.split()[0]
            lancamento = parser.parse_direct_command(comando, comando_texto)

            assert lancamento.tipo == tipo_esperado
            assert lancamento.valor == valor_esperado
            assert lancamento.descricao == descricao_esperada

    @patch('app.ai_parser.OpenAI')
    def test_casos_linguagem_natural(self, mock_openai, parser):
        """Testa casos com linguagem natural (mockado)."""
        casos = [
            ("paguei 35,90 de frete", "saida", 35.9),
            ("recebi 500 do cliente", "entrada", 500.0),
            ("gastei 25 no almoço", "saida", 25.0),
            ("entrou pix de 150", "entrada", 150.0),
        ]

        for mensagem, tipo_esperado, valor_esperado in casos:
            # Mock resposta específica para cada caso
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = f'''{{
                "tipo": "{tipo_esperado}",
                "valor": {valor_esperado},
                "descricao": "teste",
                "data": "today"
            }}'''

            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            parser.client = mock_client

            lancamento = parser.parse_message(mensagem)

            assert lancamento.tipo == tipo_esperado
            assert float(lancamento.valor) == valor_esperado
