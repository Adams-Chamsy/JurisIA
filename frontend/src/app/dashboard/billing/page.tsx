'use client';

/**
 * JurisIA — Page Facturation & Abonnements
 * Affichage des plans, usage actuel et redirection vers Stripe Checkout/Portal.
 */

import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Check, Crown, Zap, Building2, ExternalLink, Loader2 } from 'lucide-react';
import { Button, Badge, Card, Skeleton } from '@/components/ui/index';
import { toast } from '@/components/ui/Toaster';
import { apiGet, apiPost } from '@/services/api';
import { useSubscription } from '@/store/auth.store';
import { cn } from '@/lib/utils';

// ── Plans ─────────────────────────────────────────────────────────────────────

const PLANS = [
  {
    key:         'starter' as const,
    name:        'Starter',
    price:       79,
    priceAnnual: 790,
    description: 'Pour les freelances et micro-entreprises',
    icon:        Zap,
    color:       'text-blue-600',
    bgColor:     'bg-blue-50',
    borderColor: 'border-blue-200',
    features: [
      '20 documents/mois (analyse + génération)',
      '50 questions juridiques/mois',
      'Tous les templates de base (contrats, CGV, NDA)',
      'Veille réglementaire basique',
      'Export PDF',
      'Support par email',
    ],
    notIncluded: ['Audit RGPD complet', 'Module AI Act', 'Utilisateurs multiples'],
  },
  {
    key:         'pro' as const,
    name:        'Pro',
    price:       149,
    priceAnnual: 1490,
    description: 'Pour les PME et ETI jusqu\'à 50 salariés',
    icon:        Crown,
    color:       'text-purple-600',
    bgColor:     'bg-purple-50',
    borderColor: 'border-purple-300',
    featured:    true,
    badge:       'Le plus populaire',
    features: [
      'Documents illimités',
      'Questions illimitées',
      'Tous les templates (dont RH : CDI, rupture conv…)',
      'Audit RGPD complet + plan d\'action',
      'Signature électronique (5/mois)',
      'Veille réglementaire complète',
      '2 utilisateurs',
      'Support prioritaire',
    ],
    notIncluded: ['Module AI Act', 'API partenaires'],
  },
  {
    key:         'business' as const,
    name:        'Business',
    price:       299,
    priceAnnual: 2990,
    description: 'Pour les PME/ETI avec enjeux compliance avancés',
    icon:        Building2,
    color:       'text-amber-600',
    bgColor:     'bg-amber-50',
    borderColor: 'border-amber-200',
    features: [
      'Tout le plan Pro, plus :',
      'Module AI Act complet (audit + documentation)',
      'Signature électronique (20/mois)',
      '5 utilisateurs',
      'Accès API partenaires (beta)',
      'Tableau de bord équipe',
      'Support dédié + accès avocat partenaire',
    ],
    notIncluded: [],
  },
];

interface CheckoutResponse { checkout_url: string; }
interface PortalResponse   { portal_url:   string; }
interface SubStatus {
  plan:                string;
  status:              string;
  current_period_end?: string;
  cancel_at_period_end: boolean;
  usage: {
    documents_analyzed:  number;
    documents_generated: number;
    questions_asked:     number;
  };
  limits: {
    documents_analyzed:  number;
    documents_generated: number;
    questions_asked:     number;
  };
}

// ── Composant Plan Card ───────────────────────────────────────────────────────

function PlanCard({
  plan, isCurrentPlan, isAnnual, onSelect, isLoading,
}: {
  plan:          typeof PLANS[0];
  isCurrentPlan: boolean;
  isAnnual:      boolean;
  onSelect:      () => void;
  isLoading:     boolean;
}) {
  const Icon  = plan.icon;
  const price = isAnnual ? Math.floor(plan.priceAnnual / 12) : plan.price;

  return (
    <div className={cn(
      'relative rounded-2xl border-2 p-6 flex flex-col',
      plan.featured ? plan.borderColor + ' shadow-lg' : 'border-border',
      isCurrentPlan && 'ring-2 ring-brand-electric ring-offset-2',
    )}>
      {/* Badge "populaire" */}
      {plan.featured && (
        <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
          <span className="rounded-full bg-purple-600 px-4 py-1 text-xs font-bold text-white shadow">
            {plan.badge}
          </span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className={cn('flex h-10 w-10 items-center justify-center rounded-xl', plan.bgColor)}>
          <Icon className={cn('h-5 w-5', plan.color)} aria-hidden="true" />
        </div>
        <div>
          <h3 className="font-bold text-foreground">{plan.name}</h3>
          {isCurrentPlan && (
            <Badge variant="success" className="text-2xs">Plan actuel</Badge>
          )}
        </div>
      </div>

      {/* Prix */}
      <div className="mb-4">
        <div className="flex items-baseline gap-1">
          <span className="text-4xl font-extrabold text-foreground">{price}€</span>
          <span className="text-muted-foreground">/mois</span>
        </div>
        {isAnnual && (
          <p className="text-xs text-green-600 mt-0.5 font-medium">
            Soit {plan.priceAnnual}€/an — 2 mois offerts !
          </p>
        )}
        <p className="text-xs text-muted-foreground mt-1">{plan.description}</p>
      </div>

      {/* Features incluses */}
      <ul className="space-y-2 flex-1" role="list">
        {plan.features.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm">
            <Check className="h-4 w-4 text-green-600 flex-shrink-0 mt-0.5" aria-hidden="true" />
            <span className={f.startsWith('Tout le') ? 'font-medium text-foreground' : 'text-foreground/80'}>{f}</span>
          </li>
        ))}
        {plan.notIncluded.map((f) => (
          <li key={f} className="flex items-start gap-2 text-sm text-muted-foreground/50">
            <span className="h-4 w-4 flex-shrink-0 text-center text-xs mt-0.5" aria-hidden="true">—</span>
            <span className="line-through">{f}</span>
          </li>
        ))}
      </ul>

      {/* CTA */}
      <div className="mt-6">
        {isCurrentPlan ? (
          <Button variant="secondary" className="w-full" disabled>
            Plan actuel
          </Button>
        ) : (
          <Button
            onClick={onSelect}
            isLoading={isLoading}
            variant={plan.featured ? 'primary' : 'outline'}
            className="w-full"
          >
            {isLoading ? 'Redirection…' : `Passer à ${plan.name}`}
          </Button>
        )}
      </div>
    </div>
  );
}

// ── Page Principale ───────────────────────────────────────────────────────────

export default function BillingPage() {
  const subscription = useSubscription();
  const [isAnnual, setIsAnnual] = useState(false);
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null);

  // État complet de l'abonnement + usage
  const { data: subStatus, isLoading: subLoading } = useQuery({
    queryKey: ['billing', 'subscription'],
    queryFn:  () => apiGet<SubStatus>('/billing/subscription'),
  });

  // Ouvrir le portail Stripe
  const portalMutation = useMutation({
    mutationFn: () => apiPost<PortalResponse>('/billing/portal'),
    onSuccess:  (data) => window.open(data.portal_url, '_blank'),
    onError:    (err: Error) => toast.error('Erreur', err.message),
  });

  // Créer un checkout Stripe
  const checkoutMutation = useMutation({
    mutationFn: (plan: string) =>
      apiPost<CheckoutResponse>('/billing/checkout', { plan }),
    onSuccess: (data) => { window.location.href = data.checkout_url; },
    onError:   (err: Error) => { toast.error('Erreur paiement', err.message); setLoadingPlan(null); },
  });

  const currentPlan = subStatus?.plan ?? subscription?.plan ?? 'free';

  const handleSelectPlan = (planKey: string) => {
    setLoadingPlan(planKey);
    checkoutMutation.mutate(planKey);
  };

  return (
    <div className="space-y-8">

      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Abonnement & Facturation</h1>
          <p className="text-muted-foreground mt-1">
            Gérez votre plan et suivez votre utilisation mensuelle.
          </p>
        </div>
        {currentPlan !== 'free' && (
          <Button
            variant="secondary"
            isLoading={portalMutation.isPending}
            onClick={() => portalMutation.mutate()}
            rightIcon={<ExternalLink className="h-3.5 w-3.5" />}
          >
            Gérer ma facturation
          </Button>
        )}
      </div>

      {/* Usage actuel */}
      {subLoading ? (
        <div className="grid grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
        </div>
      ) : subStatus && (
        <Card>
          <h2 className="text-sm font-semibold text-foreground mb-4">Utilisation ce mois</h2>
          <div className="grid sm:grid-cols-3 gap-6">
            {[
              { label: 'Documents analysés',  used: subStatus.usage.documents_analyzed,  limit: subStatus.limits.documents_analyzed },
              { label: 'Documents générés',   used: subStatus.usage.documents_generated, limit: subStatus.limits.documents_generated },
              { label: 'Questions posées',    used: subStatus.usage.questions_asked,     limit: subStatus.limits.questions_asked },
            ].map(({ label, used, limit }) => {
              const pct    = limit < 9999 && limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
              const color  = pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-amber-500' : 'bg-brand-electric';
              const isUnlimited = limit >= 9999;
              return (
                <div key={label}>
                  <div className="flex justify-between items-baseline mb-1">
                    <span className="text-xs text-muted-foreground">{label}</span>
                    <span className="text-sm font-bold text-foreground">
                      {used}{isUnlimited ? '' : `/${limit}`}
                    </span>
                  </div>
                  {!isUnlimited ? (
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct}%` }} />
                    </div>
                  ) : (
                    <p className="text-xs text-green-600 font-medium">Illimité ✓</p>
                  )}
                </div>
              );
            })}
          </div>
          {subStatus.current_period_end && (
            <p className="text-xs text-muted-foreground mt-4 pt-4 border-t border-border">
              Prochain renouvellement : {new Date(subStatus.current_period_end).toLocaleDateString('fr-FR')}
              {subStatus.cancel_at_period_end && (
                <span className="ml-2 text-red-600 font-medium">(Résiliation programmée)</span>
              )}
            </p>
          )}
        </Card>
      )}

      {/* Toggle mensuel / annuel */}
      <div className="flex items-center justify-center gap-4">
        <span className={cn('text-sm font-medium', !isAnnual ? 'text-foreground' : 'text-muted-foreground')}>
          Mensuel
        </span>
        <button
          role="switch"
          aria-checked={isAnnual}
          onClick={() => setIsAnnual((v) => !v)}
          className={cn(
            'relative inline-flex h-7 w-12 items-center rounded-full transition-colors',
            isAnnual ? 'bg-brand-electric' : 'bg-muted',
          )}
        >
          <span className={cn(
            'inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform',
            isAnnual ? 'translate-x-6' : 'translate-x-1',
          )} />
        </button>
        <span className={cn('text-sm font-medium flex items-center gap-1.5', isAnnual ? 'text-foreground' : 'text-muted-foreground')}>
          Annuel
          <Badge variant="success" className="text-2xs">-17%</Badge>
        </span>
      </div>

      {/* Plans */}
      <div className="grid sm:grid-cols-3 gap-6">
        {PLANS.map((plan) => (
          <PlanCard
            key={plan.key}
            plan={plan}
            isCurrentPlan={currentPlan === plan.key}
            isAnnual={isAnnual}
            onSelect={() => handleSelectPlan(plan.key)}
            isLoading={loadingPlan === plan.key && checkoutMutation.isPending}
          />
        ))}
      </div>

      {/* Garanties */}
      <div className="grid sm:grid-cols-3 gap-4 text-center text-sm">
        {[
          { emoji: '🔒', title: 'Sans engagement',        desc: 'Résiliez à tout moment, effet immédiat' },
          { emoji: '🇫🇷', title: 'Données en France',     desc: 'Hébergement OVH — RGPD garanti' },
          { emoji: '💳', title: 'Paiement sécurisé',       desc: 'Stripe · Carte bancaire · Virement' },
        ].map(({ emoji, title, desc }) => (
          <div key={title} className="rounded-xl bg-muted/40 p-4">
            <span className="text-2xl" aria-hidden="true">{emoji}</span>
            <p className="font-semibold text-foreground mt-2">{title}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{desc}</p>
          </div>
        ))}
      </div>

      {/* FAQ rapide */}
      <Card>
        <h2 className="font-semibold text-foreground mb-4">Questions fréquentes</h2>
        <div className="space-y-4">
          {[
            {
              q: 'Puis-je changer de plan à tout moment ?',
              a: 'Oui. Les changements de plan sont effectifs immédiatement. En cas de montée en gamme, vous êtes facturé au prorata.',
            },
            {
              q: 'Les documents générés sont-ils juridiquement valides ?',
              a: 'Nos documents sont conformes au droit français en vigueur. Ils constituent une aide à la rédaction. Pour les enjeux critiques (>10K€), consultez un avocat.',
            },
            {
              q: 'Mes données sont-elles protégées ?',
              a: 'Toutes les données sont hébergées en France (OVH), chiffrées en transit et au repos. Nous sommes nativement conformes RGPD.',
            },
          ].map(({ q, a }) => (
            <div key={q}>
              <p className="text-sm font-medium text-foreground">{q}</p>
              <p className="text-sm text-muted-foreground mt-1">{a}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
