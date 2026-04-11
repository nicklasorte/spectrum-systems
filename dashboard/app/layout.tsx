import './globals.css'

export const metadata = {
  title: 'Spectrum Systems Dashboard',
  description: 'Live operational dashboard'
}

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang='en'>
      <body>{children}</body>
    </html>
  )
}
