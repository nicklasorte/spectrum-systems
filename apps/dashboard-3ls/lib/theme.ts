// D3L-MASTER-01 Phase 7 — theme system.
//
// Light / Dark / System with persistence in localStorage. Status colors
// (red / orange / yellow / green / gray) keep their semantic meaning
// across both themes — the helpers below pick light- and dark-mode
// foreground/background pairs that satisfy contrast.

export type ThemePreference = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'd3l-theme';

export type SemanticColor = 'red' | 'orange' | 'yellow' | 'green' | 'gray';

interface ColorClasses {
  text: string;
  bg: string;
  border: string;
}

/**
 * Tailwind class pairs that preserve semantic meaning across themes.
 * Light variants pick saturated foregrounds on subtle backgrounds; dark
 * variants pick high-contrast foregrounds on darker backgrounds. We use
 * `dark:` modifiers so a single className survives both themes.
 */
export const STATUS_CLASSES: Record<SemanticColor, ColorClasses> = {
  red: {
    text: 'text-red-700 dark:text-red-300',
    bg: 'bg-red-50 dark:bg-red-950',
    border: 'border-red-300 dark:border-red-700',
  },
  orange: {
    text: 'text-orange-700 dark:text-orange-300',
    bg: 'bg-orange-50 dark:bg-orange-950',
    border: 'border-orange-300 dark:border-orange-700',
  },
  yellow: {
    text: 'text-yellow-800 dark:text-yellow-200',
    bg: 'bg-yellow-50 dark:bg-yellow-950',
    border: 'border-yellow-300 dark:border-yellow-700',
  },
  green: {
    text: 'text-green-700 dark:text-green-300',
    bg: 'bg-green-50 dark:bg-green-950',
    border: 'border-green-300 dark:border-green-700',
  },
  gray: {
    text: 'text-gray-700 dark:text-gray-300',
    bg: 'bg-gray-50 dark:bg-gray-900',
    border: 'border-gray-300 dark:border-gray-700',
  },
};

/**
 * Resolve a `system` preference against a media-query result. Pure
 * function so it is fully testable without window globals.
 */
export function resolveTheme(pref: ThemePreference, prefersDark: boolean): ResolvedTheme {
  if (pref === 'system') return prefersDark ? 'dark' : 'light';
  return pref;
}

export function isThemePreference(value: unknown): value is ThemePreference {
  return value === 'light' || value === 'dark' || value === 'system';
}

/**
 * Map an arbitrary trust state / signal level onto the canonical
 * semantic colors so the UI never invents a new color per state.
 */
export function semanticColorForTrustState(state: string | undefined | null): SemanticColor {
  switch (state) {
    case 'blocked_signal':
      return 'red';
    case 'freeze_signal':
      return 'orange';
    case 'caution_signal':
    case 'warn':
      return 'yellow';
    case 'ready_signal':
      return 'green';
    default:
      return 'gray';
  }
}
