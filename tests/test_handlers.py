"""
Testes para handlers do bot Telegram.
Testa comportamento dos comandos e respostas.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal

from app.models import LancamentoFinanceiro, SaldoGeral, RelatorioMensal


class TestBotHandlers:
    """Testes para handlers do bot."""

    @pytest.fixture
    def mock_update(self):
        """Mock do objeto Update do Telegram."""
        update = Mock()
        update.effective_chat.id = 12345
        update.effective_user.full_name = "Usuário Teste"
        update.effective_user.first_name = "Usuário"
        update.effective_user.last_name = "Teste"
        update.message.message_id = 999
        update.message.text = "mensagem teste"
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Mock do objeto Context do Telegram."""
        context = Mock()
        context.args = []
        return context


@pytest.mark.asyncio
class TestCommandHandlers:
    """Testes para handlers de comandos."""

    @pytest.fixture
    def mock_update(self):
        update = Mock()
        update.effective_chat.id = 12345
        update.effective_user.full_name = "Test User"
        update.message.message_id = 999
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        context = Mock()
        context.args = []
        return context

    async def test_handle_start(self, mock_update, mock_context):
        """Testa comando /start."""
        from app.bot_handlers import handle_start

        with patch('app.bot_handlers.sheets_manager') as mock_sheets:
            mock_sheets.registrar_usuario = Mock()

            await handle_start(mock_update, mock_context)

            # Verifica se resposta foi enviada
            mock_update.message.reply_text.assert_called_once()

            # Verifica conteúdo da resposta
            args, kwargs = mock_update.message.reply_text.call_args
            resposta = args[0]

            assert "Bem-vindo" in resposta
            assert "/entrada" in resposta
            assert "/saldo" in resposta

    async def test_handle_help(self, mock_update, mock_context):
        """Testa comando /help."""
        from app.bot_handlers import handle_help

        await handle_help(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()

        args, kwargs = mock_update.message.reply_text.call_args
        resposta = args[0]

        assert "Guia Completo" in resposta
        assert "/entrada" in resposta
        assert "/saida" in resposta
        assert "Linguagem Natural" in resposta

    async def test_handle_entrada_sucesso(self, mock_update, mock_context):
        """Testa comando /entrada bem-sucedido."""
        from app.bot_handlers import handle_entrada

        mock_update.message.text = "/entrada 150 venda produto"

        with patch('app.bot_handlers.ai_parser') as mock_parser, \
                patch('app.bot_handlers.sheets_manager') as mock_sheets, \
                patch('app.bot_handlers.rate_limiter') as mock_limiter:

            # Mock do parser
            lancamento = LancamentoFinanceiro(
                tipo="entrada",
                valor=Decimal("150"),
                descricao="venda produto",
                categoria="",
                data="today"
            )
            mock_parser.parse_direct_command.return_value = lancamento

            # Mock rate limiter
            mock_limiter.is_allowed.return_value = True

            # Mock sheets
            mock_sheets.registrar_lancamento = Mock()

            await handle_entrada(mock_update, mock_context)

            # Verifica se foi registrado
            mock_sheets.registrar_lancamento.assert_called_once()

            # Verifica resposta
            mock_update.message.reply_text.assert_called_once()
            args, kwargs = mock_update.message.reply_text.call_args
            resposta = args[0]

            assert "Entrada registrada" in resposta
            assert "R$ 150" in resposta
            assert "venda produto" in resposta

    async def test_handle_entrada_rate_limit(self, mock_update, mock_context):
        """Testa rate limiting no comando /entrada."""
        from app.bot_handlers import handle_entrada

        with patch('app.bot_handlers.rate_limiter') as mock_limiter:
            mock_limiter.is_allowed.return_value = False
            mock_limiter.get_wait_time.return_value = 1.5

            await handle_entrada(mock_update, mock_context)

            # Verifica mensagem de rate limit
            mock_update.message.reply_text.assert_called_once()
            args, kwargs = mock_update.message.reply_text.call_args
            resposta = args[0]

            assert "Aguarde" in resposta
            assert "1.5" in resposta

    async def test_handle_saida_sucesso(self, mock_update, mock_context):
        """Testa comando /saida bem-sucedido."""
        from app.bot_handlers import handle_saida

        mock_update.message.text = "/saida 35,90 frete"

        with patch('app.bot_handlers.ai_parser') as mock_parser, \
                patch('app.bot_handlers.sheets_manager') as mock_sheets, \
                patch('app.bot_handlers.rate_limiter') as mock_limiter:

            # Mock do parser
            lancamento = LancamentoFinanceiro(
                tipo="saida",
                valor=Decimal("35.90"),
                descricao="frete",
                categoria="logística",
                data="today"
            )
            mock_parser.parse_direct_command.return_value = lancamento

            # Mock rate limiter
            mock_limiter.is_allowed.return_value = True

            # Mock sheets
            mock_sheets.registrar_lancamento = Mock()

            await handle_saida(mock_update, mock_context)

            # Verifica resposta
            mock_update.message.reply_text.assert_called_once()
            args, kwargs = mock_update.message.reply_text.call_args
            resposta = args[0]

            assert "Saída registrada" in resposta
            assert "R$ 35" in resposta
            assert "frete" in resposta
            assert "logística" in resposta

    async def test_handle_saldo(self, mock_update, mock_context):
        """Testa comando /saldo."""
        from app.bot_handlers import handle_saldo

        with patch('app.bot_handlers.sheets_manager') as mock_sheets:
            # Mock do saldo
            saldo = SaldoGeral(
                saldo_total=Decimal("1000.50"),
                saldo_mes_atual=Decimal("250.00"),
                total_entradas=Decimal("2000.00"),
                total_saidas=Decimal("999.50"),
                mes_atual="2025-10"
            )
            mock_sheets.calcular_saldo.return_value = saldo

            await handle_saldo(mock_update, mock_context)

            # Verifica resposta
            mock_update.message.reply_text.assert_called_once()
            args, kwargs = mock_update.message.reply_text.call_args
            resposta = args[0]

            assert "Saldo Total" in resposta
            assert "1.000,50" in resposta
            assert "250,00" in resposta
            assert "2025-10" in resposta

    async def test_handle_relatorio_mes_atual(self, mock_update, mock_context):
        """Testa comando /relatorio sem argumentos (mês atual)."""
        from app.bot_handlers import handle_relatorio

        with patch('app.bot_handlers.sheets_manager') as mock_sheets:
            # Mock do relatório
            relatorio = RelatorioMensal(
                mes="2025-10",
                total_entradas=Decimal("1500.00"),
                total_saidas=Decimal("800.00"),
                saldo_mensal=Decimal("700.00"),
                quantidade_lancamentos=15
            )
            mock_sheets.gerar_relatorio_mensal.return_value = relatorio

            await handle_relatorio(mock_update, mock_context)

            # Verifica resposta
            mock_update.message.reply_text.assert_called_once()
            args, kwargs = mock_update.message.reply_text.call_args
            resposta = args[0]

            assert "Relatório Mensal" in resposta
            assert "2025-10" in resposta
            assert "1.500,00" in resposta
            assert "800,00" in resposta
            assert "700,00" in resposta
            assert "15" in resposta

    async def test_handle_relatorio_mes_especifico(self, mock_update, mock_context):
        """Testa comando /relatorio com mês específico."""
        from app.bot_handlers import handle_relatorio

        mock_context.args = ["2025-09"]

        with patch('app.bot_handlers.sheets_manager') as mock_sheets:
            relatorio = RelatorioMensal(
                mes="2025-09",
                total_entradas=Decimal("1200.00"),
                total_saidas=Decimal("900.00"),
                saldo_mensal=Decimal("300.00"),
                quantidade_lancamentos=10
            )
            mock_sheets.gerar_relatorio_mensal.return_value = relatorio

            await handle_relatorio(mock_update, mock_context)

            # Verifica que foi chamado com mês correto
            mock_sheets.gerar_relatorio_mensal.assert_called_once_with(
                12345, "2025-09")

    async def test_handle_free_text_sucesso(self, mock_update, mock_context):
        """Testa handler de mensagem livre bem-sucedido."""
        from app.bot_handlers import handle_free_text

        mock_update.message.text = "paguei 35,90 de frete hoje"

        with patch('app.bot_handlers.ai_parser') as mock_parser, \
                patch('app.bot_handlers.sheets_manager') as mock_sheets, \
                patch('app.bot_handlers.rate_limiter') as mock_limiter:

            # Mock do parser
            lancamento = LancamentoFinanceiro(
                tipo="saida",
                valor=Decimal("35.90"),
                descricao="frete",
                categoria="logística",
                data="today"
            )
            mock_parser.parse_message.return_value = lancamento

            # Mock rate limiter
            mock_limiter.is_allowed.return_value = True

            # Mock sheets
            mock_sheets.registrar_lancamento = Mock()

            await handle_free_text(mock_update, mock_context)

            # Verifica resposta
            mock_update.message.reply_text.assert_called_once()
            args, kwargs = mock_update.message.reply_text.call_args
            resposta = args[0]

            assert "registrada" in resposta
            assert "📉" in resposta  # Emoji de saída
            assert "35,90" in resposta

    async def test_handle_free_text_erro_parser(self, mock_update, mock_context):
        """Testa erro no parser de mensagem livre."""
        from app.bot_handlers import handle_free_text
        from app.ai_parser import OpenAIParseError

        mock_update.message.text = "mensagem inválida"

        with patch('app.bot_handlers.ai_parser') as mock_parser, \
                patch('app.bot_handlers.rate_limiter') as mock_limiter:

            # Mock rate limiter
            mock_limiter.is_allowed.return_value = True

            # Mock erro no parser
            mock_parser.parse_message.side_effect = OpenAIParseError(
                "Não entendi")

            await handle_free_text(mock_update, mock_context)

            # Verifica mensagem de erro
            mock_update.message.reply_text.assert_called_once()
            args, kwargs = mock_update.message.reply_text.call_args
            resposta = args[0]

            assert "Não consegui entender" in resposta
            assert "Tente algo como" in resposta
