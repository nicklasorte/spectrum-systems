/**
 * D3L-DATA-REGISTRY-01 — OC bottleneck loader tests.
 *
 * The dashboard never fabricates a bottleneck. The loader must surface
 * unavailable / invalid_schema / stale_proof / conflict_proof / ambiguous
 * states explicitly so the operator can tell when the OC layer has not
 * yet been wired in.
 */
import fs from 'fs';
import os from 'os';
import path from 'path';
import { loadOcBottleneck } from '@/lib/ocBottleneck';

function tmpRepo(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'oc-bottleneck-'));
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

  it('returns unavailable when the artifact is not on disk', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const result = loadOcBottleneck();
    expect(result.state).toBe('unavailable');
    expect(result.card).toBeNull();
    expect(result.reason).toMatch(/not present/);
  });

  it('returns invalid_schema when shape does not match', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const target = path.join(repo, 'artifacts/operational_closure/oc_bottleneck_steering.json');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, JSON.stringify({ artifact_type: 'wrong_kind' }));
    const result = loadOcBottleneck();
    expect(result.state).toBe('invalid_schema');
    expect(result.card).toBeNull();
  });

  it('returns ok and populated card on a well-formed artifact', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const target = path.join(repo, 'artifacts/operational_closure/oc_bottleneck_steering.json');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(
      target,
      JSON.stringify({
        artifact_type: 'oc_bottleneck_steering',
        generated_at: '2026-04-28T00:00:00Z',
        bottleneck: {
          category: 'eval_coverage',
          owner_system: 'EVL',
          reason_code: 'missing_required_eval',
          evidence_status: 'artifact_backed',
          next_safe_action: 'attach eval evidence to TLS-FIX-EVL bundle',
          warnings: [],
        },
      }),
    );
    const result = loadOcBottleneck();
    expect(result.state).toBe('ok');
    expect(result.card?.owner_system).toBe('EVL');
    expect(result.card?.category).toBe('eval_coverage');
  });

  it('returns stale_proof when the artifact carries stale_proof=true', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const target = path.join(repo, 'artifacts/operational_closure/oc_bottleneck_steering.json');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(
      target,
      JSON.stringify({
        artifact_type: 'oc_bottleneck_steering',
        bottleneck: { category: 'eval_coverage', owner_system: 'EVL', reason_code: 'x', evidence_status: 'partial', next_safe_action: 'y', stale_proof: true },
      }),
    );
    const result = loadOcBottleneck();
    expect(result.state).toBe('stale_proof');
    expect(result.card?.owner_system).toBe('EVL');
  });

  it('returns conflict_proof when the artifact carries conflict_proof=true', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const target = path.join(repo, 'artifacts/operational_closure/oc_bottleneck_steering.json');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(
      target,
      JSON.stringify({
        artifact_type: 'oc_bottleneck_steering',
        bottleneck: { category: 'trust_handoff', owner_system: 'TPA', reason_code: 'x', evidence_status: 'partial', next_safe_action: 'y', conflict_proof: true },
      }),
    );
    const result = loadOcBottleneck();
    expect(result.state).toBe('conflict_proof');
  });

  it('returns ambiguous when the artifact carries ambiguous=true', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const target = path.join(repo, 'artifacts/operational_closure/oc_bottleneck_steering.json');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(
      target,
      JSON.stringify({
        artifact_type: 'oc_bottleneck_steering',
        bottleneck: { category: 'control_input', owner_system: null, reason_code: 'x', evidence_status: 'missing', next_safe_action: 'y', ambiguous: true },
      }),
    );
    const result = loadOcBottleneck();
    expect(result.state).toBe('ambiguous');
    expect(result.card?.owner_system).toBeNull();
  });
});
