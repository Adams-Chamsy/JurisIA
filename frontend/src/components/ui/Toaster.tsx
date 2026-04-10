'use client';

import * as React from 'react';
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react';
import { cn } from '@/lib/utils';

// ── Types ─────────────────────────────────────────────────────────────────────

type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
}

interface ToastContextValue {
  toasts: Toast[];
  toast: (opts: Omit<Toast, 'id'>) => void;
  success: (title: string, message?: string) => void;
  error:   (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
  info:    (title: string, message?: string) => void;
  dismiss: (id: string) => void;
}

// ── Context ───────────────────────────────────────────────────────────────────

const ToastContext = React.createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<Toast[]>([]);

  const dismiss = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = React.useCallback((opts: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).slice(2);
    const duration = opts.duration ?? 4000;
    setToasts((prev) => [...prev.slice(-4), { ...opts, id }]); // Max 5 toasts
    if (duration > 0) {
      setTimeout(() => dismiss(id), duration);
    }
  }, [dismiss]);

  const success = React.useCallback((title: string, message?: string) => toast({ type: 'success', title, message }), [toast]);
  const error   = React.useCallback((title: string, message?: string) => toast({ type: 'error', title, message, duration: 6000 }), [toast]);
  const warning = React.useCallback((title: string, message?: string) => toast({ type: 'warning', title, message }), [toast]);
  const info    = React.useCallback((title: string, message?: string) => toast({ type: 'info', title, message }), [toast]);

  return (
    <ToastContext.Provider value={{ toasts, toast, success, error, warning, info, dismiss }}>
      {children}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = React.useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

// ── Composant Toaster ─────────────────────────────────────────────────────────

const ICONS: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle  className="h-5 w-5 text-green-600" />,
  error:   <XCircle      className="h-5 w-5 text-red-600" />,
  warning: <AlertTriangle className="h-5 w-5 text-amber-600" />,
  info:    <Info          className="h-5 w-5 text-blue-600" />,
};

const STYLES: Record<ToastType, string> = {
  success: 'border-green-200 bg-green-50',
  error:   'border-red-200 bg-red-50',
  warning: 'border-amber-200 bg-amber-50',
  info:    'border-blue-200 bg-blue-50',
};

export function Toaster() {
  const [toasts, setToasts] = React.useState<Toast[]>([]);

  // On utilise un event system simple pour ne pas avoir besoin du context dans le Toaster
  React.useEffect(() => {
    const handler = (e: CustomEvent<Toast>) => {
      setToasts((prev) => [...prev.slice(-4), e.detail]);
      if ((e.detail.duration ?? 4000) > 0) {
        setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== e.detail.id));
        }, e.detail.duration ?? 4000);
      }
    };
    window.addEventListener('jurisai:toast', handler as EventListener);
    return () => window.removeEventListener('jurisai:toast', handler as EventListener);
  }, []);

  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80"
      role="region"
      aria-label="Notifications"
      aria-live="polite"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            'flex items-start gap-3 rounded-xl border p-4 shadow-lg',
            'animate-slide-in-right',
            STYLES[t.type],
          )}
          role="alert"
        >
          <span aria-hidden="true">{ICONS[t.type]}</span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-foreground">{t.title}</p>
            {t.message && <p className="text-xs text-muted-foreground mt-0.5">{t.message}</p>}
          </div>
          <button
            onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
            className="text-muted-foreground hover:text-foreground transition-colors flex-shrink-0"
            aria-label="Fermer la notification"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}

// ── Helper global (utilisable sans context) ───────────────────────────────────

export const toast = {
  success: (title: string, message?: string) =>
    window.dispatchEvent(new CustomEvent('jurisai:toast', { detail: { id: Date.now().toString(), type: 'success', title, message } })),
  error:   (title: string, message?: string) =>
    window.dispatchEvent(new CustomEvent('jurisai:toast', { detail: { id: Date.now().toString(), type: 'error', title, message, duration: 6000 } })),
  warning: (title: string, message?: string) =>
    window.dispatchEvent(new CustomEvent('jurisai:toast', { detail: { id: Date.now().toString(), type: 'warning', title, message } })),
  info:    (title: string, message?: string) =>
    window.dispatchEvent(new CustomEvent('jurisai:toast', { detail: { id: Date.now().toString(), type: 'info', title, message } })),
};
