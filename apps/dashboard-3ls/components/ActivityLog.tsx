import React from 'react';

export interface ActivityEntry {
  timestamp: string;
  message: string;
}

export function ActivityLog({ entries }: { entries: ActivityEntry[] }) {
  return (
    <div className="border dark:border-slate-700 rounded p-3 bg-white dark:bg-slate-900 dark:text-slate-100" data-testid="activity-log">
      <h3 className="font-semibold mb-2">Activity Log</h3>
      <ul className="text-xs space-y-1">
        {entries.map((entry, index) => (
          <li key={`${entry.timestamp}-${index}`}>{entry.timestamp}: {entry.message}</li>
        ))}
      </ul>
    </div>
  );
}
