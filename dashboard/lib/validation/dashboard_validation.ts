import type { ArtifactRecord } from '../../types/dashboard'

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

export function validateArtifactShape(name: string, data: unknown): { valid: boolean; error?: string } {
  if (data === null || data === undefined) return { valid: false, error: `${name} is null` }

  if (name === 'deferred_item_register.json' || name === 'deferred_return_tracker.json') {
    if (!isObject(data)) return { valid: false, error: `${name} must be object` }
    return { valid: true }
  }

  if (!isObject(data)) return { valid: false, error: `${name} must be object` }

  return { valid: true }
}

export function markValidated<T>(artifact: ArtifactRecord<T>): ArtifactRecord<T> {
  if (!artifact.exists) return artifact
  const check = validateArtifactShape(artifact.name, artifact.data)
  return {
    ...artifact,
    valid: check.valid,
    error: check.error ?? artifact.error
  }
}
