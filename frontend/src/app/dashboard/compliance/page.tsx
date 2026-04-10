'use client';

/**
 * JurisIA — Page Conformité (RGPD + AI Act)
 * Questionnaire guidé → score de conformité → plan d'action priorisé.
 */

import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ShieldCheck, ShieldAlert, CheckCircle, Circle, Clock, ChevronRight, ArrowLeft } from 'lucide-react';
import { Button, Badge, Card, Skeleton } from '@/components/ui/index';
import { toast } from '@/components/ui/Toaster';
import { apiPost, apiGet } from '@/services/api';
import { usePlan } from '@/store/auth.store';
import { cn, getScoreColor, getScoreBg, getScoreLabel } from '@/lib/utils';

// ── Types ─────────────────────────────────────────────────────────────────────

interface AuditResult {
  id:            string;
  audit_type:    string;
  score:         number;
  action_plan:   ActionItem[];
  completed_at:  string;
  created_at:    string;
}

interface ActionItem {
  action:      string;
  priority:    'high' | 'medium' | 'low';
  description: string;
  deadline:    string;
}

// ── Questions RGPD ────────────────────────────────────────────────────────────

const RGPD_QUESTIONS = [
  {
    key:         'has_privacy_policy',
    label:       'Avez-vous une politique de confidentialité publiée sur votre site ?',
    description: 'Obligatoire si vous collectez des données personnelles (email, formulaires, cookies…)',
    article:     'Art. 13 RGPD',
  },
  {
    key:         'has_cookie_consent',
    label:       'Votre site affiche-t-il un bandeau de consentement aux cookies conforme ?',
    description: 'Le bandeau doit permettre d\'accepter ET refuser facilement, avec liste des cookies.',
    article:     'Art. 7 RGPD + Délibération CNIL 2020',
  },
  {
    key:         'has_data_register',
    label:       'Avez-vous un registre des activités de traitement (Art. 30 RGPD) ?',
    description: 'Obligatoire pour toute entreprise de + de 250 salariés (et recommandé en dessous).',
    article:     'Art. 30 RGPD',
  },
  {
    key:         'has_dpo_contact',
    label:       'Avez-vous un DPO ou un contact dédié pour les questions données personnelles ?',
    description: 'Obligatoire si vous traitez des données sensibles ou à grande échelle.',
    article:     'Art. 37 RGPD',
  },
  {
    key:         'data_minimization',
    label:       'Collectez-vous uniquement les données strictement nécessaires à vos services ?',
    description: 'Principe de minimisation : ne collecter que ce qui est utile, ni plus ni moins.',
    article:     'Art. 5.1.c RGPD',
  },
  {
    key:         'has_user_rights_process',
    label:       'Avez-vous une procédure pour répondre aux demandes d\'accès/suppression de données ?',
    description: 'Délai légal : 1 mois pour répondre à tout exercice de droit.',
    article:     'Art. 12 RGPD',
  },
  {
    key:         'uses_eu_hosting',
    label:       'Vos données sont-elles hébergées dans l\'Union Européenne ?',
    description: 'Transfert hors UE autorisé uniquement avec garanties appropriées (clauses contractuelles types…).',
    article:     'Art. 44-49 RGPD',
  },
  {
    key:         'has_vendor_contracts',
    label:       'Avez-vous des contrats de sous-traitance IA/tech incluant des clauses RGPD ?',
    description: 'Obligatoire avec tout prestataire qui traite des données pour votre compte.',
    article:     'Art. 28 RGPD',
  },
];

// ── Questions AI Act ──────────────────────────────────────────────────────────

const AI_ACT_QUESTIONS = [
  {
    key:         'has_ai_inventory',
    label:       'Avez-vous listé tous les outils IA utilisés dans votre entreprise ?',
    description: 'Ex : ChatGPT, Copilot, outils de scoring RH, chatbots… Obligation de transparence.',
    article:     'Art. 53 AI Act',
  },
  {
    key:         'knows_risk_classification',
    label:       'Avez-vous évalué la classification de risque de vos systèmes IA ?',
    description: 'Risque inacceptable / élevé / limité / minimal — chaque niveau a des obligations différentes.',
    article:     'Art. 6-9 AI Act',
  },
  {
    key:         'has_human_oversight',
    label:       'Les décisions importantes basées sur l\'IA sont-elles soumises à supervision humaine ?',
    description: 'Critique pour les systèmes à haut risque : recrutement, scoring crédit, évaluation salariés.',
    article:     'Art. 14 AI Act',
  },
  {
    key:         'has_ai_documentation',
    label:       'Disposez-vous de documentation technique sur vos systèmes IA à haut risque ?',
    description: 'Documentation obligatoire pour les systèmes à haut risque à partir d\'août 2026.',
    article:     'Art. 11-12 AI Act',
  },
  {
    key:         'uses_bias_testing',
    label:       'Avez-vous testé vos outils IA pour détecter des biais discriminatoires ?',
    description: 'Particulièrement important pour les outils RH et de scoring client.',
    article:     'Art. 9-10 AI Act',
  },
  {
    key:         'has_transparency_notices',
    label:       'Informez-vous vos utilisateurs/salariés quand une IA est impliquée dans une décision ?',
    description: 'Obligation de transparence : les personnes concernées doivent être informées.',
    article:     'Art. 50 AI Act',
  },
];

// ── Composant Question ────────────────────────────────────────────────────────

function QuestionRow({
  q, value, onChange,
}: {
  q:        typeof RGPD_QUESTIONS[0];
  value:    boolean | null;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start gap-4 py-4 border-b border-border last:border-0">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground">{q.label}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{q.description}</p>
        <span className="inline-block mt-1 text-2xs font-mono bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
          {q.article}
        </span>
      </div>
      <div className="flex gap-2 flex-shrink-0">
        <button
          onClick={() => onChange(true)}
          className={cn(
            'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium border transition-all',
            value === true
              ? 'bg-green-600 text-white border-green-600'
              : 'border-border text-muted-foreground hover:border-green-400',
          )}
          aria-pressed={value === true}
        >
          <CheckCircle className="h-3.5 w-3.5" aria-hidden="true" />
          Oui
        </button>
        <button
          onClick={() => onChange(false)}
          className={cn(
            'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium border transition-all',
            value === false
              ? 'bg-red-100 text-red-700 border-red-300'
              : 'border-border text-muted-foreground hover:border-red-300',
          )}
          aria-pressed={value === false}
        >
          <Circle className="h-3.5 w-3.5" aria-hidden="true" />
          Non
        </button>
      </div>
    </div>
  );
}

// ── Composant Résultat ────────────────────────────────────────────────────────

function AuditResultView({
  result, onRedo,
}: {
  result: AuditResult;
  onRedo: () => void;
}) {
  const priorityConfig = {
    high:   { label: 'Urgent',    color: 'danger',  icon: '🔴' },
    medium: { label: 'Important', color: 'warning', icon: '🟡' },
    low:    { label: 'À planifier', color: 'muted', icon: '🟢' },
  } as const;

  const high   = result.action_plan?.filter((a) => a.priority === 'high') ?? [];
  const medium = result.action_plan?.filter((a) => a.priority === 'medium') ?? [];
  const done   = 8 - (result.action_plan?.length ?? 0); // Nb de points conformes

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Score */}
      <Card className={cn('border', getScoreBg(result.score))}>
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <p className="text-sm text-muted-foreground">Score de conformité {result.audit_type.toUpperCase()}</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className={`text-5xl font-extrabold ${getScoreColor(result.score)}`}>
                {result.score}
              </span>
              <span className="text-xl text-muted-foreground">/100</span>
              <Badge variant={result.score >= 70 ? 'success' : result.score >= 40 ? 'warning' : 'danger'}>
                {getScoreLabel(result.score)}
              </Badge>
            </div>
          </div>
          <div className="flex gap-6">
            <div className="text-center">
              <p className="text-2xl font-bold text-red-600">{high.length}</p>
              <p className="text-xs text-muted-foreground">Actions urgentes</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-amber-600">{medium.length}</p>
              <p className="text-xs text-muted-foreground">À planifier</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold text-green-600">{done}</p>
              <p className="text-xs text-muted-foreground">Conformes</p>
            </div>
          </div>
        </div>
        {result.score < 70 && (
          <p className="mt-3 text-sm text-foreground/70 border-t border-current/10 pt-3">
            💡 Avec {result.action_plan?.length ?? 0} action{result.action_plan?.length !== 1 ? 's' : ''} corrective{result.action_plan?.length !== 1 ? 's' : ''},
            votre score peut atteindre 100/100.
          </p>
        )}
      </Card>

      {/* Plan d'action */}
      {(result.action_plan?.length ?? 0) > 0 && (
        <section>
          <h2 className="text-base font-semibold mb-4">Plan d'action priorisé</h2>
          <div className="space-y-3">
            {result.action_plan.map((item, i) => {
              const cfg = priorityConfig[item.priority];
              return (
                <Card key={i} className={cn('p-4', item.priority === 'high' ? 'border-red-200' : 'border-border')}>
                  <div className="flex items-start gap-3">
                    <span className="text-lg flex-shrink-0 mt-0.5" aria-hidden="true">{cfg.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <p className="text-sm font-semibold text-foreground">{item.action}</p>
                        <Badge variant={cfg.color as 'danger' | 'warning' | 'muted'} className="text-2xs">
                          {cfg.label}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground">{item.description}</p>
                      <div className="flex items-center gap-1.5 mt-2">
                        <Clock className="h-3 w-3 text-muted-foreground" aria-hidden="true" />
                        <span className="text-2xs text-muted-foreground">{item.deadline}</span>
                      </div>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </section>
      )}

      {result.score === 100 && (
        <Card className="border-green-200 bg-green-50 text-center py-8">
          <ShieldCheck className="h-14 w-14 text-green-600 mx-auto mb-3" aria-hidden="true" />
          <p className="text-xl font-bold text-green-900">Félicitations ! Score parfait.</p>
          <p className="text-sm text-green-700 mt-1">
            Votre organisation est pleinement conforme {result.audit_type.toUpperCase()}.
          </p>
        </Card>
      )}

      <Button variant="secondary" onClick={onRedo} leftIcon={<ArrowLeft className="h-4 w-4" />}>
        Recommencer l'audit
      </Button>
    </div>
  );
}

// ── Page Principale ───────────────────────────────────────────────────────────

export default function CompliancePage() {
  const plan                          = usePlan();
  const [auditType,   setAuditType]   = useState<'rgpd' | 'ai_act' | null>(null);
  const [answers,     setAnswers]     = useState<Record<string, boolean | null>>({});
  const [auditResult, setAuditResult] = useState<AuditResult | null>(null);

  const canDoAiAct = plan === 'pro' || plan === 'business';

  const questions = auditType === 'rgpd' ? RGPD_QUESTIONS : AI_ACT_QUESTIONS;

  const submitMutation = useMutation({
    mutationFn: () =>
      apiPost<AuditResult>('/compliance/audit', {
        audit_type: auditType,
        answers: Object.fromEntries(
          Object.entries(answers).map(([k, v]) => [k, v ?? false])
        ),
      }),
    onSuccess: (data) => setAuditResult(data),
    onError:   (err: Error) => toast.error('Erreur', err.message),
  });

  const allAnswered = auditType
    ? questions.every((q) => answers[q.key] !== null && answers[q.key] !== undefined)
    : false;

  // Résultats précédents
  const { data: previousAudits } = useQuery({
    queryKey: ['compliance', 'audits'],
    queryFn:  () => apiGet<AuditResult[]>('/compliance/audits'),
    enabled:  !auditType,
  });

  // ── RÉSULTAT ────────────────────────────────────────────────────────────────
  if (auditResult) {
    return (
      <div className="max-w-2xl space-y-6">
        <h1 className="text-2xl font-bold text-foreground">Audit {auditResult.audit_type.toUpperCase()}</h1>
        <AuditResultView result={auditResult} onRedo={() => { setAuditResult(null); setAuditType(null); setAnswers({}); }} />
      </div>
    );
  }

  // ── QUESTIONNAIRE ────────────────────────────────────────────────────────────
  if (auditType) {
    return (
      <div className="max-w-2xl space-y-6">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => { setAuditType(null); setAnswers({}); }} aria-label="Retour">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-xl font-bold text-foreground">
              Audit {auditType === 'rgpd' ? 'RGPD' : 'AI Act'}
            </h1>
            <p className="text-sm text-muted-foreground">
              {questions.length} questions · Répondez honnêtement pour un score précis
            </p>
          </div>
        </div>

        {/* Progression */}
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-electric rounded-full transition-all"
              style={{ width: `${(Object.values(answers).filter((v) => v !== null && v !== undefined).length / questions.length) * 100}%` }}
              role="progressbar"
              aria-valuenow={Object.values(answers).filter((v) => v !== null).length}
              aria-valuemax={questions.length}
            />
          </div>
          <span className="text-xs text-muted-foreground flex-shrink-0">
            {Object.values(answers).filter((v) => v !== null).length}/{questions.length}
          </span>
        </div>

        <Card className="divide-y divide-border p-0 overflow-hidden">
          <div className="p-5 space-y-0">
            {questions.map((q) => (
              <QuestionRow
                key={q.key}
                q={q}
                value={answers[q.key] ?? null}
                onChange={(v) => setAnswers((prev) => ({ ...prev, [q.key]: v }))}
              />
            ))}
          </div>
        </Card>

        <Button
          onClick={() => submitMutation.mutate()}
          disabled={!allAnswered}
          isLoading={submitMutation.isPending}
          size="lg"
          className="w-full"
          rightIcon={<ChevronRight className="h-4 w-4" />}
        >
          Calculer mon score de conformité
        </Button>

        {!allAnswered && (
          <p className="text-xs text-muted-foreground text-center">
            Répondez à toutes les questions pour obtenir votre score.
          </p>
        )}
      </div>
    );
  }

  // ── ACCUEIL ──────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Conformité Réglementaire</h1>
        <p className="text-muted-foreground mt-1">
          Évaluez votre conformité RGPD et AI Act en quelques minutes.
        </p>
      </div>

      {/* Cartes audit */}
      <div className="grid sm:grid-cols-2 gap-6">
        {/* RGPD */}
        <button
          onClick={() => setAuditType('rgpd')}
          className="group text-left rounded-xl border border-border p-6 hover:border-brand-electric/50 hover:shadow-card-hover transition-all"
        >
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 flex-shrink-0">
              <ShieldCheck className="h-6 w-6 text-white" aria-hidden="true" />
            </div>
            <div>
              <h2 className="font-bold text-lg text-foreground group-hover:text-brand-electric transition-colors">
                Audit RGPD
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                8 questions sur votre conformité au Règlement Général sur la Protection des Données.
              </p>
              <div className="flex flex-wrap gap-2 mt-3">
                <Badge variant="default">Cookies</Badge>
                <Badge variant="default">Registre traitements</Badge>
                <Badge variant="default">Droits utilisateurs</Badge>
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
            <span className="text-xs text-muted-foreground">~5 minutes · Gratuit</span>
            <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-brand-electric transition-colors" />
          </div>
        </button>

        {/* AI Act */}
        <button
          onClick={() => canDoAiAct ? setAuditType('ai_act') : undefined}
          className={cn(
            'group text-left rounded-xl border p-6 transition-all',
            canDoAiAct
              ? 'border-border hover:border-orange-400/50 hover:shadow-card-hover cursor-pointer'
              : 'border-border opacity-60 cursor-not-allowed',
          )}
          aria-disabled={!canDoAiAct}
        >
          <div className="flex items-start gap-4">
            <div className={cn(
              'flex h-12 w-12 items-center justify-center rounded-xl flex-shrink-0',
              canDoAiAct ? 'bg-orange-500' : 'bg-muted',
            )}>
              <ShieldAlert className={cn('h-6 w-6', canDoAiAct ? 'text-white' : 'text-muted-foreground')} aria-hidden="true" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className={cn('font-bold text-lg', canDoAiAct ? 'text-foreground group-hover:text-orange-600 transition-colors' : 'text-muted-foreground')}>
                  Audit AI Act
                </h2>
                {!canDoAiAct && (
                  <Badge variant="warning" className="text-2xs">Plan Pro requis</Badge>
                )}
              </div>
              <p className="text-sm text-muted-foreground mt-1">
                6 questions sur votre conformité au règlement européen sur l'IA.
                <strong className="text-foreground"> Obligations applicables dès août 2026.</strong>
              </p>
              <div className="flex flex-wrap gap-2 mt-3">
                <Badge variant="warning">⚡ Urgent</Badge>
                <Badge variant="default">Inventaire IA</Badge>
                <Badge variant="default">Classification risques</Badge>
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
            <span className="text-xs text-muted-foreground">~5 minutes · Plan Pro</span>
            {canDoAiAct
              ? <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-orange-600 transition-colors" />
              : <span className="text-xs font-medium text-amber-600">
                  <a href="/dashboard/billing" className="hover:underline" onClick={(e) => e.stopPropagation()}>Passer à Pro →</a>
                </span>
            }
          </div>
        </button>
      </div>

      {/* Historique */}
      {previousAudits && previousAudits.length > 0 && (
        <section>
          <h2 className="text-base font-semibold mb-4">Historique des audits</h2>
          <div className="space-y-3">
            {previousAudits.slice(0, 5).map((audit) => (
              <Card key={audit.id} className="p-4 flex items-center gap-4">
                <div className={cn(
                  'flex h-10 w-10 items-center justify-center rounded-xl flex-shrink-0',
                  audit.audit_type === 'rgpd' ? 'bg-blue-100' : 'bg-orange-100',
                )}>
                  <ShieldCheck className={cn('h-5 w-5', audit.audit_type === 'rgpd' ? 'text-blue-700' : 'text-orange-700')} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{audit.audit_type.toUpperCase()}</p>
                  <p className="text-xs text-muted-foreground">
                    {new Date(audit.created_at).toLocaleDateString('fr-FR')}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-lg font-bold ${getScoreColor(audit.score)}`}>{audit.score}/100</span>
                  <Badge variant={audit.score >= 70 ? 'success' : audit.score >= 40 ? 'warning' : 'danger'}>
                    {getScoreLabel(audit.score)}
                  </Badge>
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
