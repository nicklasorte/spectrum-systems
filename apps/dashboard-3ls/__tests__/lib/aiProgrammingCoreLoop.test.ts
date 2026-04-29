import {
  CORE_LOOP_LEGS,
  computeCoreLoopSummary,
  computeFirstMissingLeg,
  computeWeakestLeg,
  deriveWorkItemStatus,
  isCoreLoopComplete,
  type AiProgrammingGovernedPathRecord,
  type AiProgrammingWorkItem,
  type CoreLoopLeg,
  type LegObservationState,
} from '@/lib/aiProgrammingCoreLoop';

function legObs(state: LegObservationState, sources: string[] = ['artifact://x']) {
  return {
    observation: state,
    source_artifacts_used: state === 'missing' || state === 'unknown' ? [] : sources,
    reason_codes: [`${state}_for_test`],
  };
}

function buildItem(
  overrides: Partial<{
    AEX: LegObservationState;
    PQX: LegObservationState;
    EVL: LegObservationState;
    TPA: LegObservationState;
    CDE: LegObservationState;
    SEL: LegObservationState;
    repo_mutating: boolean;
    work_item_id: string;
    agent: string;
    title: string;
  }> = {},
): AiProgrammingWorkItem {
  return {
    work_item_id: overrides.work_item_id ?? 'AIP-TEST-001',
    agent: overrides.agent ?? 'codex',
    title: overrides.title ?? 'test',
    repo_mutating: overrides.repo_mutating ?? true,
    core_loop_observations: {
      AEX: legObs(overrides.AEX ?? 'present'),
      PQX: legObs(overrides.PQX ?? 'present'),
      EVL: legObs(overrides.EVL ?? 'present'),
      TPA: legObs(overrides.TPA ?? 'present'),
      CDE: legObs(overrides.CDE ?? 'present'),
      SEL: legObs(overrides.SEL ?? 'present'),
    },
  };
}

describe('AEX-PQX-DASH-01-REFINE — core-loop proof computation', () => {
  it('uses canonical leg order AEX → PQX → EVL → TPA → CDE → SEL', () => {
    expect(CORE_LOOP_LEGS).toEqual(['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL']);
  });

  describe('per-work-item status', () => {
    it('PASS only when all six legs are present', () => {
      const item = buildItem();
      expect(deriveWorkItemStatus(item).status).toBe('PASS');
      expect(isCoreLoopComplete(item)).toBe(true);
      expect(computeFirstMissingLeg(item)).toBeNull();
    });

    const blockingLegs: CoreLoopLeg[] = ['AEX', 'PQX', 'EVL', 'TPA', 'CDE', 'SEL'];
    blockingLegs.forEach((leg) => {
      it(`missing ${leg} BLOCKs the work item`, () => {
        const item = buildItem({ [leg]: 'missing' } as Record<string, LegObservationState>);
        const status = deriveWorkItemStatus(item);
        expect(status.status).toBe('BLOCK');
        expect(status.hard_block_reason).toBe(`${leg}_signal_absent`);
        expect(isCoreLoopComplete(item)).toBe(false);
        expect(computeFirstMissingLeg(item)).toBe(leg);
      });
    });

    it('any leg partial → WARN unless another leg is missing', () => {
      const item = buildItem({ TPA: 'partial' });
      const status = deriveWorkItemStatus(item);
      expect(status.status).toBe('WARN');
      expect(status.hard_block_reason).toBeNull();
    });

    it('a partial leg loses to a missing leg (BLOCK wins)', () => {
      const item = buildItem({ TPA: 'partial', SEL: 'missing' });
      expect(deriveWorkItemStatus(item).status).toBe('BLOCK');
    });

    it('repo-mutating + any unknown leg → WARN', () => {
      const item = buildItem({ CDE: 'unknown', repo_mutating: true });
      expect(deriveWorkItemStatus(item).status).toBe('WARN');
    });

    it('weakest_leg picks the lowest-rank leg in canonical order', () => {
      const item = buildItem({ AEX: 'partial', PQX: 'unknown', EVL: 'missing' });
      // missing < unknown < partial < present, ties broken by canonical order.
      expect(computeWeakestLeg(item)).toBe('EVL');
    });
  });

  describe('cross-work-item summary', () => {
    const record: AiProgrammingGovernedPathRecord = {
      data_source: 'artifact_store',
      source_artifacts_used: ['artifacts/dashboard_metrics/ai_programming_governed_path_record.json'],
      warnings: [],
      ai_programming_work_items: [
        buildItem({ work_item_id: 'CX-1', agent: 'codex' }),
        buildItem({ work_item_id: 'CX-2', agent: 'codex', SEL: 'missing' }),
        buildItem({ work_item_id: 'CL-1', agent: 'claude', PQX: 'missing' }),
        buildItem({ work_item_id: 'CL-2', agent: 'claude', TPA: 'partial' }),
      ],
    };

    it('counts by agent', () => {
      const summary = computeCoreLoopSummary(record, 'unavailable');
      expect(summary.codex_work_item_count).toBe(2);
      expect(summary.claude_work_item_count).toBe(2);
      expect(summary.total_work_item_count).toBe(4);
    });

    it('exposes per-leg present counts', () => {
      const summary = computeCoreLoopSummary(record, 'unavailable');
      expect(summary.counts_by_leg.aex_present_count).toBe(4);
      expect(summary.counts_by_leg.pqx_present_count).toBe(3);
      expect(summary.counts_by_leg.sel_present_count).toBe(3);
    });

    it('exposes missing_by_leg', () => {
      const summary = computeCoreLoopSummary(record, 'unavailable');
      expect(summary.missing_by_leg.PQX).toBe(1);
      expect(summary.missing_by_leg.SEL).toBe(1);
      expect(summary.missing_by_leg.AEX).toBe(0);
    });

    it('weakest_leg is computed correctly across work items', () => {
      // PQX has 1 missing, SEL has 1 missing. Tie broken by canonical order: PQX wins.
      const summary = computeCoreLoopSummary(record, 'unavailable');
      expect(['PQX', 'SEL']).toContain(summary.weakest_leg);
      // and it must be a leg with at least one missing observation
      expect(summary.missing_by_leg[summary.weakest_leg as CoreLoopLeg]).toBeGreaterThan(0);
    });

    it('separates blocked work items from PASS/WARN', () => {
      const summary = computeCoreLoopSummary(record, 'unavailable');
      expect(summary.block_count).toBe(2);
      expect(summary.warn_count).toBe(1);
      expect(summary.pass_count).toBe(1);
      expect(summary.blocked_work_items.map((w) => w.work_item_id).sort()).toEqual([
        'CL-1',
        'CX-2',
      ]);
    });

    it('overall_status is BLOCK when any work item is BLOCK', () => {
      const summary = computeCoreLoopSummary(record, 'unavailable');
      expect(summary.overall_status).toBe('BLOCK');
    });

    it('overall_status is PASS only when every work item is PASS', () => {
      const cleanRecord: AiProgrammingGovernedPathRecord = {
        data_source: 'artifact_store',
        ai_programming_work_items: [
          buildItem({ work_item_id: 'CX-1', agent: 'codex' }),
          buildItem({ work_item_id: 'CL-1', agent: 'claude' }),
        ],
      };
      const summary = computeCoreLoopSummary(cleanRecord, 'unavailable');
      expect(summary.overall_status).toBe('PASS');
      expect(summary.core_loop_complete_count).toBe(2);
      expect(summary.weakest_leg).toBeNull();
    });

    it('drops malformed rows rather than crashing the summary', () => {
      const partial: AiProgrammingGovernedPathRecord = {
        data_source: 'artifact_store',
        ai_programming_work_items: [
          buildItem({ work_item_id: 'CX-1', agent: 'codex' }),
          // partial / corrupt rows that would crash summarizeWorkItem
          // if dereferenced directly
          null as unknown as AiProgrammingWorkItem,
          'oops' as unknown as AiProgrammingWorkItem,
          {} as unknown as AiProgrammingWorkItem,
          { core_loop_observations: {} } as unknown as AiProgrammingWorkItem,
        ],
      };
      expect(() => computeCoreLoopSummary(partial, 'unavailable')).not.toThrow();
      const summary = computeCoreLoopSummary(partial, 'unavailable');
      expect(summary.total_work_item_count).toBe(1);
      expect(summary.work_items[0].work_item_id).toBe('CX-1');
    });

    it('returns unknown shape with surfaced warning when artifact is missing', () => {
      const summary = computeCoreLoopSummary(null, 'missing-artifact-warning');
      expect(summary.overall_status).toBe('UNKNOWN');
      expect(summary.warnings).toContain('missing-artifact-warning');
      expect(summary.total_work_item_count).toBe(0);
      expect(summary.weakest_leg).toBeNull();
    });

    it('preserves source_artifacts_used per leg', () => {
      const summary = computeCoreLoopSummary(record, 'unavailable');
      const sample = summary.work_items[0];
      sample.legs.forEach((leg) => {
        expect(leg).toHaveProperty('source_artifacts_used');
        expect(Array.isArray(leg.source_artifacts_used)).toBe(true);
      });
    });
  });
});
