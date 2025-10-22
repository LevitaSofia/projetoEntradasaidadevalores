# Multi-stage Dockerfile para produção otimizada
FROM python:3.11-slim as builder

# Metadados
LABEL maintainer="Bot Financeiro Team"
LABEL version="1.0.0"
LABEL description="Bot Telegram para gestão financeira com IA"

# Variáveis de build
ARG BUILD_DATE
ARG VCS_REF
LABEL build-date=$BUILD_DATE
LABEL vcs-ref=$VCS_REF

# Instala dependências do sistema para build
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Configura ambiente Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Cria diretório de trabalho
WORKDIR /app

# Copia requirements primeiro (cache layer)
COPY requirements.txt .

# Instala dependências Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Stage de produção
FROM python:3.11-slim as production

# Instala dependências mínimas de runtime
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Cria usuário não-root para segurança
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Configura ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    APP_ENV=prod

# Cria diretórios necessários
WORKDIR /app
RUN mkdir -p /app/logs && chown -R botuser:botuser /app

# Copia dependências do stage builder
COPY --from=builder /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copia código da aplicação
COPY app/ ./app/
COPY requirements.txt .

# Define usuário não-root
USER botuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8081/healthz || exit 1

# Expõe portas
EXPOSE 8080 8081

# Comando padrão
CMD ["python", "-m", "app.main"]

# ====== Stage de desenvolvimento ======
FROM builder as development

# Instala dependências de desenvolvimento
RUN pip install pytest pytest-asyncio pytest-cov black flake8 mypy

# Copia código para desenvolvimento
COPY . .

# Usuário root para desenvolvimento (facilita debugging)
USER root

# Comando de desenvolvimento com hot reload
CMD ["python", "-m", "app.main"]

# ====== Stage de testes ======
FROM development as testing

# Executa testes durante build
RUN python -m pytest tests/ -v --cov=app --cov-report=html --cov-report=term

# Comando para executar testes
CMD ["python", "-m", "pytest", "tests/", "-v"]