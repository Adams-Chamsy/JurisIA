/**
 * JurisIA — Tests Frontend : Utilitaires & Composants
 * Tests sur les fonctions utilitaires et les composants UI critiques.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// ── Tests : lib/utils ────────────────────────────────────────────────────────

describe('utils/cn', () => {
  it('fusionne les classes sans conflit', async () => {
    const { cn } = await import('@/lib/utils');
    expect(cn('px-4', 'py-2')).toBe('px-4 py-2');
  });

  it('résout les conflits Tailwind (dernière classe gagne)', async () => {
    const { cn } = await import('@/lib/utils');
    expect(cn('px-4', 'px-8')).toBe('px-8');
  });

  it('ignore les valeurs falsy', async () => {
    const { cn } = await import('@/lib/utils');
    expect(cn('px-4', false && 'hidden', undefined, null, 'py-2')).toBe('px-4 py-2');
  });
});

describe('utils/getScoreColor', () => {
  it('retourne vert pour score >= 70', async () => {
    const { getScoreColor } = await import('@/lib/utils');
    expect(getScoreColor(85)).toContain('green');
    expect(getScoreColor(70)).toContain('green');
  });

  it('retourne amber pour 40 <= score < 70', async () => {
    const { getScoreColor } = await import('@/lib/utils');
    expect(getScoreColor(55)).toContain('amber');
    expect(getScoreColor(40)).toContain('amber');
  });

  it('retourne rouge pour score < 40', async () => {
    const { getScoreColor } = await import('@/lib/utils');
    expect(getScoreColor(39)).toContain('red');
    expect(getScoreColor(0)).toContain('red');
  });
});

describe('utils/getScoreLabel', () => {
  it('retourne "Solide" pour score >= 70', async () => {
    const { getScoreLabel } = await import('@/lib/utils');
    expect(getScoreLabel(80)).toBe('Solide');
  });

  it('retourne "Modéré" pour 40-69', async () => {
    const { getScoreLabel } = await import('@/lib/utils');
    expect(getScoreLabel(50)).toBe('Modéré');
  });

  it('retourne "Risqué" pour score < 40', async () => {
    const { getScoreLabel } = await import('@/lib/utils');
    expect(getScoreLabel(20)).toBe('Risqué');
  });
});

describe('utils/truncate', () => {
  it('ne tronque pas si le texte est assez court', async () => {
    const { truncate } = await import('@/lib/utils');
    expect(truncate('Court texte', 50)).toBe('Court texte');
  });

  it('tronque et ajoute des points de suspension', async () => {
    const { truncate } = await import('@/lib/utils');
    const result = truncate('Un texte très long qui dépasse la limite', 20);
    expect(result).toHaveLength(21); // 20 chars + "…"
    expect(result.endsWith('…')).toBe(true);
  });
});

describe('utils/formatDate', () => {
  it('formate en français', async () => {
    const { formatDate } = await import('@/lib/utils');
    const result = formatDate('2026-04-01');
    expect(result).toContain('2026');
    expect(result).toMatch(/avril/i);
  });
});

// ── Tests : Composant Button ─────────────────────────────────────────────────

describe('Button', () => {
  it('rend le texte correctement', async () => {
    const { Button } = await import('@/components/ui/index');
    render(<Button>Analyser mon contrat</Button>);
    expect(screen.getByText('Analyser mon contrat')).toBeDefined();
  });

  it('affiche un spinner en état loading', async () => {
    const { Button } = await import('@/components/ui/index');
    render(<Button isLoading>Analyser</Button>);
    // Le spinner remplace le texte
    expect(screen.queryByText('Analyser')).toBeDefined();
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('aria-busy', 'true');
    expect(btn).toBeDisabled();
  });

  it('est désactivé quand disabled=true', async () => {
    const { Button } = await import('@/components/ui/index');
    render(<Button disabled>Test</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('appelle onClick quand cliqué', async () => {
    const { Button } = await import('@/components/ui/index');
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Cliquer</Button>);
    await userEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('ne déclenche pas onClick quand isLoading=true', async () => {
    const { Button } = await import('@/components/ui/index');
    const onClick = vi.fn();
    render(<Button isLoading onClick={onClick}>Test</Button>);
    await userEvent.click(screen.getByRole('button'));
    expect(onClick).not.toHaveBeenCalled();
  });
});

// ── Tests : Composant Input ──────────────────────────────────────────────────

describe('Input', () => {
  it('affiche le label', async () => {
    const { Input } = await import('@/components/ui/index');
    render(<Input label="Email professionnel" />);
    expect(screen.getByText('Email professionnel')).toBeDefined();
  });

  it('affiche l\'erreur avec aria-invalid', async () => {
    const { Input } = await import('@/components/ui/index');
    render(<Input label="Email" error="Email invalide" />);
    expect(screen.getByText('Email invalide')).toBeDefined();
    expect(screen.getByRole('textbox')).toHaveAttribute('aria-invalid', 'true');
  });

  it('appelle onChange quand la valeur change', async () => {
    const { Input } = await import('@/components/ui/index');
    const onChange = vi.fn();
    render(<Input label="Nom" onChange={onChange} />);
    await userEvent.type(screen.getByRole('textbox'), 'Marie');
    expect(onChange).toHaveBeenCalled();
  });

  it('affiche le marqueur obligatoire quand required', async () => {
    const { Input } = await import('@/components/ui/index');
    render(<Input label="Nom" required />);
    expect(screen.getByLabelText('obligatoire')).toBeDefined();
  });
});

// ── Tests : Composant Badge ──────────────────────────────────────────────────

describe('Badge', () => {
  it('applique la variante success', async () => {
    const { Badge } = await import('@/components/ui/index');
    const { container } = render(<Badge variant="success">Conforme</Badge>);
    expect(container.firstChild).toHaveClass('bg-green-50');
  });

  it('applique la variante danger', async () => {
    const { Badge } = await import('@/components/ui/index');
    const { container } = render(<Badge variant="danger">Risque</Badge>);
    expect(container.firstChild).toHaveClass('bg-red-50');
  });
});

// ── Tests : Composant Skeleton ───────────────────────────────────────────────

describe('Skeleton', () => {
  it('est aria-hidden', async () => {
    const { Skeleton } = await import('@/components/ui/index');
    render(<Skeleton className="h-4 w-32" />);
    const el = document.querySelector('[aria-hidden="true"]');
    expect(el).not.toBeNull();
  });
});

// ── Tests : Toast system ─────────────────────────────────────────────────────

describe('toast helper', () => {
  it('dispatch un événement DOM pour success', async () => {
    const { toast } = await import('@/components/ui/Toaster');
    const listener = vi.fn();
    window.addEventListener('jurisai:toast', listener);
    toast.success('Titre', 'Message');
    expect(listener).toHaveBeenCalledOnce();
    const event = listener.mock.calls[0][0] as CustomEvent;
    expect(event.detail.type).toBe('success');
    expect(event.detail.title).toBe('Titre');
    window.removeEventListener('jurisai:toast', listener);
  });

  it('dispatch un événement DOM pour error avec durée plus longue', async () => {
    const { toast } = await import('@/components/ui/Toaster');
    const listener = vi.fn();
    window.addEventListener('jurisai:toast', listener);
    toast.error('Erreur', 'Détails');
    const event = listener.mock.calls[0][0] as CustomEvent;
    expect(event.detail.type).toBe('error');
    expect(event.detail.duration).toBe(6000);
    window.removeEventListener('jurisai:toast', listener);
  });
});

// ── Tests : Auth Store ───────────────────────────────────────────────────────

describe('useAuthStore', () => {
  beforeEach(() => {
    // Reset le store entre chaque test
    vi.resetModules();
  });

  it('état initial : non authentifié', async () => {
    const { useAuthStore } = await import('@/store/auth.store');
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.user).toBeNull();
  });

  it('clearError efface l\'erreur', async () => {
    const { useAuthStore } = await import('@/store/auth.store');
    useAuthStore.setState({ error: 'Une erreur' });
    useAuthStore.getState().clearError();
    expect(useAuthStore.getState().error).toBeNull();
  });

  it('setSubscription met à jour l\'abonnement', async () => {
    const { useAuthStore } = await import('@/store/auth.store');
    const sub = { plan: 'pro' as const, status: 'active' as const, current_period_end: null };
    useAuthStore.getState().setSubscription(sub);
    expect(useAuthStore.getState().subscription?.plan).toBe('pro');
  });
});

// ── Tests : API Service ──────────────────────────────────────────────────────

describe('api/tokenStore', () => {
  it('stocke et récupère les tokens', async () => {
    const { tokenStore } = await import('@/services/api');
    tokenStore.setTokens('access_123', 'refresh_456');
    expect(tokenStore.getAccessToken()).toBe('access_123');
    expect(tokenStore.getRefreshToken()).toBe('refresh_456');
    tokenStore.clearTokens();
    expect(tokenStore.getAccessToken()).toBeNull();
  });

  it('clearTokens supprime tous les tokens', async () => {
    const { tokenStore } = await import('@/services/api');
    tokenStore.setTokens('a', 'b');
    tokenStore.clearTokens();
    expect(tokenStore.getAccessToken()).toBeNull();
    expect(tokenStore.getRefreshToken()).toBeNull();
  });
});
