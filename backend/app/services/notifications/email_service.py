"""
JurisIA — Service Email (Mailjet)
Emails transactionnels : vérification, reset, analyse terminée, alertes réglementaires.
"""
from __future__ import annotations
from typing import Optional

import structlog
import httpx

from app.core.config import settings

logger = structlog.get_logger(__name__)


class EmailService:
    """Service d'envoi d'emails via l'API Mailjet."""

    BASE_URL = "https://api.mailjet.com/v3.1/send"

    async def _send(self, to_email: str, to_name: str, subject: str, html_content: str) -> bool:
        """Envoie un email via l'API Mailjet."""
        if not settings.MAILJET_API_KEY:
            logger.debug("email_skipped_no_config", to=to_email, subject=subject)
            return True  # En dev sans config, ne pas bloquer

        payload = {
            "Messages": [{
                "From": {"Email": settings.MAILJET_FROM_EMAIL, "Name": settings.MAILJET_FROM_NAME},
                "To": [{"Email": to_email, "Name": to_name}],
                "Subject": subject,
                "HTMLPart": html_content,
            }]
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.BASE_URL,
                    json=payload,
                    auth=(settings.MAILJET_API_KEY, settings.MAILJET_SECRET_KEY),
                    timeout=10.0,
                )
                if response.status_code == 200:
                    logger.info("email_sent", to=to_email, subject=subject)
                    return True
                logger.warning("email_failed", status=response.status_code, to=to_email)
                return False
            except Exception as e:
                logger.error("email_error", error=str(e), to=to_email)
                return False

    async def send_verification_email(self, to_email: str, to_name: str, verify_url: str) -> bool:
        html = f"""
        <div style="font-family: Inter, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <div style="text-align: center; margin-bottom: 32px;">
            <h1 style="color: #0F2447; font-size: 28px; margin: 0;">JurisIA</h1>
            <p style="color: #64748B; font-size: 14px;">Assistant Juridique IA Souverain</p>
          </div>
          <div style="background: #F8FAFC; border-radius: 12px; padding: 32px;">
            <h2 style="color: #1E293B; font-size: 20px;">Vérifiez votre adresse email</h2>
            <p style="color: #475569; line-height: 1.6;">Bonjour {to_name},</p>
            <p style="color: #475569; line-height: 1.6;">
              Merci de vous être inscrit sur JurisIA. Cliquez sur le bouton ci-dessous pour confirmer votre adresse email.
            </p>
            <div style="text-align: center; margin: 32px 0;">
              <a href="{verify_url}"
                 style="background: #1E5FD8; color: white; padding: 14px 32px; border-radius: 8px;
                        text-decoration: none; font-weight: 600; font-size: 16px; display: inline-block;">
                Vérifier mon email
              </a>
            </div>
            <p style="color: #94A3B8; font-size: 12px;">
              Ce lien expire dans 24 heures. Si vous n'avez pas créé de compte, ignorez cet email.
            </p>
          </div>
          <p style="color: #94A3B8; font-size: 11px; text-align: center; margin-top: 24px;">
            JurisIA SAS — Données hébergées en France 🇫🇷 | RGPD conforme
          </p>
        </div>
        """
        return await self._send(to_email, to_name, "Vérifiez votre email — JurisIA", html)

    async def send_password_reset_email(self, to_email: str, to_name: str, reset_url: str) -> bool:
        html = f"""
        <div style="font-family: Inter, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <h1 style="color: #0F2447; text-align: center;">JurisIA</h1>
          <div style="background: #F8FAFC; border-radius: 12px; padding: 32px;">
            <h2 style="color: #1E293B;">Réinitialisation de mot de passe</h2>
            <p style="color: #475569;">Bonjour {to_name},</p>
            <p style="color: #475569;">
              Vous avez demandé la réinitialisation de votre mot de passe. Cliquez ci-dessous :
            </p>
            <div style="text-align: center; margin: 32px 0;">
              <a href="{reset_url}"
                 style="background: #DC2626; color: white; padding: 14px 32px; border-radius: 8px;
                        text-decoration: none; font-weight: 600; display: inline-block;">
                Réinitialiser mon mot de passe
              </a>
            </div>
            <p style="color: #94A3B8; font-size: 12px;">
              Ce lien expire dans 1 heure. Si vous n'avez pas fait cette demande, sécurisez votre compte.
            </p>
          </div>
        </div>
        """
        return await self._send(to_email, to_name, "Réinitialisation de mot de passe — JurisIA", html)

    async def send_analysis_complete_email(
        self, to_email: str, to_name: str, document_title: str, score: int, document_url: str
    ) -> bool:
        score_color = "#16A34A" if score >= 70 else "#D97706" if score >= 40 else "#DC2626"
        score_label = "Solide" if score >= 70 else "Modéré" if score >= 40 else "Risqué"
        html = f"""
        <div style="font-family: Inter, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <h1 style="color: #0F2447; text-align: center;">JurisIA</h1>
          <div style="background: #F8FAFC; border-radius: 12px; padding: 32px;">
            <h2 style="color: #1E293B;">✅ Votre analyse est prête</h2>
            <p style="color: #475569;">Bonjour {to_name},</p>
            <p style="color: #475569;">L'analyse de <strong>"{document_title}"</strong> est terminée.</p>
            <div style="background: white; border-radius: 8px; padding: 16px; margin: 16px 0;
                        border-left: 4px solid {score_color};">
              <p style="margin: 0; font-size: 18px; font-weight: bold; color: {score_color};">
                Score de solidité : {score}/100 — {score_label}
              </p>
            </div>
            <div style="text-align: center; margin-top: 24px;">
              <a href="{document_url}"
                 style="background: #1E5FD8; color: white; padding: 14px 32px; border-radius: 8px;
                        text-decoration: none; font-weight: 600; display: inline-block;">
                Voir l'analyse complète →
              </a>
            </div>
          </div>
        </div>
        """
        return await self._send(to_email, to_name, f"Analyse terminée : {score}/100 — {document_title}", html)

    async def send_regulatory_alert(
        self, to_email: str, to_name: str, alert_title: str, alert_body: str
    ) -> bool:
        html = f"""
        <div style="font-family: Inter, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
          <h1 style="color: #0F2447; text-align: center;">JurisIA — Alerte Réglementaire</h1>
          <div style="background: #FEF3C7; border: 1px solid #F59E0B; border-radius: 12px; padding: 32px;">
            <h2 style="color: #92400E;">⚠️ {alert_title}</h2>
            <div style="color: #78350F; line-height: 1.6;">{alert_body}</div>
          </div>
          <p style="color: #94A3B8; font-size: 11px; text-align: center; margin-top: 16px;">
            Vous recevez cet email car vous êtes abonné aux alertes réglementaires JurisIA.
            <a href="{settings.FRONTEND_URL}/settings/notifications">Se désabonner</a>
          </p>
        </div>
        """
        return await self._send(to_email, to_name, f"⚠️ Alerte réglementaire : {alert_title}", html)
