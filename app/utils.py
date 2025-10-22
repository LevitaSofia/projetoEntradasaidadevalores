"""
Funções utilitárias para o bot financeiro.
Inclui manipulação de datas, formatação e rate limiting.
"""
import re
import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Optional, Any
from collections import defaultdict, deque
import pytz

from .models import TZ_BRASIL

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiter simples por usuário.
    Controla quantas requisições um usuário pode fazer por segundo.
    """

    def __init__(self, max_requests_per_second: int = 2):
        """
        Inicializa rate limiter.

        Args:
            max_requests_per_second: Máximo de requisições por segundo por usuário
        """
        self.max_requests = max_requests_per_second
        self.user_requests: Dict[int, deque] = defaultdict(deque)

    def is_allowed(self, user_id: int) -> bool:
        """
        Verifica se usuário pode fazer uma nova requisição.

        Args:
            user_id: ID do usuário

        Returns:
            bool: True se permitido, False se deve aguardar
        """
        now = datetime.now()
        user_deque = self.user_requests[user_id]

        # Remove requisições antigas (mais de 1 segundo)
        while user_deque and (now - user_deque[0]).total_seconds() > 1:
            user_deque.popleft()

        # Verifica se pode fazer nova requisição
        if len(user_deque) < self.max_requests:
            user_deque.append(now)
            return True

        return False

    def get_wait_time(self, user_id: int) -> float:
        """
        Retorna tempo de espera em segundos para próxima requisição.

        Args:
            user_id: ID do usuário

        Returns:
            float: Segundos para aguardar
        """
        user_deque = self.user_requests[user_id]
        if not user_deque:
            return 0.0

        oldest_request = user_deque[0]
        elapsed = (datetime.now() - oldest_request).total_seconds()
        return max(0.0, 1.0 - elapsed)


def resolve_date(data_str: Optional[str]) -> date:
    """
    Resolve string de data para objeto date.

    Args:
        data_str: String da data ('today', 'yesterday', 'YYYY-MM-DD' ou None)

    Returns:
        date: Data resolvida

    Raises:
        ValueError: Data em formato inválido
    """
    if not data_str or data_str.lower() == "today":
        return datetime.now(TZ_BRASIL).date()

    if data_str.lower() == "yesterday":
        return (datetime.now(TZ_BRASIL) - timedelta(days=1)).date()

    # Tenta parse YYYY-MM-DD
    try:
        return datetime.strptime(data_str, "%Y-%m-%d").date()
    except ValueError:
        # Tenta outros formatos comuns
        formatos = ["%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"]

        for formato in formatos:
            try:
                return datetime.strptime(data_str, formato).date()
            except ValueError:
                continue

        raise ValueError(
            f"Formato de data inválido: '{data_str}'. "
            f"Use 'today', 'yesterday' ou YYYY-MM-DD"
        )


def format_currency(valor: float) -> str:
    """
    Formata valor monetário em formato brasileiro.

    Args:
        valor: Valor numérico

    Returns:
        str: Valor formatado (ex: "R$ 1.234,56")
    """
    # Formata com separadores
    formatted = f"{valor:,.2f}"

    # Converte para padrão brasileiro (ponto para milhar, vírgula para decimal)
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    return f"R$ {formatted}"


def parse_month(mes_str: Optional[str]) -> str:
    """
    Valida e normaliza string de mês.

    Args:
        mes_str: String do mês (YYYY-MM, MM/YYYY, ou vazio para mês atual)

    Returns:
        str: Mês no formato YYYY-MM

    Raises:
        ValueError: Formato de mês inválido
    """
    if not mes_str:
        return datetime.now(TZ_BRASIL).strftime("%Y-%m")

    mes_str = mes_str.strip()

    # Tenta formato YYYY-MM
    if re.match(r'^\d{4}-\d{2}$', mes_str):
        year, month = mes_str.split('-')
        if 1 <= int(month) <= 12:
            return mes_str
        else:
            raise ValueError(f"Mês inválido: {month}")

    # Tenta formato MM/YYYY
    if re.match(r'^\d{1,2}/\d{4}$', mes_str):
        month, year = mes_str.split('/')
        month = month.zfill(2)  # Adiciona zero à esquerda se necessário
        if 1 <= int(month) <= 12:
            return f"{year}-{month}"
        else:
            raise ValueError(f"Mês inválido: {month}")

    # Tenta apenas ano (retorna janeiro do ano)
    if re.match(r'^\d{4}$', mes_str):
        return f"{mes_str}-01"

    raise ValueError(
        f"Formato de mês inválido: '{mes_str}'. "
        f"Use YYYY-MM ou MM/YYYY"
    )


def clean_text(text: str) -> str:
    """
    Limpa texto removendo caracteres especiais e normalizando.

    Args:
        text: Texto para limpar

    Returns:
        str: Texto limpo
    """
    if not text:
        return ""

    # Remove espaços extras
    text = " ".join(text.split())

    # Remove caracteres de controle
    text = "".join(char for char in text if ord(char) >= 32)

    return text.strip()


def extract_amount_from_text(text: str) -> Optional[float]:
    """
    Extrai valor monetário de texto livre.

    Args:
        text: Texto contendo valor

    Returns:
        Optional[float]: Valor extraído ou None se não encontrado
    """
    # Padrões para valores monetários
    patterns = [
        r'R?\$?\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)',  # R$ 1.234,56
        r'(\d+(?:,\d{2})?)',  # 1234,56
        r'(\d+(?:\.\d{2})?)',  # 1234.56
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            valor_str = match.group(1)
            # Converte para formato padrão
            valor_str = valor_str.replace(".", "").replace(",", ".")
            try:
                return float(valor_str)
            except ValueError:
                continue

    return None


def validate_telegram_message(text: str) -> bool:
    """
    Valida se texto é uma mensagem válida do Telegram.

    Args:
        text: Texto da mensagem

    Returns:
        bool: True se válida, False caso contrário
    """
    if not text or not text.strip():
        return False

    # Verifica tamanho (Telegram tem limite de ~4096 caracteres)
    if len(text) > 4000:
        return False

    # Verifica se não é apenas espaços ou caracteres especiais
    if not any(char.isalnum() for char in text):
        return False

    return True


def get_user_display_name(user) -> str:
    """
    Extrai nome de exibição de usuário do Telegram.

    Args:
        user: Objeto User do Telegram

    Returns:
        str: Nome para exibição
    """
    if not user:
        return "Usuário Anônimo"

    # Prioriza full_name, depois first_name, depois username
    if hasattr(user, 'full_name') and user.full_name:
        return clean_text(user.full_name)

    if hasattr(user, 'first_name') and user.first_name:
        name = clean_text(user.first_name)
        if hasattr(user, 'last_name') and user.last_name:
            name += f" {clean_text(user.last_name)}"
        return name

    if hasattr(user, 'username') and user.username:
        return f"@{user.username}"

    return "Usuário Anônimo"


def log_user_action(chat_id: int, username: str, action: str, details: str = "") -> None:
    """
    Registra ação do usuário nos logs.

    Args:
        chat_id: ID do chat
        username: Nome do usuário
        action: Ação realizada
        details: Detalhes adicionais
    """
    log_msg = f"User {chat_id} ({username}) - {action}"
    if details:
        log_msg += f" - {details}"

    logger.info(log_msg)


def safe_int(value: Any, default: int = 0) -> int:
    """
    Converte valor para int de forma segura.

    Args:
        value: Valor para converter
        default: Valor padrão se conversão falhar

    Returns:
        int: Valor convertido ou padrão
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Converte valor para float de forma segura.

    Args:
        value: Valor para converter
        default: Valor padrão se conversão falhar

    Returns:
        float: Valor convertido ou padrão
    """
    try:
        if isinstance(value, str):
            value = value.replace(",", ".")
        return float(value)
    except (ValueError, TypeError):
        return default


async def async_retry(func, max_attempts: int = 3, delay: float = 1.0):
    """
    Executa função com retry assíncrono.

    Args:
        func: Função para executar
        max_attempts: Máximo de tentativas
        delay: Delay entre tentativas

    Returns:
        Resultado da função

    Raises:
        Exception: Última exceção se todas as tentativas falharem
    """
    last_exception = None

    for attempt in range(max_attempts):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func()
            else:
                return func()
        except Exception as e:
            last_exception = e
            if attempt < max_attempts - 1:
                logger.warning(
                    f"Tentativa {attempt + 1} falhou: {e}. Tentando novamente...")
                await asyncio.sleep(delay * (attempt + 1))
            else:
                logger.error(f"Todas as {max_attempts} tentativas falharam")

    raise last_exception


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Trunca texto se muito longo.

    Args:
        text: Texto para truncar
        max_length: Comprimento máximo

    Returns:
        str: Texto truncado se necessário
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    return text[:max_length - 3] + "..."


# Instância global do rate limiter
rate_limiter = RateLimiter(max_requests_per_second=2)
