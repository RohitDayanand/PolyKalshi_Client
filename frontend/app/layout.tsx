import type { Metadata } from 'next'
import './globals.css'
import { ReduxProvider } from '@/lib/providers'
import { ThemeProvider } from '@/components/containers/theme-provider'
import { LoadingBarContainer } from '@/components/containers/loading-bar-container'

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
            <LoadingBarContainer />
            {children}
          </ReduxProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
