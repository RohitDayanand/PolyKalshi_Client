import type { Metadata } from 'next'
import './globals.css'
import { ReduxProvider } from '@/lib/providers'
import { ThemeProvider } from '@/components/containers/theme-provider'

export const metadata: Metadata = {
  title: 'Websocket Market Dashboard',
  description: 'Real-time market data visualization for Polymarket and Kalshi',
  generator: 'v0.dev',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-black text-white min-h-screen">
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
        >
          <ReduxProvider>
            {children}
          </ReduxProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
