'use client';

/**
 * JurisIA — Page de Génération de Documents
 * Catalogue de templates + formulaire guidé étape par étape + polling résultat.
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import {
  FileText, ChevronRight, ChevronLeft, Download,
  Lock, CheckCircle, Loader2, ArrowLeft, RefreshCw,
} from 'lucide-react';
import { Button, Badge, Card, Spinner, Skeleton } from '@/components/ui/index';
import { toast } from '@/components/ui/Toaster';
import { apiGet, apiPost } from '@/services/api';
import { usePlan } from '@/store/auth.store';
import { cn } from '@/lib/utils';

// ── Types ─────────────────────────────────────────────────────────────────────

interface TemplateField {
  key:          string;
  label:        string;
  type:         'text' | 'textarea' | 'select' | 'date' | 'number' | 'boolean';
  required:     boolean;
  placeholder?: string;
  options?:     string[];
}

interface Template {
  key:            string;
  name:           string;
  category:       string;
  description:    string;
  available:      boolean;
  required_plan?: string;
  fields:         TemplateField[];
}

interface TemplatesResponse {
  templates: Template[];
}

interface DocumentStatus {
  id:            string;
  status:        string;
  error_message: string | null;
}

// ── Catégories ────────────────────────────────────────────────────────────────

const CATEGORY_LABELS: Record<string, { label: string; emoji: string; color: string }> = {
  contract: { label: 'Contrats Commerciaux', emoji: '📄', color: 'bg-blue-100 text-blue-800' },
  rh:       { label: 'Ressources Humaines',  emoji: '👥', color: 'bg-purple-100 text-purple-800' },
  recovery: { label: 'Recouvrement',         emoji: '💶', color: 'bg-amber-100 text-amber-800' },
  other:    { label: 'Autres',               emoji: '📋', color: 'bg-gray-100 text-gray-800' },
};

// ── Composant : Template Card ─────────────────────────────────────────────────

function TemplateCard({ template, onSelect }: { template: Template; onSelect: () => void }) {
  const cat = CATEGORY_LABELS[template.category] ?? CATEGORY_LABELS.other;

  return (
    <button
      onClick={template.available ? onSelect : undefined}
      className={cn(
        'group w-full text-left rounded-xl border p-5 transition-all',
        template.available
          ? 'border-border hover:border-brand-electric/50 hover:shadow-card-hover cursor-pointer'
          : 'border-border bg-muted/30 cursor-not-allowed opacity-60',
      )}
      aria-disabled={!template.available}
      aria-label={template.available ? `Générer : ${template.name}` : `${template.name} — Plan requis : ${template.required_plan}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <span className="text-2xl flex-shrink-0" aria-hidden="true">{cat.emoji}</span>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className={cn(
                'font-semibold text-sm text-foreground',
                template.available && 'group-hover:text-brand-electric transition-colors',
              )}>
                {template.name}
              </h3>
              {!template.available && (
                <Badge variant="muted" className="text-2xs gap-1 flex-shrink-0">
                  <Lock className="h-2.5 w-2.5" />
                  Plan {template.required_plan}
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{template.description}</p>
          </div>
        </div>
        {template.available && (
          <ChevronRight
            className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5 group-hover:text-brand-electric transition-colors"
            aria-hidden="true"
          />
        )}
      </div>
      <div className="mt-3">
        <span className={cn('inline-block rounded-full px-2 py-0.5 text-2xs font-medium', cat.color)}>
          {cat.label}
        </span>
      </div>
    </button>
  );
}

// ── Composant : Champ de formulaire ──────────────────────────────────────────

function FormField({
  field, value, onChange,
}: {
  field:    TemplateField;
  value:    string | boolean;
  onChange: (v: string | boolean) => void;
}) {
  const baseClass = cn(
    'w-full rounded-lg border border-input bg-background px-3 py-2 text-sm',
    'focus:outline-none focus:ring-2 focus:ring-ring transition-colors',
    'placeholder:text-muted-foreground',
  );

  const label = (
    <label className="block text-sm font-medium text-foreground mb-1.5">
      {field.label}
      {field.required && <span className="ml-1 text-brand-danger" aria-label="obligatoire">*</span>}
    </label>
  );

  if (field.type === 'boolean') {
    return (
      <div className="flex items-center gap-3">
        <button
          type="button"
          role="switch"
          aria-checked={!!value}
          onClick={() => onChange(!value)}
          className={cn(
            'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
            value ? 'bg-brand-electric' : 'bg-muted',
          )}
        >
          <span className={cn(
            'inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform',
            value ? 'translate-x-6' : 'translate-x-1',
          )} />
        </button>
        <label className="text-sm font-medium text-foreground cursor-pointer" onClick={() => onChange(!value)}>
          {field.label}
          {field.required && <span className="ml-1 text-brand-danger" aria-label="obligatoire">*</span>}
        </label>
      </div>
    );
  }

  if (field.type === 'select') {
    return (
      <div>
        {label}
        <select
          value={String(value)}
          onChange={(e) => onChange(e.target.value)}
          className={baseClass}
          required={field.required}
        >
          <option value="">Sélectionner…</option>
          {field.options?.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      </div>
    );
  }

  if (field.type === 'textarea') {
    return (
      <div>
        {label}
        <textarea
          value={String(value)}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          placeholder={field.placeholder}
          required={field.required}
          className={cn(baseClass, 'resize-none')}
        />
      </div>
    );
  }

  return (
    <div>
      {label}
      <input
        type={field.type}
        value={String(value)}
        onChange={(e) => onChange(e.target.value)}
        placeholder={field.placeholder}
        required={field.required}
        min={field.type === 'number' ? 0 : undefined}
        className={baseClass}
      />
    </div>
  );
}

// ── Page Principale ───────────────────────────────────────────────────────────

export default function GeneratePage() {
  const plan                          = usePlan();
  const queryClient                   = useQueryClient();
  const [selectedTemplate, setTemplate] = useState<Template | null>(null);
  const [formData,         setFormData] = useState<Record<string, string | boolean>>({});
  const [currentStep,      setStep]     = useState(0);     // Étape du wizard
  const [documentId,       setDocId]    = useState<string | null>(null);
  const [polling,          setPolling]  = useState(false);

  // Charger les templates
  const { data, isLoading } = useQuery({
    queryKey: ['templates'],
    queryFn:  () => apiGet<TemplatesResponse>('/documents/templates/list'),
  });

  // Polling du statut après génération
  const { data: statusData } = useQuery({
    queryKey: ['doc-status', documentId],
    queryFn:  () => apiGet<DocumentStatus>(`/documents/${documentId}/status`),
    enabled:  !!documentId && polling,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      if (s === 'completed' || s === 'failed') {
        setPolling(false);
        if (s === 'completed') toast.success('Document généré !', 'Téléchargez-le ci-dessous.');
        else toast.error('Génération échouée', query.state.data?.error_message ?? '');
        return false;
      }
      return 2000;
    },
  });

  // Mutation de génération
  const generateMutation = useMutation({
    mutationFn: () =>
      apiPost<DocumentStatus>('/documents/generate', {
        template_key: selectedTemplate!.key,
        title: selectedTemplate!.name,
        form_data: formData,
      }),
    onSuccess: (data) => {
      setDocId(data.id);
      setPolling(true);
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
    onError: (err: Error) => toast.error('Erreur', err.message),
  });

  // Grouper les templates par catégorie
  const templatesByCategory = (data?.templates ?? []).reduce<Record<string, Template[]>>((acc, t) => {
    const cat = t.category ?? 'other';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(t);
    return acc;
  }, {});

  // Champs de l'étape courante (on en montre 4 par étape)
  const FIELDS_PER_STEP = 4;
  const fields           = selectedTemplate?.fields ?? [];
  const steps            = Math.ceil(fields.length / FIELDS_PER_STEP);
  const currentFields    = fields.slice(currentStep * FIELDS_PER_STEP, (currentStep + 1) * FIELDS_PER_STEP);
  const isLastStep       = currentStep === steps - 1;

  const handleFieldChange = (key: string, value: string | boolean) =>
    setFormData((prev) => ({ ...prev, [key]: value }));

  const handleNext = () => {
    if (isLastStep) generateMutation.mutate();
    else setStep((s) => s + 1);
  };

  const handleBack = () => {
    if (currentStep > 0) setStep((s) => s - 1);
    else { setTemplate(null); setFormData({}); setStep(0); }
  };

  const resetAll = () => {
    setTemplate(null); setFormData({});
    setStep(0); setDocId(null); setPolling(false);
  };

  // ── RÉSULTAT ────────────────────────────────────────────────────────────────
  if (documentId && (statusData?.status === 'completed' || polling)) {
    return (
      <div className="max-w-lg mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Génération de document</h1>
        </div>
        <Card className={cn(
          'text-center py-10',
          statusData?.status === 'completed' ? 'border-green-200' : 'border-blue-200',
        )}>
          {polling && statusData?.status !== 'completed' ? (
            <>
              <Spinner size="lg" className="mx-auto mb-4" />
              <p className="font-semibold text-foreground">Génération en cours…</p>
              <p className="text-sm text-muted-foreground mt-1">
                L'IA rédige votre document. Environ 10–20 secondes.
              </p>
            </>
          ) : (
            <>
              <CheckCircle className="h-14 w-14 text-green-600 mx-auto mb-4" aria-hidden="true" />
              <p className="text-xl font-bold text-foreground">{selectedTemplate?.name}</p>
              <p className="text-sm text-muted-foreground mt-1">Votre document est prêt !</p>
              <div className="flex flex-col sm:flex-row gap-3 justify-center mt-6">
                <a href={`/api/v1/documents/${documentId}/download?format=docx`} download>
                  <Button leftIcon={<Download className="h-4 w-4" />}>
                    Télécharger en DOCX
                  </Button>
                </a>
                <a href={`/api/v1/documents/${documentId}/download?format=pdf`} download>
                  <Button variant="secondary" leftIcon={<Download className="h-4 w-4" />}>
                    Télécharger en PDF
                  </Button>
                </a>
              </div>
              <Button variant="ghost" size="sm" className="mt-4" onClick={resetAll}
                leftIcon={<RefreshCw className="h-3.5 w-3.5" />}>
                Générer un autre document
              </Button>
            </>
          )}
        </Card>
        <p className="text-xs text-muted-foreground text-center bg-amber-50 border border-amber-200 rounded-lg p-3">
          ⚠️ Document généré à titre d'aide à la rédaction. Pour tout enjeu important, consultez un avocat.
        </p>
      </div>
    );
  }

  // ── FORMULAIRE ──────────────────────────────────────────────────────────────
  if (selectedTemplate) {
    return (
      <div className="max-w-xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={handleBack} aria-label="Retour">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-xl font-bold text-foreground">{selectedTemplate.name}</h1>
            <p className="text-sm text-muted-foreground">{selectedTemplate.description}</p>
          </div>
        </div>

        {/* Progress bar */}
        {steps > 1 && (
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>Étape {currentStep + 1} sur {steps}</span>
              <span>{Math.round(((currentStep + 1) / steps) * 100)}%</span>
            </div>
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-electric rounded-full transition-all duration-300"
                style={{ width: `${((currentStep + 1) / steps) * 100}%` }}
                role="progressbar"
                aria-valuenow={currentStep + 1}
                aria-valuemin={1}
                aria-valuemax={steps}
              />
            </div>
          </div>
        )}

        {/* Champs */}
        <Card className="space-y-5">
          {currentFields.map((field) => (
            <FormField
              key={field.key}
              field={field}
              value={formData[field.key] ?? (field.type === 'boolean' ? false : '')}
              onChange={(v) => handleFieldChange(field.key, v)}
            />
          ))}
        </Card>

        {/* Navigation */}
        <div className="flex gap-3">
          <Button variant="secondary" onClick={handleBack} className="flex-1">
            <ChevronLeft className="h-4 w-4 mr-1" />
            {currentStep === 0 ? 'Annuler' : 'Précédent'}
          </Button>
          <Button
            onClick={handleNext}
            isLoading={generateMutation.isPending}
            className="flex-1"
          >
            {isLastStep ? (
              <>Générer le document <ChevronRight className="h-4 w-4 ml-1" /></>
            ) : (
              <>Suivant <ChevronRight className="h-4 w-4 ml-1" /></>
            )}
          </Button>
        </div>

        <p className="text-xs text-muted-foreground text-center">
          🔒 Données traitées et hébergées en France
        </p>
      </div>
    );
  }

  // ── CATALOGUE ───────────────────────────────────────────────────────────────
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Générer un document</h1>
        <p className="text-muted-foreground mt-1">
          Choisissez un type de document — l'IA génère un document personnalisé en moins de 30 secondes.
        </p>
      </div>

      {isLoading ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
        </div>
      ) : (
        Object.entries(templatesByCategory).map(([cat, templates]) => {
          const catInfo = CATEGORY_LABELS[cat] ?? CATEGORY_LABELS.other;
          return (
            <section key={cat}>
              <div className="flex items-center gap-2 mb-4">
                <span className="text-xl" aria-hidden="true">{catInfo.emoji}</span>
                <h2 className="text-base font-semibold text-foreground">{catInfo.label}</h2>
                <span className="text-xs text-muted-foreground">({templates.length})</span>
              </div>
              <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {templates.map((tpl) => (
                  <TemplateCard
                    key={tpl.key}
                    template={tpl}
                    onSelect={() => {
                      setTemplate(tpl);
                      setFormData({});
                      setStep(0);
                    }}
                  />
                ))}
              </div>
            </section>
          );
        })
      )}

      {/* CTA upgrade si plan free */}
      {plan === 'free' && (
        <Card className="border-purple-200 bg-purple-50">
          <div className="flex items-center gap-4">
            <Lock className="h-8 w-8 text-purple-500 flex-shrink-0" aria-hidden="true" />
            <div>
              <p className="font-semibold text-purple-900">Débloquez tous les templates RH</p>
              <p className="text-sm text-purple-700 mt-0.5">
                Contrats CDI, rupture conventionnelle, avertissements… disponibles à partir du plan Pro.
              </p>
            </div>
            <Button variant="navy" size="sm" className="flex-shrink-0 bg-purple-700 hover:bg-purple-800" asChild>
              <Link href="/dashboard/billing">Passer à Pro →</Link>
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
