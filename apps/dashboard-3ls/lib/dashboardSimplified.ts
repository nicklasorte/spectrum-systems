import type { PriorityArtifactLoadResult, RequestedCandidateRow } from './artifactLoader';

export interface TopRecommendationCard {
  system_id: string;
  what_to_fix: string;
  why_now: string;
  safe_prompt_scope: string;
  prerequisite_systems: string[];
  boundary_warning: string;
}

export interface QueueItem {
  bundle_id: string;
  title: string;
  why_it_matters: string;
  dependency: string;
  next_safe_action: string;
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

function rowToCard(row: RequestedCandidateRow): TopRecommendationCard {
  return {
    system_id: row.system_id,
    what_to_fix: row.recommended_action,
    why_now: row.why_now,
    safe_prompt_scope: row.minimum_safe_prompt_scope,
    prerequisite_systems: row.prerequisite_systems,
    boundary_warning:
      row.risk_if_built_before_prerequisites ||
      'Boundary warning missing in artifact; do_not_touch not provided by source artifact.',
  };
}

export function extractTopThreeRecommendations(
  priority: PriorityArtifactLoadResult | null,
): { cards: TopRecommendationCard[]; warning?: string } {
  if (!priority || priority.state !== 'ok' || !priority.payload) {
    return { cards: [], warning: 'Top 3 unavailable: artifacts/system_dependency_priority_report.json missing or invalid.' };
  }

  const rows = (priority.payload.requested_candidate_ranking ?? []).slice(0, 3);
  if (rows.length < 3) {
    return {
      cards: rows.map(rowToCard),
      warning: 'Top 3 unavailable: requested_candidate_ranking has fewer than 3 rows.',
    };
  }

  return { cards: rows.map(rowToCard) };
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

export function buildLeverageQueueFromRoadmap(
  roadmap: RoadmapArtifact | null,
): { queues: QueueGroups; warning?: string } {
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
    empty[group].push({
      bundle_id: bundle.bundle_id,
      title: firstEntry?.title ?? bundle.bundle_id,
      why_it_matters: firstEntry?.why_it_matters ?? bundle.rationale ?? 'Why-it-matters not present in artifact.',
      dependency: (firstEntry?.dependencies ?? []).join(', ') || 'none_declared',
      next_safe_action: `Run bundle ${bundle.bundle_id} in declared order: ${bundle.steps.join(' -> ')}`,
      steps: bundle.steps,
    });
  }

  return { queues: empty };
}
