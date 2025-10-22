# Bot Telegram + OpenAI + Google Sheets

Um bot inteligente para o Telegram que gerencia entradas e saídas financeiras usando processamento de linguagem natural da OpenAI e registra tudo no Google Sheets.

## 🚀 Características

- **Comandos diretos**: `/entrada 100 venda` ou `/saida 35,90 frete`
- **Linguagem natural**: "paguei 35,90 de frete hoje" ou "entrou 500 pix do Carlos"
- **Integração OpenAI**: Extração inteligente de dados de mensagens livres
- **Google Sheets**: Registro automático em planilha
- **Relatórios**: Saldo e relatórios mensais
- **Validações**: Tratamento robusto de erros e dados

## 📋 Pré-requisitos

- Python 3.11+
- Conta do Telegram (para criar bot)
- Conta OpenAI com API key
- Conta Google (para Service Account e Sheets)

## 🛠️ Configuração

### 1. Bot do Telegram

1. Acesse [@BotFather](https://t.me/botfather) no Telegram
2. Execute `/newbot` e siga as instruções
3. Salve o token recebido (formato: `123456789:ABCDefGhI...`)

### 2. OpenAI API

1. Acesse [platform.openai.com](https://platform.openai.com)
2. Vá em "API Keys" e crie uma nova chave
3. Salve a chave (formato: `sk-proj-...`)

### 3. Google Sheets + Service Account

1. Acesse [Google Cloud Console](https://console.cloud.google.com)
2. Crie um novo projeto ou selecione um existente
3. Ative a API do Google Sheets:
   - Vá em "APIs & Services" > "Library"
   - Procure por "Google Sheets API" e ative
4. Crie uma Service Account:
   - Vá em "APIs & Services" > "Credentials"
   - Clique em "Create Credentials" > "Service Account"
   - Preencha os dados e clique em "Create"
   - Na tela de permissões, pode pular
   - Clique em "Done"
5. Gere uma chave JSON:
   - Clique na Service Account criada
   - Vá na aba "Keys"
   - Clique em "Add Key" > "Create new key" > "JSON"
   - Baixe o arquivo JSON
6. Crie uma planilha no Google Sheets:
   - Acesse [sheets.google.com](https://sheets.google.com)
   - Crie uma nova planilha
   - Compartilhe com o email da Service Account (com permissão de edição)
   - Copie o ID da planilha da URL (parte entre `/d/` e `/edit`)

### 4. Estrutura da Planilha

Crie duas abas na planilha:

**Aba "movimentos"** (principais dados):
```
timestamp | chat_id | usuario | tipo | valor | descricao | categoria | data_lancamento | message_id
```

**Aba "usuarios"** (controle de usuários):
```
chat_id | nome | primeiro_uso
```

## 🔧 Instalação

1. Clone ou baixe o projeto
2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure as variáveis de ambiente:
```bash
cp .env.example .env
```

4. Edite o arquivo `.env` com suas credenciais:
- `TELEGRAM_BOT_TOKEN`: Token do BotFather
- `OPENAI_API_KEY`: Chave da API OpenAI
- `GOOGLE_SHEET_ID`: ID da planilha Google
- `GOOGLE_SERVICE_ACCOUNT_JSON`: JSON completo da Service Account

## ▶️ Execução

### Desenvolvimento (polling)
```bash
python -m app.main
```

### Produção (webhook)
Configure um webhook apontando para sua aplicação implantada.

## 🤖 Como usar o bot

### Comandos disponíveis

- `/start` - Boas-vindas e ajuda
- `/help` - Lista de comandos e exemplos
- `/entrada <valor> <descrição>` - Registra entrada direta
- `/saida <valor> <descrição>` - Registra saída direta  
- `/saldo` - Mostra saldo do mês e total
- `/relatorio [YYYY-MM]` - Relatório mensal

### Exemplos de uso

**Comandos diretos:**
```
/entrada 150 venda produto
/saida 35,90 frete sedex
```

**Linguagem natural:**
```
paguei 49,90 de combustível hoje
entrou 500 pix do Carlos
recebi 1200 do freelance ontem
```

**Relatórios:**
```
/saldo
/relatorio 2025-10
```

## 🧪 Testes

Execute os testes unitários:
```bash
pytest tests/
```

## 🐳 Docker

### Build da imagem
```bash
docker build -t telegram-finance-bot .
```

### Execução
```bash
docker run -d --name finance-bot --env-file .env telegram-finance-bot
```

## 🚀 Deploy

### Railway
1. Conecte seu repositório ao Railway
2. Configure as variáveis de ambiente
3. Deploy automático

### Render
1. Conecte seu repositório ao Render
2. Configure as variáveis de ambiente
3. Deploy automático

### Heroku
```bash
heroku create meu-finance-bot
heroku config:set TELEGRAM_BOT_TOKEN=seu_token
heroku config:set OPENAI_API_KEY=sua_chave
# ... outras variáveis
git push heroku main
```

## 📊 Estrutura do Projeto

```
.
├── app/
│   ├── __init__.py
│   ├── main.py           # Aplicação principal
│   ├── config.py         # Configurações
│   ├── models.py         # Modelos Pydantic
│   ├── ai_parser.py      # Parser OpenAI
│   ├── sheets.py         # Integração Google Sheets
│   ├── bot_handlers.py   # Handlers do Telegram
│   └── utils.py          # Utilitários
├── tests/
│   ├── test_parser.py    # Testes do parser
│   └── test_handlers.py  # Testes dos handlers
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

## 🔐 Segurança

- ✅ Não registra chaves/tokens em logs
- ✅ Validação robusta de entradas
- ✅ Rate limiting por usuário
- ✅ Tratamento de exceções com retry
- ✅ Sanitização de dados do usuário

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.

## ❓ Suporte

Se encontrar problemas:

1. Verifique se todas as variáveis de ambiente estão configuradas
2. Confirme que a Service Account tem acesso à planilha
3. Teste a conectividade com as APIs
4. Consulte os logs para detalhes de erros

Para dúvidas específicas, abra uma issue no repositório.