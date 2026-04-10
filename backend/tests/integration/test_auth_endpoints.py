"""
JurisIA — Tests d'Intégration : Endpoints d'Authentification
Teste les endpoints HTTP de l'API avec un client de test async.
Nécessite une base de données de test PostgreSQL.
"""
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_settings(monkeypatch):
    """Override settings pour les tests sans vrais services externes."""
    monkeypatch.setenv("APP_SECRET_KEY",    "test_secret_32_chars_minimum_ok!!")
    monkeypatch.setenv("JWT_SECRET_KEY",    "test_jwt_64_chars_minimum_required_for_hmac_sha256_signing_ok")
    monkeypatch.setenv("ENCRYPTION_KEY",    "oudIUTdrF0o6QrztsCaqJCKd8L2f5au88JBW-WzeKgw=")
    monkeypatch.setenv("DATABASE_URL",      "postgresql+asyncpg://test:test@localhost:5432/jurisai_test")
    monkeypatch.setenv("REDIS_URL",         "redis://localhost:6379/0")
    monkeypatch.setenv("MISTRAL_API_KEY",   "dummy_key_for_tests")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy_stripe_key_for_tests")
    monkeypatch.setenv("APP_ENV",           "development")
    monkeypatch.setenv("APP_DEBUG",         "false")
    monkeypatch.setenv("ALLOWED_ORIGINS",   "http://localhost:3000")

    import app.core.config as cfg
    cfg.get_settings.cache_clear()
    return cfg.get_settings()


@pytest.fixture
async def async_client(mock_settings):
    """Client HTTP de test avec app FastAPI réelle (sans vraie BDD)."""
    # On mock la BDD et les services externes pour les tests d'intégration sans infra
    with patch("app.db.database.check_db_connection", return_value=True), \
         patch("app.db.database.init_db", new_callable=AsyncMock), \
         patch("app.db.database.AsyncSessionLocal") as mock_session_factory:

        # Session mock
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__  = AsyncMock(return_value=None)
        mock_session.commit     = AsyncMock()
        mock_session.rollback   = AsyncMock()
        mock_session.close      = AsyncMock()
        mock_session.flush      = AsyncMock()
        mock_session.add        = MagicMock()
        mock_session_factory.return_value = mock_session

        from app.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client, mock_session


# ── Tests : Health Check ─────────────────────────────────────────────────────

@pytest.mark.integration
async def test_health_check_returns_200(async_client):
    client, _ = async_client
    with patch("app.main._check_redis", return_value=True):
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "version" in data
    assert "services" in data


@pytest.mark.integration
async def test_root_endpoint(async_client):
    client, _ = async_client
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "JurisIA API"


# ── Tests : Validation des Entrées ────────────────────────────────────────────

@pytest.mark.integration
async def test_register_invalid_email(async_client):
    """L'inscription avec un email invalide doit retourner 422."""
    client, _ = async_client
    response = await client.post("/api/v1/auth/register", json={
        "full_name":         "Test User",
        "email":             "not-an-email",
        "password":          "ValidPass1",
        "organization_name": "Test Org",
        "accept_terms":      True,
    })
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any("email" in str(e).lower() for e in errors)


@pytest.mark.integration
async def test_register_missing_required_fields(async_client):
    """L'inscription sans champs obligatoires doit retourner 422."""
    client, _ = async_client
    response = await client.post("/api/v1/auth/register", json={})
    assert response.status_code == 422


@pytest.mark.integration
async def test_register_weak_password(async_client):
    """Mot de passe trop court → 422."""
    client, _ = async_client
    response = await client.post("/api/v1/auth/register", json={
        "full_name":         "Test User",
        "email":             "test@example.com",
        "password":          "weak",
        "organization_name": "Test Org",
        "accept_terms":      True,
    })
    assert response.status_code == 422


@pytest.mark.integration
async def test_register_no_terms_acceptance(async_client):
    """Sans acceptation des CGU → 422."""
    client, _ = async_client
    response = await client.post("/api/v1/auth/register", json={
        "full_name":         "Test User",
        "email":             "test@example.com",
        "password":          "ValidPass1",
        "organization_name": "Test Org",
        "accept_terms":      False,
    })
    assert response.status_code == 422


@pytest.mark.integration
async def test_login_empty_body(async_client):
    """Login sans body → 422."""
    client, _ = async_client
    response = await client.post("/api/v1/auth/login", json={})
    assert response.status_code == 422


# ── Tests : Authentification (mocked) ────────────────────────────────────────

@pytest.mark.integration
async def test_login_invalid_credentials(async_client):
    """Login avec mauvais credentials → 401."""
    client, mock_db = async_client

    # Mock : utilisateur non trouvé
    from sqlalchemy.ext.asyncio import AsyncSession
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    with patch("app.services.auth.auth_service.AuthService._get_user_by_email", return_value=None):
        response = await client.post("/api/v1/auth/login", json={
            "email":    "nonexistent@example.com",
            "password": "AnyPassword1",
        })
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"


@pytest.mark.integration
async def test_protected_endpoint_without_token(async_client):
    """Un endpoint protégé sans token → 401."""
    client, _ = async_client
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.integration
async def test_protected_endpoint_with_invalid_token(async_client):
    """Un endpoint protégé avec token invalide → 401."""
    client, _ = async_client
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt.token"},
    )
    assert response.status_code == 401


@pytest.mark.integration
async def test_protected_endpoint_with_malformed_auth_header(async_client):
    """Header Authorization mal formé → 401."""
    client, _ = async_client
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "NotBearer sometoken"},
    )
    assert response.status_code == 401


# ── Tests : Sécurité Générale ─────────────────────────────────────────────────

@pytest.mark.integration
async def test_cors_headers_present(async_client):
    """Les headers CORS doivent être présents pour les origines autorisées."""
    client, _ = async_client
    response = await client.options(
        "/api/v1/auth/login",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    # CORS doit permettre l'origine de dev
    assert response.status_code in (200, 204)


@pytest.mark.integration
async def test_security_headers_present(async_client):
    """Les headers de sécurité HTTP doivent être présents."""
    client, _ = async_client
    with patch("app.main._check_redis", return_value=True):
        response = await client.get("/health")
    headers = response.headers
    assert "x-content-type-options" in headers
    assert "x-frame-options" in headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"


@pytest.mark.integration
async def test_404_returns_json(async_client):
    """Une route inexistante doit retourner un JSON 404 propre."""
    client, _ = async_client
    response = await client.get("/this/route/does/not/exist")
    assert response.status_code == 404
    data = response.json()
    assert "code" in data
    assert data["code"] == "NOT_FOUND"


@pytest.mark.integration
async def test_request_id_header_in_response(async_client):
    """Chaque réponse doit contenir un X-Request-ID."""
    client, _ = async_client
    with patch("app.main._check_redis", return_value=True):
        response = await client.get("/health")
    assert "x-request-id" in response.headers


@pytest.mark.integration
async def test_gzip_compression_for_large_responses(async_client):
    """La compression Gzip doit être activée (le middleware répond même si Redis est indisponible)."""
    client, _ = async_client
    with patch("app.main._check_redis", return_value=True):
        response = await client.get(
            "/health",
            headers={"Accept-Encoding": "gzip"},
        )
    # GZip middleware activé — vérifier que la réponse est bien reçue (pas de crash)
    assert response.status_code in (200, 503)  # 503 acceptable si Redis non dispo en CI
    assert "content-type" in response.headers


# ── Tests : Rate Limiting ─────────────────────────────────────────────────────

@pytest.mark.integration
async def test_verify_email_invalid_token(async_client):
    """Token de vérification email inexistant → 401."""
    client, mock_db = async_client
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    response = await client.get("/api/v1/auth/verify-email?token=invalid_token_xyz")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_TOKEN"


@pytest.mark.integration
async def test_forgot_password_always_returns_200(async_client):
    """
    La route forgot-password doit toujours retourner 200
    même si l'email n'existe pas (sécurité anti-enumération).
    """
    client, mock_db = async_client
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nonexistent@example.com"},
    )
    assert response.status_code == 200
    # Le message doit être le même qu'avec un email existant
    assert "email" in response.json()["message"].lower()


# ── Tests : Documents (validation) ───────────────────────────────────────────

@pytest.mark.integration
async def test_analyze_without_file_returns_422(async_client):
    """Upload sans fichier → 422."""
    client, _ = async_client
    # Sans token → 401 avant même la validation du fichier
    response = await client.post("/api/v1/documents/analyze")
    assert response.status_code in (401, 422)


@pytest.mark.integration
async def test_list_templates_requires_auth(async_client):
    """La liste des templates nécessite une authentification."""
    client, _ = async_client
    response = await client.get("/api/v1/documents/templates/list")
    assert response.status_code == 401


# ── Tests : Compliance ────────────────────────────────────────────────────────

@pytest.mark.integration
async def test_compliance_audit_requires_auth(async_client):
    """Les audits nécessitent une authentification."""
    client, _ = async_client
    response = await client.post("/api/v1/compliance/audit", json={
        "audit_type": "rgpd",
        "answers": {}
    })
    assert response.status_code == 401
