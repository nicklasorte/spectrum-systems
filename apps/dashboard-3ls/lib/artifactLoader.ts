import fs from 'fs';
import path from 'path';

// Resolve the repo root that contains the artifacts/ directory.
//
// On Vercel, set REPO_ROOT to the absolute path of the monorepo root inside the
// serverless function bundle (e.g. /var/task) so artifact paths resolve correctly.
// In local dev and CI, process.cwd() is apps/dashboard-3ls, so ../.. is the repo root.
export function getRepoRoot(): string {
  if (process.env.REPO_ROOT) {
    return process.env.REPO_ROOT;
  }
  return path.resolve(process.cwd(), '../..');
}

export function loadArtifact<T>(relativePath: string): T | null {
  try {
    const fullPath = path.join(getRepoRoot(), relativePath);
    const raw = fs.readFileSync(fullPath, 'utf-8');
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}
