import type { Metadata } from 'next'
import { Navigation } from '@/components/Navigation'
import './globals.css'

export const metadata: Metadata = {
  title: '3-Letter Systems Dashboard',
  description: 'Real-time health monitoring of 28+ governance systems in Spectrum Systems',
}

// D3L-MASTER-01 Phase 7 — pre-hydration theme bootstrap. Avoids a flash
// of light mode on first paint when the persisted preference is dark.
const THEME_BOOTSTRAP = `
  (function () {
    try {
      var pref = localStorage.getItem('d3l-theme') || 'system';
      var dark = pref === 'dark' || (pref === 'system' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
      if (dark) document.documentElement.classList.add('dark');
      document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    } catch (e) {}
  })();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
      </head>
      <body className="bg-white text-gray-900 dark:bg-[#0b1220] dark:text-gray-100">
        <Navigation />
        {children}
      </body>
    </html>
  )
}
