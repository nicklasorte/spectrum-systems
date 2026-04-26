/**
 * D3L-01 — Tests for the TLS-04 priority artifact loader.
 *
 * The loader is the dashboard's only entry point into the priority report.
 * The dashboard MUST NOT compute ranking, so these tests pin the loader's
 * fail-closed contract: missing / stale / invalid / blocked / freeze states
 * must be surfaced explicitly instead of silently returning data.
 */
import fs from 'fs';
import os from 'os';
import path from 'path';
import { loadPriorityArtifact } from '@/lib/artifactLoader';

function tmpRepo(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'tls-loader-'));
}

const VALID_PAYLOAD = {
  schema_version: 'tls-04.v1',
  phase: 'TLS-04',
  priority_order: ['a', 'b', 'c', 'd', 'e'],
  penalties: ['deprecated', 'unknown'],
  ranked_systems: [],
  top_5: [
    {
      rank: 1,
      system_id: 'EVL',
      classification: 'active_system',
      score: 100,
      action: 'harden_authority',
      why_now: 'on canonical loop',
      trust_gap_signals: ['missing_eval'],
      dependencies: { upstream: ['PQX'], downstream: ['TPA'] },
      unlocks: ['CDE'],
      finish_definition: 'close(missing_eval)',
      next_prompt: 'Run TLS-FIX-EVL',
      trust_state: 'blocked_signal',
    },
  ],
};

describe('loadPriorityArtifact', () => {
  let prevRepoRoot: string | undefined;

  beforeEach(() => {
    prevRepoRoot = process.env.REPO_ROOT;
  });
  afterEach(() => {
    if (prevRepoRoot === undefined) delete process.env.REPO_ROOT;
    else process.env.REPO_ROOT = prevRepoRoot;
  });

  it('returns missing when artifact does not exist', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const result = loadPriorityArtifact();
    expect(result.state).toBe('missing');
    expect(result.payload).toBeNull();
    expect(result.reason).toMatch(/not_found/);
  });

  it('returns ok when artifact is fresh and well-formed', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const target = path.join(repo, 'artifacts/system_dependency_priority_report.json');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, JSON.stringify({ ...VALID_PAYLOAD, generated_at: new Date().toISOString() }));
    const result = loadPriorityArtifact();
    expect(result.state).toBe('ok');
    expect(result.payload?.top_5?.[0].system_id).toBe('EVL');
  });

  it('returns invalid_schema when shape is wrong', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const target = path.join(repo, 'artifacts/system_dependency_priority_report.json');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, JSON.stringify({ schema_version: 'something_else' }));
    const result = loadPriorityArtifact();
    expect(result.state).toBe('invalid_schema');
    expect(result.payload).toBeNull();
  });

  it('returns invalid_schema when JSON is malformed', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const target = path.join(repo, 'artifacts/system_dependency_priority_report.json');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, '{not json');
    const result = loadPriorityArtifact();
    expect(result.state).toBe('invalid_schema');
    expect(result.reason).toMatch(/parse_failed/);
  });

  it('returns stale when artifact is older than threshold', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const target = path.join(repo, 'artifacts/system_dependency_priority_report.json');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    const stale = new Date('2025-01-01T00:00:00Z');
    fs.writeFileSync(target, JSON.stringify({ ...VALID_PAYLOAD, generated_at: stale.toISOString() }));
    const result = loadPriorityArtifact(undefined, new Date('2026-04-25T00:00:00Z'));
    expect(result.state).toBe('stale');
    expect(result.payload?.top_5?.length).toBe(1);
  });

  it('returns blocked_signal when control_signal declares blocked_signal', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const target = path.join(repo, 'artifacts/system_dependency_priority_report.json');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(
      target,
      JSON.stringify({
        ...VALID_PAYLOAD,
        generated_at: new Date().toISOString(),
        control_signal: 'blocked_signal',
      }),
    );
    const result = loadPriorityArtifact();
    expect(result.state).toBe('blocked_signal');
  });

  it('returns freeze_signal when control_signal declares freeze_signal', () => {
    const repo = tmpRepo();
    process.env.REPO_ROOT = repo;
    const target = path.join(repo, 'artifacts/system_dependency_priority_report.json');
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(
      target,
      JSON.stringify({
        ...VALID_PAYLOAD,
        generated_at: new Date().toISOString(),
        control_signal: 'freeze_signal',
      }),
    );
    const result = loadPriorityArtifact();
    expect(result.state).toBe('freeze_signal');
  });
});
