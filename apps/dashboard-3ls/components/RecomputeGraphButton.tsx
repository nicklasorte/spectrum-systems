import React, { useState } from 'react';

interface RecomputeResult {
  status: 'recompute_success_signal' | 'recompute_failed_signal' | 'recompute_unavailable_signal';
  warnings?: string[];
  error_message?: string | null;
}

export function RecomputeGraphButton({ onResult }: { onResult: (result: RecomputeResult) => void }) {
  const [running, setRunning] = useState(false);

  return (
    <button
      type="button"
      className="px-3 py-1.5 text-sm border rounded bg-black text-white disabled:opacity-50"
      onClick={async () => {
        setRunning(true);
        try {
          const res = await fetch('/api/recompute-graph', { method: 'POST' });
          const payload = (await res.json()) as RecomputeResult;
          onResult(payload);
        } finally {
          setRunning(false);
        }
      }}
      disabled={running}
      data-testid="recompute-graph-button"
    >
      {running ? 'Recomputing…' : 'Recompute Graph'}
    </button>
  );
}
