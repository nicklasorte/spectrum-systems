/**
 * D3L-DATA-REGISTRY-01 Phase 7 — OC bottleneck loader tests.
 *
 * The dashboard never fabricates a bottleneck. The loader consumes the
 * OC-ALL-01 governed artifacts (dashboard_truth_projection v1.0.0 or
 * operational_closure_bundle v1.0.0) and surfaces unavailable /
 * invalid_schema / stale_proof / conflict_proof / ambiguous states
 * explicitly.
 */
import fs from 'fs';
import os from 'os';
import path from 'path';
import { loadOcBottleneck } from '@/lib/ocBottleneck';

function tmpRepo(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'oc-bottleneck-'));
}

const VALID_PROJECTION = {
  artifact_type: 'dashboard_truth_projection',
  schema_version: '1.0.0',
  projection_id: 'dtp-test-1',
  audit_timestamp: '2026-04-28T12:00:00Z',
  current_status: 'block',
  latest_proof_ref: 'lpb-test-1',
  owning_system: 'EVL',
  reason_code: 'EVAL_COVERAGE_INSUFFICIENT',
  bottleneck_category: 'eval',
  next_safe_action: 'attach eval evidence to TLS-FIX-EVL bundle',
  freshness_status: 'fresh',
  alignment_status: 'aligned',
};

const VALID_BUNDLE = {
  artifact_type: 'operational_closure_bundle',
  schema_version: '1.0.0',
  bundle_id: 'ocb-test-1',
  audit_timestamp: '2026-04-28T12:00:00Z',
  overall_status: 'block',
  current_bottleneck: { category: 'eval', reason_code: 'EVAL_COVERAGE_INSUFFICIENT' },
  owning_system: 'EVL',
  supporting_proof_ref: 'lpb-test-1',
  dashboard_alignment: 'aligned',
  fast_trust_gate_sufficiency: 'sufficient',
  next_work_item: { work_item_id: 'OC-NEXT-1', selection_status: 'selected' },
  justifying_signal_or_failure: 'EVAL_COVERAGE_INSUFFICIENT',
  evidence_refs: {
    proof_intake_ref: null,
    bottleneck_classification_ref: null,
    dashboard_projection_ref: null,
    closure_packet_ref: null,
    fast_trust_gate_ref: null,
    work_selection_ref: null,
  },
  non_authority_assertions: ['advisory_only'],
};

function writeProjection(repo: string, payload: unknown): void {
  const target = path.join(repo, 'artifacts/operational_closure/dashboard_truth_projection.json');
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, JSON.stringify(payload));
}

function writeBundle(repo: string, payload: unknown): void {
  const target = path.join(repo, 'artifacts/operational_closure/operational_closure_bundle.json');
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, JSON.stringify(payload));
}

describe('loadOcBottleneck', () => {
  let prevRepoRoot: string | undefined;

  beforeEach(() => {
    prevRepoRoot = process.env.REPO_ROOT;
  });
  afterEach(() => {
    if (prevRepoRoot === undefined) delete process.env.REPO_ROOT;
    else process.env.REPO_ROOT = prevRepoRoot;
  });

  it('returns unavailable when neither artifact is on disk', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const result = loadOcBottleneck();
    expect(result.state).toBe('unavailable');
    expect(result.card).toBeNull();
    expect(result.reason).toMatch(/not present/);
    expect(result.sources).toContain('artifacts/operational_closure/dashboard_truth_projection.json');
    expect(result.sources).toContain('artifacts/operational_closure/operational_closure_bundle.json');
  });

  it('returns invalid_schema when dashboard_truth_projection shape is wrong', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    writeProjection(repo, { artifact_type: 'dashboard_truth_projection', current_status: 'pass' });
    const result = loadOcBottleneck();
    expect(result.state).toBe('invalid_schema');
    expect(result.card).toBeNull();
  });

  it('returns ok with a populated card from a valid dashboard_truth_projection', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    writeProjection(repo, VALID_PROJECTION);
    const result = loadOcBottleneck();
    expect(result.state).toBe('ok');
    expect(result.card?.overall_status).toBe('block');
    expect(result.card?.category).toBe('eval');
    expect(result.card?.owning_system).toBe('EVL');
    expect(result.card?.reason_code).toBe('EVAL_COVERAGE_INSUFFICIENT');
    expect(result.card?.next_safe_action).toMatch(/attach eval evidence/);
    expect(result.card?.source_artifact_type).toBe('dashboard_truth_projection');
  });

  it('returns stale_proof when projection freshness_status=stale', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    writeProjection(repo, { ...VALID_PROJECTION, freshness_status: 'stale' });
    const result = loadOcBottleneck();
    expect(result.state).toBe('stale_proof');
    // Card still populated for the warnings panel.
    expect(result.card?.warnings).toEqual(expect.arrayContaining(['freshness_status=stale']));
  });

  it('returns conflict_proof when projection alignment_status=drifted', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    writeProjection(repo, { ...VALID_PROJECTION, alignment_status: 'drifted' });
    const result = loadOcBottleneck();
    expect(result.state).toBe('conflict_proof');
    expect(result.card?.warnings).toEqual(expect.arrayContaining(['alignment_status=drifted']));
  });

  it('returns conflict_proof when projection alignment_status=corrupt', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    writeProjection(repo, { ...VALID_PROJECTION, alignment_status: 'corrupt' });
    const result = loadOcBottleneck();
    expect(result.state).toBe('conflict_proof');
  });

  it('returns conflict_proof when projection alignment_status=missing', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    writeProjection(repo, { ...VALID_PROJECTION, alignment_status: 'missing' });
    const result = loadOcBottleneck();
    expect(result.state).toBe('conflict_proof');
  });

  it('returns ambiguous when projection bottleneck_category=unknown', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    writeProjection(repo, { ...VALID_PROJECTION, bottleneck_category: 'unknown' });
    const result = loadOcBottleneck();
    expect(result.state).toBe('ambiguous');
  });

  it('returns ambiguous when projection current_status=unknown', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    writeProjection(repo, { ...VALID_PROJECTION, current_status: 'unknown' });
    const result = loadOcBottleneck();
    expect(result.state).toBe('ambiguous');
  });

  it('falls back to operational_closure_bundle when projection is absent', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    writeBundle(repo, VALID_BUNDLE);
    const result = loadOcBottleneck();
    expect(result.state).toBe('ok');
    expect(result.card?.source_artifact_type).toBe('operational_closure_bundle');
    expect(result.card?.owning_system).toBe('EVL');
    expect(result.card?.next_safe_action).toBe('OC-NEXT-1');
  });

  it('bundle dashboard_alignment=drifted classifies as conflict_proof', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    writeBundle(repo, { ...VALID_BUNDLE, dashboard_alignment: 'drifted' });
    const result = loadOcBottleneck();
    expect(result.state).toBe('conflict_proof');
    expect(result.card?.warnings).toEqual(expect.arrayContaining(['dashboard_alignment=drifted']));
  });

  it('bundle invalid shape returns invalid_schema', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    writeBundle(repo, { artifact_type: 'operational_closure_bundle', overall_status: 'pass' });
    const result = loadOcBottleneck();
    expect(result.state).toBe('invalid_schema');
  });

  it('prefers projection over bundle when both are present', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    writeProjection(repo, VALID_PROJECTION);
    writeBundle(repo, { ...VALID_BUNDLE, owning_system: 'TPA' });
    const result = loadOcBottleneck();
    expect(result.state).toBe('ok');
    expect(result.card?.source_artifact_type).toBe('dashboard_truth_projection');
    expect(result.card?.owning_system).toBe('EVL');
  });

  it('does not invent a bottleneck when bundle next_work_item.selection_status=unknown', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    writeBundle(repo, { ...VALID_BUNDLE, next_work_item: { work_item_id: null, selection_status: 'unknown' } });
    const result = loadOcBottleneck();
    expect(result.state).toBe('ambiguous');
    expect(result.card?.next_safe_action).toBe('unknown');
  });
});
