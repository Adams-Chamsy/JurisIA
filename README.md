# JurisIA — Assistant Juridique IA Souverain pour PME Françaises

> **Analysez vos contrats, générez des documents juridiques et gérez votre conformité RGPD & AI Act.  
> IA propulsée par Mistral · Données hébergées en France 🇫🇷 · RGPD natif**

[![Tests](https://github.com/jurisai/jurisai/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/jurisai/jurisai/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org)

---

## 📋 Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Prérequis](#prérequis)
- [Installation rapide](#installation-rapide-dev)
- [Configuration](#configuration)
- [Développement](#développement)
- [Tests](#tests)
- [Déploiement Production](#déploiement-production)
- [Structure du Projet](#structure-du-projet)
- [API Documentation](#api-documentation)
- [Contribuer](#contribuer)

---

## ✨ Fonctionnalités

| Module | Fonctionnalités |
|---|---|
| 📄 **Analyse de contrats** | Upload PDF/DOCX → Identification des clauses à risque → Score de solidité → Export rapport PDF |
| ✍️ **Génération de documents** | 8 templates (CGV, NDA, CDI, rupture conv., mise en demeure…) → Formulaire guidé → Export DOCX/PDF |
| 💬 **Assistant juridique** | Chat IA conversationnel → Sources Légifrance citées → Historique |
| 🛡️ **Conformité RGPD** | Audit guidé 8 questions → Score → Plan d'action priorisé |
| ⚡ **Conformité AI Act** | Inventaire IA → Classification risques → Documentation auto (échéance août 2026) |
| 💳 **Abonnements** | Plans Starter/Pro/Business → Stripe Checkout → Portail client |

---

## 🏗 Architecture

```
jurisai/
├── backend/          # FastAPI + Python 3.12
│   ├── app/
│   │   ├── api/      # Endpoints REST (auth, documents, chat, billing…)
│   │   ├── core/     # Config, sécurité, logging
│   │   ├── db/       # SQLAlchemy async, migrations Alembic
│   │   ├── models/   # Modèles PostgreSQL (12 tables)
│   │   ├── schemas/  # Validation Pydantic
│   │   └── services/ # Logique métier (IA, documents, billing…)
│   └── tests/        # 59 tests (unitaires + intégration)
│
├── frontend/         # Next.js 15 + TypeScript + Tailwind CSS
│   └── src/
│       ├── app/      # Pages (App Router)
│       ├── components/ # Composants UI + features
│       ├── services/ # Client API Axios
│       └── store/    # Zustand (état global)
│
└── infra/
    ├── nginx/        # Config Nginx production (SSL, reverse proxy)
    ├── docker/       # Init scripts
    └── scripts/      # Deploy zero-downtime
```

**Stack technique :**
- **Backend :** FastAPI · SQLAlchemy async · PostgreSQL 16 · Redis 7 · Celery · Qdrant
- **IA :** Mistral AI (souverain, France) · LangChain · RAG sur corpus Légifrance
- **Frontend :** Next.js 15 · TypeScript · Tailwind CSS · React Query · Zustand
- **Infra :** OVH Cloud France · Docker · Nginx · GitHub Actions · Let's Encrypt

---

## 🔧 Prérequis

| Outil | Version minimale | Vérifier |
|---|---|---|
| Python | 3.12+ | `python --version` |
| Node.js | 22+ | `node --version` |
| Docker | 24+ | `docker --version` |
| Docker Compose | 2.20+ | `docker compose version` |
| Git | 2.40+ | `git --version` |

---

## 🚀 Installation Rapide (Dev)

### 1. Cloner le dépôt

```bash
git clone https://github.com/jurisai/jurisai.git
cd jurisai
```

### 2. Démarrer l'infrastructure locale

```bash
docker compose up -d
```

Cela lance : **PostgreSQL 16**, **Redis 7**, **MinIO** (S3 local), **Qdrant** (vector DB).

Vérifier que tout est UP :
```bash
docker compose ps
```

### 3. Configurer le Backend

```bash
cd backend

# Copier et remplir les variables d'environnement
cp ../.env.example .env
# Remplir au minimum : MISTRAL_API_KEY, STRIPE_SECRET_KEY
# Les autres valeurs par défaut fonctionnent en dev

# Créer l'environnement virtuel Python
python -m venv .venv
source .venv/bin/activate    # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Appliquer les migrations (crée les tables)
alembic upgrade head

# Lancer le serveur de développement
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

✅ API disponible sur : http://localhost:8000  
📚 Documentation Swagger : http://localhost:8000/docs

### 4. Configurer le Frontend

```bash
cd ../frontend

# Copier les variables d'environnement
cp ../.env.example .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
# NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...

# Installer les dépendances
npm install

# Lancer le serveur de développement
npm run dev
```

✅ Application disponible sur : http://localhost:3000

### 5. Vérification complète

```bash
# Backend health check
curl http://localhost:8000/health

# Lancer tous les tests
cd backend && python -m pytest tests/ -q
```

---

## ⚙️ Configuration

### Variables d'environnement essentielles

```bash
# ─── Obligatoires dès le premier lancement ───────────────────────────────────
MISTRAL_API_KEY=         # https://console.mistral.ai/ — Clé API Mistral (IA souveraine FR)
STRIPE_SECRET_KEY=       # https://dashboard.stripe.com — sk_test_... (dev) / sk_live_... (prod)
APP_SECRET_KEY=          # openssl rand -hex 32
JWT_SECRET_KEY=          # openssl rand -hex 64
ENCRYPTION_KEY=          # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# ─── Optionnelles en développement (defaults fonctionnels) ───────────────────
MAILJET_API_KEY=         # Pour les emails (vérification, alertes)
PAPPERS_API_KEY=         # Pour l'auto-complétion SIREN
SENTRY_DSN=              # Pour le monitoring d'erreurs
```

### Générer les clés de sécurité

```bash
# APP_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(64))"

# ENCRYPTION_KEY (Fernet)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

---

## 💻 Développement

### Commandes utiles Backend

```bash
# Lancer le serveur (hot reload)
uvicorn app.main:app --reload

# Créer une migration après modification des modèles
alembic revision --autogenerate -m "description_du_changement"

# Appliquer les migrations
alembic upgrade head

# Rollback d'une migration
alembic downgrade -1

# Lancer les workers Celery (tâches asynchrones IA)
celery -A app.core.celery_app worker --loglevel=info

# Vérifier le formatage du code
ruff check app/
ruff format --check app/
```

### Commandes utiles Frontend

```bash
# Développement avec hot reload
npm run dev

# Vérifier les types TypeScript
npm run type-check

# Linter
npm run lint

# Build de production (test local)
npm run build && npm run start
```

---

## 🧪 Tests

### Backend

```bash
cd backend

# Tous les tests (unitaires + intégration)
python -m pytest tests/ -v

# Tests unitaires uniquement (rapides, sans infra)
python -m pytest tests/unit/ -v

# Tests avec couverture
python -m pytest tests/ --cov=app --cov-report=html
# Ouvrir htmlcov/index.html pour le rapport

# Tests spécifiques
python -m pytest tests/unit/test_security_and_auth.py -v -k "test_hash"
```

**Résultats attendus :** 59/59 tests verts ✅

### Frontend

```bash
cd frontend

# Tests unitaires
npm test

# Tests avec UI interactive
npm run test:ui

# Tests avec couverture
npm run test:coverage
```

### Tests de charge (optionnel)

```bash
# Installer k6
# https://k6.io/docs/get-started/installation/

# Lancer un test de charge basique
k6 run infra/scripts/load-test.js
```

---

## 🚀 Déploiement Production

### Prérequis serveur

- VPS OVH (ou équivalent EU) : minimum 4 vCPU, 8 Go RAM, 50 Go SSD
- Ubuntu 24.04 LTS
- Docker + Docker Compose installés
- Noms de domaine configurés : `app.jurisai.fr` et `api.jurisai.fr` → IP du serveur

### 1. Préparer le serveur

```bash
# Sur le serveur de production
mkdir -p /opt/jurisai/data/{postgres,redis,qdrant}
mkdir -p /opt/jurisai/logs/{backend,nginx}
mkdir -p /opt/jurisai/backups/postgres

# Cloner le dépôt
git clone https://github.com/jurisai/jurisai.git /opt/jurisai
cd /opt/jurisai

# Configurer le .env de production
cp .env.example .env
# REMPLIR TOUTES LES VARIABLES (APP_ENV=production, vrais secrets, etc.)
nano .env
```

### 2. Obtenir les certificats SSL

```bash
# Installer Certbot
apt install certbot

# Obtenir les certificats
certbot certonly --standalone \
    -d app.jurisai.fr \
    -d api.jurisai.fr \
    --email votre@email.fr \
    --agree-tos
```

### 3. Premier déploiement

```bash
cd /opt/jurisai

# Démarrer les services
docker compose -f docker-compose.prod.yml up -d

# Vérifier que tout est healthy
docker compose -f docker-compose.prod.yml ps

# Appliquer les migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Vérifier les logs
docker compose -f docker-compose.prod.yml logs -f backend
```

### 4. Déploiements suivants

```bash
# Script de déploiement zero-downtime avec backup automatique
chmod +x infra/scripts/deploy.sh
./infra/scripts/deploy.sh
```

---

## 📁 Structure du Projet

```
jurisai/
├── .github/
│   └── workflows/
│       └── ci-cd.yml          # Pipeline CI/CD complet
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── dependencies/  # Guards (auth, plan, role)
│   │   │   └── endpoints/     # Routes HTTP (auth, documents, chat, billing…)
│   │   ├── core/
│   │   │   ├── config.py      # Pydantic Settings (variables d'env)
│   │   │   ├── security.py    # JWT, Argon2, Fernet, CSRF
│   │   │   └── logging.py     # Structlog (JSON prod / pretty dev)
│   │   ├── db/
│   │   │   ├── database.py    # Engine SQLAlchemy async
│   │   │   └── migrations/    # Scripts Alembic
│   │   ├── models/            # SQLAlchemy ORM (12 tables)
│   │   ├── schemas/           # Pydantic (validation entrées/sorties)
│   │   └── services/
│   │       ├── ai/            # Intégration Mistral + RAG
│   │       ├── auth/          # Logique authentification
│   │       ├── billing/       # Stripe
│   │       ├── documents/     # Analyse + Génération + Storage + Quotas
│   │       └── notifications/ # Email Mailjet
│   ├── tests/
│   │   ├── conftest.py        # Fixtures et configuration pytest
│   │   ├── unit/              # Tests unitaires (38 tests)
│   │   └── integration/       # Tests d'intégration (21 tests)
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── login/         # Page connexion
│       │   ├── register/      # Page inscription
│       │   └── dashboard/     # Dashboard + sous-pages
│       │       ├── analyze/   # Analyse de documents
│       │       ├── generate/  # Génération de documents
│       │       ├── chat/      # Assistant juridique
│       │       ├── compliance/# Audits RGPD + AI Act
│       │       └── billing/   # Abonnements
│       ├── components/
│       │   ├── layout/        # Providers, Sidebar, Header
│       │   └── ui/            # Composants (Button, Input, Badge…)
│       ├── services/          # Client API (Axios + intercepteurs)
│       └── store/             # Zustand (auth, abonnements)
├── infra/
│   ├── docker/                # Scripts init PostgreSQL
│   ├── nginx/                 # Config Nginx production
│   └── scripts/               # Scripts déploiement
├── docs/
│   └── adr/                   # Architecture Decision Records
├── .env.example               # Template variables d'environnement
├── .gitignore
├── docker-compose.yml         # Dev local
└── docker-compose.prod.yml    # Production
```

---

## 📚 API Documentation

La documentation Swagger/OpenAPI est disponible en développement uniquement :

- **Swagger UI :** http://localhost:8000/docs
- **ReDoc :** http://localhost:8000/redoc
- **OpenAPI JSON :** http://localhost:8000/openapi.json

### Endpoints principaux

| Méthode | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Inscription |
| `POST` | `/api/v1/auth/login` | Connexion (retourne JWT) |
| `POST` | `/api/v1/auth/refresh` | Renouvellement du token |
| `POST` | `/api/v1/documents/analyze` | Analyser un document (upload) |
| `POST` | `/api/v1/documents/generate` | Générer un document |
| `GET`  | `/api/v1/documents` | Lister les documents |
| `POST` | `/api/v1/chat/messages` | Envoyer un message à l'assistant |
| `GET`  | `/api/v1/chat/conversations` | Lister les conversations |
| `POST` | `/api/v1/compliance/audit` | Lancer un audit RGPD/AI Act |
| `POST` | `/api/v1/billing/checkout` | Créer une session Stripe |
| `GET`  | `/health` | Health check (monitoring) |

### Authentification

Tous les endpoints (sauf `/auth/*` et `/health`) nécessitent un Bearer token :

```bash
curl -H "Authorization: Bearer eyJhbGci..." \
     https://api.jurisai.fr/api/v1/documents
```

---

## 🤝 Contribuer

```bash
# 1. Fork + Clone
git clone https://github.com/votre-fork/jurisai.git

# 2. Créer une branche
git checkout -b feature/ma-fonctionnalite

# 3. Développer + tester
python -m pytest tests/ -q         # Backend : tous verts
npm test                            # Frontend : tous verts

# 4. Commit (format Conventional Commits)
git commit -m "feat(documents): ajout template bail commercial"

# 5. Push + Pull Request vers main
```

**Conventions de commit :**
- `feat:` nouvelle fonctionnalité
- `fix:` correction de bug
- `docs:` documentation
- `test:` ajout/modification de tests
- `refactor:` refactoring sans changement de comportement
- `chore:` maintenance (deps, CI, config)

---

## 📄 Licence

MIT License — Voir [LICENSE](LICENSE)

---

## 🆘 Support

- **Documentation :** https://docs.jurisai.fr
- **Email :** support@jurisai.fr
- **Issues GitHub :** https://github.com/jurisai/jurisai/issues

---

*JurisIA SAS — Données hébergées en France 🇫🇷 — RGPD conforme — AI Act confiant*
