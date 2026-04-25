// DSH-06 / DSH-07: 3-letter-system display layer.
//
// This module is *display-only*. It MUST NOT rename, alias, or merge canonical
// system IDs. The grouping exists to make the cockpit easier to scan while the
// authority boundary helper preserves each system's distinct role.
//
// Group ordering matches the operational loop:
//   input -> RIL -> CDE -> TLC -> PQX -> evals -> control -> SEL -> certification
// followed by replay/lineage/observability and the planning/dashboard loops.

export type DisplayGroupId =
  | 'execution'
  | 'eval_and_trust'
  | 'control_and_enforcement'
  | 'replay_lineage_observability'
  | 'governance_and_certification'
  | 'artifact_intelligence'
  | 'dashboard_and_ux'
  | 'roadmap_and_planning';

export interface DisplayGroup {
  id: DisplayGroupId;
  label: string;
  description: string;
  // Canonical system IDs in this group. IDs are NOT renamed; they appear here
  // exactly as the registry knows them.
  system_ids: string[];
}

// Authority boundary roles for the systems whose distinctness must be
// preserved per DSH-07. Each role is a one-line statement of canonical
// authority — the dashboard renders these labels next to the system card so
// the boundary is visible without inferring it from layout.
export const AUTHORITY_ROLES: Record<string, string> = {
  AEX: 'admits',
  PQX: 'executes',
  EVL: 'evaluates',
  TPA: 'adjudicates trust/policy',
  CDE: 'decides',
  SEL: 'enforces',
  REP: 'replays',
  LIN: 'links lineage',
  OBS: 'observes',
  SLO: 'manages reliability budget',
};

// The set of systems whose authority boundary is non-negotiable. The UI must
// always render a distinct card or detail row for each — never collapse.
export const AUTHORITY_BOUNDARY_SYSTEMS: ReadonlyArray<string> = Object.freeze([
  'AEX',
  'PQX',
  'EVL',
  'TPA',
  'CDE',
  'SEL',
  'REP',
  'LIN',
  'OBS',
  'SLO',
]);

export const DISPLAY_GROUPS: DisplayGroup[] = [
  {
    id: 'execution',
    label: 'Execution',
    description: 'Admits work, executes bounded changes, runs the harness.',
    system_ids: ['AEX', 'PQX', 'TLC', 'HNX', 'RQX', 'RDX'],
  },
  {
    id: 'eval_and_trust',
    label: 'Eval and Trust',
    description: 'Assesses artifacts and adjudicates trust/policy gates.',
    system_ids: ['EVL', 'TPA', 'MAP', 'RIL'],
  },
  {
    id: 'control_and_enforcement',
    label: 'Control and Enforcement',
    description: 'CDE decides, SEL enforces. No other system shares this authority.',
    system_ids: ['CDE', 'SEL', 'BRM', 'FRE'],
  },
  {
    id: 'replay_lineage_observability',
    label: 'Replay, Lineage, Observability',
    description: 'Replays runs, links lineage, observes the system over time.',
    system_ids: ['REP', 'LIN', 'OBS', 'SLO', 'XRL'],
  },
  {
    id: 'governance_and_certification',
    label: 'Governance and Certification',
    description: 'Governance authority and done-certification surface.',
    system_ids: ['GOV', 'DCL', 'SAL', 'SAS', 'SHA'],
  },
  {
    id: 'artifact_intelligence',
    label: 'Artifact Intelligence',
    description: 'Memory compaction, decision economics, the artifact bus.',
    system_ids: ['MCL', 'DEM', 'DBB', 'ABX'],
  },
  {
    id: 'dashboard_and_ux',
    label: 'Dashboard and UX',
    description: 'Operator-facing surfaces. Control surface, not decoration.',
    system_ids: [],
  },
  {
    id: 'roadmap_and_planning',
    label: 'Roadmap and Planning',
    description: 'Roadmap generation, next-step extraction, reconciliation.',
    system_ids: ['NSX', 'PRG', 'RSM', 'PRA', 'LCE'],
  },
];

// Look up the display group for a canonical system ID. Returns null when the
// system has no declared group — callers should render it under an "Other"
// bucket rather than guessing.
export function groupForSystem(system_id: string): DisplayGroup | null {
  for (const g of DISPLAY_GROUPS) {
    if (g.system_ids.includes(system_id)) return g;
  }
  return null;
}

// Authority role for a canonical system ID. Returns null when the system is
// not in the authority-boundary set; the UI should render no role label for
// such systems rather than fabricating one.
export function authorityRoleFor(system_id: string): string | null {
  return AUTHORITY_ROLES[system_id] ?? null;
}

// Group a list of system records by display group. Systems not assigned to
// any declared group land in `ungrouped`. Canonical IDs are preserved.
export function partitionByDisplayGroup<T extends { system_id: string }>(
  systems: T[]
): { groups: Array<{ group: DisplayGroup; systems: T[] }>; ungrouped: T[] } {
  const buckets = new Map<DisplayGroupId, T[]>();
  for (const g of DISPLAY_GROUPS) buckets.set(g.id, []);
  const ungrouped: T[] = [];

  for (const sys of systems) {
    const g = groupForSystem(sys.system_id);
    if (g) buckets.get(g.id)!.push(sys);
    else ungrouped.push(sys);
  }

  const groups = DISPLAY_GROUPS
    .map((g) => ({ group: g, systems: buckets.get(g.id) ?? [] }))
    .filter((entry) => entry.systems.length > 0);

  return { groups, ungrouped };
}
