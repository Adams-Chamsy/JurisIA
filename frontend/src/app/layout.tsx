import type { Metadata, Viewport } from 'next';
import { Inter } from 'next/font/google';
import { Providers } from '@/components/layout/Providers';
import '@/app/globals.css';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: {
    default: 'JurisIA — Assistant Juridique IA pour PME',
    template: '%s | JurisIA',
  },
  description:
    'Analysez vos contrats, générez des documents juridiques et gérez votre conformité RGPD et AI Act. Assistant juridique IA souverain hébergé en France.',
  keywords: [
    'assistant juridique',
    'IA juridique',
    'contrat PME',
    'conformité RGPD',
    'AI Act',
    'droit des affaires',
    'droit du travail',
  ],
  authors: [{ name: 'JurisIA SAS' }],
  openGraph: {
    type:        'website',
    locale:      'fr_FR',
    url:         process.env.NEXT_PUBLIC_APP_URL,
    siteName:    'JurisIA',
    title:       'JurisIA — Assistant Juridique IA pour PME',
    description: 'Analysez vos contrats et gérez votre conformité juridique avec l\'IA souveraine française.',
  },
  twitter: {
    card:  'summary_large_image',
    title: 'JurisIA — Assistant Juridique IA pour PME',
  },
  robots: {
    index:  true,
    follow: true,
  },
  icons: {
    icon: '/favicon.ico',
    apple: '/apple-touch-icon.png',
  },
};

export const viewport: Viewport = {
  themeColor:    '#0F2447',
  width:         'device-width',
  initialScale:  1,
  maximumScale:  5,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
