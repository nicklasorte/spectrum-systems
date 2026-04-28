/**
 * D3L-MASTER-01 Phase 7 — theme helper tests.
 *
 * Pins:
 *   - resolveTheme('system', prefersDark) follows the system preference.
 *   - STATUS_CLASSES preserve red/orange/yellow/green/gray semantics.
 *   - semanticColorForTrustState maps known signal labels to colors.
 */
import {
  isThemePreference,
  resolveTheme,
  semanticColorForTrustState,
  STATUS_CLASSES,
} from '@/lib/theme';

describe('resolveTheme', () => {
  it('returns the explicit preference when not system', () => {
    expect(resolveTheme('light', true)).toBe('light');
    expect(resolveTheme('dark', false)).toBe('dark');
  });

  it('follows the media query when preference is system', () => {
    expect(resolveTheme('system', true)).toBe('dark');
    expect(resolveTheme('system', false)).toBe('light');
  });
});

describe('isThemePreference', () => {
  it('accepts only the canonical strings', () => {
    expect(isThemePreference('light')).toBe(true);
    expect(isThemePreference('dark')).toBe(true);
    expect(isThemePreference('system')).toBe(true);
    expect(isThemePreference('rainbow')).toBe(false);
    expect(isThemePreference(null)).toBe(false);
    expect(isThemePreference(undefined)).toBe(false);
  });
});

describe('STATUS_CLASSES preserves semantic colors across themes', () => {
  it('red → red text both light and dark', () => {
    expect(STATUS_CLASSES.red.text).toContain('text-red-700');
    expect(STATUS_CLASSES.red.text).toContain('dark:text-red-300');
  });

  it('green → green text both light and dark', () => {
    expect(STATUS_CLASSES.green.text).toContain('text-green-700');
    expect(STATUS_CLASSES.green.text).toContain('dark:text-green-300');
  });

  it('every semantic color carries text/bg/border classes', () => {
    for (const color of ['red', 'orange', 'yellow', 'green', 'gray'] as const) {
      const c = STATUS_CLASSES[color];
      expect(c.text).toContain(color);
      expect(c.bg).toContain(color);
      expect(c.border).toContain(color);
      expect(c.text).toContain('dark:');
      expect(c.bg).toContain('dark:');
      expect(c.border).toContain('dark:');
    }
  });
});

describe('semanticColorForTrustState', () => {
  it.each([
    ['blocked_signal', 'red'],
    ['freeze_signal', 'orange'],
    ['caution_signal', 'yellow'],
    ['warn', 'yellow'],
    ['ready_signal', 'green'],
    [undefined, 'gray'],
    ['unknown_signal', 'gray'],
  ])('maps %s -> %s', (state, expected) => {
    expect(semanticColorForTrustState(state as string | undefined)).toBe(expected);
  });
});
