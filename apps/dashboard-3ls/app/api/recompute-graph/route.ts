import { NextResponse } from 'next/server';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { getRepoRoot, loadPriorityArtifact } from '@/lib/artifactLoader';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type RecomputeStatus = 'recompute_success_signal' | 'recompute_failed_signal' | 'recompute_unavailable_signal';

interface CommandResult {
  command: string[];
  description: string;
  code: number | null;
  stdout: string;
  stderr: string;
  timed_out: boolean;
  produced_artifact: string | null;
  produced_artifact_present_after: boolean;
}

interface RecomputeResponseBody {
  status: RecomputeStatus;
  started_at: string;
  completed_at: string;
  commands: CommandResult[];
  generated_artifacts: string[];
  skipped_artifacts: string[];
  artifacts_checked: string[];
  warnings: string[];
  failing_command: string[] | null;
  failure_reason: string | null;
  stale_after_recompute: boolean;
  error_message: string | null;
}

// D3L-DATA-REGISTRY-01: registry-active candidates only. The previous
// list (H01,RFX,MET,METS) included roadmap / batch labels that confused
// the operator about what the priority artifact actually scores.
const RECOMPUTE_CANDIDATES = 'HOP,RAX,RSM,CAP,SEC,EVL,OBS,SLO';

// Dashboard-critical artifacts the operator expects to see refreshed
// after a successful recompute. The route reports each as either
// generated (file timestamp updated) or skipped (script missing or
// step explicitly skipped).
const DASHBOARD_CRITICAL_ARTIFACTS = [
  'artifacts/system_dependency_priority_report.json',
  'artifacts/tls/system_dependency_priority_report.json',
  'artifacts/tls/system_registry_dependency_graph.json',
  'artifacts/tls/system_evidence_attachment.json',
  'artifacts/tls/system_candidate_classification.json',
  'artifacts/tls/system_trust_gap_report.json',
];

function runCommand(command: string[], cwd: string, timeoutMs: number): Promise<Pick<CommandResult, 'code' | 'stdout' | 'stderr' | 'timed_out'>> {
  return new Promise((resolve) => {
    const child = spawn(command[0], command.slice(1), { cwd, stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill('SIGKILL');
    }, timeoutMs);

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    child.on('error', (error) => {
      clearTimeout(timer);
      resolve({ code: 1, stdout, stderr: `${stderr}\n${error.message}`, timed_out: timedOut });
    });

    child.on('close', (code) => {
      clearTimeout(timer);
      resolve({ code, stdout, stderr, timed_out: timedOut });
    });
  });
}

function fileTimestamp(repoRoot: string, relativePath: string): number | null {
  try {
    return fs.statSync(path.join(repoRoot, relativePath)).mtime.getTime();
  } catch {
    return null;
  }
}

export async function POST() {
  const startedAt = new Date().toISOString();
  const startedAtMs = Date.parse(startedAt);
  const repoRoot = getRepoRoot();

  if (process.env.VERCEL === '1') {
    const completedAt = new Date().toISOString();
    const body: RecomputeResponseBody = {
      status: 'recompute_unavailable_signal',
      started_at: startedAt,
      completed_at: completedAt,
      commands: [],
      generated_artifacts: [],
      skipped_artifacts: DASHBOARD_CRITICAL_ARTIFACTS,
      artifacts_checked: DASHBOARD_CRITICAL_ARTIFACTS,
      warnings: [
        'vercel_runtime_detected:python_execution_disabled',
        `Run from repo root: python scripts/build_tls_dependency_priority.py --candidates ${RECOMPUTE_CANDIDATES} --fail-if-missing`,
        'Then: python scripts/build_dashboard_3ls_with_tls.py --skip-next-build',
      ],
      failing_command: null,
      failure_reason: 'serverless_runtime_no_python',
      stale_after_recompute: false,
      error_message: 'Recompute requires a node runtime with Python available; serverless deployment cannot execute the TLS pipeline.',
    };
    return NextResponse.json(body, { status: 200 });
  }

  // Step 1 — TLS priority artifact (also publishes the top-level path).
  // Step 2 — Dashboard TLS integration build (verifies all artifacts are
  //          present after the priority build; never starts next build).
  // Step 3 — Optional graph validation report (only if script exists).
  type Step = {
    description: string;
    command: string[];
    produced_artifact: string | null;
    skip_reason?: string;
  };

  const steps: Step[] = [
    {
      description: 'TLS dependency priority (registry-active candidates only)',
      command: [
        'python',
        'scripts/build_tls_dependency_priority.py',
        '--candidates',
        RECOMPUTE_CANDIDATES,
        '--fail-if-missing',
      ],
      produced_artifact: 'artifacts/system_dependency_priority_report.json',
    },
    {
      description: 'Dashboard 3LS / TLS integration verifier',
      command: [
        'python',
        'scripts/build_dashboard_3ls_with_tls.py',
        '--skip-next-build',
      ],
      produced_artifact: 'artifacts/system_dependency_priority_report.json',
    },
  ];

  const graphValidationScript = path.join(repoRoot, 'scripts', 'build_system_graph_validation_report.py');
  if (fs.existsSync(graphValidationScript)) {
    steps.push({
      description: 'Graph validation report',
      command: ['python', 'scripts/build_system_graph_validation_report.py'],
      produced_artifact: 'artifacts/tls/system_graph_validation_report.json',
    });
  } else {
    steps.push({
      description: 'Graph validation report (skipped: script missing)',
      command: ['python', 'scripts/build_system_graph_validation_report.py'],
      produced_artifact: 'artifacts/tls/system_graph_validation_report.json',
      skip_reason: 'missing_script',
    });
  }

  const warnings: string[] = [];
  const commandResults: CommandResult[] = [];
  const generated: string[] = [];
  const skipped: string[] = [];
  let failedResult: CommandResult | null = null;
  let failureReason: string | null = null;

  for (const step of steps) {
    if (step.skip_reason) {
      skipped.push(step.produced_artifact ?? step.description);
      warnings.push(`${step.skip_reason}:${step.command.join(' ')}`);
      commandResults.push({
        command: step.command,
        description: step.description,
        code: null,
        stdout: '',
        stderr: '',
        timed_out: false,
        produced_artifact: step.produced_artifact,
        produced_artifact_present_after: !!step.produced_artifact && fileTimestamp(repoRoot, step.produced_artifact) !== null,
      });
      continue;
    }
    const exec = await runCommand(step.command, repoRoot, 120000);
    const presentAfter = !!step.produced_artifact && fileTimestamp(repoRoot, step.produced_artifact) !== null;
    const result: CommandResult = {
      command: step.command,
      description: step.description,
      code: exec.code,
      stdout: exec.stdout,
      stderr: exec.stderr,
      timed_out: exec.timed_out,
      produced_artifact: step.produced_artifact,
      produced_artifact_present_after: presentAfter,
    };
    commandResults.push(result);
    if (exec.code !== 0 || exec.timed_out) {
      failedResult = result;
      failureReason = exec.timed_out ? 'timed_out' : `exit_code:${exec.code ?? 'unknown'}`;
      // Fail-closed: stop pipeline on first failure. Last good state on
      // disk is preserved because we never wrote anything ourselves.
      break;
    }
    if (step.produced_artifact && presentAfter) {
      const ts = fileTimestamp(repoRoot, step.produced_artifact) ?? 0;
      if (Number.isFinite(startedAtMs) && ts >= startedAtMs - 1000) {
        generated.push(step.produced_artifact);
      }
    } else if (step.produced_artifact) {
      skipped.push(step.produced_artifact);
    }
  }

  // Stale-after-recompute check: even on success, the priority artifact
  // must be loadable, fresh, and registry-aligned. Otherwise the operator
  // is staring at a recomputed-but-stale-looking dashboard.
  let staleAfterRecompute = false;
  if (!failedResult) {
    const reload = loadPriorityArtifact();
    if (reload.state !== 'ok') {
      staleAfterRecompute = true;
      warnings.push(`stale_after_recompute:priority_state=${reload.state}:reason=${reload.reason ?? 'unknown'}`);
    }
  }

  const completedAt = new Date().toISOString();
  if (failedResult) {
    const body: RecomputeResponseBody = {
      status: 'recompute_failed_signal',
      started_at: startedAt,
      completed_at: completedAt,
      commands: commandResults,
      generated_artifacts: generated,
      skipped_artifacts: skipped,
      artifacts_checked: DASHBOARD_CRITICAL_ARTIFACTS,
      warnings,
      failing_command: failedResult.command,
      failure_reason: failureReason,
      stale_after_recompute: staleAfterRecompute,
      error_message: failedResult.stderr || 'recompute command failed',
    };
    return NextResponse.json(body, { status: 500 });
  }

  const body: RecomputeResponseBody = {
    status: 'recompute_success_signal',
    started_at: startedAt,
    completed_at: completedAt,
    commands: commandResults,
    generated_artifacts: generated,
    skipped_artifacts: skipped,
    artifacts_checked: DASHBOARD_CRITICAL_ARTIFACTS,
    warnings,
    failing_command: null,
    failure_reason: null,
    stale_after_recompute: staleAfterRecompute,
    error_message: null,
  };
  return NextResponse.json(body, { status: 200 });
}
