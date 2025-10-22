"""
Aplicação principal do bot financeiro.
Configura e inicia o bot Telegram com todos os handlers.
"""
import asyncio
import logging
import signal
import sys
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

from .config import config, logger
from .bot_handlers import (
    handle_start, handle_help, handle_entrada, handle_saida,
    handle_saldo, handle_relatorio, handle_free_text, handle_error,
    handle_photo, handle_document
)
from .ai_parser import ai_parser
from .sheets import sheets_manager


class BotFinanceiro:
    """
    Classe principal do bot financeiro.
    Gerencia ciclo de vida e configuração do bot.
    """

    def __init__(self):
        """Inicializa o bot."""
        self.application: Optional[Application] = None
        self._is_running = False

    async def setup(self) -> None:
        """Configura o bot e seus handlers."""
        logger.info("Configurando bot financeiro...")

        # Cria aplicação
        self.application = Application.builder().token(config.telegram_bot_token).build()

        # Adiciona handlers de comandos
        self.application.add_handler(CommandHandler("start", handle_start))
        self.application.add_handler(CommandHandler("help", handle_help))
        self.application.add_handler(CommandHandler("entrada", handle_entrada))
        self.application.add_handler(CommandHandler("saida", handle_saida))
        self.application.add_handler(CommandHandler("saldo", handle_saldo))
        self.application.add_handler(
            CommandHandler("relatorio", handle_relatorio))

        # Handlers para uploads
        self.application.add_handler(
            MessageHandler(filters.PHOTO, handle_photo)
        )
        self.application.add_handler(
            MessageHandler(filters.Document.ALL, handle_document)
        )

        # Handler para mensagens livres (não comandos)
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_free_text)
        )

        # Handler global de erros
        self.application.add_error_handler(handle_error)

        logger.info("Handlers configurados com sucesso")

    async def test_connections(self) -> bool:
        """
        Testa conectividade com serviços externos.

        Returns:
            bool: True se todos os testes passaram
        """
        logger.info("Testando conectividade com serviços externos...")

        all_ok = True

        # Teste OpenAI
        try:
            ai_test = await ai_parser.test_connection()
            if ai_test:
                logger.info("✅ OpenAI - Conectividade OK")
            else:
                logger.error("❌ OpenAI - Falha na conectividade")
                all_ok = False
        except Exception as e:
            logger.error(f"❌ OpenAI - Erro no teste: {e}")
            all_ok = False

        # Teste Google Sheets
        try:
            sheets_test = sheets_manager.test_connection()
            if sheets_test:
                logger.info("✅ Google Sheets - Conectividade OK")
            else:
                logger.error("❌ Google Sheets - Falha na conectividade")
                all_ok = False
        except Exception as e:
            logger.error(f"❌ Google Sheets - Erro no teste: {e}")
            all_ok = False

        # Teste Telegram Bot
        try:
            bot_info = await self.application.bot.get_me()
            logger.info(f"✅ Telegram Bot - @{bot_info.username} conectado")
        except Exception as e:
            logger.error(f"❌ Telegram Bot - Erro: {e}")
            all_ok = False

        return all_ok

    async def start_polling(self) -> None:
        """Inicia o bot em modo polling (desenvolvimento)."""
        if not self.application:
            await self.setup()

        logger.info("Iniciando bot em modo polling...")
        self._is_running = True

        try:
            # Testa conectividade
            if not await self.test_connections():
                logger.warning(
                    "Alguns serviços falharam no teste, mas continuando...")

            # Inicia polling
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )

            logger.info(
                "🚀 Bot iniciado com sucesso! Pressione Ctrl+C para parar.")

            # Mantém o bot rodando
            while self._is_running:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Interrupção pelo usuário (Ctrl+C)")
        except Exception as e:
            logger.error(f"Erro durante execução: {e}")
            raise
        finally:
            await self.stop()

    async def start_webhook(self, webhook_url: str, port: int = 8080) -> None:
        """
        Inicia o bot em modo webhook (produção).

        Args:
            webhook_url: URL pública para webhook
            port: Porta para escutar webhook
        """
        if not self.application:
            await self.setup()

        logger.info(f"Iniciando bot em modo webhook na porta {port}...")
        self._is_running = True

        try:
            # Testa conectividade
            if not await self.test_connections():
                logger.warning(
                    "Alguns serviços falharam no teste, mas continuando...")

            # Configura webhook
            await self.application.initialize()
            await self.application.start()
            await self.application.bot.set_webhook(
                url=f"{webhook_url}/webhook",
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )

            # Inicia servidor webhook
            await self.application.updater.start_webhook(
                listen="0.0.0.0",
                port=port,
                webhook_url=f"{webhook_url}/webhook"
            )

            logger.info(f"🚀 Bot webhook iniciado em {webhook_url}!")

            # Mantém o bot rodando
            while self._is_running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Erro durante execução webhook: {e}")
            raise
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Para o bot graciosamente."""
        logger.info("Parando bot...")
        self._is_running = False

        if self.application:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
                logger.info("✅ Bot parado com sucesso")
            except Exception as e:
                logger.error(f"Erro ao parar bot: {e}")

    def setup_signal_handlers(self) -> None:
        """Configura handlers para sinais do sistema."""
        def signal_handler(signum, frame):
            logger.info(f"Recebido sinal {signum}, parando bot...")
            self._is_running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def create_healthcheck_endpoint() -> None:
    """Cria endpoint simples de healthcheck para deploy."""
    from aiohttp import web

    async def health(request):
        return web.json_response({"status": "healthy", "service": "telegram-finance-bot"})

    app = web.Application()
    app.router.add_get("/healthz", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8081)
    await site.start()
    logger.info(
        "💚 Healthcheck endpoint disponível em http://0.0.0.0:8081/healthz")


async def main() -> None:
    """Função principal da aplicação."""
    logger.info("🤖 Iniciando Bot Financeiro Telegram...")
    logger.info(f"Ambiente: {config.app_env}")

    bot = BotFinanceiro()
    bot.setup_signal_handlers()

    try:
        # Inicia healthcheck em background
        if config.is_production:
            asyncio.create_task(create_healthcheck_endpoint())

        # Decide modo de execução
        if config.is_production and config.webhook_url:
            # Produção com webhook
            await bot.start_webhook(config.webhook_url, config.webhook_port)
        else:
            # Desenvolvimento com polling
            await bot.start_polling()

    except KeyboardInterrupt:
        logger.info("Aplicação interrompida pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal na aplicação: {e}")
        sys.exit(1)
    finally:
        logger.info("👋 Bot financeiro finalizado")


if __name__ == "__main__":
    """Ponto de entrada quando executado diretamente."""
    try:
        # Usa uvloop se disponível (Linux)
        try:
            import uvloop
            uvloop.install()
            logger.info("🚀 Usando uvloop para melhor performance")
        except ImportError:
            pass

        # Executa aplicação
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info("Aplicação cancelada pelo usuário")
    except Exception as e:
        logger.error(f"Erro crítico: {e}")
        sys.exit(1)
