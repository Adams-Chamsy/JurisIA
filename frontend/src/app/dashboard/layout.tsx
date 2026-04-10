'use client';

/**
 * JurisIA — Layout Dashboard
 * Sidebar de navigation + header + zone de contenu principale.
 * Protège toutes les routes /dashboard/* contre les accès non authentifiés.
 */

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import {
  BarChart3,
  FileSearch,
  FilePlus2,
  MessageSquare,
  ShieldCheck,
  Settings,
  HelpCircle,
  Scale,
  Bell,
  CreditCard,
  LogOut,
  ChevronRight,
  Menu,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Button, Badge } from '@/components/ui/index';
import { useAuthStore, usePlan, useUser } from '@/store/auth.store';
import { Toaster } from '@/components/ui/Toaster';

// ── Navigation Items ──────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { href: '/dashboard',         label: 'Tableau de bord',    icon: BarChart3,    exact: true },
  { href: '/dashboard/analyze', label: 'Analyser',           icon: FileSearch,   badge: 'Nouveau' },
  { href: '/dashboard/generate',label: 'Générer',            icon: FilePlus2 },
  { href: '/dashboard/chat',    label: 'Assistant',          icon: MessageSquare },
  { href: '/dashboard/compliance', label: 'Conformité',      icon: ShieldCheck },
];

const BOTTOM_ITEMS = [
  { href: '/dashboard/billing',  label: 'Abonnement',  icon: CreditCard },
  { href: '/dashboard/settings', label: 'Paramètres',  icon: Settings },
  { href: '/support',            label: 'Support',     icon: HelpCircle, external: true },
];

// ── Sidebar ───────────────────────────────────────────────────────────────────
function Sidebar({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const { logout } = useAuthStore();
  const user       = useUser();
  const plan       = usePlan();
  const router     = useRouter();

  const isActive = (href: string, exact?: boolean) =>
    exact ? pathname === href : pathname.startsWith(href);

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  const planColors: Record<string, string> = {
    free:     'muted',
    starter:  'starter',
    pro:      'pro',
    business: 'business',
  };

  return (
    <>
      {/* Overlay mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-brand-navy',
          'transition-transform duration-250 ease-out',
          'lg:static lg:z-auto lg:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full',
        )}
        aria-label="Navigation principale"
      >
        {/* Header sidebar */}
        <div className="flex items-center justify-between px-5 py-5 border-b border-white/10">
          <Link href="/dashboard" className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10">
              <Scale className="h-5 w-5 text-white" />
            </div>
            <span className="text-lg font-bold text-white">JurisIA</span>
          </Link>
          <button
            onClick={onClose}
            className="lg:hidden text-white/60 hover:text-white"
            aria-label="Fermer le menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Plan badge */}
        <div className="px-4 py-3 border-b border-white/10">
          <div className="flex items-center justify-between">
            <span className="text-xs text-white/50">Plan actuel</span>
            <Badge variant={planColors[plan] as 'muted' | 'starter' | 'pro' | 'business'} className="capitalize">
              {plan}
            </Badge>
          </div>
          {plan === 'free' && (
            <Link href="/dashboard/billing">
              <Button variant="navy" size="sm" className="mt-2 w-full bg-white/10 hover:bg-white/20 text-white border-0">
                Passer à Pro →
              </Button>
            </Link>
          )}
        </div>

        {/* Navigation principale */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1" role="navigation">
          {NAV_ITEMS.map(({ href, label, icon: Icon, exact, badge }) => (
            <Link
              key={href}
              href={href}
              onClick={onClose}
              className={cn(
                'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                isActive(href, exact)
                  ? 'bg-white/15 text-white'
                  : 'text-white/70 hover:bg-white/10 hover:text-white',
              )}
              aria-current={isActive(href, exact) ? 'page' : undefined}
            >
              <Icon className="h-4.5 w-4.5 flex-shrink-0" aria-hidden="true" />
              <span className="flex-1">{label}</span>
              {badge && (
                <span className="rounded-full bg-brand-electric px-1.5 py-0.5 text-2xs font-semibold text-white">
                  {badge}
                </span>
              )}
              <ChevronRight
                className={cn(
                  'h-3.5 w-3.5 transition-opacity',
                  isActive(href, exact) ? 'opacity-60' : 'opacity-0 group-hover:opacity-40',
                )}
                aria-hidden="true"
              />
            </Link>
          ))}
        </nav>

        {/* Navigation secondaire + Profil */}
        <div className="border-t border-white/10 px-3 py-3 space-y-1">
          {BOTTOM_ITEMS.map(({ href, label, icon: Icon, external }) => (
            external ? (
              <a
                key={href}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-white/60 hover:bg-white/10 hover:text-white transition-colors"
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {label}
              </a>
            ) : (
              <Link
                key={href}
                href={href}
                onClick={onClose}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive(href) ? 'bg-white/15 text-white' : 'text-white/60 hover:bg-white/10 hover:text-white',
                )}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {label}
              </Link>
            )
          ))}

          {/* Profil utilisateur */}
          <div className="flex items-center gap-3 px-3 py-2 mt-2 border-t border-white/10 pt-3">
            <div className="h-8 w-8 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0">
              <span className="text-xs font-semibold text-white" aria-hidden="true">
                {user?.full_name?.charAt(0)?.toUpperCase() ?? '?'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-white truncate">{user?.full_name}</p>
              <p className="text-2xs text-white/50 truncate">{user?.email}</p>
            </div>
            <button
              onClick={handleLogout}
              className="text-white/50 hover:text-white transition-colors"
              aria-label="Se déconnecter"
              title="Se déconnecter"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}

// ── Layout Principal ──────────────────────────────────────────────────────────
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router       = useRouter();
  const { isAuthenticated, isLoading } = useAuthStore();
  const [sidebarOpen, setSidebarOpen]  = useState(false);

  // Protection des routes
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, isLoading, router]);

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-electric border-t-transparent" aria-label="Chargement" />
          <p className="text-sm text-muted-foreground">Vérification de l'authentification…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Zone principale */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header mobile */}
        <header className="flex items-center justify-between border-b border-border bg-background px-4 py-3 lg:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="text-foreground"
            aria-label="Ouvrir le menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-2">
            <Scale className="h-5 w-5 text-brand-navy" />
            <span className="font-bold text-brand-navy">JurisIA</span>
          </div>
          <button className="text-muted-foreground" aria-label="Notifications">
            <Bell className="h-5 w-5" />
          </button>
        </header>

        {/* Contenu scrollable */}
        <main className="flex-1 overflow-y-auto" id="main-content">
          <div className="page-container py-6 lg:py-8 animate-fade-in">
            {children}
          </div>
        </main>
      </div>

      <Toaster />
    </div>
  );
}
