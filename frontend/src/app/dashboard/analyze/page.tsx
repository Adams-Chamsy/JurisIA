'use client';

/**
 * JurisIA — Page d'Analyse de Documents
 * Upload drag & drop → analyse IA → affichage résultats avec clauses.
 */

import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import {
  Upload, FileText, CheckCircle, AlertTriangle, XCircle,
  AlertCircle, Download, RefreshCw, ExternalLink, ChevronDown, ChevronUp
} from 'lucide-react';
import { Button, Badge, Card, Skeleton, Spinner } from '@/components/ui/index';
import { toast } from '@/components/ui/Toaster';
import { apiUpload, apiGet } from '@/services/api';
import { cn, formatDate, getScoreColor, getScoreBg, getScoreLabel } from '@/lib/utils';

// ── Types ─────────────────────────────────────────────────────────────────────
interface DocumentStatus {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  score: number | null;
  error_message: string | null;
}

interface Clause {
  id: string;
  clause_text: string;
  risk_level: 'danger' | 'warning' | 'safe' | 'missing';
  explanation: string;
  suggestion: string | null;
  legal_reference: string | null;
  legal_reference_url: string | null;
}

interface DocumentDetail {
  id: string;
  title: string;
  status: string;
  score: number | null;
  created_at: string;
  analysis_result: {
    summary: string;
    risk_counts: Record<string, number>;
  } | null;
  clauses: Clause[];
}

// ── Clause Row ────────────────────────────────────────────────────────────────
function ClauseRow({ clause }: { clause: Clause }) {
  const [expanded, setExpanded] = useState(clause.risk_level === 'danger');

  const config = {
    danger:  { label: '🔴 Risque élevé',   className: 'risk-danger',  icon: XCircle },
    warning: { label: '🟡 Avertissement',  className: 'risk-warning', icon: AlertTriangle },
    safe:    { label: '✅ Conforme',       className: 'risk-safe',    icon: CheckCircle },
    missing: { label: '⚠️ Clause manquante', className: 'risk-missing', icon: AlertCircle },
  }[clause.risk_level];

  const Icon = config.icon;

  return (
    <div className={cn('rounded-lg border p-4', config.className)}>
      <button
        className="w-full flex items-center justify-between gap-3 text-left"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <div className="flex items-center gap-3 min-w-0">
          <Icon className="h-4 w-4 flex-shrink-0" aria-hidden="true" />
          <span className="text-xs font-semibold uppercase tracking-wide">{config.label}</span>
          <span className="text-xs text-foreground/70 truncate hidden sm:block">
            {clause.clause_text.slice(0, 80)}…
          </span>
        </div>
        {expanded
          ? <ChevronUp  className="h-4 w-4 flex-shrink-0 opacity-50" />
          : <ChevronDown className="h-4 w-4 flex-shrink-0 opacity-50" />}
      </button>

      {expanded && (
        <div className="mt-3 space-y-3 pt-3 border-t border-current/10">
          {/* Texte de la clause */}
          <div>
            <p className="text-2xs font-semibold uppercase tracking-wide opacity-60 mb-1">Clause identifiée</p>
            <p className="text-sm italic opacity-80">"{clause.clause_text}"</p>
          </div>

          {/* Explication */}
          <div>
            <p className="text-2xs font-semibold uppercase tracking-wide opacity-60 mb-1">Explication</p>
            <p className="text-sm">{clause.explanation}</p>
          </div>

          {/* Suggestion */}
          {clause.suggestion && (
            <div className="rounded-md bg-white/40 p-3">
              <p className="text-2xs font-semibold uppercase tracking-wide opacity-60 mb-1">💡 Recommandation</p>
              <p className="text-sm font-medium">{clause.suggestion}</p>
            </div>
          )}

          {/* Référence légale */}
          {clause.legal_reference && (
            <div className="flex items-center gap-2">
              <span className="text-xs opacity-60">📖</span>
              {clause.legal_reference_url ? (
                <a
                  href={clause.legal_reference_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs font-medium underline underline-offset-2 hover:opacity-80 flex items-center gap-1"
                >
                  {clause.legal_reference}
                  <ExternalLink className="h-3 w-3" aria-hidden="true" />
                </a>
              ) : (
                <span className="text-xs">{clause.legal_reference}</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Page Principale ───────────────────────────────────────────────────────────
export default function AnalyzePage() {
  const [documentId, setDocumentId]   = useState<string | null>(null);
  const [polling,    setPolling]      = useState(false);
  const queryClient                   = useQueryClient();

  // Mutation upload
  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return apiUpload<DocumentStatus>('/documents/analyze', form);
    },
    onSuccess: (data) => {
      setDocumentId(data.id);
      setPolling(true);
      toast.info('Analyse lancée', 'Votre document est en cours d\'analyse (environ 30–60 secondes)…');
    },
    onError: (err: Error) => {
      toast.error('Erreur d\'upload', err.message);
    },
  });

  // Polling du statut (toutes les 3 secondes tant que pending/processing)
  const { data: statusData } = useQuery({
    queryKey: ['document-status', documentId],
    queryFn:  () => apiGet<DocumentStatus>(`/documents/${documentId}/status`),
    enabled:  !!documentId && polling,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === 'completed' || status === 'failed') {
        setPolling(false);
        if (status === 'completed') {
          toast.success('Analyse terminée !', 'Consultez les résultats ci-dessous.');
          queryClient.invalidateQueries({ queryKey: ['documents'] });
        }
        return false;
      }
      return 3000;
    },
  });

  // Chargement du document complet une fois terminé
  const { data: documentDetail, isLoading: detailLoading } = useQuery({
    queryKey: ['document-detail', documentId],
    queryFn:  () => apiGet<DocumentDetail>(`/documents/${documentId}`),
    enabled:  statusData?.status === 'completed',
  });

  // Dropzone
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      setDocumentId(null);
      uploadMutation.mutate(acceptedFiles[0]);
    }
  }, [uploadMutation]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
    },
    maxSize: 20 * 1024 * 1024,
    multiple: false,
    onDropRejected: (files) => {
      const err = files[0]?.errors[0];
      toast.error(
        'Fichier refusé',
        err?.code === 'file-too-large' ? 'Taille maximale : 20 Mo' : 'Format non supporté (PDF, DOCX, TXT uniquement)',
      );
    },
  });

  const currentStatus = statusData?.status ?? uploadMutation.data?.status;
  const isProcessing  = uploadMutation.isPending || currentStatus === 'pending' || currentStatus === 'processing';
  const doc           = documentDetail;

  return (
    <div className="space-y-6 max-w-4xl">
      {/* En-tête */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Analyser un document</h1>
        <p className="text-muted-foreground mt-1">
          Uploadez un contrat, des CGV ou tout document juridique — l'IA identifie les clauses à risque en moins d'une minute.
        </p>
      </div>

      {/* Zone d'upload */}
      {!documentId && (
        <div
          {...getRootProps()}
          className={cn(
            'rounded-xl border-2 border-dashed p-12 text-center cursor-pointer',
            'transition-all duration-150',
            isDragActive
              ? 'border-brand-electric bg-blue-50'
              : 'border-border hover:border-brand-electric/50 hover:bg-muted/30',
            uploadMutation.isPending && 'pointer-events-none opacity-60',
          )}
          role="button"
          aria-label="Zone de dépôt de fichier"
          tabIndex={0}
        >
          <input {...getInputProps()} aria-label="Sélectionner un fichier" />
          <div className="flex flex-col items-center gap-3">
            {uploadMutation.isPending ? (
              <Spinner size="lg" />
            ) : (
              <div className={cn(
                'flex h-16 w-16 items-center justify-center rounded-2xl transition-colors',
                isDragActive ? 'bg-brand-electric' : 'bg-muted',
              )}>
                <Upload className={cn('h-7 w-7', isDragActive ? 'text-white' : 'text-muted-foreground')} aria-hidden="true" />
              </div>
            )}
            <div>
              <p className="text-base font-semibold text-foreground">
                {isDragActive ? 'Déposez votre fichier ici' : 'Glissez votre document ou cliquez'}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                PDF, DOCX, TXT — max 20 Mo
              </p>
            </div>
            {!isDragActive && !uploadMutation.isPending && (
              <Button variant="secondary" size="sm" type="button">
                Parcourir les fichiers
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Statut du traitement */}
      {isProcessing && documentId && (
        <Card className="border-blue-200 bg-blue-50">
          <div className="flex items-center gap-4">
            <Spinner size="md" />
            <div>
              <p className="font-semibold text-blue-900">Analyse en cours…</p>
              <p className="text-sm text-blue-700 mt-0.5">
                Lecture du document → identification des clauses → analyse juridique → finalisation
              </p>
            </div>
          </div>
          {/* Barre de progression animée */}
          <div className="mt-4 h-2 rounded-full bg-blue-200 overflow-hidden">
            <div className="h-full bg-brand-electric rounded-full animate-[shimmer_2s_linear_infinite] w-3/4" />
          </div>
        </Card>
      )}

      {/* Erreur */}
      {currentStatus === 'failed' && (
        <Card className="border-red-200 bg-red-50">
          <div className="flex items-center gap-3">
            <XCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
            <div>
              <p className="font-semibold text-red-900">Analyse échouée</p>
              <p className="text-sm text-red-700 mt-0.5">
                {statusData?.error_message || 'Une erreur s\'est produite lors de l\'analyse.'}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="mt-3"
            onClick={() => { setDocumentId(null); setPolling(false); }}
            leftIcon={<RefreshCw className="h-4 w-4" />}
          >
            Réessayer
          </Button>
        </Card>
      )}

      {/* Résultats */}
      {doc && doc.status === 'completed' && (
        <div className="space-y-6 animate-fade-in">
          {/* Score global */}
          <Card className={cn('border', doc.score !== null ? getScoreBg(doc.score) : '')}>
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Score de solidité juridique</p>
                <div className="flex items-center gap-3 mt-1">
                  <span className={`text-4xl font-bold ${doc.score !== null ? getScoreColor(doc.score) : ''}`}>
                    {doc.score ?? '—'}<span className="text-xl font-normal text-muted-foreground">/100</span>
                  </span>
                  {doc.score !== null && (
                    <Badge variant={doc.score >= 70 ? 'success' : doc.score >= 40 ? 'warning' : 'danger'}>
                      {getScoreLabel(doc.score)}
                    </Badge>
                  )}
                </div>
              </div>
              {/* Compteurs */}
              <div className="flex gap-6">
                {[
                  { label: 'Danger',     count: doc.analysis_result?.risk_counts?.danger  ?? 0, color: 'text-red-600' },
                  { label: 'Attention',  count: doc.analysis_result?.risk_counts?.warning ?? 0, color: 'text-amber-600' },
                  { label: 'Conformes',  count: doc.analysis_result?.risk_counts?.safe    ?? 0, color: 'text-green-600' },
                  { label: 'Manquantes', count: doc.analysis_result?.risk_counts?.missing ?? 0, color: 'text-orange-600' },
                ].map(({ label, count, color }) => (
                  <div key={label} className="text-center">
                    <p className={`text-2xl font-bold ${color}`}>{count}</p>
                    <p className="text-xs text-muted-foreground">{label}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Résumé */}
            {doc.analysis_result?.summary && (
              <p className="mt-4 text-sm text-foreground/80 border-t border-current/10 pt-4">
                {doc.analysis_result.summary}
              </p>
            )}
          </Card>

          {/* Actions */}
          <div className="flex flex-wrap gap-3">
            <a href={`/api/v1/documents/${doc.id}/download?format=pdf`} download>
              <Button variant="secondary" leftIcon={<Download className="h-4 w-4" />}>
                Télécharger le rapport PDF
              </Button>
            </a>
            <Button
              variant="outline"
              onClick={() => { setDocumentId(null); setPolling(false); }}
              leftIcon={<Upload className="h-4 w-4" />}
            >
              Analyser un autre document
            </Button>
          </div>

          {/* Clauses */}
          <div>
            <h2 className="text-lg font-semibold text-foreground mb-4">
              Analyse clause par clause ({doc.clauses.length})
            </h2>

            {/* Filtres */}
            <FilteredClauses clauses={doc.clauses} />
          </div>
        </div>
      )}
    </div>
  );
}

// ── Clauses avec filtres ──────────────────────────────────────────────────────
function FilteredClauses({ clauses }: { clauses: Clause[] }) {
  const [filter, setFilter] = useState<string>('all');

  const levels = ['all', 'danger', 'missing', 'warning', 'safe'];
  const labels = { all: 'Toutes', danger: '🔴 Danger', missing: '⚠️ Manquantes', warning: '🟡 Attention', safe: '✅ Conformes' };

  const filtered = filter === 'all' ? clauses : clauses.filter((c) => c.risk_level === filter);
  // Trier par risque décroissant
  const ORDER: Record<string, number> = { danger: 0, missing: 1, warning: 2, safe: 3 };
  const sorted = [...filtered].sort((a, b) => (ORDER[a.risk_level] ?? 4) - (ORDER[b.risk_level] ?? 4));

  return (
    <div className="space-y-3">
      {/* Filtres */}
      <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrer les clauses">
        {levels.map((lvl) => {
          const count = lvl === 'all' ? clauses.length : clauses.filter((c) => c.risk_level === lvl).length;
          return (
            <button
              key={lvl}
              onClick={() => setFilter(lvl)}
              className={cn(
                'rounded-lg px-3 py-1.5 text-xs font-medium transition-colors border',
                filter === lvl
                  ? 'bg-foreground text-background border-foreground'
                  : 'bg-background text-muted-foreground border-border hover:border-foreground/30',
              )}
              aria-pressed={filter === lvl}
            >
              {labels[lvl as keyof typeof labels]} ({count})
            </button>
          );
        })}
      </div>

      {/* Liste */}
      <div className="space-y-2">
        {sorted.map((clause) => (
          <ClauseRow key={clause.id} clause={clause} />
        ))}
        {sorted.length === 0 && (
          <p className="text-center text-sm text-muted-foreground py-8">
            Aucune clause dans cette catégorie.
          </p>
        )}
      </div>
    </div>
  );
}
