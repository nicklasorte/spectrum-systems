import fs from 'fs';
import path from 'path';
import { NextResponse } from 'next/server';
import { getRepoRoot, loadArtifact } from '@/lib/artifactLoader';

const ROADMAP_JSON = 'artifacts/tls/tls_roadmap_final.json';
const ROADMAP_TABLE = 'artifacts/tls/tls_roadmap_table.md';

export async function GET() {
  const payload = loadArtifact<unknown>(ROADMAP_JSON);
  const tablePath = path.join(getRepoRoot(), ROADMAP_TABLE);

  let tableMarkdown: string | null = null;
  if (fs.existsSync(tablePath)) {
    tableMarkdown = fs.readFileSync(tablePath, 'utf-8');
  }

  if (!payload || !tableMarkdown) {
    return NextResponse.json(
      {
        state: 'missing',
        reason: 'tls_roadmap_artifacts_missing',
        payload: null,
        table_markdown: tableMarkdown,
        source_artifacts_used: [ROADMAP_JSON, ROADMAP_TABLE],
      },
      { status: 200 },
    );
  }

  return NextResponse.json({
    state: 'ok',
    payload,
    table_markdown: tableMarkdown,
    source_artifacts_used: [ROADMAP_JSON, ROADMAP_TABLE],
  });
}
