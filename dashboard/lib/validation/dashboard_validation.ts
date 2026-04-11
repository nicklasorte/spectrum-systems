import type { ArtifactRecord } from '../../types/dashboard'

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

function hasRequiredFields(data: Record<string, unknown>, fields: string[]): boolean {
  return fields.every((field) => data[field] !== undefined && data[field] !== null)
}

export function validateArtifactShape(name: string, data: unknown): { valid: boolean; error?: string } {
  if (data === null || data === undefined) return { valid: false, error: `${name} is null` }

  if (!isObject(data)) return { valid: false, error: `${name} must be object` }

  if (name === 'deferred_item_register.json' || name === 'deferred_return_tracker.json') {
    return { valid: true }
  }

  if (name === 'next_action_recommendation_record.json') {
    if (!Array.isArray(data.records)) {
      return { valid: false, error: `${name} missing required discriminator field: records` }
    }
    return { valid: true }
  }

  const requiredDiscriminatorFields: Record<string, string[]> = {
    'repo_snapshot_meta.json': ['data_source_state', 'last_refreshed_time'],
    'hard_gate_status_record.json': ['readiness_status'],
    'current_run_state_record.json': ['current_run_status']
  }

  const required = requiredDiscriminatorFields[name]
  if (required && !hasRequiredFields(data, required)) {
    return { valid: false, error: `${name} missing required discriminator fields: ${required.join(', ')}` }
  }

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
