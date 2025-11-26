import type { Metadata } from 'next'
import './globals.css'
import { Providers } from './providers'

export const metadata: Metadata = {
  title: 'InvestFlow - Rental Property Management',
  description: 'Manage your rental properties, expenses, and cash flow analysis',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="light">
      <body className="font-['Roboto',sans-serif] antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}

