import { Analytics } from '@vercel/analytics/next'
import type { Metadata, Viewport } from 'next'
import { Geist, Geist_Mono, Outfit } from 'next/font/google'
import { Toaster } from '@/components/ui/sonner'
import './globals.css'

const geistSans = Geist({ variable: '--font-geist-sans', subsets: ['latin'] })
const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
})
const outfit = Outfit({
  variable: '--font-outfit',
  subsets: ['latin'],
  weight: ['500', '600', '700', '800'],
})

export const metadata: Metadata = {
  title: 'Telegram Ultra',
  description: 'Next-Gen Telegram Userbot & Control Panel',
  generator: 'v0.app',
  icons: {
    icon: '/telegram-ultra.png',
    apple: '/telegram-ultra.png',
  },
  openGraph: {
    title: 'Telegram Ultra',
    description: 'Next-Gen Telegram Userbot & Control Panel',
    images: [{ url: '/telegram-ultra.png', width: 1260, height: 1260, alt: 'Telegram Ultra' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Telegram Ultra',
    description: 'Next-Gen Telegram Userbot & Control Panel',
    images: ['/telegram-ultra.png'],
  },
}

export const viewport: Viewport = {
  colorScheme: 'dark',
  themeColor: '#0a0f1e',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${geistMono.variable} ${outfit.variable} bg-background`}
    >
      <body className="font-sans antialiased">
        {children}
        <Toaster position="top-center" richColors />
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
