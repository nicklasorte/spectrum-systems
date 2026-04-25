import fs from 'fs';
import path from 'path';

// When running from apps/dashboard-3ls, process.cwd() is the app dir;
// artifacts live two levels up at the repo root.
export function getRepoRoot(): string {
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
