"""
JurisIA — Tests Unitaires : Sécurité & Authentification
Teste les fonctions critiques de sécurité et la logique d'auth.
"""
import pytest
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# ── Tests : Hashage de mots de passe ─────────────────────────────────────────

def test_hash_password_produces_hash():
    """Le hash d'un mot de passe ne doit pas être égal au mot de passe en clair."""
    from app.core.security import hash_password
    pwd    = "MonMotDePasse123!"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert len(hashed) > 30  # Argon2 hashes sont longs


def test_hash_password_different_hashes_for_same_password():
    """Deux hashages du même mot de passe doivent produire des hashes différents (salt)."""
    from app.core.security import hash_password
    pwd  = "MonMotDePasse123!"
    h1   = hash_password(pwd)
    h2   = hash_password(pwd)
    assert h1 != h2  # Le salt est différent à chaque fois


def test_verify_password_correct():
    from app.core.security import hash_password, verify_password
    pwd    = "MonMotDePasse123!"
    hashed = hash_password(pwd)
    assert verify_password(pwd, hashed) is True


def test_verify_password_wrong():
    from app.core.security import hash_password, verify_password
    hashed = hash_password("MonMotDePasse123!")
    assert verify_password("MauvaisMotDePasse", hashed) is False


def test_verify_password_empty_string():
    from app.core.security import hash_password, verify_password
    hashed = hash_password("MonMotDePasse123!")
    assert verify_password("", hashed) is False


def test_verify_password_invalid_hash_does_not_raise():
    """verify_password ne doit jamais lever d'exception."""
    from app.core.security import verify_password
    result = verify_password("password", "not_a_valid_hash")
    assert result is False


# ── Tests : Validation mot de passe ──────────────────────────────────────────

def test_password_strength_valid():
    from app.core.security import validate_password_strength
    is_valid, msg = validate_password_strength("MonPass1234!")
    assert is_valid is True
    assert msg == ""


def test_password_strength_too_short():
    from app.core.security import validate_password_strength
    is_valid, msg = validate_password_strength("Ab1!")
    assert is_valid is False
    assert "8" in msg


def test_password_strength_no_uppercase():
    from app.core.security import validate_password_strength
    is_valid, msg = validate_password_strength("monpass1234!")
    assert is_valid is False
    assert "majuscule" in msg.lower()


def test_password_strength_no_digit():
    from app.core.security import validate_password_strength
    is_valid, msg = validate_password_strength("MonPassword!")
    assert is_valid is False
    assert "chiffre" in msg.lower()


# ── Tests : JWT ───────────────────────────────────────────────────────────────

def test_create_access_token_contains_subject(monkeypatch):
    """Le token doit contenir le subject (user_id)."""
    monkeypatch.setenv("APP_SECRET_KEY", "test_secret_key_32_chars_minimum!!")
    monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt_secret_key_64_chars_min_required_here_abcdefghijklmno")
    monkeypatch.setenv("ENCRYPTION_KEY", "oudIUTdrF0o6QrztsCaqJCKd8L2f5au88JBW-WzeKgw=")
    monkeypatch.setenv("DATABASE_URL",   "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("MISTRAL_API_KEY", "dummy")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")

    # Recréer les settings pour prendre en compte les nouvelles vars
    import importlib
    import app.core.config as config_module
    config_module.get_settings.cache_clear()

    from app.core.security import create_access_token, verify_access_token
    token   = create_access_token(subject="user_123")
    payload = verify_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user_123"
    assert payload["type"] == "access"


def test_verify_access_token_expired(monkeypatch):
    """Un token expiré doit retourner None."""
    monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt_secret_key_64_chars_min_required_here_abcdefghijklmno")
    monkeypatch.setenv("APP_SECRET_KEY", "test_secret_key_32_chars_minimum!!")
    monkeypatch.setenv("ENCRYPTION_KEY", "oudIUTdrF0o6QrztsCaqJCKd8L2f5au88JBW-WzeKgw=")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("MISTRAL_API_KEY", "dummy")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")

    import app.core.config as config_module
    config_module.get_settings.cache_clear()

    from app.core.security import create_access_token, verify_access_token
    # Token déjà expiré
    token  = create_access_token(subject="user_123", expires_delta=timedelta(seconds=-1))
    result = verify_access_token(token)
    assert result is None


def test_verify_invalid_token():
    from app.core.security import verify_access_token
    result = verify_access_token("not.a.valid.token")
    assert result is None


def test_verify_empty_token():
    from app.core.security import verify_access_token
    result = verify_access_token("")
    assert result is None


# ── Tests : Refresh Token ─────────────────────────────────────────────────────

def test_create_refresh_token_format():
    from app.core.security import create_refresh_token
    raw, hashed = create_refresh_token()
    assert len(raw) > 32       # Token brut long
    assert len(hashed) == 64   # SHA-256 = 64 chars hex
    assert raw != hashed


def test_hash_refresh_token_deterministic():
    """Le hash d'un refresh token doit être déterministe."""
    from app.core.security import hash_refresh_token
    token  = "my_test_refresh_token_abc123"
    hash1  = hash_refresh_token(token)
    hash2  = hash_refresh_token(token)
    assert hash1 == hash2


def test_hash_refresh_token_different_inputs():
    from app.core.security import hash_refresh_token
    assert hash_refresh_token("token_a") != hash_refresh_token("token_b")


# ── Tests : Chiffrement ───────────────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", "oudIUTdrF0o6QrztsCaqJCKd8L2f5au88JBW-WzeKgw=")
    monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt_secret_key_64_chars_min_required_here_abcdefghijklmno")
    monkeypatch.setenv("APP_SECRET_KEY", "test_secret_key_32_chars_minimum!!")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("MISTRAL_API_KEY", "dummy")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")

    import app.core.config as config_module
    config_module.get_settings.cache_clear()

    from app.core.security import encrypt_data, decrypt_data
    original   = "Données confidentielles 🔐 àéîõü"
    encrypted  = encrypt_data(original)
    decrypted  = decrypt_data(encrypted)

    assert encrypted != original     # Le chiffrement a bien eu lieu
    assert decrypted == original     # Le déchiffrement est correct


def test_encrypt_produces_different_ciphertexts_each_time(monkeypatch):
    """Fernet inclut un IV aléatoire : deux chiffrements du même texte donnent des résultats différents."""
    monkeypatch.setenv("ENCRYPTION_KEY", "oudIUTdrF0o6QrztsCaqJCKd8L2f5au88JBW-WzeKgw=")
    monkeypatch.setenv("JWT_SECRET_KEY", "test_jwt_secret_key_64_chars_min_required_here_abcdefghijklmno")
    monkeypatch.setenv("APP_SECRET_KEY", "test_secret_key_32_chars_minimum!!")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("MISTRAL_API_KEY", "dummy")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")

    import app.core.config as config_module
    config_module.get_settings.cache_clear()

    from app.core.security import encrypt_data
    text = "Secret"
    assert encrypt_data(text) != encrypt_data(text)


# ── Tests : ULID ─────────────────────────────────────────────────────────────

def test_generate_ulid_format():
    from app.core.security import generate_ulid
    ulid = generate_ulid()
    assert len(ulid) == 26
    assert ulid == ulid.upper() or ulid.isalnum()  # ULID est alphanumérique


def test_generate_ulid_unique():
    from app.core.security import generate_ulid
    ids = {generate_ulid() for _ in range(100)}
    assert len(ids) == 100  # Tous uniques


# ── Tests : Sanitisation ──────────────────────────────────────────────────────

def test_sanitize_string_removes_control_chars():
    from app.core.security import sanitize_string
    evil = "Bonjour\x00 monde\x08!"
    result = sanitize_string(evil)
    assert "\x00" not in result
    assert "\x08" not in result


def test_sanitize_string_truncates():
    from app.core.security import sanitize_string
    long_str = "a" * 2000
    result   = sanitize_string(long_str, max_length=100)
    assert len(result) == 100


def test_sanitize_string_preserves_french_chars():
    from app.core.security import sanitize_string
    text   = "Vœu de l'équipe — été & hiver"
    result = sanitize_string(text)
    assert "é" in result
    assert "œ" in result


# ── Tests : Document Detection ────────────────────────────────────────────────

def test_detect_document_type_contract():
    from app.services.documents.analysis_service import DocumentAnalysisService
    svc  = DocumentAnalysisService(db=MagicMock())
    text = "CONTRAT DE PRESTATION DE SERVICES\nEntre les soussignés..."
    assert svc._detect_document_type(text) == "contract"


def test_detect_document_type_cgv():
    from app.services.documents.analysis_service import DocumentAnalysisService
    svc  = DocumentAnalysisService(db=MagicMock())
    text = "CONDITIONS GÉNÉRALES DE VENTE\nArticle 1 : Objet..."
    assert svc._detect_document_type(text) == "cgv"


def test_detect_document_type_nda():
    from app.services.documents.analysis_service import DocumentAnalysisService
    svc  = DocumentAnalysisService(db=MagicMock())
    text = "ACCORD DE CONFIDENTIALITÉ entre les parties..."
    assert svc._detect_document_type(text) == "nda"


def test_detect_document_type_unknown():
    from app.services.documents.analysis_service import DocumentAnalysisService
    svc  = DocumentAnalysisService(db=MagicMock())
    text = "Bla bla bla texte quelconque sans mots-clés juridiques"
    assert svc._detect_document_type(text) == "other"


# ── Tests : Prepare Text for LLM ─────────────────────────────────────────────

def test_prepare_text_no_truncation_for_short_doc():
    from app.services.documents.analysis_service import DocumentAnalysisService
    svc  = DocumentAnalysisService(db=MagicMock())
    text = "Court texte de 50 caractères seulement."
    result = svc._prepare_text_for_llm(text, max_chars=1000)
    assert result == text


def test_prepare_text_truncates_long_doc():
    from app.services.documents.analysis_service import DocumentAnalysisService
    svc  = DocumentAnalysisService(db=MagicMock())
    text = "A" * 20000
    result = svc._prepare_text_for_llm(text, max_chars=12000)
    assert len(result) < 15000  # Tronqué + notice
    assert "omis" in result.lower()


# ── Tests : Parse Mistral Response ────────────────────────────────────────────

def test_parse_mistral_response_valid_json():
    from app.services.documents.analysis_service import DocumentAnalysisService
    svc = DocumentAnalysisService(db=MagicMock())

    valid_json = """{
        "document_type": "contract",
        "summary": "Contrat standard avec quelques risques.",
        "score": 72,
        "clauses": [
            {
                "clause_text": "Le prestataire est responsable de tout dommage.",
                "risk_level": "danger",
                "explanation": "Responsabilité illimitée.",
                "suggestion": "Plafonner la responsabilité.",
                "legal_reference": "Article 1231-3 du Code civil",
                "legal_reference_url": "https://legifrance.fr",
                "position_approximate": 1
            }
        ]
    }"""

    result = svc._parse_mistral_response(valid_json)
    assert result.score == 72
    assert len(result.clauses) == 1
    assert result.clauses[0].risk_level.value == "danger"
    assert result.risk_counts["danger"] == 1


def test_parse_mistral_response_with_markdown_backticks():
    """Le parser doit gérer les réponses avec ```json ... ```"""
    from app.services.documents.analysis_service import DocumentAnalysisService
    svc = DocumentAnalysisService(db=MagicMock())

    with_backticks = """```json
    {"document_type": "other", "summary": "Test", "score": 50, "clauses": []}
    ```"""

    result = svc._parse_mistral_response(with_backticks)
    assert result.score == 50
    assert result.total_clauses == 0


def test_parse_mistral_response_score_clamped():
    """Le score doit être entre 0 et 100."""
    from app.services.documents.analysis_service import DocumentAnalysisService
    svc = DocumentAnalysisService(db=MagicMock())

    json_str = '{"document_type": "other", "summary": "X", "score": 150, "clauses": []}'
    result   = svc._parse_mistral_response(json_str)
    assert result.score == 100  # Clampé à 100


# ── Tests : Quota Service ────────────────────────────────────────────────────

def test_quota_limits_free_plan():
    from app.services.documents.quota_service import PLAN_QUOTAS
    from app.models import SubscriptionPlan
    limits = PLAN_QUOTAS[SubscriptionPlan.FREE]
    assert limits["documents_analyzed"] == 3
    assert limits["is_lifetime"] is True


def test_quota_limits_pro_plan():
    from app.services.documents.quota_service import PLAN_QUOTAS
    from app.models import SubscriptionPlan
    limits = PLAN_QUOTAS[SubscriptionPlan.PRO]
    assert limits["documents_analyzed"] >= 999  # "Illimité"
    assert limits["is_lifetime"] is False


# ── Tests : Document Templates ───────────────────────────────────────────────

def test_all_templates_have_required_fields():
    from app.services.documents.generation_service import DOCUMENT_TEMPLATES
    required_keys = {"name", "category", "description", "version", "fields", "prompt_template"}
    for key, tpl in DOCUMENT_TEMPLATES.items():
        missing = required_keys - set(tpl.keys())
        assert not missing, f"Template '{key}' manque les champs: {missing}"


def test_template_exists():
    from app.services.documents.generation_service import DocumentGenerationService
    from unittest.mock import MagicMock
    svc = DocumentGenerationService(db=MagicMock())
    assert svc.template_exists("prestation_services") is True
    assert svc.template_exists("template_inexistant") is False


def test_all_templates_have_prompts():
    from app.services.documents.generation_service import DOCUMENT_TEMPLATES, GENERATION_PROMPTS
    for key, tpl in DOCUMENT_TEMPLATES.items():
        prompt_key = tpl["prompt_template"]
        assert prompt_key in GENERATION_PROMPTS, f"Template '{key}' référence un prompt manquant: {prompt_key}"
