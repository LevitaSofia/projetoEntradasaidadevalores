"""
Modelos de dados usando Pydantic para validação.
Define estruturas para lançamentos financeiros e respostas da IA.
"""
from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import pytz

# Timezone brasileiro
TZ_BRASIL = pytz.timezone("America/Sao_Paulo")


class LancamentoFinanceiro(BaseModel):
    """
    Modelo para lançamentos financeiros.
    Representa uma entrada ou saída de dinheiro.
    """
    tipo: Literal["entrada", "saida"] = Field(
        description="Tipo do lançamento: entrada (recebimento) ou saida (pagamento)"
    )
    valor: Decimal = Field(
        description="Valor do lançamento em reais",
        gt=0
    )
    descricao: str = Field(
        description="Descrição do lançamento",
        min_length=1,
        max_length=200
    )
    categoria: Optional[str] = Field(
        default="",
        description="Categoria opcional do lançamento",
        max_length=50
    )
    data: Optional[str] = Field(
        default="today",
        description="Data do lançamento: 'today', 'yesterday' ou YYYY-MM-DD"
    )

    @field_validator("tipo")
    @classmethod
    def validar_tipo(cls, v: str) -> str:
        """Valida e normaliza o tipo de lançamento."""
        v = v.lower().strip()
        if v not in {"entrada", "saida"}:
            raise ValueError(f"Tipo inválido '{v}'. Use 'entrada' ou 'saida'")
        return v

    @field_validator("valor", mode="before")
    @classmethod
    def validar_valor(cls, v) -> Decimal:
        """Valida e converte o valor para Decimal."""
        if isinstance(v, (int, float)):
            return Decimal(str(v))

        if isinstance(v, str):
            # Remove espaços e substitui vírgula por ponto
            v = v.strip().replace(",", ".")

            # Remove caracteres não numéricos exceto ponto
            import re
            v = re.sub(r'[^\d.]', '', v)

            try:
                valor = Decimal(v)
                if valor <= 0:
                    raise ValueError("Valor deve ser maior que zero")
                return valor
            except (InvalidOperation, ValueError) as e:
                raise ValueError(
                    f"Valor inválido '{v}'. Use formato: 123.45 ou 123,45")

        if isinstance(v, Decimal):
            if v <= 0:
                raise ValueError("Valor deve ser maior que zero")
            return v

        raise ValueError(f"Tipo de valor não suportado: {type(v)}")

    @field_validator("descricao")
    @classmethod
    def validar_descricao(cls, v: str) -> str:
        """Valida e limpa a descrição."""
        v = v.strip()
        if not v:
            raise ValueError("Descrição não pode estar vazia")
        return v

    @field_validator("categoria")
    @classmethod
    def validar_categoria(cls, v: Optional[str]) -> str:
        """Valida e limpa a categoria."""
        if v is None:
            return ""
        return v.strip()

    @model_validator(mode="after")
    def validar_modelo_completo(self):
        """Validações que dependem de múltiplos campos."""
        # Verifica se a descrição não é apenas números
        if self.descricao.replace(",", ".").replace(" ", "").isdigit():
            raise ValueError("Descrição deve conter texto, não apenas números")

        return self


class UsuarioTelegram(BaseModel):
    """Modelo para usuários do Telegram."""
    chat_id: int = Field(description="ID do chat no Telegram")
    nome: str = Field(description="Nome do usuário", max_length=100)
    primeiro_uso: datetime = Field(description="Data do primeiro uso do bot")

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, v: str) -> str:
        """Valida o nome do usuário."""
        v = v.strip()
        if not v:
            return "Usuário Anônimo"
        return v


class LancamentoPlanilha(BaseModel):
    """Modelo para dados que vão para a planilha."""
    timestamp: datetime = Field(description="Timestamp do registro")
    chat_id: str = Field(description="ID do chat como string")
    usuario: str = Field(description="Nome do usuário")
    tipo: str = Field(description="Tipo do lançamento")
    valor: float = Field(description="Valor como float")
    descricao: str = Field(description="Descrição")
    categoria: str = Field(description="Categoria")
    data_lancamento: str = Field(description="Data do lançamento YYYY-MM-DD")
    message_id: str = Field(description="ID da mensagem no Telegram")
    comprovante_link: str = Field(default="", description="Link do comprovante no Google Drive")

    @classmethod
    def from_lancamento(
        cls,
        lancamento: LancamentoFinanceiro,
        chat_id: int,
        usuario: str,
        message_id: int,
        data_resolivda: date,
        comprovante_link: str = ""
    ) -> "LancamentoPlanilha":
        """Cria instância a partir de um LancamentoFinanceiro."""
        return cls(
            timestamp=datetime.now(TZ_BRASIL),
            chat_id=str(chat_id),
            usuario=usuario,
            tipo=lancamento.tipo,
            valor=float(lancamento.valor),
            descricao=lancamento.descricao,
            categoria=lancamento.categoria,
            data_lancamento=data_resolivda.strftime("%Y-%m-%d"),
            message_id=str(message_id),
            comprovante_link=comprovante_link
        )


class RespostaIA(BaseModel):
    """Modelo para resposta estruturada da OpenAI."""
    tipo: Literal["entrada", "saida"]
    valor: float
    descricao: str
    categoria: Optional[str] = None
    data: Optional[str] = "today"

    def to_lancamento(self) -> LancamentoFinanceiro:
        """Converte para LancamentoFinanceiro."""
        return LancamentoFinanceiro(
            tipo=self.tipo,
            valor=self.valor,
            descricao=self.descricao,
            categoria=self.categoria or "",
            data=self.data or "today"
        )


class RelatorioMensal(BaseModel):
    """Modelo para relatório mensal."""
    mes: str = Field(description="Mês no formato YYYY-MM")
    total_entradas: Decimal = Field(description="Total de entradas")
    total_saidas: Decimal = Field(description="Total de saídas")
    saldo_mensal: Decimal = Field(description="Saldo do mês")
    quantidade_lancamentos: int = Field(description="Número de lançamentos")

    @property
    def saldo_formatado(self) -> str:
        """Retorna saldo formatado em reais."""
        return f"R$ {self.saldo_mensal:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @property
    def entradas_formatadas(self) -> str:
        """Retorna entradas formatadas em reais."""
        return f"R$ {self.total_entradas:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @property
    def saidas_formatadas(self) -> str:
        """Retorna saídas formatadas em reais."""
        return f"R$ {self.total_saidas:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class SaldoGeral(BaseModel):
    """Modelo para saldo geral do usuário."""
    saldo_total: Decimal = Field(description="Saldo total acumulado")
    saldo_mes_atual: Decimal = Field(description="Saldo do mês atual")
    total_entradas: Decimal = Field(description="Total de entradas")
    total_saidas: Decimal = Field(description="Total de saídas")
    mes_atual: str = Field(description="Mês atual YYYY-MM")

    @property
    def saldo_total_formatado(self) -> str:
        """Retorna saldo total formatado."""
        return f"R$ {self.saldo_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @property
    def saldo_mes_formatado(self) -> str:
        """Retorna saldo do mês formatado."""
        return f"R$ {self.saldo_mes_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
