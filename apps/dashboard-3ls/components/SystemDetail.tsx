interface SystemMetrics {
  system_id: string;
  system_name: string;
  system_type: string;
  health_score: number;
  status: 'healthy' | 'warning' | 'critical';
  incidents_week: number;
  contract_violations: Array<{rule: string, detail: string}>;
}

function MetricBox({ 
  label, 
  value, 
  unit = '',
  status = 'info',
  isText = false
}: { 
  label: string;
  value: string | number;
  unit?: string;
  status?: string;
  isText?: boolean;
}) {
  return (
    <div className="bg-gray-50 p-4 rounded">
      <p className="text-sm text-gray-600 mb-1">{label}</p>
      <p className="text-2xl font-bold">
        {value}
        {unit && <span className="text-sm text-gray-500 ml-1">{unit}</span>}
      </p>
    </div>
  );
}

export function SystemDetail({ system }: { system?: SystemMetrics }) {
  if (!system) return null;

  return (
    <div className="bg-white rounded-lg p-6 border border-gray-200 mb-8">
      <h2 className="text-2xl font-bold mb-6">{system.system_id}: {system.system_name}</h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <MetricBox 
          label="Health Score" 
          value={system.health_score} 
          unit="%" 
        />
        <MetricBox 
          label="Incidents (week)" 
          value={system.incidents_week}
        />
        <MetricBox 
          label="Contract Violations" 
          value={system.contract_violations.length}
        />
        <MetricBox 
          label="Type" 
          value={system.system_type}
          isText={true}
        />
      </div>

      {system.contract_violations.length > 0 && (
        <div className="bg-red-50 p-4 rounded mb-6">
          <h3 className="font-semibold mb-2">Contract Violations:</h3>
          <ul className="space-y-1 text-sm">
            {system.contract_violations.map((v) => (
              <li key={v.rule} className="text-red-700">• {v.rule}: {v.detail}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
