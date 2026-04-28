/**
 * @jest-environment node
 *
 * D3L-MASTER-01 Phase 2 — recompute pipeline route tests.
 *
 * Focus: contract over the response body and the persisted pipeline
 * summary artifact. The python steps are stubbed via spawn so we exercise
 * the orchestration logic, not the underlying scripts.
 */
import fs from 'fs';
import os from 'os';
import path from 'path';
import { EventEmitter } from 'events';

const spawnMock = jest.fn();
jest.mock('node:child_process', () => ({
  spawn: spawnMock,
}));

type SpawnArgs = { code: number | null; produced?: { repoRoot: string; rel: string; payload?: string } };

function makeChild({ code }: SpawnArgs): EventEmitter {
  const emitter = new EventEmitter();
  const stdout = new EventEmitter();
  const stderr = new EventEmitter();
  (emitter as unknown as { stdout: EventEmitter }).stdout = stdout;
  (emitter as unknown as { stderr: EventEmitter }).stderr = stderr;
  (emitter as unknown as { kill: () => void }).kill = () => {};
  process.nextTick(() => {
    emitter.emit('close', code);
  });
  return emitter;
}

function setupRepo(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'd3l-recompute-'));
  fs.mkdirSync(path.join(dir, 'artifacts', 'tls'), { recursive: true });
  fs.mkdirSync(path.join(dir, 'scripts'), { recursive: true });
  // Make graph validation script "exist" so it isn't skipped.
  fs.writeFileSync(path.join(dir, 'scripts', 'build_system_graph_validation_report.py'), '# stub');
  return dir;
}

function writeValidPriority(repo: string): void {
  const payload = {
    schema_version: 'tls-04.v1',
    phase: 'TLS-04',
    priority_order: [],
    penalties: [],
    ranked_systems: [],
    global_ranked_systems: [],
    top_5: [
      {
        rank: 1,
        system_id: 'EVL',
        classification: 'active',
        score: 1,
        action: 'x',
        why_now: 'y',
        trust_gap_signals: [],
        dependencies: { upstream: [], downstream: [] },
        unlocks: [],
        finish_definition: '',
        next_prompt: '',
        trust_state: 'caution_signal',
      },
    ],
    requested_candidate_set: [],
    requested_candidate_ranking: [],
    ambiguous_requested_candidates: [],
    generated_at: new Date().toISOString(),
  };
  fs.writeFileSync(
    path.join(repo, 'artifacts', 'system_dependency_priority_report.json'),
    JSON.stringify(payload),
  );
}

function writeValidContract(repo: string): void {
  const contract = {
    artifact_type: 'd3l_registry_contract',
    phase: 'D3L-MASTER-01',
    schema_version: 'd3l-master-01.v1',
    source_artifact: 'artifacts/tls/system_registry_dependency_graph.json',
    active_system_ids: ['EVL'],
    future_system_ids: [],
    deprecated_or_merged_system_ids: [],
    excluded_ids: [],
    ranking_universe: ['EVL'],
    maturity_universe: ['EVL'],
    forbidden_node_examples: ['H01'],
    rules: [],
  };
  fs.writeFileSync(
    path.join(repo, 'artifacts', 'tls', 'd3l_registry_contract.json'),
    JSON.stringify(contract),
  );
}

describe('recompute-graph route (D3L-MASTER-01 Phase 2)', () => {
  const originalRepoRoot = process.env.REPO_ROOT;
  const originalVercel = process.env.VERCEL;

  beforeEach(() => {
    spawnMock.mockReset();
  });

  afterEach(() => {
    if (originalRepoRoot === undefined) delete process.env.REPO_ROOT;
    else process.env.REPO_ROOT = originalRepoRoot;
    if (originalVercel === undefined) delete process.env.VERCEL;
    else process.env.VERCEL = originalVercel;
    jest.resetModules();
  });

  it('full success: writes recompute summary artifact and returns success', async () => {
    delete process.env.VERCEL;
    const repo = setupRepo();
    writeValidPriority(repo);
    writeValidContract(repo);
    process.env.REPO_ROOT = repo;
    spawnMock.mockImplementation(() => makeChild({ code: 0 }));

    const { POST } = await import('@/app/api/recompute-graph/route');
    const res = await POST();
    const body = await res.json();
    expect(body.status).toBe('recompute_success_signal');
    expect(body.failing_command).toBeNull();
    expect(body.stale_after_recompute).toBe(false);

    const summaryPath = path.join(repo, 'artifacts', 'tls', 'd3l_recompute_pipeline.json');
    expect(fs.existsSync(summaryPath)).toBe(true);
    const summary = JSON.parse(fs.readFileSync(summaryPath, 'utf-8'));
    expect(summary.artifact_type).toBe('d3l_recompute_pipeline');
    expect(summary.status).toBe('recompute_success_signal');
    expect(Array.isArray(summary.commands)).toBe(true);
  });

  it('partial failure: priority step fails ⇒ recompute_failed_signal, no later steps', async () => {
    delete process.env.VERCEL;
    const repo = setupRepo();
    writeValidContract(repo);
    process.env.REPO_ROOT = repo;
    let calls = 0;
    spawnMock.mockImplementation(() => {
      calls += 1;
      // First step (priority) fails with non-zero exit code.
      return makeChild({ code: calls === 1 ? 2 : 0 });
    });

    const { POST } = await import('@/app/api/recompute-graph/route');
    const res = await POST();
    const body = await res.json();
    expect(body.status).toBe('recompute_failed_signal');
    expect(body.failing_command).not.toBeNull();
    expect(calls).toBe(1);

    const summaryPath = path.join(repo, 'artifacts', 'tls', 'd3l_recompute_pipeline.json');
    expect(fs.existsSync(summaryPath)).toBe(true);
    const summary = JSON.parse(fs.readFileSync(summaryPath, 'utf-8'));
    expect(summary.status).toBe('recompute_failed_signal');
  });

  it('graph stale after recompute: success status but stale_after_recompute=true', async () => {
    delete process.env.VERCEL;
    const repo = setupRepo();
    // Write a stale priority artifact (2018) and contract; spawn will succeed
    // but the freshness gate will mark the result stale.
    writeValidContract(repo);
    fs.writeFileSync(
      path.join(repo, 'artifacts', 'system_dependency_priority_report.json'),
      JSON.stringify({
        schema_version: 'tls-04.v1',
        phase: 'TLS-04',
        priority_order: [],
        penalties: [],
        ranked_systems: [],
        global_ranked_systems: [],
        top_5: [
          {
            rank: 1,
            system_id: 'EVL',
            classification: 'active',
            score: 1,
            action: 'x',
            why_now: 'y',
            trust_gap_signals: [],
            dependencies: { upstream: [], downstream: [] },
            unlocks: [],
            finish_definition: '',
            next_prompt: '',
            trust_state: 'caution_signal',
          },
        ],
        requested_candidate_set: [],
        requested_candidate_ranking: [],
        ambiguous_requested_candidates: [],
        generated_at: '2018-01-01T00:00:00Z',
      }),
    );
    process.env.REPO_ROOT = repo;
    spawnMock.mockImplementation(() => makeChild({ code: 0 }));

    const { POST } = await import('@/app/api/recompute-graph/route');
    const res = await POST();
    const body = await res.json();
    expect(body.status).toBe('recompute_success_signal');
    expect(body.stale_after_recompute).toBe(true);
  });

  it('vercel runtime: returns recompute_unavailable_signal without spawning', async () => {
    process.env.VERCEL = '1';
    const repo = setupRepo();
    process.env.REPO_ROOT = repo;
    spawnMock.mockImplementation(() => makeChild({ code: 0 }));

    const { POST } = await import('@/app/api/recompute-graph/route');
    const res = await POST();
    const body = await res.json();
    expect(body.status).toBe('recompute_unavailable_signal');
    expect(spawnMock.mock.calls.length).toBe(0);
  });
});
