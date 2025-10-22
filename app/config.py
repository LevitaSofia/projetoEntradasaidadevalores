"""
Configurações da aplicação.
Carrega e valida variáveis de ambiente.
"""
import os
import json
import logging
from typing import Optional
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env em desenvolvimento
load_dotenv()


class Config:
    """Configurações centralizadas da aplicação."""

    def __init__(self):
        """Inicializa e valida configurações."""
        self._validate_required_env_vars()
        self._setup_logging()

    # Configurações do Telegram
    @property
    def telegram_bot_token(self) -> str:
        """Token do bot do Telegram."""
        return os.environ["TELEGRAM_BOT_TOKEN"]

    # Configurações OpenAI
    @property
    def openai_api_key(self) -> str:
        """Chave da API OpenAI."""
        return os.environ["OPENAI_API_KEY"]

    @property
    def openai_model(self) -> str:
        """Modelo OpenAI a ser usado."""
        return os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # Configurações Google Sheets
    @property
    def google_sheet_id(self) -> str:
        """ID da planilha Google Sheets."""
        return os.environ["GOOGLE_SHEET_ID"]

    @property
    def google_service_account_json(self) -> dict:
        """Credenciais da Service Account do Google."""
        json_str = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]

        # Se começar com {, é JSON inline
        if json_str.strip().startswith("{"):
            return json.loads(json_str)

        # Senão, é caminho para arquivo
        with open(json_str, 'r', encoding='utf-8') as f:
            return json.load(f)

    # Configurações da aplicação
    @property
    def app_env(self) -> str:
        """Ambiente da aplicação (dev/prod)."""
        return os.environ.get("APP_ENV", "dev")

    @property
    def is_development(self) -> bool:
        """Verifica se está em ambiente de desenvolvimento."""
        return self.app_env == "dev"

    @property
    def is_production(self) -> bool:
        """Verifica se está em ambiente de produção."""
        return self.app_env == "prod"

    @property
    def rate_limit_per_user(self) -> int:
        """Limite de requisições por segundo por usuário."""
        return int(os.environ.get("RATE_LIMIT_PER_USER", "2"))

    @property
    def log_level(self) -> str:
        """Nível de log."""
        return os.environ.get("LOG_LEVEL", "INFO")

    @property
    def webhook_url(self) -> Optional[str]:
        """URL do webhook para produção."""
        return os.environ.get("WEBHOOK_URL")

    @property
    def webhook_port(self) -> int:
        """Porta para webhook."""
        return int(os.environ.get("PORT", "8080"))

    def _validate_required_env_vars(self) -> None:
        """Valida se todas as variáveis obrigatórias estão definidas."""
        required_vars = [
            "TELEGRAM_BOT_TOKEN",
            "OPENAI_API_KEY",
            "GOOGLE_SHEET_ID",
            "GOOGLE_SERVICE_ACCOUNT_JSON"
        ]

        missing_vars = []
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)

        if missing_vars:
            raise ValueError(
                f"Variáveis de ambiente obrigatórias não definidas: {', '.join(missing_vars)}\n"
                f"Verifique seu arquivo .env ou variáveis de ambiente do sistema."
            )

    def _setup_logging(self) -> None:
        """Configura sistema de logging."""
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
            ]
        )

        # Configura logging específico para bibliotecas externas
        if self.is_production:
            # Em produção, reduz verbosidade de bibliotecas
            logging.getLogger("httpx").setLevel(logging.WARNING)
            logging.getLogger("telegram").setLevel(logging.WARNING)
            logging.getLogger("openai").setLevel(logging.WARNING)
            logging.getLogger("gspread").setLevel(logging.WARNING)


# Instância global de configuração
config = Config()

# Logger global
logger = logging.getLogger(__name__)
