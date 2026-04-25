import type { RepoSnapshot, SystemState } from './types';

export interface SystemSignals {
  total_files: number | 'unknown';
  runtime_modules: number | 'unknown';
  test_count: number | 'unknown';
  schema_count: number | 'unknown';
  operational_signals: Array<{ title: string; status: string; detail: string }>;
  hard_gate_status: string;
  schema_backed_systems: number | 'unknown';
  test_backed_systems: number | 'unknown';
  docs_only_systems: number | 'unknown';
  domain_state: Record<string, { status: string }> | 'unknown';
  warnings: string[];
}

export function deriveSystemSignals(args: {
  repoSnapshot: RepoSnapshot | null;
  systemState: SystemState | null;
}): SystemSignals {
  const warnings: string[] = [];

  let total_files: number | 'unknown' = 'unknown';
  let runtime_modules: number | 'unknown' = 'unknown';
  let test_count: number | 'unknown' = 'unknown';
  let schema_count: number | 'unknown' = 'unknown';
  let operational_signals: Array<{ title: string; status: string; detail: string }> = [];
  let hard_gate_status = 'unknown';

  if (args.repoSnapshot) {
    const rc = args.repoSnapshot.root_counts;
    total_files = rc.files_total;
    runtime_modules = rc.runtime_modules;
    test_count = rc.tests;
    schema_count = rc.schemas;
    operational_signals = args.repoSnapshot.operational_signals;
    hard_gate_status = args.repoSnapshot.key_state.hard_gate_status_record.pass_fail;
  } else {
    warnings.push('repo counts unavailable: repo_snapshot.json not found');
  }

  let schema_backed_systems: number | 'unknown' = 'unknown';
  let test_backed_systems: number | 'unknown' = 'unknown';
  let docs_only_systems: number | 'unknown' = 'unknown';
  let domain_state: Record<string, { status: string }> | 'unknown' = 'unknown';

  if (args.systemState) {
    schema_backed_systems = args.systemState.repo_reality.schema_backed_components.length;
    test_backed_systems = args.systemState.repo_reality.test_backed_systems.length;
    docs_only_systems = args.systemState.repo_reality.docs_only_systems.length;
    domain_state = Object.fromEntries(
      Object.entries(args.systemState.domain_state).map(([k, v]) => [k, { status: v.status }])
    );
  } else {
    warnings.push('system breakdown unavailable: system_state.json not found');
  }

  return {
    total_files,
    runtime_modules,
    test_count,
    schema_count,
    operational_signals,
    hard_gate_status,
    schema_backed_systems,
    test_backed_systems,
    docs_only_systems,
    domain_state,
    warnings,
  };
}
