/**
 * D3L-DATA-REGISTRY-01 — Human-readable trust state label tests.
 *
 * Internal *_signal codes must map to operator-facing labels (Blocked,
 * Frozen, Caution, Ready, Unknown) without ever silently renaming an
 * unknown code as Ready.
 */
import { humanTrustLabel, humanTrustState } from '@/lib/humanStateLabels';

describe('humanTrustLabel', () => {
  it('maps blocked_signal → Blocked', () => {
    expect(humanTrustLabel('blocked_signal')).toBe('Blocked');
  });

  it('maps freeze_signal / freeze / frozen → Frozen', () => {
    expect(humanTrustLabel('freeze_signal')).toBe('Frozen');
    expect(humanTrustLabel('freeze')).toBe('Frozen');
    expect(humanTrustLabel('frozen')).toBe('Frozen');
  });

  it('maps caution_signal / warn / warning / degraded → Caution', () => {
    expect(humanTrustLabel('caution_signal')).toBe('Caution');
    expect(humanTrustLabel('warning')).toBe('Caution');
    expect(humanTrustLabel('warn')).toBe('Caution');
    expect(humanTrustLabel('degraded_signal')).toBe('Caution');
  });

  it('maps trusted_signal / ready / pass → Ready', () => {
    expect(humanTrustLabel('trusted_signal')).toBe('Ready');
    expect(humanTrustLabel('ready')).toBe('Ready');
    expect(humanTrustLabel('pass')).toBe('Ready');
    expect(humanTrustLabel('ready_signal')).toBe('Ready');
  });

  it('maps unknown_signal / missing / invalid → Unknown', () => {
    expect(humanTrustLabel('unknown_signal')).toBe('Unknown');
    expect(humanTrustLabel('missing')).toBe('Unknown');
    expect(humanTrustLabel('invalid')).toBe('Unknown');
  });

  it('falls through to Unknown for unrecognised codes (never silently renames to Ready)', () => {
    expect(humanTrustLabel('something_we_have_never_seen')).toBe('Unknown');
    expect(humanTrustLabel('')).toBe('Unknown');
    expect(humanTrustLabel(null)).toBe('Unknown');
    expect(humanTrustLabel(undefined)).toBe('Unknown');
  });
});

describe('humanTrustState', () => {
  it('preserves the raw code in the diagnostic field', () => {
    const state = humanTrustState('blocked_signal');
    expect(state.label).toBe('Blocked');
    expect(state.raw).toBe('blocked_signal');
  });

  it('preserves the raw code even when label is Unknown', () => {
    const state = humanTrustState('weird_code');
    expect(state.label).toBe('Unknown');
    expect(state.raw).toBe('weird_code');
    expect(state.description).toMatch(/unrecognised/);
  });

  it('returns critical tone for Blocked / Frozen', () => {
    expect(humanTrustState('blocked_signal').tone).toBe('critical');
    expect(humanTrustState('freeze_signal').tone).toBe('critical');
  });

  it('returns warning tone for Caution', () => {
    expect(humanTrustState('caution_signal').tone).toBe('warning');
  });

  it('returns ok tone for Ready', () => {
    expect(humanTrustState('trusted_signal').tone).toBe('ok');
  });
});
