# ✅ CHECKLIST DE LANCEMENT — JURISΙΑ
## Validation Complète avant Mise en Production

> **Usage :** Cochez chaque item avant le lancement officiel.  
> Format : `[ ]` = À faire · `[x]` = Validé · `[!]` = Bloquant

---

## 🔴 SECTION 1 — SÉCURITÉ (Bloquant — Aucun lancement sans ces items)

### Secrets & Configuration
- [ ] `APP_SECRET_KEY` : 64 caractères aléatoires générés via `openssl rand -hex 32`
- [ ] `JWT_SECRET_KEY` : 128 caractères aléatoires distincts de APP_SECRET_KEY
- [ ] `ENCRYPTION_KEY` : Clé Fernet valide générée via `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- [ ] Aucun fichier `.env` commité sur GitHub (vérifier via `git log --all -- .env`)
- [ ] Variables d'environnement stockées dans GitHub Secrets pour le CI/CD
- [ ] `APP_ENV=production` et `APP_DEBUG=false` en production
- [ ] Docs Swagger désactivées en production (`/docs` → 404)

### Authentification & Accès
- [ ] Rate limiting activé sur `/auth/login` (max 10 req/min/IP)
- [ ] Rate limiting global activé (max 60 req/min/IP)
- [ ] 2FA disponible et fonctionnel (test manuel de setup + connexion)
- [ ] Rotation des refresh tokens validée (usage unique)
- [ ] Révocation des tokens en cas de détection d'abus (test avec token reuse)
- [ ] Délai artificiel sur les erreurs de connexion (anti brute-force)

### OWASP Top 10
- [ ] A01 — Aucun endpoint sans vérification d'ownership (document appartient à l'org)
- [ ] A02 — TLS 1.3 uniquement (TLS 1.0/1.1 refusés par Nginx)
- [ ] A03 — Parameterized queries partout (SQLAlchemy ORM, aucune requête brute)
- [ ] A05 — Headers HTTP sécurité validés (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`)
- [ ] A06 — `pip audit` et `npm audit` sans vulnérabilités critiques
- [ ] A07 — Comptes de test supprimés de la base de production
- [ ] A09 — Logs structurés en production (Sentry DSN configuré)

### Tests de Sécurité
- [ ] Scan Snyk (ou équivalent) : 0 vulnérabilité HIGH/CRITICAL
- [ ] Test CSRF protection : refus des requêtes cross-origin sans token
- [ ] Test injection SQL : toutes les entrées sont sanitisées
- [ ] Test XSS : contenu utilisateur échappé dans l'interface
- [ ] Test fichiers : upload limité à 20 Mo, types validés (pas de `.exe`, `.php`, etc.)

---

## 🟡 SECTION 2 — RGPD & CONFORMITÉ LÉGALE (Bloquant)

### Documents Légaux (à faire rédiger par un avocat)
- [ ] CGU/CGV publiées sur `/terms` — rédigées et validées par un avocat
- [ ] Politique de confidentialité publiée sur `/privacy` — conforme RGPD
- [ ] Mentions légales publiées sur `/legal` (Loi pour la Confiance dans l'Économie Numérique)
- [ ] Disclaimers juridiques inclus dans TOUS les documents générés par l'IA

### Gestion des Données
- [ ] Registre des activités de traitement (Art. 30 RGPD) créé et tenu à jour
- [ ] DPO désigné ou contact privacy@ configuré et fonctionnel
- [ ] Procédure de réponse aux droits utilisateurs documentée (délai < 30 jours)
- [ ] Export de données utilisateur fonctionnel (bouton dans les paramètres)
- [ ] Suppression de compte fonctionnelle (soft delete J0, purge physique J+30)
- [ ] Durées de conservation respectées et configurées dans le code
- [ ] Contrats sous-traitants signés (Mistral AI, Stripe, OVH, Mailjet)

### Cookies & Consentement
- [ ] Bandeau cookies conforme CNIL (accepter ET refuser en 1 clic)
- [ ] Pas de cookies trackeurs avant consentement
- [ ] Liste des cookies documentée dans la politique de confidentialité

### AI Act (Août 2026)
- [ ] Classification du système JurisIA effectuée (risque limité — obligation de transparence)
- [ ] Notice de transparence IA affichée dans l'interface ("Réponse générée par IA")
- [ ] Documentation technique du système IA rédigée
- [ ] Mécanisme de signalement d'erreur IA fonctionnel (bouton "Signaler une erreur")

---

## 🟢 SECTION 3 — PERFORMANCES & FIABILITÉ

### Tests de Performance
- [ ] Temps de chargement initial < 3 secondes (LCP < 2.5s selon Lighthouse)
- [ ] Analyse d'un document de 10 pages : < 60 secondes
- [ ] Génération d'un document : < 30 secondes
- [ ] Réponse API (P50) < 300ms pour les endpoints non-IA
- [ ] Score Lighthouse mobile > 80 (performance, accessibilité, SEO)

### Tests de Charge
- [ ] Test k6 : 100 utilisateurs simultanés pendant 5 minutes → 0 erreur 5xx
- [ ] Celery workers : file d'attente vide en < 2 minutes sous charge
- [ ] Redis : utilisation mémoire stable (pas de memory leak)
- [ ] PostgreSQL : connexions pool saines (pg_stat_activity)

### Scalabilité
- [ ] Auto-scaling configuré pour le backend (Kubernetes ou équivalent)
- [ ] CDN configuré pour les assets statiques (Cloudflare)
- [ ] Cache Redis configuré pour les requêtes fréquentes

### Haute Disponibilité
- [ ] Uptime target 99.5% documenté et SLA défini
- [ ] Plan de reprise après sinistre documenté (RTO < 2h, RPO < 1h)
- [ ] Backups PostgreSQL testés et validés (restauration effectivement testée)
- [ ] Monitoring 24/7 configuré (Grafana alertes ou équivalent)
- [ ] Runbook incident créé (que faire si le serveur tombe à 3h du matin ?)

---

## 🔵 SECTION 4 — MONITORING & OBSERVABILITÉ

- [ ] Sentry configuré avec DSN de production (alertes email activées)
- [ ] Dashboard Grafana : métriques clés (RPS, latence, taux d'erreur, CPU, RAM)
- [ ] Alertes configurées pour :
  - [ ] Temps de réponse P95 > 1 seconde pendant 2 minutes
  - [ ] Taux d'erreur 5xx > 1%
  - [ ] CPU > 80% pendant 5 minutes
  - [ ] RAM > 85%
  - [ ] Espace disque < 20% libre
  - [ ] Backup PostgreSQL échoué
  - [ ] Certificat SSL expire dans < 30 jours
- [ ] Posthog configuré : tous les événements critiques trackés
  - [ ] `user.registered`, `user.logged_in`
  - [ ] `document.analyzed`, `document.generated`
  - [ ] `chat.message_sent`
  - [ ] `subscription.upgraded`, `subscription.canceled`
  - [ ] `compliance.audit_completed`
- [ ] Health check endpoint `/health` accessible et retourne 200

---

## 🟣 SECTION 5 — EXPÉRIENCE UTILISATEUR

### Fonctionnel
- [ ] Inscription → Email de vérification reçu → Connexion réussie
- [ ] Analyse d'un contrat PDF de bout en bout testée
- [ ] Génération d'un contrat de prestation testée
- [ ] Conversation avec l'assistant juridique testée (3 questions)
- [ ] Audit RGPD complet jusqu'au plan d'action testé
- [ ] Checkout Stripe (mode test) → Upgrade plan → Fonctionnalités Pro débloquées
- [ ] Portail client Stripe (gestion facturation) accessible
- [ ] Résiliation d'abonnement testée
- [ ] Export de données utilisateur (RGPD) fonctionnel

### Interface
- [ ] Affichage correct sur Chrome (dernière version)
- [ ] Affichage correct sur Firefox (dernière version)
- [ ] Affichage correct sur Safari (dernière version)
- [ ] Affichage correct sur Edge (dernière version)
- [ ] Responsive mobile iPhone 14 (390px) : navigation utilisable
- [ ] Responsive mobile Android (360px) : navigation utilisable
- [ ] Tablette iPad (768px) : navigation utilisable

### Accessibilité (WCAG 2.1 AA)
- [ ] Navigation clavier complète (Tab + Entrée + Échap)
- [ ] Contraste couleurs ≥ 4.5:1 (texte normal) vérifié via axe-core
- [ ] Tous les liens et boutons ont un label aria descriptif
- [ ] Formulaires : chaque input a un label associé
- [ ] Images décoratives : `aria-hidden="true"`
- [ ] Messages d'erreur : `role="alert"` et `aria-invalid`

---

## 🌐 SECTION 6 — SEO & TECHNIQUE WEB

- [ ] `<title>` et `<meta description>` uniques sur chaque page
- [ ] Open Graph tags configurés (titre, description, image)
- [ ] `robots.txt` créé (bloquer `/dashboard`, `/api`, etc.)
- [ ] `sitemap.xml` généré et soumis à Google Search Console
- [ ] Favicon `.ico` et `apple-touch-icon.png` présents
- [ ] HTTPS forcé (redirect 301 de HTTP vers HTTPS)
- [ ] En-tête HSTS configuré dans Nginx
- [ ] Compression Gzip activée pour les assets
- [ ] Images optimisées (WebP, lazy loading)

---

## 📧 SECTION 7 — EMAILS & NOTIFICATIONS

- [ ] Email de vérification reçu (tester avec une vraie adresse)
- [ ] Email de reset password reçu et lien fonctionnel
- [ ] Email "Analyse terminée" déclenché correctement
- [ ] Email "Alerte réglementaire" (test d'envoi manuel)
- [ ] Emails ne tombent pas en spam (tester via mail-tester.com → score > 8/10)
- [ ] SPF, DKIM et DMARC configurés sur le domaine d'envoi
- [ ] Lien de désinscription fonctionnel dans les emails marketing
- [ ] Email visible sur mobile (Outlook, Gmail, Apple Mail testés)

---

## 💳 SECTION 8 — PAIEMENT & FACTURATION

- [ ] Plans Stripe créés en mode LIVE (pas uniquement test)
- [ ] Prix correctement configurés (79€, 149€, 299€ HT)
- [ ] TVA configurée (20% France)
- [ ] Webhook Stripe configuré sur l'URL de production avec signature
- [ ] Test du flux complet en mode LIVE avec une vraie CB (montant symbolique)
- [ ] Factures PDF générées avec : numéro, date, TVA, SIRET, adresse
- [ ] Portail Stripe accessible depuis les paramètres
- [ ] Email de confirmation d'abonnement reçu après paiement
- [ ] Email de notification en cas d'échec de paiement

---

## 🚀 SECTION 9 — DÉPLOIEMENT & INFRA

- [ ] Docker images buildées et poussées sur le registry
- [ ] Serveur de production accessible via SSH
- [ ] Domaines DNS configurés et propagés (app.jurisai.fr, api.jurisai.fr)
- [ ] Certificats SSL Let's Encrypt valides et actifs
- [ ] Renouvellement automatique des certificats configuré (Certbot)
- [ ] Migrations Alembic appliquées en production
- [ ] Variables d'environnement de production configurées
- [ ] Logs rotatifs configurés (max 50 Mo par fichier, 5 fichiers)
- [ ] Firewall configuré (ports 22, 80, 443 uniquement depuis l'extérieur)

---

## 📣 SECTION 10 — LANCEMENT COMMERCIAL

- [ ] Landing page de présentation publiée (page publique avant login)
- [ ] Page pricing publique avec comparatif des plans
- [ ] FAQ publique avec les 10 questions les plus fréquentes
- [ ] Support Crisp configuré et testé
- [ ] Première campagne LinkedIn B2B préparée
- [ ] 5 cabinets comptables partenaires contactés et prêts
- [ ] Communiqué de presse rédigé (optionnel)
- [ ] Google Analytics configuré (ou Posthog public)
- [ ] Plan de contenu SEO (10 premiers articles) rédigé

---

## ✅ VALIDATION FINALE

```
□ Toutes les cases ROUGES cochées → SÉCURITÉ OK
□ Toutes les cases JAUNES cochées → RGPD OK
□ Au moins 80% des cases VERTES cochées → PERFORMANCE OK
□ Au moins 80% des cases BLEUES cochées → MONITORING OK
□ Test E2E complet effectué par une personne externe (non-développeur)
□ Fondateur a utilisé l'app de bout en bout pendant 30 minutes sans anomalie
```

**Signature de validation :**

| Rôle | Nom | Date | Signature |
|---|---|---|---|
| Fondateur / CEO | | | |
| Lead Developer | | | |
| Juriste / DPO | | | |

---

> ⚡ **Rappel :** Mieux vaut lancer avec 80% des items et itérer vite que d'attendre la perfection.  
> Les items ROUGES (sécurité) et JAUNES (RGPD) sont les seuls vraiment bloquants.  
> Le reste peut être amélioré post-lancement avec les premiers retours utilisateurs.
