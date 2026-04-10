"""
JurisIA — Modèles de Base de Données (SQLAlchemy)
Schéma complet de l'application. Chaque modèle correspond à une table PostgreSQL.
ULIDs utilisés comme PKs (meilleure performance d'index que UUID pur).
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


# ─── Helpers ──────────────────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ─── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    TRIALING = "trialing"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"


class DocumentType(str, enum.Enum):
    ANALYSIS = "analysis"    # Document analysé par l'IA
    GENERATED = "generated"  # Document généré par l'IA


class DocumentCategory(str, enum.Enum):
    CONTRACT = "contract"
    RH = "rh"
    COMPLIANCE = "compliance"
    RECOVERY = "recovery"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RiskLevel(str, enum.Enum):
    SAFE = "safe"
    WARNING = "warning"
    DANGER = "danger"
    MISSING = "missing"


class AuditType(str, enum.Enum):
    RGPD = "rgpd"
    AI_ACT = "ai_act"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


# ─── Modèle : User ────────────────────────────────────────────────────────────

class User(Base):
    """
    Utilisateur de la plateforme.
    Peut appartenir à plusieurs organisations (via OrganizationMember).
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verification_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    two_fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    two_fa_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Chiffré Fernet
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    password_reset_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )  # Soft delete RGPD

    # Relationships
    memberships: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# ─── Modèle : RefreshToken ────────────────────────────────────────────────────

class RefreshToken(Base):
    """
    Tokens de rafraîchissement JWT.
    Stockés en BDD pour permettre la révocation (logout, sécurité).
    """
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


# ─── Modèle : Organization ────────────────────────────────────────────────────

class Organization(Base):
    """
    Entreprise cliente de JurisIA.
    Une organisation peut avoir plusieurs membres (utilisateurs).
    """
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    siren: Mapped[Optional[str]] = mapped_column(String(14), unique=True, nullable=True, index=True)
    sector_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)   # Code NAF
    sector_label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    employee_count_range: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )  # "1-10" | "11-50" | "51-250" | "250+"
    convention_collective: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    members: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="organization"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="organization"
    )
    compliance_audits: Mapped[list["ComplianceAudit"]] = relationship(
        back_populates="organization"
    )


# ─── Modèle : OrganizationMember ─────────────────────────────────────────────

class OrganizationMember(Base):
    """Table de jointure User ↔ Organization avec le rôle."""
    __tablename__ = "organization_members"

    user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.EDITOR, nullable=False)
    invited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="memberships")
    organization: Mapped["Organization"] = relationship(back_populates="members")


# ─── Modèle : Subscription ────────────────────────────────────────────────────

class Subscription(Base):
    """
    Abonnement Stripe d'une organisation.
    Une organisation peut avoir un seul abonnement actif à la fois.
    """
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, index=True)
    organization_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(SubscriptionPlan), default=SubscriptionPlan.FREE, nullable=False
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False
    )
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="subscriptions")

    # Index pour les lookups fréquents
    __table_args__ = (
        Index("ix_subscriptions_org_status", "organization_id", "status"),
    )


# ─── Modèle : Document ────────────────────────────────────────────────────────

class Document(Base):
    """
    Document analysé ou généré par JurisIA.
    Stocke les métadonnées ; le contenu brut est dans S3.
    """
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, index=True)
    organization_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    doc_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sub_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False, index=True
    )
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)       # Chemin S3
    generated_content: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)  # Contenu structuré
    analysis_result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)    # Résultat analyse
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)  # Taille, pages, etc.
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)         # Score 0-100 (analyse)
    template_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    legal_disclaimer_version: Mapped[str] = mapped_column(String(10), default="1.0", nullable=False)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # ID tâche async
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="documents")
    clauses: Mapped[list["DocumentClause"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentClause.position_start"
    )

    __table_args__ = (
        Index("ix_documents_org_type_status", "organization_id", "doc_type", "status"),
        Index("ix_documents_org_created", "organization_id", "created_at"),
    )


# ─── Modèle : DocumentClause ──────────────────────────────────────────────────

class DocumentClause(Base):
    """Clause individuelle identifiée lors de l'analyse d'un document."""
    __tablename__ = "document_clauses"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, index=True)
    document_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    clause_text: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    legal_reference: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    legal_reference_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    position_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    position_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="clauses")


# ─── Modèle : Conversation ────────────────────────────────────────────────────

class Conversation(Base):
    """Session de conversation avec l'assistant juridique."""
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, index=True)
    organization_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Auto-généré
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="conversations")
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )


# ─── Modèle : ConversationMessage ────────────────────────────────────────────

class ConversationMessage(Base):
    """Message individuel dans une conversation."""
    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, index=True)
    conversation_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)  # [{text, url, article}]
    document_id: Mapped[Optional[str]] = mapped_column(
        String(26), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


# ─── Modèle : ComplianceAudit ─────────────────────────────────────────────────

class ComplianceAudit(Base):
    """Résultat d'un audit RGPD ou AI Act pour une organisation."""
    __tablename__ = "compliance_audits"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, index=True)
    organization_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    audit_type: Mapped[AuditType] = mapped_column(Enum(AuditType), nullable=False)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    answers: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    action_plan: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="compliance_audits")


# ─── Modèle : Notification ────────────────────────────────────────────────────

class Notification(Base):
    """Notification in-app pour un utilisateur."""
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(26), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    notification_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="notifications")

    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "read_at"),
    )


# ─── Modèle : AuditLog ────────────────────────────────────────────────────────

class AuditLog(Base):
    """
    Journal d'audit pour traçabilité RGPD.
    Enregistre toutes les actions significatives des utilisateurs.
    IMPORTANT : Cette table ne doit jamais être modifiée (append-only).
    """
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(26), nullable=True, index=True)
    organization_id: Mapped[Optional[str]] = mapped_column(String(26), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(26), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_audit_log_user_action", "user_id", "action", "created_at"),
    )


# ─── Modèle : UsageQuota ──────────────────────────────────────────────────────

class UsageQuota(Base):
    """
    Suivi des quotas d'utilisation par organisation et par mois.
    Réinitialisé automatiquement chaque mois (via tâche Celery).
    """
    __tablename__ = "usage_quotas"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    organization_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)
    documents_analyzed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    documents_generated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    questions_asked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    signatures_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ai_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "period_year", "period_month", name="uq_usage_org_period"),
        Index("ix_usage_quota_org_period", "organization_id", "period_year", "period_month"),
    )
