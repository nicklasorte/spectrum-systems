'use client';

import React, { useEffect, useState } from 'react';
import { SystemCard, type SystemCardStatus } from '@/components/SystemCard';
import { SystemDetail } from '@/components/SystemDetail';
import {
  DISPLAY_GROUPS,
  partitionByDisplayGroup,
  type DisplayGroup,
} from '@/lib/displayGroups';
import type { DataSource } from '@/lib/types';

interface SystemMetrics {
  system_id: string;
  system_name: string;
  system_type: string;
  health_score: number;
  status: SystemCardStatus;
  incidents_week: number;
  contract_violations: Array<{ rule: string; detail: string }>;
  data_source?: DataSource;
  authority_role?: string | null;
  display_group?: string | null;
}

interface HealthEnvelope {
  data_source?: DataSource;
  generated_at?: string;
  source_artifacts_used?: string[];
  warnings?: string[];
}

const SOURCE_TONE: Record<DataSource, string> = {
  artifact_store: 'text-blue-700',
  repo_registry: 'text-indigo-700',
  derived: 'text-purple-700',
  derived_estimate: 'text-amber-700',
  stub_fallback: 'text-orange-700',
  unknown: 'text-gray-500',
};

export default function Dashboard() {
  const [systems, setSystems] = useState<SystemMetrics[]>([]);
  const [envelope, setEnvelope] = useState<HealthEnvelope>({});
  const [selectedSystem, setSelectedSystem] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSystems();
  }, []);

  const fetchSystems = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/health');
      if (!response.ok) throw new Error('Failed to fetch health data');
      const data = await response.json();
      setSystems(data.systems || []);
      setEnvelope({
        data_source: data.data_source,
        generated_at: data.generated_at,
        source_artifacts_used: data.source_artifacts_used,
        warnings: data.warnings,
      });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const selectedSystemData = systems.find((s) => s.system_id === selectedSystem);
  const ds = envelope.data_source;
  const partition = partitionByDisplayGroup(systems);

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-4xl font-bold mb-2">3-Letter Systems Dashboard</h1>
          <p className="text-gray-600">
            Artifact-backed cockpit for governance systems. Source per signal is shown — no green
            without source.
          </p>
          {ds && (
            <p className="text-xs mt-2">
              Data source:{' '}
              <span className={`font-mono ${SOURCE_TONE[ds]}`}>{ds}</span>
              {envelope.generated_at && (
                <span className="text-gray-400"> · generated_at {envelope.generated_at}</span>
              )}
            </p>
          )}
        </div>
        <button
          onClick={fetchSystems}
          className="px-4 py-2 bg-blue-600 text-white rounded font-semibold hover:bg-blue-700"
        >
          Refresh
        </button>
      </div>

      {envelope.warnings && envelope.warnings.length > 0 && (
        <div
          role="alert"
          className="bg-amber-50 border border-amber-400 rounded p-4 mb-6 space-y-1"
        >
          <div className="text-sm font-semibold text-amber-800 mb-1">
            Source warnings — values backed by stubs render as unknown:
          </div>
          {envelope.warnings.map((w, i) => (
            <div key={i} className="text-xs text-amber-700 font-mono">
              {w}
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="bg-yellow-50 border border-yellow-300 p-4 rounded mb-8">
          <p className="text-sm text-yellow-800">{error}</p>
        </div>
      )}

      {loading ? (
        <div className="text-center py-12">
          <p className="text-gray-600">Loading systems...</p>
        </div>
      ) : (
        <>
          {partition.groups.length === 0 && partition.ungrouped.length === 0 ? (
            <div className="text-gray-500 mb-8">No systems available.</div>
          ) : (
            <div className="space-y-8">
              {partition.groups.map(({ group, systems: groupSystems }) => (
                <DisplayGroupSection
                  key={group.id}
                  group={group}
                  systems={groupSystems}
                  selectedSystem={selectedSystem}
                  onSelect={setSelectedSystem}
                />
              ))}
              {partition.ungrouped.length > 0 && (
                <DisplayGroupSection
                  group={{
                    id: 'execution',
                    label: 'Other / Ungrouped',
                    description: 'Systems with no declared display group.',
                    system_ids: [],
                  }}
                  systems={partition.ungrouped}
                  selectedSystem={selectedSystem}
                  onSelect={setSelectedSystem}
                />
              )}
            </div>
          )}

          {selectedSystemData && (
            <SystemDetail
              system={selectedSystemData}
              sourceArtifacts={envelope.source_artifacts_used}
            />
          )}

          <details className="mt-8 text-xs text-gray-500">
            <summary className="cursor-pointer">Display group reference</summary>
            <ul className="mt-2 space-y-1">
              {DISPLAY_GROUPS.map((g) => (
                <li key={g.id}>
                  <span className="font-mono">{g.label}</span> — {g.description}
                </li>
              ))}
            </ul>
            <p className="mt-2 italic">
              Grouping is visual only. Canonical system IDs are preserved across the API.
            </p>
          </details>
        </>
      )}
    </div>
  );
}

function DisplayGroupSection({
  group,
  systems,
  selectedSystem,
  onSelect,
}: {
  group: DisplayGroup;
  systems: SystemMetrics[];
  selectedSystem: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <section>
      <header className="mb-3">
        <h2 className="text-xl font-semibold">{group.label}</h2>
        <p className="text-xs text-gray-500">{group.description}</p>
      </header>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {systems.map((system) => (
          <SystemCard
            key={system.system_id}
            system={system}
            onClick={() => onSelect(system.system_id)}
            isSelected={selectedSystem === system.system_id}
          />
        ))}
      </div>
    </section>
  );
}
