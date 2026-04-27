import { NextResponse } from 'next/server';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { getRepoRoot } from '@/lib/artifactLoader';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

type RecomputeStatus = 'recompute_success_signal' | 'recompute_failed_signal' | 'recompute_unavailable_signal';

interface CommandResult {
  command: string[];
  code: number | null;
  stdout: string;
  stderr: string;
  timed_out: boolean;
}

function runCommand(command: string[], cwd: string, timeoutMs: number): Promise<CommandResult> {
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
      resolve({ command, code: 1, stdout, stderr: `${stderr}\n${error.message}`, timed_out: timedOut });
    });

    child.on('close', (code) => {
      clearTimeout(timer);
      resolve({ command, code, stdout, stderr, timed_out: timedOut });
    });
  });
}

export async function POST() {
  const startedAt = new Date().toISOString();
  const repoRoot = getRepoRoot();
  const artifactsChecked = [
    'artifacts/system_dependency_priority_report.json',
    'artifacts/tls/system_graph_validation_report.json',
  ];

  if (process.env.VERCEL === '1') {
    return NextResponse.json(
      {
        status: 'recompute_unavailable_signal' as RecomputeStatus,
        started_at: startedAt,
        completed_at: new Date().toISOString(),
        commands: [],
        artifacts_checked: artifactsChecked,
        warnings: [
          'vercel_runtime_detected:python_execution_disabled',
          'Run from repo root: python scripts/build_tls_dependency_priority.py --candidates H01,RFX,HOP,MET,METS --fail-if-missing',
        ],
        error_message: 'Recompute requires a node runtime with Python available; serverless deployment is unavailable for this operation.',
      },
      { status: 200 },
    );
  }

  const commands = [
    ['python', 'scripts/build_tls_dependency_priority.py', '--candidates', 'H01,RFX,HOP,MET,METS', '--fail-if-missing'],
  ];

  const graphValidationScript = path.join(repoRoot, 'scripts', 'build_system_graph_validation_report.py');
  const warnings: string[] = [];
  if (fs.existsSync(graphValidationScript)) {
    commands.push(['python', 'scripts/build_system_graph_validation_report.py']);
  } else {
    warnings.push('missing_graph_validation_script:scripts/build_system_graph_validation_report.py');
    warnings.push('missing_artifact:artifacts/tls/system_graph_validation_report.json');
  }

  const commandResults: CommandResult[] = [];
  let failedResult: CommandResult | null = null;
  for (const command of commands) {
    const result = await runCommand(command, repoRoot, 120000);
    commandResults.push(result);
    if (result.code !== 0 || result.timed_out) {
      failedResult = result;
      break;
    }
  }

  const completedAt = new Date().toISOString();
  if (failedResult) {
    return NextResponse.json(
      {
        status: 'recompute_failed_signal' as RecomputeStatus,
        started_at: startedAt,
        completed_at: completedAt,
        commands: commandResults,
        artifacts_checked: artifactsChecked,
        warnings,
        error_message: failedResult.stderr || 'recompute command failed',
      },
      { status: 500 },
    );
  }

  return NextResponse.json(
    {
      status: 'recompute_success_signal' as RecomputeStatus,
      started_at: startedAt,
      completed_at: completedAt,
      commands: commandResults,
      artifacts_checked: artifactsChecked,
      warnings,
      error_message: null,
    },
    { status: 200 },
  );
}
