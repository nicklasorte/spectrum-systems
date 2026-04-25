/**
 * DSH-09 red-team failure mode tests.
 *
 * Each test proves a specific failure mode discovered during the DSH-09 red-team
 * audit cannot regress. Tests verify route source files directly because Next.js
 * server imports (next/server) are incompatible with the jsdom test environment.
 */

import path from 'path';
import fs from 'fs';

function readRoute(relativePath: string): string {
  return fs.readFileSync(path.resolve(__dirname, '../../', relativePath), 'utf-8');
}

// ─── F-01: trends route must declare stub_fallback envelope ─────────────────

describe('F-01 — trends route envelope (DSH-09)', () => {
  const src = readRoute('app/api/trends/route.ts');

  it('declares data_source field in response', () => {
    expect(src).toContain('data_source');
  });

  it('sets data_source to stub_fallback', () => {
    expect(src).toContain("'stub_fallback'");
  });

  it('includes generated_at in response', () => {
    expect(src).toContain('generated_at');
  });

  it('includes source_artifacts_used in response', () => {
    expect(src).toContain('source_artifacts_used');
  });

  it('includes warnings in response', () => {
    expect(src).toContain('warnings');
  });

  it('does not call Math.random() in production code — trend values must be deterministic', () => {
    // Strip single-line comments before checking to avoid matching comment text.
    const codeOnly = src.replace(/\/\/[^\n]*/g, '');
    expect(codeOnly).not.toContain('Math.random()');
  });

  it('does not make affirmative live-data claims in production code', () => {
    const codeOnly = src.replace(/\/\/[^\n]*/g, '');
    expect(codeOnly).not.toMatch(/'[^']*\blive data\b[^']*'/i);
    expect(codeOnly).not.toMatch(/'[^']*\breal data\b[^']*'/i);
  });
});

// ─── F-02: compliance route must declare stub_fallback envelope ──────────────

describe('F-02 — compliance route envelope (DSH-09)', () => {
  const src = readRoute('app/api/compliance/route.ts');

  it('declares data_source field in response', () => {
    expect(src).toContain('data_source');
  });

  it('sets data_source to stub_fallback', () => {
    expect(src).toContain("'stub_fallback'");
  });

  it('includes generated_at in response', () => {
    expect(src).toContain('generated_at');
  });

  it('includes source_artifacts_used in response', () => {
    expect(src).toContain('source_artifacts_used');
  });

  it('includes warnings in response', () => {
    expect(src).toContain('warnings');
  });
});

// ─── F-03: incidents route must declare stub_fallback envelope ───────────────

describe('F-03 — incidents route envelope (DSH-09)', () => {
  const src = readRoute('app/api/incidents/route.ts');

  it('declares data_source field in response', () => {
    expect(src).toContain('data_source');
  });

  it('sets data_source to stub_fallback', () => {
    expect(src).toContain("'stub_fallback'");
  });

  it('includes generated_at in response', () => {
    expect(src).toContain('generated_at');
  });

  it('includes source_artifacts_used in response', () => {
    expect(src).toContain('source_artifacts_used');
  });

  it('includes warnings in response', () => {
    expect(src).toContain('warnings');
  });
});

// ─── F-04: proposals POST response must include envelope ────────────────────

describe('F-04 — proposals POST envelope (DSH-09)', () => {
  const src = readRoute('app/api/rge/proposals/route.ts');

  it('POST handler includes data_source in response', () => {
    // Find the POST handler block and check it contains an envelope
    const postIdx = src.indexOf('export async function POST');
    expect(postIdx).toBeGreaterThan(-1);
    const postBody = src.slice(postIdx);
    expect(postBody).toContain('data_source');
    expect(postBody).toContain('generated_at');
    expect(postBody).toContain('source_artifacts_used');
    expect(postBody).toContain('warnings');
  });
});

// ─── F-05: Vercel artifact access — artifactLoader REPO_ROOT override ───────

describe('F-05 — artifactLoader REPO_ROOT env var (DSH-09)', () => {
  const src = readRoute('lib/artifactLoader.ts');

  it('checks process.env.REPO_ROOT before falling back to process.cwd()', () => {
    expect(src).toContain('process.env.REPO_ROOT');
  });

  it('returns REPO_ROOT when env var is set', () => {
    // Dynamic test: actually invoke getRepoRoot() with env override
    const originalEnv = process.env.REPO_ROOT;
    process.env.REPO_ROOT = '/custom/repo/root';
    // Re-require the module to pick up fresh env (jest caches modules so we
    // access the function directly since it reads env at call time)
    const { getRepoRoot } = require('@/lib/artifactLoader');
    expect(getRepoRoot()).toBe('/custom/repo/root');
    if (originalEnv === undefined) {
      delete process.env.REPO_ROOT;
    } else {
      process.env.REPO_ROOT = originalEnv;
    }
  });

  it('falls back to process.cwd() two levels up when REPO_ROOT not set', () => {
    const originalEnv = process.env.REPO_ROOT;
    delete process.env.REPO_ROOT;
    const path = require('path');
    const { getRepoRoot } = require('@/lib/artifactLoader');
    expect(getRepoRoot()).toBe(path.resolve(process.cwd(), '../..'));
    if (originalEnv !== undefined) {
      process.env.REPO_ROOT = originalEnv;
    }
  });
});

// ─── F-05b: next.config.js includes outputFileTracingRoot ───────────────────

describe('F-05b — next.config.js Vercel file tracing (DSH-09)', () => {
  const src = readRoute('next.config.js');

  it('sets outputFileTracingRoot to monorepo root', () => {
    expect(src).toContain('outputFileTracingRoot');
  });

  it('includes outputFileTracingIncludes for artifacts', () => {
    expect(src).toContain('outputFileTracingIncludes');
    expect(src).toContain('artifacts');
  });

  it('documents REPO_ROOT env var requirement', () => {
    expect(src).toContain('REPO_ROOT');
  });
});

// ─── F-07: RGEPage must not render green CAN OPERATE for derived_estimate ───

describe('F-07 — RGEPage no-green-without-source for rge_can_operate (DSH-09)', () => {
  const src = readRoute('app/rge/page.tsx');

  it('defines sourceAllowsGreen guard variable', () => {
    expect(src).toContain('sourceAllowsGreen');
  });

  it('gates green CAN OPERATE on sourceAllowsGreen', () => {
    expect(src).toContain('rgeCanOperate && sourceAllowsGreen');
  });

  it('renders amber unverified label when source does not allow green', () => {
    expect(src).toContain('CAN OPERATE (unverified)');
  });

  it('uses data-testid for operational status element', () => {
    expect(src).toContain('data-testid="rge-operational-status"');
  });
});
