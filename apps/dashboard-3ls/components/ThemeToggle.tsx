'use client';

import React, { useEffect, useState } from 'react';
import {
  isThemePreference,
  resolveTheme,
  THEME_STORAGE_KEY,
  type ThemePreference,
  type ResolvedTheme,
} from '@/lib/theme';

// D3L-MASTER-01 Phase 7 — theme toggle (Light / Dark / System).
// The `dark` class is applied to <html> so Tailwind's class-strategy
// dark mode picks up across the whole app. Choice persists in
// localStorage under d3l-theme.

function applyTheme(resolved: ResolvedTheme): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  if (resolved === 'dark') root.classList.add('dark');
  else root.classList.remove('dark');
  root.dataset.theme = resolved;
}

function readPreference(): ThemePreference {
  if (typeof localStorage === 'undefined') return 'system';
  const raw = localStorage.getItem(THEME_STORAGE_KEY);
  return isThemePreference(raw) ? raw : 'system';
}

function prefersDarkMQ(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

export function ThemeToggle({ className = '' }: { className?: string }) {
  const [preference, setPreference] = useState<ThemePreference>('system');
  const [resolved, setResolved] = useState<ResolvedTheme>('light');

  useEffect(() => {
    const initial = readPreference();
    setPreference(initial);
    const r = resolveTheme(initial, prefersDarkMQ());
    setResolved(r);
    applyTheme(r);
  }, []);

  useEffect(() => {
    if (preference !== 'system') return;
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)');
    if (!mq) return;
    const handler = () => {
      const r = resolveTheme('system', mq.matches);
      setResolved(r);
      applyTheme(r);
    };
    mq.addEventListener?.('change', handler);
    return () => mq.removeEventListener?.('change', handler);
  }, [preference]);

  const choose = (value: ThemePreference) => {
    setPreference(value);
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(THEME_STORAGE_KEY, value);
    }
    const r = resolveTheme(value, prefersDarkMQ());
    setResolved(r);
    applyTheme(r);
  };

  const buttonClass = (active: boolean) =>
    `px-2 py-0.5 text-xs rounded border ${
      active
        ? 'bg-gray-900 text-white border-gray-900 dark:bg-gray-100 dark:text-gray-900 dark:border-gray-100'
        : 'bg-white text-gray-800 border-gray-300 dark:bg-gray-800 dark:text-gray-100 dark:border-gray-600'
    }`;

  return (
    <div
      data-testid="theme-toggle"
      data-active-theme={resolved}
      data-preference={preference}
      className={`inline-flex gap-1 ${className}`}
      role="group"
      aria-label="Theme"
    >
      <button type="button" onClick={() => choose('light')} className={buttonClass(preference === 'light')} data-testid="theme-light">
        Light
      </button>
      <button type="button" onClick={() => choose('dark')} className={buttonClass(preference === 'dark')} data-testid="theme-dark">
        Dark
      </button>
      <button type="button" onClick={() => choose('system')} className={buttonClass(preference === 'system')} data-testid="theme-system">
        System
      </button>
    </div>
  );
}
