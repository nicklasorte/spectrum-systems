/** @jest-environment node */
import { resolveSystemFlowEnvelope } from '@/app/api/system-flow/route';

describe('/api/system-flow route', () => {
  it('returns ok envelope for valid artifact payload', () => {
    const json = resolveSystemFlowEnvelope({
      schema_version: 'tls-00.v1',
      phase: 'TLS-00',
      active_systems: [
        { system_id: 'AEX', upstream: [], downstream: ['PQX'] },
        { system_id: 'PQX', upstream: ['AEX'], downstream: [] },
      ],
      canonical_loop: ['AEX', 'PQX'],
      canonical_overlays: ['OBS'],
    });

    expect(json).toMatchObject({
      state: 'ok',
      reason: 'artifact_loaded',
      source_artifact: 'artifacts/tls/system_registry_dependency_graph.json',
    });
    expect(json.payload?.active_systems).toHaveLength(2);
  });

  it('returns missing envelope when artifact is absent', () => {
    const json = resolveSystemFlowEnvelope(null);

    expect(json).toEqual({
      state: 'missing',
      payload: null,
      reason: 'not_found:artifacts/tls/system_registry_dependency_graph.json',
      source_artifact: 'artifacts/tls/system_registry_dependency_graph.json',
    });
  });

  it('returns invalid_schema envelope when artifact shape is invalid', () => {
    const json = resolveSystemFlowEnvelope({
      schema_version: 'tls-00.v1',
      phase: 'TLS-00',
      active_systems: [{ system_id: 'AEX', upstream: ['PQX'], downstream: 'PQX' }],
      canonical_loop: ['AEX'],
      canonical_overlays: ['OBS'],
    } as unknown);

    expect(json).toEqual({
      state: 'invalid_schema',
      payload: null,
      reason: 'shape_mismatch',
      source_artifact: 'artifacts/tls/system_registry_dependency_graph.json',
    });
  });
});
