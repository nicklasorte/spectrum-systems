'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ThemeToggle } from '@/components/ThemeToggle';

export function Navigation() {
  const pathname = usePathname();

  const links = [
    { href: '/', label: 'Dashboard', icon: '📊' },
    { href: '/on-call', label: 'On-Call', icon: '🚨' },
    { href: '/compliance', label: 'Compliance', icon: '✓' },
    { href: '/detail', label: 'Details', icon: '🔍' },
  ];

  return (
    <nav className="bg-gray-900 text-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <div className="flex-shrink-0 text-2xl font-bold">
              3-Letter Systems
            </div>
          </div>
          <div className="flex items-center space-x-1">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`px-4 py-2 rounded-md text-sm font-medium transition ${
                  pathname === link.href
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`}
              >
                <span className="mr-1">{link.icon}</span>
                {link.label}
              </Link>
            ))}
            <div className="ml-3 pl-3 border-l border-gray-700">
              <ThemeToggle />
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
