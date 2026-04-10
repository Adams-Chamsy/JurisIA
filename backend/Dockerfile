# ============================================
# JurisIA Backend — Dockerfile Multi-Stage
# Stage 1 : Builder (installation des dépendances)
# Stage 2 : Runtime (image minimale, sans outils de build)
# ============================================

# ── Stage 1 : Builder ────────────────────────────────────────────────────────
FROM python:3.12-slim as builder

WORKDIR /build

# Dépendances système pour les libs Python (reportlab, pdfplumber, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Créer un virtualenv isolé
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copier et installer les dépendances (layer cache optimisé)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Stage 2 : Runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim as runtime

WORKDIR /app

# Dépendances runtime uniquement (pas les outils de build)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copier le virtualenv depuis le stage builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Utilisateur non-root pour la sécurité
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid 1001 --no-create-home --shell /bin/sh appuser

# Copier le code de l'application
COPY --chown=appuser:appgroup . .

# Variables d'environnement de production
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Health check intégré au container
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

USER appuser

EXPOSE 8000

# Uvicorn avec workers optimisés pour la production
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--loop", "asyncio", \
     "--access-log", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
