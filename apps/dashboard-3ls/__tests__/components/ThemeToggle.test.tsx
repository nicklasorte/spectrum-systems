/**
 * D3L-MASTER-01 Phase 7 — theme toggle component tests.
 *
 * Pins UI behavior:
 *   - Light/Dark/System buttons render
 *   - Selecting Dark adds the `dark` class to <html> and persists to
 *     localStorage
 *   - Selecting Light removes the class
 *   - Selecting System follows matchMedia
 */
import React from 'react';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { ThemeToggle } from '@/components/ThemeToggle';
import { THEME_STORAGE_KEY } from '@/lib/theme';

describe('ThemeToggle', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
    delete (document.documentElement as unknown as { dataset: DOMStringMap }).dataset.theme;
  });

  afterEach(() => {
    cleanup();
  });

  it('renders three buttons', () => {
    render(<ThemeToggle />);
    expect(screen.getByTestId('theme-light')).toBeInTheDocument();
    expect(screen.getByTestId('theme-dark')).toBeInTheDocument();
    expect(screen.getByTestId('theme-system')).toBeInTheDocument();
  });

  it('selecting Dark adds .dark to <html> and persists preference', () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByTestId('theme-dark'));
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
    expect(screen.getByTestId('theme-toggle').dataset.activeTheme).toBe('dark');
  });

  it('selecting Light removes .dark and persists preference', () => {
    document.documentElement.classList.add('dark');
    render(<ThemeToggle />);
    fireEvent.click(screen.getByTestId('theme-light'));
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
  });

  it('selecting System resolves via matchMedia', () => {
    // Mock matchMedia to report dark.
    const original = window.matchMedia;
    window.matchMedia = (query: string) => ({
      matches: query === '(prefers-color-scheme: dark)',
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    } as MediaQueryList);
    render(<ThemeToggle />);
    fireEvent.click(screen.getByTestId('theme-system'));
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('system');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    window.matchMedia = original;
  });

  it('reads stored preference on mount', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'dark');
    render(<ThemeToggle />);
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(screen.getByTestId('theme-toggle').dataset.preference).toBe('dark');
  });
});
