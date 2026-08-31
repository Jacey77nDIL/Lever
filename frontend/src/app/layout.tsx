import type { Metadata } from 'next';
import './globals.css';
import Providers from './providers';
import Navigation from '@/components/Navigation';

export const metadata: Metadata = {
  title: 'Lever - NGX Paper Trading',
  description: 'A paper-trading web app for the Nigerian Exchange',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[var(--color-surface)] pb-20 md:pb-0">
        <Providers>
          <div className="md:flex md:h-screen">
            <div className="hidden md:block w-64 border-r border-gray-200 bg-white">
              <Navigation desktop />
            </div>
            <main className="flex-1 overflow-y-auto">
              {children}
            </main>
            <div className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-50">
              <Navigation mobile />
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
