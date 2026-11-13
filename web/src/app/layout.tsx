import type { Metadata } from 'next'
import { Geist } from 'next/font/google'

import { TooltipProvider } from '@/components/ui/tooltip'

import './globals.css'

const sans = Geist({ variable: '--font-sans', subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'V-Twin',
  description: 'Sandbox de simulation moteur V-Twin',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={`${sans.variable} h-full bg-muted antialiased`}>
      <body className="min-h-full bg-muted">
        <TooltipProvider>{children}</TooltipProvider>
      </body>
    </html>
  )
}
