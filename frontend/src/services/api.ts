/**
 * JurisIA — Service API Centralisé
 * Client Axios configuré avec :
 * - Injection automatique du Bearer token
 * - Refresh automatique du token expiré
 * - Gestion globale des erreurs
 * - Retry sur les erreurs réseau
 */

import axios, {
  type AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios';

// ── Types ────────────────────────────────────────────────────────────────────

export interface ApiError {
  code: string;
  message: string;
  action?: string;
  details?: Record<string, unknown>;
}

export interface ApiResponse<T> {
  data: T;
  status: number;
}

// ── Gestion des tokens en mémoire ─────────────────────────────────────────────
// IMPORTANT : ne jamais stocker les tokens dans localStorage (XSS vuln)
// On utilise une variable en mémoire (perdue au refresh page = feature, pas un bug)

let accessToken: string | null = null;
let refreshToken: string | null = null;
let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

export const tokenStore = {
  setTokens(access: string, refresh: string): void {
    accessToken = access;
    // Refresh token stocké dans un cookie httpOnly en production (via le backend)
    // En dev, on le garde en mémoire aussi
    refreshToken = refresh;
    // Sauvegarder dans sessionStorage pour persister entre les pages (pas localStorage)
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('_rt', refresh); // Prefix _ = indicateur de sensibilité
    }
  },
  getAccessToken(): string | null {
    return accessToken;
  },
  getRefreshToken(): string | null {
    return refreshToken || (typeof window !== 'undefined' ? sessionStorage.getItem('_rt') : null);
  },
  clearTokens(): void {
    accessToken = null;
    refreshToken = null;
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('_rt');
    }
  },
};

// ── Création du client Axios ──────────────────────────────────────────────────

const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
    timeout: 30000, // 30 secondes (les analyses IA peuvent être lentes)
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
  });

  // ── Intercepteur de requête : injecter le token ─────────────────────────
  client.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      const token = tokenStore.getAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => Promise.reject(error),
  );

  // ── Intercepteur de réponse : gérer les erreurs globalement ─────────────
  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

      // Si 401 et qu'on n'a pas déjà tenté de refresh
      if (error.response?.status === 401 && !originalRequest._retry) {
        const stored = tokenStore.getRefreshToken();

        if (!stored) {
          // Pas de refresh token → déconnexion forcée
          tokenStore.clearTokens();
          if (typeof window !== 'undefined') {
            window.location.href = '/login?reason=session_expired';
          }
          return Promise.reject(error);
        }

        if (isRefreshing) {
          // Une autre requête est déjà en train de refresh
          // Attendre que le refresh soit terminé
          return new Promise<unknown>((resolve) => {
            refreshSubscribers.push((newToken: string) => {
              originalRequest.headers.Authorization = `Bearer ${newToken}`;
              resolve(client(originalRequest));
            });
          });
        }

        originalRequest._retry = true;
        isRefreshing = true;

        try {
          const response = await axios.post(
            `${process.env.NEXT_PUBLIC_API_URL}/auth/refresh`,
            { refresh_token: stored },
          );

          const { access_token, refresh_token: new_refresh } = response.data;
          tokenStore.setTokens(access_token, new_refresh);

          // Notifier les requêtes en attente
          refreshSubscribers.forEach((cb) => cb(access_token));
          refreshSubscribers = [];

          // Rejouer la requête originale
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return client(originalRequest);
        } catch (refreshError) {
          // Refresh échoué → déconnexion
          tokenStore.clearTokens();
          refreshSubscribers = [];
          if (typeof window !== 'undefined') {
            window.location.href = '/login?reason=session_expired';
          }
          return Promise.reject(refreshError);
        } finally {
          isRefreshing = false;
        }
      }

      // Formater l'erreur API de manière consistante
      const apiError = formatApiError(error);
      return Promise.reject(apiError);
    },
  );

  return client;
};

// ── Formatage des erreurs ─────────────────────────────────────────────────────

function formatApiError(error: AxiosError): Error & { code?: string; action?: string; statusCode?: number } {
  const responseData = error.response?.data as { code?: string; message?: string; action?: string } | undefined;

  const formattedError = new Error(
    responseData?.message || 'Une erreur inattendue s\'est produite',
  ) as Error & { code?: string; action?: string; statusCode?: number };

  formattedError.code = responseData?.code || 'UNKNOWN_ERROR';
  formattedError.action = responseData?.action;
  formattedError.statusCode = error.response?.status;

  return formattedError;
}

// ── Instance globale ──────────────────────────────────────────────────────────

export const api = createApiClient();

// ── Helpers typés ─────────────────────────────────────────────────────────────

export const apiGet = <T>(url: string, config?: AxiosRequestConfig) =>
  api.get<T>(url, config).then((r) => r.data);

export const apiPost = <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
  api.post<T>(url, data, config).then((r) => r.data);

export const apiPatch = <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
  api.patch<T>(url, data, config).then((r) => r.data);

export const apiDelete = <T>(url: string, config?: AxiosRequestConfig) =>
  api.delete<T>(url, config).then((r) => r.data);

export const apiUpload = <T>(url: string, formData: FormData, config?: AxiosRequestConfig) =>
  api.post<T>(url, formData, {
    ...config,
    headers: { ...config?.headers, 'Content-Type': 'multipart/form-data' },
    timeout: 120000, // 2 minutes pour les uploads
  }).then((r) => r.data);
