'use client';

/**
 * JurisIA — Composants UI de Base
 * Button, Input, Badge, Spinner — Production-ready, accessibles (WCAG 2.1 AA)
 */

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

// ── Button ────────────────────────────────────────────────────────────────────

const buttonVariants = cva(
  // Base : toujours appliqué
  [
    'inline-flex items-center justify-center gap-2',
    'rounded-lg font-semibold text-sm',
    'transition-all duration-150',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
    'disabled:pointer-events-none disabled:opacity-50',
    'active:scale-[0.98]',
  ],
  {
    variants: {
      variant: {
        primary:   'bg-brand-electric text-white hover:bg-blue-700 shadow-sm',
        secondary: 'bg-secondary text-foreground hover:bg-secondary/80 border border-border',
        ghost:     'hover:bg-accent hover:text-accent-foreground',
        danger:    'bg-brand-danger text-white hover:bg-red-700 shadow-sm',
        outline:   'border border-input bg-background hover:bg-accent hover:text-accent-foreground',
        navy:      'bg-brand-navy text-white hover:bg-blue-900 shadow-sm',
        link:      'text-brand-electric underline-offset-4 hover:underline p-0 h-auto',
      },
      size: {
        sm:   'h-8  px-3  text-xs',
        md:   'h-10 px-4  text-sm',
        lg:   'h-11 px-6  text-base',
        xl:   'h-12 px-8  text-base',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size:    'md',
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, isLoading, leftIcon, rightIcon, children, disabled, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || isLoading}
      aria-busy={isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      ) : (
        leftIcon && <span aria-hidden="true">{leftIcon}</span>
      )}
      {children}
      {!isLoading && rightIcon && <span aria-hidden="true">{rightIcon}</span>}
    </button>
  ),
);
Button.displayName = 'Button';

// ── Input ─────────────────────────────────────────────────────────────────────

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  leftElement?: React.ReactNode;
  rightElement?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, hint, leftElement, rightElement, id, ...props }, ref) => {
    const inputId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-sm font-medium text-foreground"
          >
            {label}
            {props.required && <span className="ml-1 text-brand-danger" aria-label="obligatoire">*</span>}
          </label>
        )}
        <div className="relative">
          {leftElement && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" aria-hidden="true">
              {leftElement}
            </div>
          )}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              'flex h-10 w-full rounded-lg border border-input bg-background px-3 py-2',
              'text-sm text-foreground placeholder:text-muted-foreground',
              'transition-colors duration-150',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-0 focus-visible:border-transparent',
              'disabled:cursor-not-allowed disabled:opacity-50',
              error && 'border-brand-danger focus-visible:ring-red-300',
              leftElement  && 'pl-10',
              rightElement && 'pr-10',
              className,
            )}
            aria-invalid={!!error}
            aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
            {...props}
          />
          {rightElement && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground" aria-hidden="true">
              {rightElement}
            </div>
          )}
        </div>
        {error && (
          <p id={`${inputId}-error`} className="text-xs text-brand-danger flex items-center gap-1" role="alert">
            <span aria-hidden="true">⚠</span> {error}
          </p>
        )}
        {hint && !error && (
          <p id={`${inputId}-hint`} className="text-xs text-muted-foreground">{hint}</p>
        )}
      </div>
    );
  },
);
Input.displayName = 'Input';

// ── Badge ─────────────────────────────────────────────────────────────────────

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default:  'bg-primary/10 text-primary border border-primary/20',
        success:  'bg-green-50 text-green-700 border border-green-200',
        warning:  'bg-amber-50 text-amber-700 border border-amber-200',
        danger:   'bg-red-50 text-red-700 border border-red-200',
        muted:    'bg-muted text-muted-foreground',
        outline:  'border border-border text-foreground',
        // Plans
        free:     'bg-gray-100 text-gray-600',
        starter:  'bg-blue-50 text-blue-700 border border-blue-200',
        pro:      'bg-purple-50 text-purple-700 border border-purple-200',
        business: 'bg-amber-50 text-amber-700 border border-amber-200',
      },
    },
    defaultVariants: { variant: 'default' },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

// ── Spinner ───────────────────────────────────────────────────────────────────

export function Spinner({ size = 'md', className }: { size?: 'sm' | 'md' | 'lg'; className?: string }) {
  const sizes = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-8 w-8' };
  return (
    <Loader2
      className={cn('animate-spin text-primary', sizes[size], className)}
      aria-label="Chargement en cours"
    />
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('skeleton', className)}
      aria-hidden="true"
      {...props}
    />
  );
}

// ── Card ──────────────────────────────────────────────────────────────────────

export function Card({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-card p-6 shadow-sm',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('mb-4 space-y-1', className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn('text-lg font-semibold text-foreground', className)} {...props} />;
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-sm text-muted-foreground', className)} {...props} />;
}

// ── Score Gauge ───────────────────────────────────────────────────────────────

export function ScoreGauge({ score, size = 'md' }: { score: number; size?: 'sm' | 'md' | 'lg' }) {
  const scoreColor = score >= 70 ? '#16A34A' : score >= 40 ? '#D97706' : '#DC2626';
  const label = score >= 70 ? 'Solide' : score >= 40 ? 'Modéré' : 'Risqué';
  const dimensions = { sm: 80, md: 120, lg: 160 };
  const dim = dimensions[size];
  const r = (dim / 2) - 10;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2" role="meter" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100} aria-label={`Score de solidité : ${score} sur 100`}>
      <svg width={dim} height={dim} className="transform -rotate-90">
        {/* Track */}
        <circle cx={dim/2} cy={dim/2} r={r} fill="none" stroke="#E2E8F0" strokeWidth="8" />
        {/* Progress */}
        <circle
          cx={dim/2} cy={dim/2} r={r}
          fill="none"
          stroke={scoreColor}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-700 ease-out"
        />
      </svg>
      <div className="absolute flex flex-col items-center" style={{ marginTop: dim * 0.15 }}>
        <span className="text-2xl font-bold" style={{ color: scoreColor }}>{score}</span>
        <span className="text-xs text-muted-foreground">/100</span>
      </div>
      <Badge variant={score >= 70 ? 'success' : score >= 40 ? 'warning' : 'danger'}>
        {label}
      </Badge>
    </div>
  );
}
