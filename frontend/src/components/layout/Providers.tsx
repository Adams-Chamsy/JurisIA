'use client';

/**
 * JurisIA — Providers
 * Encapsule tous les providers React au niveau racine.
 * Isolé dans un Client Component car QueryClient et ThemeProvider nécessitent le client.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { ThemeProvider } from 'next-themes';
import { useState } from 'react';
import { Toaster } from '@/components/ui/Toaster';

export function Providers({ children }: { children: React.ReactNode }) {
  // QueryClient créé dans le state pour éviter le partage entre requêtes (SSR)
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Données fraîches pendant 5 minutes
            staleTime: 5 * 60 * 1000,
            // Retry 1 fois sur les erreurs réseau (pas sur les 4xx)
            retry: (failureCount, error: unknown) => {
              const err = error as { statusCode?: number };
              if (err?.statusCode && err.statusCode >= 400 && err.statusCode < 500) {
                return false; // Pas de retry sur les erreurs client
              }
              return failureCount < 1;
            },
            // Refetch au focus de la fenêtre (UX pro)
            refetchOnWindowFocus: false,
          },
          mutations: {
            // Pas de retry automatique sur les mutations
            retry: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="light"
        enableSystem={false}
        disableTransitionOnChange
      >
        {children}
        <Toaster />
      </ThemeProvider>
      {process.env.NODE_ENV === 'development' && (
        <ReactQueryDevtools initialIsOpen={false} />
      )}
    </QueryClientProvider>
  );
}
