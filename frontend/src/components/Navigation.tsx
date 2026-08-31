'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, ArrowRightLeft, Trophy, User as UserIcon } from 'lucide-react';
import clsx from 'clsx';

export default function Navigation({ desktop, mobile }: { desktop?: boolean; mobile?: boolean }) {
  const pathname = usePathname();

  const navItems = [
    { label: 'Dashboard', href: '/', icon: LayoutDashboard },
    { label: 'Trade', href: '/trade', icon: ArrowRightLeft },
    { label: 'Leaderboard', href: '/leaderboard', icon: Trophy },
    { label: 'Profile', href: '/profile', icon: UserIcon },
  ];

  if (mobile) {
    return (
      <nav className="flex justify-around items-center h-16">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                'flex flex-col items-center justify-center w-full h-full space-y-1',
                isActive ? 'text-[var(--color-brand)]' : 'text-gray-500'
              )}
            >
              <Icon size={20} />
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    );
  }

  return (
    <div className="flex flex-col h-full py-6 px-4">
      <div className="mb-10 px-2">
        <h1 className="text-2xl font-bold text-[var(--color-brand)]">Lever</h1>
      </div>
      <nav className="flex-1 space-y-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                'flex items-center space-x-3 px-3 py-2 rounded-lg transition-colors',
                isActive
                  ? 'bg-[var(--color-brand-light)] text-[var(--color-brand)] font-medium'
                  : 'text-gray-600 hover:bg-gray-50'
              )}
            >
              <Icon size={20} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
