/**
 * ReviewSignal 7.0 - Root Layout
 * Enterprise-grade Next.js 14 App Router layout with providers
 * 
 * @author Claude AI for Simon
 * @version 7.0.0
 * @license Proprietary
 */

import type { Metadata, Viewport } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import { Providers } from '@/components/providers';
import { Toaster } from '@/components/ui/toaster';
import '@/styles/globals.css';

const inter = Inter({
  subsets: ['latin', 'latin-ext'],
  variable: '--font-inter',
  display: 'swap',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'ReviewSignal | B2B Alternative Data Intelligence',
    template: '%s | ReviewSignal',
  },
  description: 'Real-time consumer sentiment intelligence for Hedge Funds & Private Equity. Track 64,380+ locations across 111 cities worldwide.',
  keywords: ['alternative data', 'hedge fund', 'private equity', 'sentiment analysis', 'google maps', 'reviews intelligence'],
  authors: [{ name: 'ReviewSignal', url: 'https://reviewsignal.com' }],
  creator: 'ReviewSignal',
  publisher: 'ReviewSignal',
  robots: {
    index: false,
    follow: false,
  },
  icons: {
    icon: '/favicon.ico',
    apple: '/apple-touch-icon.png',
  },
  manifest: '/manifest.json',
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#0a0a0a' },
  ],
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body className="min-h-screen bg-background font-sans antialiased">
        <Providers>
          {children}
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
