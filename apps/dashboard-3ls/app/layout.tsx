import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: '3-Letter Systems Dashboard',
  description: 'Real-time health monitoring of 28+ governance systems in Spectrum Systems',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
