"""
Handlers para comandos e mensagens do bot Telegram.
Processa comandos financeiros e mensagens livres do usuário.
"""
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from .config import config
from .models import UsuarioTelegram, TZ_BRASIL
from .ai_parser import ai_parser, OpenAIParseError
from .sheets import sheets_manager, SheetsManagerError
from .drive_manager import drive_manager, DriveManagerError
from .vision_analyzer import vision_analyzer, VisionAnalyzerError
from .utils import (
    rate_limiter, resolve_date, parse_month,
    get_user_display_name, log_user_action,
    validate_telegram_message, truncate_text
)

logger = logging.getLogger(__name__)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para comando /start.
    Apresenta o bot e suas funcionalidades.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = get_user_display_name(user)

    log_user_action(chat_id, username, "comando /start")

    # Registra usuário se for a primeira vez
    try:
        usuario = UsuarioTelegram(
            chat_id=chat_id,
            nome=username,
            primeiro_uso=datetime.now(TZ_BRASIL)
        )
        sheets_manager.registrar_usuario(usuario)
    except Exception as e:
        logger.warning(f"Erro ao registrar usuário {chat_id}: {e}")

    mensagem = f"""🤖 Olá, {username}! Bem-vindo ao seu assistente financeiro!

📝 **Como usar:**
• `/entrada 150 venda produto` - Registra entrada direta
• `/saida 35,90 frete` - Registra saída direta
• `paguei 49,90 de combustível` - Linguagem natural
• `entrou 500 pix do Carlos` - O bot entende contexto

� **NOVO: Upload de Comprovantes**
• Envie foto do cupom fiscal → Análise automática com IA
• Envie PDF do extrato → Salva no Google Drive
• Bot extrai valor e descrição automaticamente!

�📊 **Relatórios:**
• `/saldo` - Saldo atual e do mês (com totais detalhados)
• `/relatorio` - Relatório do mês atual
• `/relatorio 2025-10` - Relatório de mês específico

ℹ️ `/help` - Ver todos os comandos

🚀 Comece digitando algo como "paguei 25 de almoço" ou envie uma foto do cupom!"""

    await update.message.reply_text(mensagem)


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para comando /help.
    Mostra instruções detalhadas.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = get_user_display_name(user)

    log_user_action(chat_id, username, "comando /help")

    mensagem = """📚 **Guia Completo do Bot Financeiro**

🔹 **Comandos Diretos:**
• `/entrada <valor> <descrição>` - Registra recebimento
• `/saida <valor> <descrição>` - Registra pagamento
• `/saldo` - Mostra saldo atual e do mês (com totais)
• `/relatorio [YYYY-MM]` - Relatório mensal

🔸 **Linguagem Natural:**
Digite naturalmente e o bot entende:
• "paguei 35,90 de frete hoje"
• "entrou 500 pix do Carlos"
• "gastei 89,50 de combustível"
• "recebi 1200 do freelance ontem"

� **NOVO: Upload de Comprovantes**
• **Foto:** Envie foto do cupom/nota fiscal
  → IA analisa e extrai dados automaticamente
• **PDF:** Envie documento financeiro
  → Salva no Google Drive com link
• **Automático:** Registra na planilha mensal

�💡 **Exemplos Práticos:**

**Entradas:**
• `/entrada 120 venda boleto`
• "recebi 800 do cliente"
• "entrou transferência 350"

**Saídas:**
• `/saida 25,90 almoço`
• "paguei 149 da conta de luz"
• "gastei 65,80 no mercado"

**Comprovantes:**
• 📷 Foto do cupom → Análise automática
• 📄 PDF do extrato → Link na planilha

**Relatórios:**
• `/saldo` → Saldo geral e do mês
• `/relatorio` → Mês atual
• `/relatorio 2025-10` → Outubro/2025

� **Organização por Mês:**
• Cada mês = nova aba na planilha
• Totais automáticos: entradas, saídas, saldo
• Links dos comprovantes organizados

�📋 **Formatos Aceitos:**
• Valores: 123,45 ou 123.45
• Datas: hoje, ontem, 2025-10-15
• Descrições: texto livre até 200 caracteres
• Imagens: JPG, PNG (máximo 20MB)
• Documentos: PDF (máximo 10MB)

⚡ **Dicas:**
• O bot salva tudo numa planilha Google organizada por mês
• Aceita vírgula ou ponto nos valores
• Entende datas em português
• Categoriza automaticamente quando possível
• IA analisa comprovantes e extrai dados

❓ Dúvidas? Apenas digite sua transação ou envie foto do comprovante!"""

    await update.message.reply_text(mensagem)


async def handle_entrada(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para comando /entrada.
    Registra entrada financeira diretamente.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = get_user_display_name(user)

    # Rate limiting
    if not rate_limiter.is_allowed(chat_id):
        wait_time = rate_limiter.get_wait_time(chat_id)
        await update.message.reply_text(
            f"⏳ Aguarde {wait_time:.1f} segundos antes de enviar outra mensagem."
        )
        return

    log_user_action(chat_id, username, "comando /entrada")

    try:
        # Parse do comando
        lancamento = ai_parser.parse_direct_command(
            "/entrada", update.message.text)

        # Resolve data
        data_resolvida = resolve_date(lancamento.data)

        # Registra na planilha
        sheets_manager.registrar_lancamento(
            lancamento=lancamento,
            chat_id=chat_id,
            usuario=username,
            message_id=update.message.message_id,
            data_resolvida=data_resolvida
        )

        # Resposta de confirmação
        mensagem = f"""✅ **Entrada registrada com sucesso!**

💰 Valor: R$ {lancamento.valor:,.2f}
📝 Descrição: {lancamento.descricao}
📅 Data: {data_resolvida.strftime('%d/%m/%Y')}"""

        if lancamento.categoria:
            mensagem += f"\n🏷️ Categoria: {lancamento.categoria}"

        await update.message.reply_text(mensagem)

        log_user_action(
            chat_id, username, "entrada registrada",
            f"R$ {lancamento.valor} - {lancamento.descricao}"
        )

    except ValueError as e:
        await update.message.reply_text(f"❌ Erro nos dados: {str(e)}")
        logger.warning(f"Erro de validação para usuário {chat_id}: {e}")

    except SheetsManagerError as e:
        await update.message.reply_text(
            "❌ Erro ao salvar na planilha. Tente novamente em alguns segundos."
        )
        logger.error(f"Erro Sheets para usuário {chat_id}: {e}")

    except Exception as e:
        await update.message.reply_text(
            "❌ Erro interno. Tente novamente ou use linguagem natural."
        )
        logger.error(
            f"Erro geral no comando /entrada para usuário {chat_id}: {e}")


async def handle_saida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para comando /saida.
    Registra saída financeira diretamente.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = get_user_display_name(user)

    # Rate limiting
    if not rate_limiter.is_allowed(chat_id):
        wait_time = rate_limiter.get_wait_time(chat_id)
        await update.message.reply_text(
            f"⏳ Aguarde {wait_time:.1f} segundos antes de enviar outra mensagem."
        )
        return

    log_user_action(chat_id, username, "comando /saida")

    try:
        # Parse do comando
        lancamento = ai_parser.parse_direct_command(
            "/saida", update.message.text)

        # Resolve data
        data_resolvida = resolve_date(lancamento.data)

        # Registra na planilha
        sheets_manager.registrar_lancamento(
            lancamento=lancamento,
            chat_id=chat_id,
            usuario=username,
            message_id=update.message.message_id,
            data_resolvida=data_resolvida
        )

        # Resposta de confirmação
        mensagem = f"""✅ **Saída registrada com sucesso!**

💸 Valor: R$ {lancamento.valor:,.2f}
📝 Descrição: {lancamento.descricao}
📅 Data: {data_resolvida.strftime('%d/%m/%Y')}"""

        if lancamento.categoria:
            mensagem += f"\n🏷️ Categoria: {lancamento.categoria}"

        await update.message.reply_text(mensagem)

        log_user_action(
            chat_id, username, "saída registrada",
            f"R$ {lancamento.valor} - {lancamento.descricao}"
        )

    except ValueError as e:
        await update.message.reply_text(f"❌ Erro nos dados: {str(e)}")
        logger.warning(f"Erro de validação para usuário {chat_id}: {e}")

    except SheetsManagerError as e:
        await update.message.reply_text(
            "❌ Erro ao salvar na planilha. Tente novamente em alguns segundos."
        )
        logger.error(f"Erro Sheets para usuário {chat_id}: {e}")

    except Exception as e:
        await update.message.reply_text(
            "❌ Erro interno. Tente novamente ou use linguagem natural."
        )
        logger.error(
            f"Erro geral no comando /saida para usuário {chat_id}: {e}")


async def handle_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para comando /saldo.
    Mostra saldo atual do usuário com totais detalhados.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = get_user_display_name(user)

    log_user_action(chat_id, username, "comando /saldo")

    try:
        # Busca saldo na planilha
        saldo = sheets_manager.calcular_saldo(chat_id)
        
        # Gera relatório do mês atual também
        relatorio_mes = sheets_manager.gerar_relatorio_mensal(chat_id, saldo.mes_atual)

        mensagem = f"""💼 **Seu Saldo Financeiro**

🏦 **SALDO TOTAL GERAL:** {saldo.saldo_total_formatado}

� **TOTAIS GERAIS:**
• 💰 Total de Entradas: R$ {saldo.total_entradas:,.2f}
• 💸 Total de Saídas: R$ {saldo.total_saidas:,.2f}

📅 **MÊS ATUAL ({saldo.mes_atual}):**
• � Saldo do Mês: {saldo.saldo_mes_formatado}
• 📈 Entradas do Mês: R$ {relatorio_mes.total_entradas:,.2f}
• 📉 Saídas do Mês: R$ {relatorio_mes.total_saidas:,.2f}
• 🔢 Lançamentos: {relatorio_mes.quantidade_lancamentos}

💡 *Dica: Use /relatorio para ver outros meses*"""

        # Emoji baseado no saldo
        if saldo.saldo_total > 0:
            mensagem = "😊 " + mensagem
        elif saldo.saldo_total < 0:
            mensagem = "😰 " + mensagem
        else:
            mensagem = "😐 " + mensagem

        await update.message.reply_text(mensagem)

    except SheetsManagerError as e:
        await update.message.reply_text(
            "❌ Erro ao buscar saldo. Tente novamente em alguns segundos."
        )
        logger.error(f"Erro ao calcular saldo para usuário {chat_id}: {e}")

    except Exception as e:
        await update.message.reply_text(
            "❌ Erro interno ao calcular saldo."
        )
        logger.error(
            f"Erro geral no comando /saldo para usuário {chat_id}: {e}")


async def handle_relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para comando /relatorio.
    Gera relatório mensal do usuário.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = get_user_display_name(user)

    log_user_action(chat_id, username, "comando /relatorio")

    try:
        # Parse do mês (pega argumento ou usa mês atual)
        mes_arg = context.args[0] if context.args else None
        mes = parse_month(mes_arg)

        # Gera relatório
        relatorio = sheets_manager.gerar_relatorio_mensal(chat_id, mes)

        mensagem = f"""📊 **Relatório Mensal - {relatorio.mes}**

💰 **Resumo:**
• Entradas: {relatorio.entradas_formatadas}
• Saídas: {relatorio.saidas_formatadas}
• **Saldo do Mês:** {relatorio.saldo_formatado}

📈 **Estatísticas:**
• Total de lançamentos: {relatorio.quantidade_lancamentos}"""

        if relatorio.quantidade_lancamentos > 0:
            media_por_lancamento = relatorio.total_entradas + relatorio.total_saidas
            media_por_lancamento = media_por_lancamento / relatorio.quantidade_lancamentos
            mensagem += f"\n• Valor médio por lançamento: R$ {media_por_lancamento:,.2f}"

        # Emoji baseado no saldo do mês
        if relatorio.saldo_mensal > 0:
            mensagem = "📈 " + mensagem
        elif relatorio.saldo_mensal < 0:
            mensagem = "📉 " + mensagem
        else:
            mensagem = "➖ " + mensagem

        await update.message.reply_text(mensagem)

    except ValueError as e:
        await update.message.reply_text(f"❌ Erro no formato: {str(e)}")
        logger.warning(f"Erro de parsing do mês para usuário {chat_id}: {e}")

    except SheetsManagerError as e:
        await update.message.reply_text(
            "❌ Erro ao gerar relatório. Tente novamente em alguns segundos."
        )
        logger.error(f"Erro ao gerar relatório para usuário {chat_id}: {e}")

    except Exception as e:
        await update.message.reply_text(
            "❌ Erro interno ao gerar relatório."
        )
        logger.error(
            f"Erro geral no comando /relatorio para usuário {chat_id}: {e}")


async def handle_free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para mensagens livres (linguagem natural).
    Usa IA para extrair dados financeiros.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = get_user_display_name(user)
    message_text = update.message.text

    # Rate limiting
    if not rate_limiter.is_allowed(chat_id):
        wait_time = rate_limiter.get_wait_time(chat_id)
        await update.message.reply_text(
            f"⏳ Aguarde {wait_time:.1f} segundos antes de enviar outra mensagem."
        )
        return

    # Valida mensagem
    if not validate_telegram_message(message_text):
        await update.message.reply_text(
            "❌ Mensagem inválida. Tente descrever uma transação financeira."
        )
        return

    log_user_action(
        chat_id, username, "mensagem livre",
        truncate_text(message_text, 50)
    )

    try:
        # Parse com IA
        lancamento = ai_parser.parse_message(message_text)

        # Resolve data
        data_resolvida = resolve_date(lancamento.data)

        # Registra na planilha
        sheets_manager.registrar_lancamento(
            lancamento=lancamento,
            chat_id=chat_id,
            usuario=username,
            message_id=update.message.message_id,
            data_resolvida=data_resolvida
        )

        # Resposta de confirmação
        emoji = "📈" if lancamento.tipo == "entrada" else "📉"
        tipo_nome = "Entrada" if lancamento.tipo == "entrada" else "Saída"

        mensagem = f"""{emoji} **{tipo_nome} registrada!**

💰 Valor: R$ {lancamento.valor:,.2f}
📝 Descrição: {lancamento.descricao}
📅 Data: {data_resolvida.strftime('%d/%m/%Y')}"""

        if lancamento.categoria:
            mensagem += f"\n🏷️ Categoria: {lancamento.categoria}"

        await update.message.reply_text(mensagem)

        log_user_action(
            chat_id, username, f"{lancamento.tipo} via IA",
            f"R$ {lancamento.valor} - {lancamento.descricao}"
        )

    except OpenAIParseError as e:
        await update.message.reply_text(
            "🤔 Não consegui entender sua mensagem financeira.\n\n"
            "💡 **Tente algo como:**\n"
            "• 'paguei 35,90 de frete'\n"
            "• 'recebi 500 do cliente'\n"
            "• `/entrada 100 venda`\n"
            "• `/saida 25,50 almoço`"
        )
        logger.warning(f"Erro de parsing IA para usuário {chat_id}: {e}")

    except ValueError as e:
        await update.message.reply_text(
            f"❌ Erro nos dados extraídos: {str(e)}\n\n"
            "💡 Tente ser mais específico com o valor e descrição."
        )
        logger.warning(f"Erro de validação IA para usuário {chat_id}: {e}")

    except SheetsManagerError as e:
        await update.message.reply_text(
            "❌ Entendi sua mensagem, mas houve erro ao salvar.\n"
            "Tente novamente em alguns segundos."
        )
        logger.error(
            f"Erro Sheets para mensagem livre do usuário {chat_id}: {e}")

    except Exception as e:
        await update.message.reply_text(
            "❌ Erro interno.\n\n"
            "💡 Tente usar comandos diretos:\n"
            "• `/entrada 100 descrição`\n"
            "• `/saida 50 descrição`"
        )
        logger.error(f"Erro geral em mensagem livre do usuário {chat_id}: {e}")


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler global para erros não capturados.
    """
    logger.error(
        f"Exceção não capturada: {context.error}", exc_info=context.error)

    # Tenta enviar mensagem de erro se possível
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Ocorreu um erro interno. Tente novamente."
            )
        except Exception:
            pass  # Ignora se não conseguir enviar mensagem


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para recebimento de fotos (comprovantes).
    Analisa a imagem e extrai dados financeiros automaticamente.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = get_user_display_name(user)

    # Rate limiting
    if not rate_limiter.is_allowed(chat_id):
        wait_time = rate_limiter.get_wait_time(chat_id)
        await update.message.reply_text(
            f"⏳ Aguarde {wait_time:.1f} segundos antes de enviar outra mensagem."
        )
        return

    log_user_action(chat_id, username, "upload de foto/comprovante")

    try:
        # Obtém a foto em maior resolução
        photo = update.message.photo[-1]
        
        await update.message.reply_text("📷 Analisando comprovante... ⏳")
        
        # Baixa a foto
        file = await context.bot.get_file(photo.file_id)
        file_data = await file.download_as_bytearray()
        
        # Analisa com IA
        try:
            lancamento, analise = vision_analyzer.analyze_receipt(
                image_data=bytes(file_data),
                user_context=update.message.caption
            )
        except VisionAnalyzerError as e:
            await update.message.reply_text(
                f"❌ Erro ao analisar imagem: {str(e)}\n\n"
                "💡 Tente enviar uma imagem mais clara ou digite os dados manualmente."
            )
            return
        
        if not lancamento:
            await update.message.reply_text(
                "⚠️ Não consegui extrair dados financeiros desta imagem.\n\n"
                "💡 Tente:\n"
                "• Foto mais clara e com boa iluminação\n"
                "• Foque no valor e descrição principais\n"
                "• Use comandos manuais: `/entrada 100 descrição`"
            )
            return
        
        # Faz upload para o Drive
        try:
            file_id, public_link = drive_manager.upload_comprovante(
                file_data=bytes(file_data),
                filename=f"comprovante_{photo.file_id}.jpg",
                mime_type="image/jpeg",
                chat_id=chat_id,
                descricao=lancamento.descricao
            )
        except DriveManagerError as e:
            logger.warning(f"Erro ao fazer upload: {e}")
            public_link = ""  # Continua sem o link
        
        # Resolve data
        data_resolvida = resolve_date(lancamento.data)
        
        # Registra na planilha
        sheets_manager.registrar_lancamento(
            lancamento=lancamento,
            chat_id=chat_id,
            usuario=username,
            message_id=update.message.message_id,
            data_resolvida=data_resolvida,
            comprovante_link=public_link
        )
        
        # Resposta de confirmação
        comprovante_info = f"\n📎 [Comprovante salvo]({public_link})" if public_link else ""
        
        mensagem = f"""✅ **Comprovante analisado e registrado!**

📊 **Dados extraídos:**
• {lancamento.tipo.title()}: R$ {lancamento.valor:,.2f}
• Descrição: {lancamento.descricao}
• Categoria: {lancamento.categoria or 'Não categorizado'}
• Data: {data_resolvida.strftime('%d/%m/%Y')}{comprovante_info}

🤖 **Análise da IA:**
{analise[:500]}{'...' if len(analise) > 500 else ''}

💡 Use `/saldo` para ver seu saldo atualizado!"""
        
        await update.message.reply_text(mensagem, parse_mode='Markdown')
        
    except SheetsManagerError as e:
        await update.message.reply_text(
            "❌ Erro ao salvar na planilha. Dados foram analisados mas não salvos."
        )
        logger.error(f"Erro ao salvar comprovante na planilha: {e}")
    
    except Exception as e:
        await update.message.reply_text(
            "❌ Erro ao processar comprovante.\n\n"
            "💡 Tente novamente ou use comandos manuais."
        )
        logger.error(f"Erro geral no processamento de foto: {e}")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler para recebimento de documentos (PDFs, etc.).
    Salva o documento no Drive e permite análise posterior.
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    username = get_user_display_name(user)

    # Rate limiting
    if not rate_limiter.is_allowed(chat_id):
        wait_time = rate_limiter.get_wait_time(chat_id)
        await update.message.reply_text(
            f"⏳ Aguarde {wait_time:.1f} segundos antes de enviar outra mensagem."
        )
        return

    log_user_action(chat_id, username, "upload de documento")

    try:
        document = update.message.document
        
        # Verifica se é PDF
        if not document.mime_type or 'pdf' not in document.mime_type.lower():
            await update.message.reply_text(
                "📄 Documento recebido, mas só processo automaticamente PDFs.\n\n"
                "💡 Para outros formatos, digite os dados manualmente:\n"
                "• `/entrada 100 descrição`\n"
                "• `/saida 50 descrição`"
            )
            return
        
        # Verifica tamanho (máximo 10MB)
        if document.file_size and document.file_size > 10 * 1024 * 1024:
            await update.message.reply_text(
                "📄 Arquivo muito grande (máximo 10MB).\n\n"
                "💡 Tente enviar uma imagem do comprovante ou digite os dados manualmente."
            )
            return
        
        await update.message.reply_text("📄 Processando documento... ⏳")
        
        # Baixa o documento
        file = await context.bot.get_file(document.file_id)
        file_data = await file.download_as_bytearray()
        
        # Faz upload para o Drive
        try:
            file_id, public_link = drive_manager.upload_comprovante(
                file_data=bytes(file_data),
                filename=document.file_name or f"documento_{document.file_id}.pdf",
                mime_type=document.mime_type,
                chat_id=chat_id,
                descricao=update.message.caption or "Documento financeiro"
            )
            
            mensagem = f"""✅ **Documento salvo com sucesso!**

📄 **Arquivo:** {document.file_name or 'Documento'}
💾 **Tamanho:** {document.file_size / 1024:.1f} KB
📎 [Acessar documento]({public_link})

💡 **Para registrar lançamento:**
Envie os dados do documento usando:
• `/entrada valor descrição`
• `/saida valor descrição`

Ou envie uma foto do comprovante para análise automática! 📷"""
            
            await update.message.reply_text(mensagem, parse_mode='Markdown')
            
        except DriveManagerError as e:
            await update.message.reply_text(
                f"❌ Erro ao salvar documento: {str(e)}\n\n"
                "💡 Tente novamente ou envie uma foto do comprovante."
            )
            logger.error(f"Erro ao salvar documento: {e}")
        
    except Exception as e:
        await update.message.reply_text(
            "❌ Erro ao processar documento.\n\n"
            "💡 Tente enviar uma foto do comprovante ou digite os dados manualmente."
        )
        logger.error(f"Erro geral no processamento de documento: {e}")
