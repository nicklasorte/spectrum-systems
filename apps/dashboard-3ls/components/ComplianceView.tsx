'use client';

import React from 'react';

interface SystemCompliance {
  system_id: string;
  compliant: boolean;
  violations: Array<{ rule: string; detail: string }>;
}

export function ComplianceView({ systems }: { systems: SystemCompliance[] }) {
  const violations = systems.filter(s => !s.compliant);
  const compliant = systems.filter(s => s.compliant);

  const handleExport = () => {
    const report = {
      generated_at: new Date().toISOString(),
      total_systems: systems.length,
      compliant_count: compliant.length,
      violations_count: violations.length,
      systems: systems,
    };
    const dataStr = JSON.stringify(report, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `compliance-report-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-blue-50 p-6 rounded-lg border border-blue-300">
          <p className="text-sm text-gray-600 mb-1">Total Systems</p>
          <p className="text-3xl font-bold">{systems.length}</p>
        </div>
        <div className="bg-green-50 p-6 rounded-lg border border-green-300">
          <p className="text-sm text-gray-600 mb-1">Compliant</p>
          <p className="text-3xl font-bold">{compliant.length}</p>
        </div>
        <div className="bg-red-50 p-6 rounded-lg border border-red-300">
          <p className="text-sm text-gray-600 mb-1">Violations</p>
          <p className="text-3xl font-bold">{violations.length}</p>
        </div>
      </div>

      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">System Status</h3>
        <button
          onClick={handleExport}
          className="px-4 py-2 bg-green-600 text-white rounded font-semibold hover:bg-green-700"
        >
          Export Report
        </button>
      </div>

      {violations.length > 0 && (
        <div className="mb-6">
          <h4 className="text-md font-semibold text-red-700 mb-3">Systems with Violations</h4>
          <div className="space-y-3">
            {violations.map((system) => (
              <div key={system.system_id} className="bg-red-50 border border-red-300 p-4 rounded">
                <h5 className="font-semibold text-red-800">{system.system_id}</h5>
                <ul className="mt-2 space-y-1 text-sm">
                  {system.violations.map((v) => (
                    <li key={v.rule} className="text-red-700 ml-4">
                      • <span className="font-semibold">{v.rule}:</span> {v.detail}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
        <h4 className="text-md font-semibold text-green-700 mb-3">Compliant Systems</h4>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {compliant.map((system) => (
            <div
              key={system.system_id}
              className="bg-green-50 border border-green-300 p-3 rounded text-center"
            >
              <p className="font-semibold text-green-800">{system.system_id}</p>
              <p className="text-xs text-green-600 mt-1">✓ Compliant</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
