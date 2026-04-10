'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { FileSearch, FilePlus2, MessageSquare, ShieldCheck, AlertTriangle, TrendingUp, Clock, FileText } from 'lucide-react';
import { Button, Card, Badge, Skeleton } from '@/components/ui/index';
import { useUser, useOrganization, usePlan } from '@/store/auth.store';
import { apiGet } from '@/services/api';
import { formatDate, getScoreColor, getScoreLabel } from '@/lib/utils';

// ── Types ─────────────────────────────────────────────────────────────────────
interface DocumentSummary {
  id: string;
  title: string;
  doc_type: 'analysis' | 'generated';
  status: string;
  score: number | null;
  created_at: string;
}

interface SubscriptionStatus {
  plan: string;
  usage: { documents_analyzed: number; documents_generated: number; questions_asked: number };
  limits: { documents_analyzed: number; documents_generated: number; questions_asked: number };
}

// ── Composant QuickAction ─────────────────────────────────────────────────────
function QuickActionCard({ href, icon: Icon, title, description, badge, color }: {
  href:        string;
  icon:        React.ElementType;
  title:       string;
  description: string;
  badge?:      string;
  color:       string;
}) {
  return (
    <Link href={href}>
      <Card className="group card-interactive h-full border-border hover:border-brand-electric/40 transition-all">
        <div className="flex items-start gap-4">
          <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${color} flex-shrink-0`}>
            <Icon className="h-5 w-5 text-white" aria-hidden="true" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-foreground group-hover:text-brand-electric transition-colors">
                {title}
              </h3>
              {badge && (
                <Badge variant="default" className="text-2xs">{badge}</Badge>
              )}
            </div>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        </div>
      </Card>
    </Link>
  );
}

// ── Composant DocRow ──────────────────────────────────────────────────────────
function DocumentRow({ doc }: { doc: DocumentSummary }) {
  const isAnalysis = doc.doc_type === 'analysis';

  return (
    <Link
      href={`/dashboard/${isAnalysis ? 'analyze' : 'generate'}/${doc.id}`}
      className="flex items-center gap-4 py-3 px-4 hover:bg-muted/50 rounded-lg transition-colors group"
    >
      <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg ${isAnalysis ? 'bg-blue-100' : 'bg-purple-100'}`}>
        {isAnalysis
          ? <FileSearch className="h-4 w-4 text-blue-700" />
          : <FilePlus2  className="h-4 w-4 text-purple-700" />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground truncate group-hover:text-brand-electric transition-colors">
          {doc.title}
        </p>
        <p className="text-xs text-muted-foreground">{formatDate(doc.created_at)}</p>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {doc.status === 'completed' && doc.score !== null && (
          <span className={`text-sm font-bold ${getScoreColor(doc.score)}`}>
            {doc.score}/100
          </span>
        )}
        {doc.status === 'processing' && (
          <Badge variant="warning" className="text-2xs gap-1">
            <Clock className="h-3 w-3" /> En cours
          </Badge>
        )}
        {doc.status === 'completed' && doc.score === null && (
          <Badge variant="success" className="text-2xs">Généré</Badge>
        )}
      </div>
    </Link>
  );
}

// ── Page Dashboard ────────────────────────────────────────────────────────────
export default function DashboardPage() {
  const user = useUser();
  const org  = useOrganization();
  const plan = usePlan();

  // Récupérer les documents récents
  const { data: docsData, isLoading: docsLoading } = useQuery({
    queryKey: ['documents', 'recent'],
    queryFn: () => apiGet<{ items: DocumentSummary[] }>('/documents?page=1&page_size=5'),
  });

  // Récupérer l'état de l'abonnement et des quotas
  const { data: subData, isLoading: subLoading } = useQuery({
    queryKey: ['billing', 'subscription'],
    queryFn: () => apiGet<SubscriptionStatus>('/billing/subscription'),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Bonjour';
    if (h < 18) return 'Bon après-midi';
    return 'Bonsoir';
  };

  return (
    <div className="space-y-8">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            {greeting()}, {user?.full_name?.split(' ')[0]} 👋
          </h1>
          <p className="text-muted-foreground mt-1">
            {org?.name} · Plan <span className="capitalize font-medium text-foreground">{plan}</span>
          </p>
        </div>
        {/* Alerte urgente si plan Free proche des limites */}
        {plan === 'free' && (
          <div className="flex items-center gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 flex-shrink-0" aria-hidden="true" />
            <p className="text-xs text-amber-700 font-medium">
              Plan gratuit ·{' '}
              <Link href="/dashboard/billing" className="underline">Passer à Pro</Link>
            </p>
          </div>
        )}
      </div>

      {/* Quotas */}
      {subData && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Documents analysés',  used: subData.usage.documents_analyzed,  limit: subData.limits.documents_analyzed },
            { label: 'Documents générés',   used: subData.usage.documents_generated, limit: subData.limits.documents_generated },
            { label: 'Questions posées',    used: subData.usage.questions_asked,     limit: subData.limits.questions_asked },
          ].map(({ label, used, limit }) => {
            const pct   = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
            const color = pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-amber-500' : 'bg-brand-electric';
            return (
              <Card key={label} className="p-4">
                <p className="text-xs text-muted-foreground mb-1">{label}</p>
                <p className="text-lg font-bold text-foreground">
                  {used}
                  {limit < 9999 && <span className="text-sm font-normal text-muted-foreground">/{limit}</span>}
                </p>
                {limit < 9999 && (
                  <div className="mt-2 h-1.5 rounded-full bg-muted overflow-hidden" aria-hidden="true">
                    <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* Actions rapides */}
      <section>
        <h2 className="text-base font-semibold text-foreground mb-4">Actions rapides</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <QuickActionCard
            href="/dashboard/analyze"
            icon={FileSearch}
            title="Analyser un contrat"
            description="Upload un PDF et obtenez l'analyse en 60s"
            color="bg-blue-600"
          />
          <QuickActionCard
            href="/dashboard/generate"
            icon={FilePlus2}
            title="Générer un document"
            description="8 types de documents juridiques disponibles"
            badge="8 templates"
            color="bg-purple-600"
          />
          <QuickActionCard
            href="/dashboard/chat"
            icon={MessageSquare}
            title="Poser une question"
            description="Assistant IA juridique disponible 24h/24"
            color="bg-green-600"
          />
          <QuickActionCard
            href="/dashboard/compliance"
            icon={ShieldCheck}
            title="Audit conformité"
            description="RGPD et AI Act — évaluez votre conformité"
            badge="Aug. 2026"
            color="bg-orange-600"
          />
        </div>
      </section>

      {/* Documents récents */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-foreground">Documents récents</h2>
          <Link href="/dashboard/documents" className="text-sm text-brand-electric hover:underline">
            Voir tout →
          </Link>
        </div>

        <Card className="p-0 overflow-hidden">
          {docsLoading ? (
            <div className="p-4 space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex items-center gap-4">
                  <Skeleton className="h-9 w-9 rounded-lg" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-3 w-48" />
                    <Skeleton className="h-2 w-24" />
                  </div>
                  <Skeleton className="h-5 w-12" />
                </div>
              ))}
            </div>
          ) : docsData?.items?.length ? (
            <div>
              {docsData.items.map((doc) => (
                <DocumentRow key={doc.id} doc={doc} />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <FileText className="h-12 w-12 text-muted-foreground/30 mb-3" aria-hidden="true" />
              <p className="text-sm font-medium text-muted-foreground">Aucun document pour le moment</p>
              <p className="text-xs text-muted-foreground mt-1">Commencez par analyser un contrat</p>
              <Button size="sm" className="mt-4" asChild>
                <Link href="/dashboard/analyze">Analyser mon premier document</Link>
              </Button>
            </div>
          )}
        </Card>
      </section>

      {/* Alerte réglementaire AI Act */}
      <section>
        <Card className="border-amber-200 bg-amber-50">
          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-amber-500">
              <AlertTriangle className="h-5 w-5 text-white" aria-hidden="true" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-amber-900">⚡ AI Act : obligations en vigueur août 2026</h3>
              <p className="text-sm text-amber-700 mt-1">
                Si votre entreprise utilise des outils IA (ChatGPT, outils de scoring, etc.), 
                vous avez des obligations déclaratives à remplir avant août 2026.
              </p>
              <Button variant="outline" size="sm" className="mt-3 border-amber-300 text-amber-800 hover:bg-amber-100" asChild>
                <Link href="/dashboard/compliance">Évaluer ma conformité →</Link>
              </Button>
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
}
