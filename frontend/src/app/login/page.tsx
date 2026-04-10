'use client';

/**
 * JurisIA — Page de Connexion
 * Formulaire email/MDP avec gestion 2FA, validation Zod, feedback UX.
 */

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, Lock, Mail, Scale } from 'lucide-react';
import { Button, Input } from '@/components/ui/index';
import { toast } from '@/components/ui/Toaster';
import { useAuthStore } from '@/store/auth.store';

// ── Validation Schéma ────────────────────────────────────────────────────────
const loginSchema = z.object({
  email:    z.string().email('Adresse email invalide'),
  password: z.string().min(1, 'Mot de passe requis'),
  totpCode: z.string().optional(),
});

type LoginForm = z.infer<typeof loginSchema>;

// ── Page ──────────────────────────────────────────────────────────────────────
export default function LoginPage() {
  const router   = useRouter();
  const { login, isLoading, error, clearError } = useAuthStore();
  const [showPassword, setShowPassword] = useState(false);
  const [requires2FA,  setRequires2FA]  = useState(false);

  const { register, handleSubmit, formState: { errors }, setError } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    clearError();
    try {
      await login(data.email, data.password, data.totpCode);

      // Si l'error state devient '2FA_REQUIRED', afficher le champ 2FA
      if (useAuthStore.getState().error === '2FA_REQUIRED') {
        setRequires2FA(true);
        return;
      }

      toast.success('Connexion réussie', 'Bienvenue sur JurisIA !');
      router.push('/dashboard');
    } catch (err: unknown) {
      const e = err as { code?: string; message?: string };
      if (e?.code === '2FA_REQUIRED') {
        setRequires2FA(true);
        return;
      }
      // Les erreurs sont affichées via le state du store
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-8">

        {/* Logo + Header */}
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-navy">
            <Scale className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-brand-navy">JurisIA</h1>
          <p className="mt-2 text-muted-foreground text-sm">
            Assistant juridique IA souverain 🇫🇷
          </p>
        </div>

        {/* Card du formulaire */}
        <div className="rounded-2xl border border-border bg-white p-8 shadow-sm space-y-6">
          <div>
            <h2 className="text-xl font-semibold text-foreground">Connexion</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Accédez à votre espace juridique
            </p>
          </div>

          {/* Erreur globale */}
          {error && error !== '2FA_REQUIRED' && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3" role="alert">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <Input
              {...register('email')}
              type="email"
              label="Adresse email"
              placeholder="marie@entreprise.fr"
              autoComplete="email"
              error={errors.email?.message}
              leftElement={<Mail className="h-4 w-4" />}
              required
            />

            <Input
              {...register('password')}
              type={showPassword ? 'text' : 'password'}
              label="Mot de passe"
              placeholder="••••••••"
              autoComplete="current-password"
              error={errors.password?.message}
              leftElement={<Lock className="h-4 w-4" />}
              rightElement={
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
                  className="hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              }
              required
            />

            {/* Champ 2FA (affiché uniquement si requis) */}
            {requires2FA && (
              <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 space-y-3">
                <p className="text-sm font-medium text-blue-800">
                  🔐 Double authentification requise
                </p>
                <p className="text-xs text-blue-600">
                  Entrez le code à 6 chiffres de votre application d'authentification.
                </p>
                <Input
                  {...register('totpCode')}
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]{6}"
                  maxLength={6}
                  label="Code TOTP"
                  placeholder="000000"
                  autoComplete="one-time-code"
                  error={errors.totpCode?.message}
                  required
                />
              </div>
            )}

            <div className="flex items-center justify-end">
              <Link
                href="/forgot-password"
                className="text-sm text-brand-electric hover:underline underline-offset-4"
              >
                Mot de passe oublié ?
              </Link>
            </div>

            <Button
              type="submit"
              size="lg"
              className="w-full"
              isLoading={isLoading}
              aria-label="Se connecter"
            >
              Se connecter
            </Button>
          </form>

          {/* Séparateur */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center" aria-hidden="true">
              <div className="w-full border-t border-border" />
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-white px-2 text-muted-foreground">Pas encore de compte ?</span>
            </div>
          </div>

          <Button variant="outline" size="lg" className="w-full" asChild>
            <Link href="/register">Créer un compte gratuit</Link>
          </Button>
        </div>

        {/* Footer mentions */}
        <p className="text-center text-xs text-muted-foreground">
          Données hébergées en France 🇫🇷 · RGPD conforme ·{' '}
          <Link href="/privacy" className="hover:underline">Confidentialité</Link>
        </p>
      </div>
    </div>
  );
}
