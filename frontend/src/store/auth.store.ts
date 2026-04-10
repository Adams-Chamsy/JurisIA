/**
 * JurisIA — Store d'Authentification (Zustand)
 * État global : utilisateur, organisation, abonnement, actions d'auth.
 */

import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { apiPost } from '@/services/api';
import { tokenStore } from '@/services/api';

// ── Types ─────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  email_verified: boolean;
  two_fa_enabled: boolean;
}

export interface Organization {
  id: string;
  name: string;
  siren: string | null;
  sector_label: string | null;
  employee_count_range: string | null;
}

export interface Subscription {
  plan: 'free' | 'starter' | 'pro' | 'business';
  status: 'active' | 'trialing' | 'past_due' | 'canceled';
  current_period_end: string | null;
}

export interface AuthState {
  user: User | null;
  organization: Organization | null;
  subscription: Subscription | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string, totpCode?: string) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  setSubscription: (sub: Subscription) => void;
  clearError: () => void;
}

export interface RegisterData {
  full_name: string;
  email: string;
  password: string;
  organization_name: string;
  siren?: string;
  accept_terms: boolean;
}

// ── Store ─────────────────────────────────────────────────────────────────────

export const useAuthStore = create<AuthState>()(
  devtools(
    persist(
      (set, get) => ({
        user: null,
        organization: null,
        subscription: null,
        isAuthenticated: false,
        isLoading: false,
        error: null,

        login: async (email, password, totpCode) => {
          set({ isLoading: true, error: null });
          try {
            const response = await apiPost<{
              user: User;
              organization: Organization;
              tokens: { access_token: string; refresh_token: string };
              requires_2fa: boolean;
            }>('/auth/login', { email, password, totp_code: totpCode });

            if (response.requires_2fa && !totpCode) {
              // Signaler que le 2FA est requis
              set({ isLoading: false, error: '2FA_REQUIRED' });
              return;
            }

            tokenStore.setTokens(response.tokens.access_token, response.tokens.refresh_token);

            set({
              user: response.user,
              organization: response.organization,
              isAuthenticated: true,
              isLoading: false,
              error: null,
            });
          } catch (err: unknown) {
            const error = err as Error;
            set({ isLoading: false, error: error.message, isAuthenticated: false });
            throw err;
          }
        },

        register: async (data) => {
          set({ isLoading: true, error: null });
          try {
            await apiPost('/auth/register', data);
            set({ isLoading: false });
          } catch (err: unknown) {
            const error = err as Error;
            set({ isLoading: false, error: error.message });
            throw err;
          }
        },

        logout: async () => {
          const refresh = tokenStore.getRefreshToken();
          try {
            if (refresh) {
              await apiPost('/auth/logout', { refresh_token: refresh });
            }
          } catch {
            // Ignorer les erreurs de logout (token déjà expiré, etc.)
          } finally {
            tokenStore.clearTokens();
            set({
              user: null,
              organization: null,
              subscription: null,
              isAuthenticated: false,
              isLoading: false,
            });
          }
        },

        refreshProfile: async () => {
          try {
            const user = await apiPost<User>('/auth/me');
            set({ user });
          } catch {
            // Si le token est invalide, déconnecter
            get().logout();
          }
        },

        setSubscription: (sub) => set({ subscription: sub }),

        clearError: () => set({ error: null }),
      }),
      {
        name: 'jurisai-auth',
        // Ne persister QUE les infos non-sensibles (pas les tokens !)
        partialize: (state) => ({
          user: state.user,
          organization: state.organization,
          subscription: state.subscription,
          isAuthenticated: state.isAuthenticated,
        }),
      },
    ),
    { name: 'AuthStore' },
  ),
);

// ── Hooks de sélection optimisés ─────────────────────────────────────────────

export const useUser = () => useAuthStore((state) => state.user);
export const useOrganization = () => useAuthStore((state) => state.organization);
export const useSubscription = () => useAuthStore((state) => state.subscription);
export const useIsAuthenticated = () => useAuthStore((state) => state.isAuthenticated);
export const usePlan = () => useAuthStore((state) => state.subscription?.plan ?? 'free');
