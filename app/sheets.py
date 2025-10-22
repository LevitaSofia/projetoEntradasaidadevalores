"""
Integração com Google Sheets para armazenar dados financeiros.
Gerencia leitura e escrita na planilha.
"""
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Dict, Any
from tenacity import retry, wait_exponential, stop_after_attempt

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, SpreadsheetNotFound, WorksheetNotFound

from .config import config
from .models import LancamentoFinanceiro, LancamentoPlanilha, UsuarioTelegram, RelatorioMensal, SaldoGeral, TZ_BRASIL

logger = logging.getLogger(__name__)


class SheetsManagerError(Exception):
    """Erro específico do gerenciador de planilhas."""
    pass


class GoogleSheetsManager:
    """
    Gerenciador para operações no Google Sheets.
    Responsável por ler e escrever dados da planilha.
    """

    def __init__(self):
        """Inicializa cliente Google Sheets."""
        self._client = None
        self._spreadsheet = None
        self._ws_movimentos = None
        self._ws_usuarios = None
        self._setup_sheets()

    def _setup_sheets(self) -> None:
        """Configura acesso às planilhas."""
        try:
            # Configura credenciais
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]

            creds = Credentials.from_service_account_info(
                config.google_service_account_json,
                scopes=scopes
            )

            # Inicializa cliente
            self._client = gspread.authorize(creds)

            # Abre planilha
            self._spreadsheet = self._client.open_by_key(
                config.google_sheet_id)

            # Configura abas
            self._setup_worksheets()

            logger.info("Google Sheets configurado com sucesso")

        except Exception as e:
            error_msg = f"Erro ao configurar Google Sheets: {e}"
            logger.error(error_msg)
            raise SheetsManagerError(error_msg)

    def _setup_worksheets(self) -> None:
        """Configura as abas da planilha."""
        # Aba de usuários
        try:
            self._ws_usuarios = self._spreadsheet.worksheet("usuarios")
        except WorksheetNotFound:
            logger.info("Criando aba 'usuarios'")
            self._ws_usuarios = self._spreadsheet.add_worksheet(
                title="usuarios",
                rows=1000,
                cols=3
            )
            # Adiciona cabeçalhos
            self._ws_usuarios.append_row([
                "chat_id", "nome", "primeiro_uso"
            ])

        # Configura aba do mês atual
        self._setup_current_month_worksheet()

    def _get_month_worksheet_name(self, data: Optional[date] = None) -> str:
        """Retorna o nome da aba para um mês específico."""
        if data is None:
            data = datetime.now(TZ_BRASIL).date()
        return data.strftime("%Y-%m")

    def _setup_current_month_worksheet(self) -> None:
        """Configura a aba do mês atual."""
        mes_atual = self._get_month_worksheet_name()

        try:
            self._ws_movimentos = self._spreadsheet.worksheet(mes_atual)
        except WorksheetNotFound:
            logger.info(f"Criando aba '{mes_atual}'")
            self._ws_movimentos = self._spreadsheet.add_worksheet(
                title=mes_atual,
                rows=1000,
                cols=13
            )
            # Adiciona cabeçalhos principais
            self._ws_movimentos.append_row([
                "timestamp", "chat_id", "usuario", "tipo", "valor",
                "descricao", "categoria", "data_lancamento", "message_id",
                "comprovante", "TOTAIS", "VALORES"
            ])

            # Adiciona linha de totais com fórmulas
            self._setup_totals_formulas(mes_atual)

    def _setup_totals_formulas(self, worksheet_name: str) -> None:
        """Configura fórmulas de totais para a aba."""
        ws = self._spreadsheet.worksheet(worksheet_name)

        # Linha 2: Títulos dos totais
        ws.update('K2:L2', [['TOTAL ENTRADAS:', '=SUMIF(D:D,"entrada",E:E)']])

        # Linha 3: Total saídas
        ws.update('K3:L3', [['TOTAL SAÍDAS:', '=SUMIF(D:D,"saida",E:E)']])

        # Linha 4: Saldo do mês
        ws.update('K4:L4', [['SALDO MENSAL:', '=L2-L3']])

        # Linha 5: Quantidade de lançamentos
        ws.update('K5:L5', [['QTD LANÇAMENTOS:', '=COUNTA(D:D)-1']])

        # Formatação das células de totais
        ws.format('K2:K5', {'textFormat': {'bold': True}})
        ws.format('L2:L5', {'numberFormat': {
                  'type': 'CURRENCY', 'pattern': 'R$ #,##0.00'}})

    def _ensure_month_worksheet(self, data: date) -> None:
        """Garante que a aba do mês existe."""
        mes_nome = self._get_month_worksheet_name(data)

        try:
            ws = self._spreadsheet.worksheet(mes_nome)
            self._ws_movimentos = ws
        except WorksheetNotFound:
            logger.info(f"Criando nova aba para mês '{mes_nome}'")
            self._ws_movimentos = self._spreadsheet.add_worksheet(
                title=mes_nome,
                rows=1000,
                cols=13
            )

            # Adiciona cabeçalhos
            self._ws_movimentos.append_row([
                "timestamp", "chat_id", "usuario", "tipo", "valor",
                "descricao", "categoria", "data_lancamento", "message_id",
                "comprovante", "TOTAIS", "VALORES"
            ])

            # Configura fórmulas de totais
            self._setup_totals_formulas(mes_nome)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        before_sleep=lambda retry_state: logger.warning(
            f"Tentativa {retry_state.attempt_number} falhou, tentando novamente..."
        )
    )
    def registrar_lancamento(
        self,
        lancamento: LancamentoFinanceiro,
        chat_id: int,
        usuario: str,
        message_id: int,
        data_resolvida: date,
        comprovante_link: str = ""
    ) -> None:
        """
        Registra um lançamento na planilha.

        Args:
            lancamento: Dados do lançamento
            chat_id: ID do chat Telegram
            usuario: Nome do usuário
            message_id: ID da mensagem
            data_resolvida: Data resolvida do lançamento
            comprovante_link: Link do comprovante no Google Drive
        """
        try:
            # Garante que a aba do mês existe
            self._ensure_month_worksheet(data_resolvida)

            # Converte para modelo da planilha
            dados_planilha = LancamentoPlanilha.from_lancamento(
                lancamento=lancamento,
                chat_id=chat_id,
                usuario=usuario,
                message_id=message_id,
                data_resolivda=data_resolvida,
                comprovante_link=comprovante_link
            )

            # Prepara linha para inserção
            linha = [
                dados_planilha.timestamp.isoformat(),
                dados_planilha.chat_id,
                dados_planilha.usuario,
                dados_planilha.tipo,
                dados_planilha.valor,
                dados_planilha.descricao,
                dados_planilha.categoria,
                dados_planilha.data_lancamento,
                dados_planilha.message_id,
                dados_planilha.comprovante_link
            ]

            # Insere na planilha do mês correto
            if self._ws_movimentos:
                self._ws_movimentos.append_row(linha)

            logger.info(
                f"Lançamento registrado na aba {self._get_month_worksheet_name(data_resolvida)}: "
                f"{lancamento.tipo} R$ {lancamento.valor} para usuário {chat_id}"
            )

        except APIError as e:
            error_msg = f"Erro da API Google Sheets: {e}"
            logger.error(error_msg)
            raise SheetsManagerError(error_msg)
        except Exception as e:
            error_msg = f"Erro ao registrar lançamento: {e}"
            logger.error(error_msg)
            raise SheetsManagerError(error_msg)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3)
    )
    def registrar_usuario(self, usuario: UsuarioTelegram) -> None:
        """
        Registra um novo usuário na planilha.

        Args:
            usuario: Dados do usuário
        """
        try:
            # Verifica se usuário já existe
            if self._usuario_existe(usuario.chat_id):
                logger.debug(
                    f"Usuário {usuario.chat_id} já existe, não registrando novamente")
                return

            linha = [
                str(usuario.chat_id),
                usuario.nome,
                usuario.primeiro_uso.isoformat()
            ]

            self._ws_usuarios.append_row(linha)
            logger.info(f"Usuário {usuario.chat_id} registrado")

        except Exception as e:
            logger.error(f"Erro ao registrar usuário: {e}")
            # Não levanta exceção para não interromper fluxo principal

    def _usuario_existe(self, chat_id: int) -> bool:
        """Verifica se usuário já está registrado."""
        try:
            usuarios = self._ws_usuarios.get_all_records()
            return any(int(u.get("chat_id", 0)) == chat_id for u in usuarios)
        except Exception:
            return False

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=5),
        stop=stop_after_attempt(2)
    )
    def calcular_saldo(self, chat_id: int) -> SaldoGeral:
        """
        Calcula saldo geral e do mês atual para um usuário.

        Args:
            chat_id: ID do chat do usuário

        Returns:
            SaldoGeral: Dados do saldo
        """
        try:
            # Busca todos os worksheets que são meses (formato YYYY-MM)
            worksheets = self._spreadsheet.worksheets()
            mes_atual = datetime.now(TZ_BRASIL).strftime("%Y-%m")

            total_entradas = Decimal("0")
            total_saidas = Decimal("0")
            saldo_mes_atual = Decimal("0")

            # Percorre todas as abas mensais
            for ws in worksheets:
                # Verifica se é uma aba de mês (formato YYYY-MM)
                if not self._is_month_worksheet(ws.title):
                    continue

                try:
                    movimentos = ws.get_all_records()

                    # Filtra por usuário
                    movimentos_usuario = [
                        m for m in movimentos
                        if str(m.get("chat_id", "")) == str(chat_id)
                    ]

                    for movimento in movimentos_usuario:
                        try:
                            valor = Decimal(str(movimento.get("valor", 0)))
                            tipo = movimento.get("tipo", "").lower()

                            if tipo == "entrada":
                                total_entradas += valor
                                if ws.title == mes_atual:
                                    saldo_mes_atual += valor
                            elif tipo == "saida":
                                total_saidas += valor
                                if ws.title == mes_atual:
                                    saldo_mes_atual -= valor

                        except (ValueError, TypeError) as e:
                            logger.warning(f"Erro ao processar movimento: {e}")
                            continue

                except Exception as e:
                    logger.warning(f"Erro ao acessar aba {ws.title}: {e}")
                    continue

            saldo_total = total_entradas - total_saidas

            return SaldoGeral(
                saldo_total=saldo_total,
                saldo_mes_atual=saldo_mes_atual,
                total_entradas=total_entradas,
                total_saidas=total_saidas,
                mes_atual=mes_atual
            )

        except Exception as e:
            error_msg = f"Erro ao calcular saldo: {e}"
            logger.error(error_msg)
            raise SheetsManagerError(error_msg)

    def _is_month_worksheet(self, title: str) -> bool:
        """Verifica se o título da aba é um mês válido (formato YYYY-MM)."""
        try:
            datetime.strptime(title, "%Y-%m")
            return True
        except ValueError:
            return False

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=5),
        stop=stop_after_attempt(2)
    )
    def gerar_relatorio_mensal(self, chat_id: int, mes: str) -> RelatorioMensal:
        """
        Gera relatório mensal para um usuário.

        Args:
            chat_id: ID do chat do usuário
            mes: Mês no formato YYYY-MM

        Returns:
            RelatorioMensal: Dados do relatório
        """
        try:
            # Verifica se a aba do mês existe
            try:
                ws_mes = self._spreadsheet.worksheet(mes)
                movimentos = ws_mes.get_all_records()
            except WorksheetNotFound:
                # Mês não existe, retorna relatório vazio
                return RelatorioMensal(
                    mes=mes,
                    total_entradas=Decimal("0"),
                    total_saidas=Decimal("0"),
                    saldo_mensal=Decimal("0"),
                    quantidade_lancamentos=0
                )

            # Filtra por usuário
            movimentos_filtrados = [
                m for m in movimentos
                if str(m.get("chat_id", "")) == str(chat_id)
            ]

            total_entradas = Decimal("0")
            total_saidas = Decimal("0")

            for movimento in movimentos_filtrados:
                try:
                    valor = Decimal(str(movimento.get("valor", 0)))
                    tipo = movimento.get("tipo", "").lower()

                    if tipo == "entrada":
                        total_entradas += valor
                    elif tipo == "saida":
                        total_saidas += valor

                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Erro ao processar movimento no relatório: {e}")
                    continue

            saldo_mensal = total_entradas - total_saidas

            return RelatorioMensal(
                mes=mes,
                total_entradas=total_entradas,
                total_saidas=total_saidas,
                saldo_mensal=saldo_mensal,
                quantidade_lancamentos=len(movimentos_filtrados)
            )

        except Exception as e:
            error_msg = f"Erro ao gerar relatório mensal: {e}"
            logger.error(error_msg)
            raise SheetsManagerError(error_msg)

    def test_connection(self) -> bool:
        """
        Testa conectividade com Google Sheets.

        Returns:
            bool: True se conexão ok, False caso contrário
        """
        try:
            # Tenta acessar metadados da planilha
            title = self._spreadsheet.title
            logger.info(
                f"Teste de conexão Google Sheets OK - Planilha: {title}")
            return True
        except Exception as e:
            logger.error(f"Erro no teste de conexão Google Sheets: {e}")
            return False


# Instância global do gerenciador
sheets_manager = GoogleSheetsManager()
