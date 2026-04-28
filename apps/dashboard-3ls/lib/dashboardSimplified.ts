import type { PriorityArtifactLoadResult, RankedSystem, RequestedCandidateRow } from './artifactLoader';
import type { RegistryGraphContract } from './registryContract';

export interface TopRecommendationCard {
  /** Always populated: the system or label as it appears in the artifact. */
  system_id: string;
  /** True iff system_id is a registry-active node and may render as a graph node. */
  is_registry_backed: boolean;
  /** Registry purpose/role, when registry-backed. */
  registry_role: string | null;
  what_to_fix: string;
  why_now: string;
  safe_prompt_scope: string;
  prerequisite_systems: string[];
  boundary_warning: string;
  /** Producing artifact path the recommendation derives from. */
  supporting_artifact: string;
  /** Optional next-bundle / next-prompt hint, surfaced as plain text only. */
  next_bundle_text: string | null;
  rank: number;
}

export interface QueueItem {
  bundle_id: string;
  title: string;
  why_it_matters: string;
  dependency_count: number;
  next_safe_action: string;
  /** Optional registry-backed system the queue card lines up with (Top 3 link). */
  linked_top3_system_id: string | null;
  /** Always present so the Roadmap tab can show full step list. */
  steps: string[];
}

export interface QueueGroups {
  queue_1_immediate_next_bundle: QueueItem[];
  queue_2_next_hardening_bundle: QueueItem[];
  queue_3_next_review_fix_bundle: QueueItem[];
  queue_4_later_work: QueueItem[];
}

export interface RoadmapBundle {
  bundle_id: string;
  steps: string[];
  rationale?: string;
}

export interface RoadmapEntry {
  id: string;
  title?: string;
  why_it_matters?: string;
  dependencies?: string[];
}

export interface RoadmapArtifact {
  safe_bundles?: RoadmapBundle[];
  entries?: RoadmapEntry[];
}

const PRIORITY_ARTIFACT_PATH = 'artifacts/system_dependency_priority_report.json';

function fallbackBoundary(): string {
  return 'Boundary warning missing in artifact; do_not_touch not provided by source artifact.';
}

function isContractUsable(contract: RegistryGraphContract | null): contract is RegistryGraphContract {
  return !!contract && Array.isArray(contract.allowed_active_node_ids) && contract.allowed_active_node_ids.length > 0;
}

function rankedSystemToCard(
  row: RankedSystem,
  contract: RegistryGraphContract | null,
  fallbackRank: number,
): TopRecommendationCard {
  const isBacked = isContractUsable(contract) ? contract.allowed_active_node_ids.includes(row.system_id) : true;
  const registryRow = isContractUsable(contract)
    ? (contract.active_systems ?? []).find((entry) => entry.system_id === row.system_id) ?? null
    : null;
  return {
    system_id: row.system_id,
    is_registry_backed: isBacked,
    registry_role: registryRow?.purpose ?? null,
    what_to_fix: row.action,
    why_now: row.why_now,
    safe_prompt_scope: row.next_prompt || `recommendation: scope hardening to ${row.system_id}`,
    prerequisite_systems: row.dependencies?.upstream ?? [],
    boundary_warning: registryRow
      ? `do_not_touch: hold to ${row.system_id} authority boundary; do not extend scope to ${row.dependencies?.downstream?.join(', ') || 'downstream owners'}.`
      : fallbackBoundary(),
    supporting_artifact: PRIORITY_ARTIFACT_PATH,
    next_bundle_text: row.next_prompt || null,
    rank: row.rank ?? fallbackRank,
  };
}

function requestedCandidateToCard(
  row: RequestedCandidateRow,
  contract: RegistryGraphContract | null,
): TopRecommendationCard {
  const isBacked = isContractUsable(contract) ? contract.allowed_active_node_ids.includes(row.system_id) : true;
  const registryRow = isContractUsable(contract)
    ? (contract.active_systems ?? []).find((entry) => entry.system_id === row.system_id) ?? null
    : null;
  return {
    system_id: row.system_id,
    is_registry_backed: isBacked,
    registry_role: registryRow?.purpose ?? null,
    what_to_fix: row.recommended_action,
    why_now: row.why_now,
    safe_prompt_scope: row.minimum_safe_prompt_scope,
    prerequisite_systems: row.prerequisite_systems,
    boundary_warning: row.risk_if_built_before_prerequisites || fallbackBoundary(),
    supporting_artifact: PRIORITY_ARTIFACT_PATH,
    next_bundle_text: row.safe_next_action || null,
    rank: row.requested_rank,
  };
}

export interface TopThreeResult {
  /**
   * All Top 3 cards in artifact order. Some may carry
   * `is_registry_backed: false`; those must render as text-only recommendations
   * (not graph nodes). The dashboard never re-orders this list.
   */
  cards: TopRecommendationCard[];
  /** system_ids in cards that ARE registry-active (eligible for graph overlay). */
  registry_backed_system_ids: string[];
  /** system_ids in cards that are NOT registry-active (text-only). */
  non_registry_system_ids: string[];
  warning?: string;
  recompute_command?: string;
}

/**
 * Extract the Top 3 cards from the priority artifact. Registry-backed cards
 * may drive the graph overlay; non-registry-backed cards are returned as
 * `non_registry_cards` so the UI surfaces them as text-only recommendations
 * with an explicit warning.
 *
 * Source preference:
 *   1. `top_5` (canonical TLS Top 3 surface)
 *   2. `requested_candidate_ranking` (fallback when top_5 is empty)
 */
export function extractTopThreeRecommendations(
  priority: PriorityArtifactLoadResult | null,
  contract: RegistryGraphContract | null = null,
): TopThreeResult {
  const empty = (warning: string, recompute?: string): TopThreeResult => ({
    cards: [],
    registry_backed_system_ids: [],
    non_registry_system_ids: [],
    warning,
    recompute_command: recompute,
  });

  if (!priority) return empty('Top 3 unavailable: priority loader returned no result.');
  if (priority.state === 'missing') {
    return empty(`Top 3 unavailable: ${priority.reason ?? 'priority artifact missing'}.`, priority.recompute_command);
  }
  if (priority.state === 'invalid_schema') {
    return empty(`Top 3 unavailable: priority artifact invalid (${priority.reason ?? 'shape_mismatch'}).`, priority.recompute_command);
  }
  if (!priority.payload) {
    return empty('Top 3 unavailable: priority artifact carried no payload.', priority.recompute_command);
  }

  const top5: RankedSystem[] = priority.payload.top_5 ?? [];
  const requested: RequestedCandidateRow[] = priority.payload.requested_candidate_ranking ?? [];

  let cards: TopRecommendationCard[] = [];
  if (top5.length > 0) {
    cards = top5.slice(0, 3).map((row, idx) => rankedSystemToCard(row, contract, idx + 1));
  } else if (requested.length > 0) {
    cards = requested.slice(0, 3).map((row) => requestedCandidateToCard(row, contract));
  }

  const registryBackedIds = cards.filter((c) => c.is_registry_backed).map((c) => c.system_id);
  const nonRegistryIds = cards.filter((c) => !c.is_registry_backed).map((c) => c.system_id);

  let warning: string | undefined;
  if (cards.length < 3) {
    warning = `Top 3 partial: ranking artifact contains ${cards.length} entries (expected 3).`;
  } else if (nonRegistryIds.length > 0) {
    warning = `Top 3 includes ${nonRegistryIds.length} non-registry recommendation(s) (${nonRegistryIds.join(', ')}); rendered as text-only.`;
  }
  if (priority.state === 'stale') {
    warning = `Top 3 stale: ${warning ?? 'artifact older than freshness threshold'}.`;
  }
  if (priority.state === 'blocked_signal') {
    warning = `Top 3 carries blocked_signal: ${warning ?? 'control authority must adjudicate before acting'}.`;
  }
  if (priority.state === 'freeze_signal') {
    warning = `Top 3 carries freeze_signal: ${warning ?? 'control authority must adjudicate before acting'}.`;
  }

  return {
    cards,
    registry_backed_system_ids: registryBackedIds,
    non_registry_system_ids: nonRegistryIds,
    warning,
    recompute_command: priority.recompute_command,
  };
}

function entryById(entries: RoadmapEntry[]): Map<string, RoadmapEntry> {
  return new Map(entries.map((entry) => [entry.id, entry]));
}

function classifyBundle(bundleId: string): keyof QueueGroups {
  if (bundleId.endsWith('01')) return 'queue_1_immediate_next_bundle';
  if (bundleId.endsWith('02')) return 'queue_2_next_hardening_bundle';
  if (bundleId.endsWith('03')) return 'queue_3_next_review_fix_bundle';
  return 'queue_4_later_work';
}

function findLinkedTop3System(
  bundleSteps: string[],
  topThreeSystemIds: ReadonlyArray<string>,
): string | null {
  for (const step of bundleSteps) {
    for (const systemId of topThreeSystemIds) {
      if (step.includes(systemId)) return systemId;
    }
  }
  return null;
}

export interface QueueResult {
  queues: QueueGroups;
  warning?: string;
}

/**
 * Build the compressed leverage queue from the TLS roadmap artifact.
 * Each queue card is one short summary; full details remain in the
 * Roadmap tab. The card may reference a registry-active Top 3 system,
 * but bundle IDs / roadmap labels never become graph nodes.
 */
export function buildLeverageQueueFromRoadmap(
  roadmap: RoadmapArtifact | null,
  topThreeSystemIds: ReadonlyArray<string> = [],
): QueueResult {
  const empty: QueueGroups = {
    queue_1_immediate_next_bundle: [],
    queue_2_next_hardening_bundle: [],
    queue_3_next_review_fix_bundle: [],
    queue_4_later_work: [],
  };

  if (!roadmap?.safe_bundles?.length || !roadmap.entries?.length) {
    return {
      queues: empty,
      warning: 'Leverage queue unavailable: tls roadmap artifact missing required safe_bundles/entries.',
    };
  }

  const byId = entryById(roadmap.entries);

  for (const bundle of roadmap.safe_bundles) {
    const firstStep = bundle.steps[0];
    const firstEntry = firstStep ? byId.get(firstStep) : undefined;
    const group = classifyBundle(bundle.bundle_id);
    const dependencies = firstEntry?.dependencies ?? [];
    empty[group].push({
      bundle_id: bundle.bundle_id,
      title: firstEntry?.title ?? bundle.bundle_id,
      why_it_matters: firstEntry?.why_it_matters ?? bundle.rationale ?? 'Why-it-matters not present in artifact.',
      dependency_count: dependencies.length,
      next_safe_action: `Run bundle ${bundle.bundle_id} in declared order: ${bundle.steps.slice(0, 2).join(' -> ')}${bundle.steps.length > 2 ? ' …' : ''}`,
      linked_top3_system_id: findLinkedTop3System(bundle.steps, topThreeSystemIds),
      steps: bundle.steps,
    });
  }

  return { queues: empty };
}
