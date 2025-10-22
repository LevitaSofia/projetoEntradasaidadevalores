#!/bin/bash

# Script de inicialização e deploy para diferentes ambientes

set -e  # Para na primeira falha

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Sem cor

# Funções auxiliares
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Função para verificar dependências
check_dependencies() {
    log_info "Verificando dependências..."
    
    # Verifica Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker não encontrado. Instale o Docker primeiro."
        exit 1
    fi
    
    # Verifica Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose não encontrado. Instale o Docker Compose primeiro."
        exit 1
    fi
    
    # Verifica Python (para desenvolvimento local)
    if ! command -v python3.11 &> /dev/null; then
        log_warning "Python 3.11 não encontrado. Necessário para desenvolvimento local."
    fi
    
    log_success "Dependências verificadas"
}

# Função para configurar ambiente
setup_environment() {
    log_info "Configurando ambiente..."
    
    # Cria .env se não existir
    if [ ! -f .env ]; then
        log_info "Criando arquivo .env a partir do template..."
        cp .env.example .env
        log_warning "Configure suas variáveis de ambiente no arquivo .env antes de continuar"
        log_warning "Pressione Enter quando terminar a configuração..."
        read
    fi
    
    # Verifica se variáveis essenciais estão definidas
    source .env
    
    if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ "$TELEGRAM_BOT_TOKEN" == "123456789:ABCDefGhIjKlMnOpQrStUvWxYz" ]; then
        log_error "TELEGRAM_BOT_TOKEN não configurado no .env"
        exit 1
    fi
    
    if [ -z "$OPENAI_API_KEY" ] || [[ "$OPENAI_API_KEY" == sk-proj-* ]] && [ ${#OPENAI_API_KEY} -lt 50 ]; then
        log_error "OPENAI_API_KEY não configurado no .env"
        exit 1
    fi
    
    if [ -z "$GOOGLE_SHEET_ID" ]; then
        log_error "GOOGLE_SHEET_ID não configurado no .env"
        exit 1
    fi
    
    log_success "Ambiente configurado"
}

# Função para desenvolvimento local
dev_setup() {
    log_info "Configurando ambiente de desenvolvimento..."
    
    # Instala dependências Python localmente
    if command -v python3.11 &> /dev/null; then
        log_info "Instalando dependências Python..."
        python3.11 -m pip install --upgrade pip
        python3.11 -m pip install -r requirements.txt
        log_success "Dependências Python instaladas"
    else
        log_warning "Python 3.11 não encontrado, usando apenas Docker"
    fi
    
    # Inicia com Docker Compose
    log_info "Iniciando serviços de desenvolvimento..."
    docker-compose up --build -d
    
    log_success "Ambiente de desenvolvimento iniciado"
    log_info "Bot disponível em: http://localhost:8080"
    log_info "Healthcheck: http://localhost:8081/healthz"
    log_info "Logs: docker-compose logs -f bot-financeiro"
}

# Função para executar testes
run_tests() {
    log_info "Executando testes..."
    
    # Para testes locais se Python disponível
    if command -v python3.11 &> /dev/null && [ -d "venv" ] || [ -n "$VIRTUAL_ENV" ]; then
        log_info "Executando testes localmente..."
        python3.11 -m pytest tests/ -v --cov=app --cov-report=html
    else
        log_info "Executando testes no Docker..."
        docker-compose --profile testing up --build tests
    fi
    
    log_success "Testes concluídos"
}

# Função para build de produção
build_production() {
    log_info "Fazendo build para produção..."
    
    # Build da imagem de produção
    docker build --target production -t telegram-finance-bot:latest .
    
    # Testa a imagem
    log_info "Testando imagem de produção..."
    docker run --rm --env-file .env telegram-finance-bot:latest python -c "from app.config import config; print('Config OK')"
    
    log_success "Build de produção concluído"
}

# Função para deploy
deploy() {
    local platform=$1
    
    case $platform in
        "railway")
            deploy_railway
            ;;
        "render")
            deploy_render
            ;;
        "heroku")
            deploy_heroku
            ;;
        "docker")
            deploy_docker
            ;;
        *)
            log_error "Plataforma não suportada: $platform"
            log_info "Plataformas suportadas: railway, render, heroku, docker"
            exit 1
            ;;
    esac
}

deploy_railway() {
    log_info "Deploy para Railway..."
    
    if ! command -v railway &> /dev/null; then
        log_error "Railway CLI não instalado. Instale com: npm install -g @railway/cli"
        exit 1
    fi
    
    railway login
    railway deploy
    
    log_success "Deploy para Railway concluído"
}

deploy_render() {
    log_info "Deploy para Render..."
    log_info "Conecte seu repositório no dashboard do Render: https://render.com"
    log_info "Configure as variáveis de ambiente na interface web"
}

deploy_heroku() {
    log_info "Deploy para Heroku..."
    
    if ! command -v heroku &> /dev/null; then
        log_error "Heroku CLI não instalado"
        exit 1
    fi
    
    # Cria app se não existir
    read -p "Nome do app Heroku: " app_name
    heroku create $app_name
    
    # Configura variáveis de ambiente
    source .env
    heroku config:set TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" -a $app_name
    heroku config:set OPENAI_API_KEY="$OPENAI_API_KEY" -a $app_name
    heroku config:set GOOGLE_SHEET_ID="$GOOGLE_SHEET_ID" -a $app_name
    heroku config:set GOOGLE_SERVICE_ACCOUNT_JSON="$GOOGLE_SERVICE_ACCOUNT_JSON" -a $app_name
    heroku config:set APP_ENV="prod" -a $app_name
    
    # Deploy
    git push heroku main
    
    log_success "Deploy para Heroku concluído"
}

deploy_docker() {
    log_info "Deploy com Docker (produção)..."
    
    # Para serviços atuais
    docker-compose down
    
    # Inicia produção
    docker-compose --profile production up --build -d
    
    log_success "Deploy Docker concluído"
    log_info "Bot disponível na porta configurada"
}

# Função para limpar ambiente
cleanup() {
    log_info "Limpando ambiente..."
    
    docker-compose down
    docker system prune -f
    
    log_success "Ambiente limpo"
}

# Função para mostrar status
status() {
    log_info "Status dos serviços..."
    
    docker-compose ps
    
    if [ "$(docker-compose ps -q)" ]; then
        log_info "Testando healthcheck..."
        curl -f http://localhost:8081/healthz || log_warning "Healthcheck falhou"
    fi
}

# Função de ajuda
show_help() {
    echo "Bot Financeiro Telegram - Script de Deploy"
    echo ""
    echo "Uso: $0 [COMANDO] [OPÇÕES]"
    echo ""
    echo "Comandos:"
    echo "  setup          Configura ambiente inicial"
    echo "  dev            Inicia desenvolvimento local"
    echo "  test           Executa testes"
    echo "  build          Build para produção"
    echo "  deploy <plat>  Deploy para plataforma (railway/render/heroku/docker)"
    echo "  status         Mostra status dos serviços"
    echo "  cleanup        Limpa ambiente Docker"
    echo "  help           Mostra esta ajuda"
    echo ""
    echo "Exemplos:"
    echo "  $0 setup"
    echo "  $0 dev"
    echo "  $0 test"
    echo "  $0 deploy railway"
    echo ""
}

# Função principal
main() {
    local command=${1:-help}
    
    case $command in
        "setup")
            check_dependencies
            setup_environment
            ;;
        "dev")
            check_dependencies
            setup_environment
            dev_setup
            ;;
        "test")
            check_dependencies
            run_tests
            ;;
        "build")
            check_dependencies
            setup_environment
            build_production
            ;;
        "deploy")
            check_dependencies
            setup_environment
            deploy $2
            ;;
        "status")
            status
            ;;
        "cleanup")
            cleanup
            ;;
        "help"|"--help"|"-h")
            show_help
            ;;
        *)
            log_error "Comando não reconhecido: $command"
            show_help
            exit 1
            ;;
    esac
}

# Executa função principal com todos os argumentos
main "$@"