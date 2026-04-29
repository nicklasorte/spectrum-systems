// AEX-PQX-DASH-01 — aiProgrammingGovernance helper tests.
//
// Verify fail-closed behaviour: missing artifact reports unknown counts (not 0)
// and Codex/Claude repo-mutating items with missing AEX or PQX render block.

import {
  computeGovernedPathSummary,
  computeWorkItemStatus,
  normalizeAgentType,
  normalizeWorkItem,
  type AiProgrammingGovernedPathRecord,
  type AiProgrammingWorkItem,
} from '@/lib/aiProgrammingGovernance';

function workItem(
  overrides: Partial<AiProgrammingWorkItem> = {},
): AiProgrammingWorkItem {
  return {
    work_item_id: overrides.work_item_id ?? 'AIPG-TEST-001',
    agent_type: overrides.agent_type ?? 'codex',
    repo_mutating: overrides.repo_mutating ?? true,
    aex_admission_observation: overrides.aex_admission_observation ?? 'present',
    pqx_execution_observation: overrides.pqx_execution_observation ?? 'present',
    eval_observation: overrides.eval_observation ?? 'present',
    control_signal_observation: overrides.control_signal_observation ?? 'present',
    enforcement_or_readiness_signal_observation:
      overrides.enforcement_or_readiness_signal_observation ?? 'present',
    lineage_observation: overrides.lineage_observation ?? 'present',
    bypass_risk: overrides.bypass_risk ?? 'none',
    next_recommended_input: overrides.next_recommended_input,
    source_artifacts_used: overrides.source_artifacts_used ?? ['some/source.json'],
    source_ref: overrides.source_ref,
    pr_ref: overrides.pr_ref,
    branch_ref: overrides.branch_ref,
    changed_files_count: overrides.changed_files_count,
  };
}

describe('aiProgrammingGovernance — agent normalization', () => {
  it('normalizes codex/claude/unknown into a fixed enum', () => {
    expect(normalizeAgentType('codex')).toBe('codex');
    expect(normalizeAgentType('CODEX')).toBe('codex');
    expect(normalizeAgentType('claude')).toBe('claude');
    expect(normalizeAgentType('Claude')).toBe('claude');
    expect(normalizeAgentType('grok')).toBe('unknown_ai_agent');
    expect(normalizeAgentType(undefined)).toBe('unknown_ai_agent');
  });

  it('falls back to unknown_ai_agent on a malformed work item', () => {
    const item = normalizeWorkItem({ work_item_id: 'X', agent_type: 'pilot' });
    expect(item).not.toBeNull();
    expect(item!.agent_type).toBe('unknown_ai_agent');
  });

  it('rejects work items missing work_item_id', () => {
    expect(normalizeWorkItem({})).toBeNull();
    expect(normalizeWorkItem(null)).toBeNull();
  });
});

describe('aiProgrammingGovernance — per-item status', () => {
  it('codex repo-mutating with AEX missing renders block', () => {
    const item = workItem({
      agent_type: 'codex',
      aex_admission_observation: 'missing',
      bypass_risk: 'aex_missing',
    });
    expect(computeWorkItemStatus(item)).toBe('block');
  });

  it('codex repo-mutating with PQX missing renders block', () => {
    const item = workItem({
      agent_type: 'codex',
      pqx_execution_observation: 'missing',
      bypass_risk: 'pqx_missing',
    });
    expect(computeWorkItemStatus(item)).toBe('block');
  });

  it('claude repo-mutating with AEX missing renders block', () => {
    const item = workItem({
      agent_type: 'claude',
      aex_admission_observation: 'missing',
      bypass_risk: 'aex_missing',
    });
    expect(computeWorkItemStatus(item)).toBe('block');
  });

  it('claude repo-mutating with PQX missing renders block', () => {
    const item = workItem({
      agent_type: 'claude',
      pqx_execution_observation: 'missing',
      bypass_risk: 'pqx_missing',
    });
    expect(computeWorkItemStatus(item)).toBe('block');
  });

  it('unknown ai agent with repo mutation and missing AEX/PQX renders block', () => {
    const item = workItem({
      agent_type: 'unknown_ai_agent',
      aex_admission_observation: 'missing',
      bypass_risk: 'aex_missing',
    });
    expect(computeWorkItemStatus(item)).toBe('block');
  });

  it('unknown ai agent with repo mutation and partial AEX/PQX renders warn', () => {
    const item = workItem({
      agent_type: 'unknown_ai_agent',
      aex_admission_observation: 'partial',
      pqx_execution_observation: 'partial',
      bypass_risk: 'unknown',
    });
    expect(computeWorkItemStatus(item)).toBe('warn');
  });

  it('codex with all evidence present and bypass_risk=none renders pass', () => {
    const item = workItem({ agent_type: 'codex' });
    expect(computeWorkItemStatus(item)).toBe('pass');
  });

  it('codex with partial AEX/PQX renders warn (not pass)', () => {
    const item = workItem({
      agent_type: 'codex',
      aex_admission_observation: 'partial',
      bypass_risk: 'unknown',
    });
    expect(computeWorkItemStatus(item)).toBe('warn');
  });

  it('codex with partial AEX and bypass_risk=none still renders warn (not pass)', () => {
    // Regression: an item whose AEX evidence is only partial must not slip
    // through to pass merely because bypass_risk happens to be 'none'.
    const item = workItem({
      agent_type: 'codex',
      aex_admission_observation: 'partial',
      pqx_execution_observation: 'present',
      bypass_risk: 'none',
    });
    expect(computeWorkItemStatus(item)).toBe('warn');
  });

  it('claude with partial PQX and bypass_risk=none still renders warn (not pass)', () => {
    const item = workItem({
      agent_type: 'claude',
      aex_admission_observation: 'present',
      pqx_execution_observation: 'partial',
      bypass_risk: 'none',
    });
    expect(computeWorkItemStatus(item)).toBe('warn');
  });

  it('repo_mutating=unknown for a known agent renders warn', () => {
    const item = workItem({
      agent_type: 'codex',
      repo_mutating: 'unknown',
    });
    expect(computeWorkItemStatus(item)).toBe('warn');
  });
});

describe('aiProgrammingGovernance — summary aggregation', () => {
  it('missing artifact degrades to status=unknown with unknown counts (not 0)', () => {
    const summary = computeGovernedPathSummary(null);
    expect(summary.status).toBe('unknown');
    expect(summary.total_ai_programming_work_items).toBe('unknown');
    expect(summary.codex_work_count).toBe('unknown');
    expect(summary.claude_work_count).toBe('unknown');
    expect(summary.governed_work_count).toBe('unknown');
    expect(summary.bypass_risk_count).toBe('unknown');
    expect(summary.unknown_path_count).toBe('unknown');
    expect(summary.warnings.some((w) => w.includes('ai_programming_governed_path_record'))).toBe(true);
  });

  it('any block-level item bubbles up to overall block', () => {
    const record: AiProgrammingGovernedPathRecord = {
      data_source: 'artifact_store',
      ai_programming_work_items: [
        workItem({ work_item_id: 'A', agent_type: 'codex' }),
        workItem({
          work_item_id: 'B',
          agent_type: 'claude',
          aex_admission_observation: 'missing',
          bypass_risk: 'aex_missing',
        }),
      ],
    };
    const summary = computeGovernedPathSummary(record);
    expect(summary.status).toBe('block');
    expect(summary.total_ai_programming_work_items).toBe(2);
    expect(summary.codex_work_count).toBe(1);
    expect(summary.claude_work_count).toBe(1);
  });

  it('top_attention_items prioritise block over warn over pass', () => {
    const record: AiProgrammingGovernedPathRecord = {
      data_source: 'artifact_store',
      ai_programming_work_items: [
        workItem({ work_item_id: 'PASS-1', agent_type: 'codex' }),
        workItem({
          work_item_id: 'WARN-1',
          agent_type: 'claude',
          aex_admission_observation: 'partial',
          bypass_risk: 'unknown',
        }),
        workItem({
          work_item_id: 'BLOCK-1',
          agent_type: 'codex',
          pqx_execution_observation: 'missing',
          bypass_risk: 'pqx_missing',
        }),
      ],
    };
    const summary = computeGovernedPathSummary(record);
    expect(summary.top_attention_items[0]?.work_item_id).toBe('BLOCK-1');
    expect(summary.top_attention_items[1]?.work_item_id).toBe('WARN-1');
    expect(summary.top_attention_items.find((i) => i.work_item_id === 'PASS-1')).toBeUndefined();
  });

  it('coerces malformed array fields to safe empty arrays (fail-closed)', () => {
    const malformed = {
      data_source: 42 as unknown as string,
      source_artifacts_used: 'not-an-array' as unknown as string[],
      warnings: { oops: true } as unknown as string[],
      reason_codes: null as unknown as string[],
      ai_programming_work_items: 'also-not-an-array' as unknown as never[],
    } as unknown as AiProgrammingGovernedPathRecord;
    const summary = computeGovernedPathSummary(malformed);
    expect(summary.data_source).toBe('unknown');
    expect(Array.isArray(summary.source_artifacts_used)).toBe(true);
    expect(summary.source_artifacts_used).toEqual([]);
    expect(Array.isArray(summary.warnings)).toBe(true);
    expect(summary.warnings).toEqual([]);
    expect(Array.isArray(summary.reason_codes)).toBe(true);
    expect(summary.reason_codes).toEqual([]);
    expect(summary.ai_programming_work_items).toEqual([]);
    // Empty work-item set degrades to status=unknown rather than throwing.
    expect(summary.status).toBe('unknown');
  });

  it('drops non-string entries from coerced array fields', () => {
    const dirty = {
      data_source: 'artifact_store',
      source_artifacts_used: ['ok.json', 42, null, 'also-ok.json'] as unknown as string[],
      warnings: ['warn1', undefined, 'warn2'] as unknown as string[],
      reason_codes: [1, 'rc-ok'] as unknown as string[],
      ai_programming_work_items: [],
    } as unknown as AiProgrammingGovernedPathRecord;
    const summary = computeGovernedPathSummary(dirty);
    expect(summary.source_artifacts_used).toEqual(['ok.json', 'also-ok.json']);
    expect(summary.warnings).toEqual(['warn1', 'warn2']);
    expect(summary.reason_codes).toEqual(['rc-ok']);
  });

  it('all items pass renders status=pass and reports concrete counts', () => {
    const record: AiProgrammingGovernedPathRecord = {
      data_source: 'artifact_store',
      ai_programming_work_items: [
        workItem({ work_item_id: 'A', agent_type: 'codex' }),
        workItem({ work_item_id: 'B', agent_type: 'claude' }),
      ],
    };
    const summary = computeGovernedPathSummary(record);
    expect(summary.status).toBe('pass');
    expect(summary.governed_work_count).toBe(2);
    expect(summary.aex_present_count).toBe(2);
    expect(summary.pqx_present_count).toBe(2);
    expect(summary.bypass_risk_count).toBe(0);
  });
});
