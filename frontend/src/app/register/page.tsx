'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Building2, Eye, EyeOff, Lock, Mail, Scale, User } from 'lucide-react';
import { Button, Input } from '@/components/ui/index';
import { toast } from '@/components/ui/Toaster';
import { useAuthStore } from '@/store/auth.store';

const registerSchema = z.object({
  full_name:          z.string().min(2, 'Nom requis (2 caractères min)').max(255),
  email:              z.string().email('Email invalide'),
  password:           z.string()
                       .min(8, 'Minimum 8 caractères')
                       .regex(/[A-Z]/, 'Une majuscule requise')
                       .regex(/[0-9]/, 'Un chiffre requis'),
  organization_name:  z.string().min(2, 'Nom entreprise requis').max(255),
  accept_terms:       z.literal(true, { errorMap: () => ({ message: 'Vous devez accepter les CGU' }) }),
});

type RegisterForm = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router    = useRouter();
  const { register: registerUser, isLoading, error, clearError } = useAuthStore();
  const [showPwd, setShowPwd] = useState(false);
  const [sent,    setSent]    = useState(false);

  const { register, handleSubmit, formState: { errors } } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
  });

  const onSubmit = async (data: RegisterForm) => {
    clearError();
    try {
      await registerUser({ ...data, siren: undefined });
      setSent(true);
    } catch {}
  };

  if (sent) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center p-4">
        <div className="w-full max-w-md text-center space-y-6">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
            <Mail className="h-8 w-8 text-green-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Vérifiez votre email</h1>
            <p className="text-muted-foreground mt-2">
              Un lien de vérification a été envoyé à votre adresse email.
              Cliquez dessus pour activer votre compte.
            </p>
          </div>
          <Button onClick={() => router.push('/login')} className="w-full">
            Aller à la connexion
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-navy">
            <Scale className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-brand-navy">JurisIA</h1>
          <p className="mt-2 text-muted-foreground text-sm">Créez votre compte gratuit</p>
        </div>

        <div className="rounded-2xl border border-border bg-white p-8 shadow-sm space-y-6">
          <div>
            <h2 className="text-xl font-semibold">Inscription</h2>
            <p className="text-sm text-muted-foreground mt-1">3 documents d'analyse offerts, sans carte bancaire</p>
          </div>

          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3" role="alert">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
            <Input {...register('full_name')} label="Nom complet" placeholder="Marie Dupont"
              leftElement={<User className="h-4 w-4" />} error={errors.full_name?.message} required />

            <Input {...register('email')} type="email" label="Email professionnel" placeholder="marie@entreprise.fr"
              leftElement={<Mail className="h-4 w-4" />} error={errors.email?.message} required />

            <Input {...register('organization_name')} label="Nom de l'entreprise" placeholder="Dupont & Associés SAS"
              leftElement={<Building2 className="h-4 w-4" />} error={errors.organization_name?.message} required />

            <Input
              {...register('password')}
              type={showPwd ? 'text' : 'password'}
              label="Mot de passe"
              placeholder="Min. 8 car., 1 majuscule, 1 chiffre"
              leftElement={<Lock className="h-4 w-4" />}
              rightElement={
                <button type="button" onClick={() => setShowPwd(v => !v)} aria-label={showPwd ? 'Masquer' : 'Afficher'}>
                  {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              }
              error={errors.password?.message}
              required
            />

            <div className="flex items-start gap-3">
              <input
                {...register('accept_terms')}
                type="checkbox"
                id="accept_terms"
                className="mt-0.5 h-4 w-4 rounded border-border text-brand-electric focus:ring-brand-electric"
                required
              />
              <label htmlFor="accept_terms" className="text-sm text-muted-foreground">
                J'accepte les{' '}
                <Link href="/terms" className="text-brand-electric hover:underline">conditions d'utilisation</Link>
                {' '}et la{' '}
                <Link href="/privacy" className="text-brand-electric hover:underline">politique de confidentialité</Link>
              </label>
            </div>
            {errors.accept_terms && (
              <p className="text-xs text-brand-danger">{errors.accept_terms.message}</p>
            )}

            <Button type="submit" size="lg" className="w-full" isLoading={isLoading}>
              Créer mon compte gratuitement
            </Button>
          </form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-border" /></div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-white px-2 text-muted-foreground">Déjà un compte ?</span>
            </div>
          </div>
          <Button variant="outline" size="lg" className="w-full" asChild>
            <Link href="/login">Se connecter</Link>
          </Button>
        </div>

        <p className="text-center text-xs text-muted-foreground">
          Données hébergées en France 🇫🇷 · RGPD conforme · Sans engagement
        </p>
      </div>
    </div>
  );
}
