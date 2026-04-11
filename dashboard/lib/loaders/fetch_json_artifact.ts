import { readFile } from 'node:fs/promises'
import path from 'node:path'
import type { ArtifactRecord } from '../../types/dashboard'

export async function fetchJsonArtifact<T>(filename: string): Promise<ArtifactRecord<T>> {
  const fullPath = path.join(process.cwd(), 'public', filename)
  try {
    const raw = await readFile(fullPath, 'utf8')
    const data = JSON.parse(raw) as T
    return {
      name: filename,
      path: `/${filename}`,
      exists: true,
      valid: true,
      data,
      timestamp: new Date().toISOString()
    }
  } catch (error) {
    return {
      name: filename,
      path: `/${filename}`,
      exists: false,
      valid: false,
      data: null,
      error: error instanceof Error ? error.message : 'Unknown artifact retrieve failure'
    }
  }
}
