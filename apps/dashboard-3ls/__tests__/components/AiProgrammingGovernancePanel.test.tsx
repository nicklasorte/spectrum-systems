import React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import DashboardPage from '@/app/page';

global.fetch = jest.fn();

type Leg = 'AEX' | 'PQX' | 'EVL' | 'TPA' | 'CDE' | 'SEL';
type Obs = 'present' | 'partial' | 'missing' | 'unknown';

function legCell(state: Obs, sources: string[] = ['artifact://x']) {
  return {
    observation: state,
    source_artifacts_used: state === 'missing' || state === 'unknown' ? [] : sources,
    reason_codes: [`${state}_for_test`],
  };
}

function buildLegs(overrides: Partial<Record<Leg, Obs>>) {
  return {
    AEX: legCell(overrides.AEX ?? 'present'),
    PQX: legCell(overrides.PQX ?? 'present'),
    EVL: legCell(overrides.EVL ?? 'present'),
    TPA: legCell(overrides.TPA ?? 'present'),
    CDE: legCell(overrides.CDE ?? 'present'),
    SEL: legCell(overrides.SEL ?? 'present'),
  };
}

function buildBlock(workItems: Array<{
  work_item_id: string;
  agent: string;
  title: string;
  legs: Partial<Record<Leg, Obs>>;
}>) {
  const summarised = workItems.map((w) => {
    const legs = buildLegs(w.legs);
    const order: Leg[] = ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'];
    let firstMissing: Leg | null = null;
    for (const leg of order) {
      if (legs[leg].observation === 'missing') {
        firstMissing = leg;
        break;
      }
    }
    const status = firstMissing
      ? 'BLOCK'
      : order.some((leg) => legs[leg].observation !== 'present')
        ? 'WARN'
        : 'PASS';
    return {
      work_item_id: w.work_item_id,
      agent: w.agent,
      title: w.title,
      status,
      first_missing_leg: firstMissing,
      weakest_leg: firstMissing,
      core_loop_complete: status === 'PASS',
      hard_block_reason: firstMissing ? `${firstMissing}_signal_absent` : null,
      next_recommended_input: firstMissing ? `route to ${firstMissing}` : null,
      legs: order.map((leg) => ({
        leg,
        observation: legs[leg].observation,
        source_artifacts_used: legs[leg].source_artifacts_used,
        reason_codes: legs[leg].reason_codes,
      })),
    };
  });
  const blocked = summarised.filter((w) => w.status === 'BLOCK');
  const present = (leg: Leg) => summarised.filter((w) => w.legs.find((l) => l.leg === leg)!.observation === 'present').length;
  const missing = (leg: Leg) => summarised.filter((w) => w.legs.find((l) => l.leg === leg)!.observation === 'missing').length;
  return {
    overall_status: blocked.length > 0 ? 'BLOCK' : summarised.some((w) => w.status === 'WARN') ? 'WARN' : 'PASS',
    aex_present_count: present('AEX'),
    pqx_present_count: present('PQX'),
    evl_present_count: present('EVL'),
    tpa_present_count: present('TPA'),
    cde_present_count: present('CDE'),
    sel_present_count: present('SEL'),
    missing_by_leg: {
      AEX: missing('AEX'),
      PQX: missing('PQX'),
      EVL: missing('EVL'),
      TPA: missing('TPA'),
      CDE: missing('CDE'),
      SEL: missing('SEL'),
    },
    blocked_work_items: blocked,
    weakest_leg: blocked[0]?.first_missing_leg ?? null,
    codex_count: summarised.filter((w) => w.agent === 'codex').length,
    claude_count: summarised.filter((w) => w.agent === 'claude').length,
    core_loop_complete_count: summarised.filter((w) => w.core_loop_complete).length,
    work_items: summarised,
    source_artifacts_used: ['artifacts/dashboard_metrics/ai_programming_governed_path_record.json'],
    warnings: [],
    data_source: 'artifact_store',
    core_loop_summary: {
      total_work_item_count: summarised.length,
      pass_count: summarised.filter((w) => w.status === 'PASS').length,
      warn_count: summarised.filter((w) => w.status === 'WARN').length,
      block_count: blocked.length,
    },
  };
}

function setupFetch(intelligencePayload: Record<string, unknown> = {}) {
  (global.fetch as jest.Mock).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/health')) return Promise.resolve({ ok: true, json: async () => ({ warnings: [] }) });
    if (url.includes('/api/intelligence')) return Promise.resolve({ ok: true, json: async () => intelligencePayload });
    if (url.includes('/api/priority')) return Promise.resolve({ ok: true, json: async () => ({ state: 'missing', payload: null }) });
    if (url.includes('/api/system-flow')) return Promise.resolve({ ok: true, json: async () => ({ state: 'ok', payload: { canonical_loop: ['AEX','PQX','EVL','TPA','CDE','SEL'], canonical_overlays: ['REP','LIN','OBS','SLO'], active_systems: [] } }) });
    if (url.includes('/api/system-graph')) return Promise.resolve({ ok: true, json: async () => ({ graph_state: 'caution_signal', generated_at: '2026-04-28T00:00:00.000Z', source_mix: { artifact_store: 1, repo_registry: 0, derived: 0, stub_fallback: 0, missing: 0 }, trust_posture: 'caution_signal', nodes: [], edges: [], focus_systems: [], failure_path: [], missing_artifacts: [], warnings: [], replay_commands: [] }) });
    if (url.includes('/api/tls-roadmap')) return Promise.resolve({ ok: true, json: async () => ({ state: 'missing', payload: null, table_markdown: null }) });
    return Promise.resolve({ ok: false, status: 404, json: async () => ({}) });
  });
}

describe('AEX-PQX-DASH-01-REFINE — AI Programming Governance panel', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('renders all six legs (AEX, PQX, EVL, TPA, CDE, SEL) for the top blocked item', async () => {
    const block = buildBlock([
      {
        work_item_id: 'AIP-CODEX-X',
        agent: 'codex',
        title: 'codex work',
        legs: { SEL: 'missing' },
      },
    ]);
    setupFetch({ ai_programming_governed_path: block });
    render(<DashboardPage />);
    fireEvent.click(await screen.findByTestId('tab-diagnostics'));
    const section = await screen.findByTestId('ai-programming-governance-section');
    ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'].forEach((leg) => {
      expect(within(section).getByTestId(`ai-prog-leg-${leg}`)).toBeInTheDocument();
    });
  });

  const legs: Array<'AEX' | 'PQX' | 'EVL' | 'TPA' | 'CDE' | 'SEL'> = [
    'AEX',
    'PQX',
    'EVL',
    'TPA',
    'CDE',
    'SEL',
  ];

  legs.forEach((leg) => {
    it(`missing ${leg} flips overall status to BLOCK`, async () => {
      const block = buildBlock([
        {
          work_item_id: `AIP-MISS-${leg}`,
          agent: 'claude',
          title: `missing ${leg}`,
          legs: { [leg]: 'missing' as const },
        },
      ]);
      setupFetch({ ai_programming_governed_path: block });
      render(<DashboardPage />);
      fireEvent.click(await screen.findByTestId('tab-diagnostics'));
      await waitFor(() =>
        expect(screen.getByTestId('ai-prog-overall-status')).toHaveTextContent('BLOCK'),
      );
      expect(screen.getByTestId(`ai-prog-missing-${leg}`)).toHaveTextContent(`${leg}=1`);
    });
  });

  it('PASS only when all six legs are present for every work item', async () => {
    const block = buildBlock([
      {
        work_item_id: 'AIP-PASS-1',
        agent: 'codex',
        title: 'all green',
        legs: {},
      },
    ]);
    setupFetch({ ai_programming_governed_path: block });
    render(<DashboardPage />);
    fireEvent.click(await screen.findByTestId('tab-diagnostics'));
    await waitFor(() =>
      expect(screen.getByTestId('ai-prog-overall-status')).toHaveTextContent('PASS'),
    );
  });

  it('exposes Codex count, Claude count, complete count, and weakest leg', async () => {
    const block = buildBlock([
      { work_item_id: 'AIP-CX-1', agent: 'codex', title: 'a', legs: {} },
      { work_item_id: 'AIP-CL-1', agent: 'claude', title: 'b', legs: { TPA: 'missing' } },
    ]);
    setupFetch({ ai_programming_governed_path: block });
    render(<DashboardPage />);
    fireEvent.click(await screen.findByTestId('tab-diagnostics'));
    await waitFor(() => expect(screen.getByTestId('ai-prog-codex-count')).toHaveTextContent('1'));
    expect(screen.getByTestId('ai-prog-claude-count')).toHaveTextContent('1');
    expect(screen.getByTestId('ai-prog-complete-count')).toHaveTextContent('1');
    expect(screen.getByTestId('ai-prog-weakest-leg')).toHaveTextContent('TPA');
  });

  it('renders top 3 blocked work items with a six-leg row each', async () => {
    const block = buildBlock([
      { work_item_id: 'B-1', agent: 'codex', title: 't1', legs: { AEX: 'missing' } },
      { work_item_id: 'B-2', agent: 'codex', title: 't2', legs: { PQX: 'missing' } },
      { work_item_id: 'B-3', agent: 'claude', title: 't3', legs: { CDE: 'missing' } },
      { work_item_id: 'B-4', agent: 'claude', title: 't4', legs: { SEL: 'missing' } },
    ]);
    setupFetch({ ai_programming_governed_path: block });
    render(<DashboardPage />);
    fireEvent.click(await screen.findByTestId('tab-diagnostics'));
    await waitFor(() => expect(screen.getByTestId('ai-prog-blocked-list')).toBeInTheDocument());
    const items = screen.getAllByTestId('ai-prog-blocked-item');
    expect(items.length).toBe(3);
    items.forEach((item) => {
      expect(within(item).getAllByTestId('ai-prog-leg-row').length).toBe(1);
    });
  });

  it('does not include the forbidden authority verb "Execute" in the panel text', async () => {
    const block = buildBlock([
      { work_item_id: 'AIP-PASS', agent: 'codex', title: 'fine', legs: {} },
    ]);
    setupFetch({ ai_programming_governed_path: block });
    render(<DashboardPage />);
    fireEvent.click(await screen.findByTestId('tab-diagnostics'));
    const section = await screen.findByTestId('ai-programming-governance-section');
    expect(/\bExecute\b/.test(section.textContent ?? '')).toBe(false);
  });

  it('falls back gracefully when the AI programming block is missing', async () => {
    setupFetch({});
    render(<DashboardPage />);
    fireEvent.click(await screen.findByTestId('tab-diagnostics'));
    await waitFor(() => expect(screen.getByTestId('ai-programming-governance-section')).toBeInTheDocument());
    expect(screen.getByTestId('ai-prog-unavailable')).toBeInTheDocument();
  });
});
