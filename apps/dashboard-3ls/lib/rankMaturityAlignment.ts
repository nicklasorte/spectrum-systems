// D3L-MASTER-01 Phase 5 — ranking ↔ maturity alignment.
//
// The dashboard never re-ranks based on maturity. This helper checks
// whether the Top 3 correlates with the lowest-maturity active systems
// and, if not, surfaces a warning for the operator. Mismatch DOES NOT
// mutate ranking — control authority lives in CDE.

import type { MaturityRow } from './maturity';
import type { RankingRow } from './ranking';

export interface AlignmentResult {
  ok: boolean;
  warning: string | null;
  /**
   * Top 3 system_ids whose maturity level is HIGHER than the lowest
   * maturity level present in the universe — i.e. there are systems
   * with worse maturity that did not make Top 3.
   */
  top_3_above_lowest_maturity: string[];
  /** Lowest maturity level observed across the universe. */
  lowest_maturity_level: number | null;
  /** Highest priority Top 3 levels for context. */
  top_3_levels: Array<{ system_id: string; level: number | null }>;
  /** Notes (e.g. "no data" / "Top 3 short"). */
  notes: string[];
}

const EMPTY: AlignmentResult = {
  ok: false,
  warning: null,
  top_3_above_lowest_maturity: [],
  lowest_maturity_level: null,
  top_3_levels: [],
  notes: [],
};

/**
 * Compute alignment between Top 3 and maturity. Mismatch is a warning,
 * never a re-ranking. Empty / partial inputs return ok=true with notes —
 * we don't want a missing maturity report to look like a control alarm.
 */
export function evaluateRankMaturityAlignment(
  top3: RankingRow[],
  maturityRows: MaturityRow[],
): AlignmentResult {
  if (top3.length === 0 || maturityRows.length === 0) {
    return {
      ...EMPTY,
      ok: true,
      notes: [
        ...(top3.length === 0 ? ['top_3_empty'] : []),
        ...(maturityRows.length === 0 ? ['maturity_universe_empty'] : []),
      ],
    };
  }

  const maturityById = new Map(maturityRows.map((row) => [row.system_id, row]));
  const lowestLevel = Math.min(...maturityRows.map((r) => r.level));
  const top3Levels = top3.map((row) => ({
    system_id: row.system_id,
    level: maturityById.get(row.system_id)?.level ?? null,
  }));

  // A Top 3 entry is "above lowest" iff its maturity level is strictly
  // greater than the global minimum. That means there are systems with
  // worse maturity not in Top 3 — an alignment mismatch.
  const above = top3Levels
    .filter((row) => typeof row.level === 'number' && (row.level as number) > lowestLevel)
    .map((row) => row.system_id);

  // Special case: Top 3 entry has no maturity data at all (level=null).
  // That is a mismatch by missing-data rather than ordering — flag it
  // with a separate note rather than counting it as "above".
  const missingLevel = top3Levels.filter((row) => row.level === null).map((row) => row.system_id);

  const notes: string[] = [];
  if (missingLevel.length > 0) {
    notes.push(`top_3_without_maturity:${missingLevel.join(',')}`);
  }

  let warning: string | null = null;
  let ok = above.length === 0 && missingLevel.length === 0;
  if (above.length > 0) {
    warning =
      `Top 3 contains systems above the lowest maturity (${lowestLevel}). ` +
      `Above-lowest: ${above.join(', ')}. Mismatch is informational; control authority (CDE) decides.`;
  } else if (missingLevel.length > 0) {
    warning =
      `Top 3 contains systems with no maturity data (${missingLevel.join(', ')}). ` +
      `Mismatch is informational; control authority (CDE) decides.`;
    ok = false;
  }

  return {
    ok,
    warning,
    top_3_above_lowest_maturity: above,
    lowest_maturity_level: lowestLevel,
    top_3_levels: top3Levels,
    notes,
  };
}
