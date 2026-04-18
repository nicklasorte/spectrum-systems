import { Execution } from './types';
import StatusBadge from './StatusBadge';

interface ExecutionTableProps {
  executions: Execution[];
  onSelectTrace: (trace_id: string) => void;
}

export default function ExecutionTable({
  executions,
  onSelectTrace,
}: ExecutionTableProps) {
  const getControlDecisionDisplay = (decision: string | null): string => {
    if (decision === 'ALLOW') return '✓ ALLOW';
    if (decision === 'BLOCK') return '✗ BLOCK';
    return '—';
  };

  return (
    <div className="overflow-x-auto border border-gray-200 dark:border-gray-800 rounded-lg">
      <table className="w-full">
        <thead className="bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
          <tr>
            <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900 dark:text-gray-100">
              Run ID
            </th>
            <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900 dark:text-gray-100">
              Phase
            </th>
            <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900 dark:text-gray-100">
              Status
            </th>
            <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900 dark:text-gray-100">
              Time
            </th>
            <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900 dark:text-gray-100">
              Control Decision
            </th>
          </tr>
        </thead>
        <tbody>
          {executions.map((execution) => (
            <tr
              key={execution.trace_id}
              onClick={() => onSelectTrace(execution.trace_id)}
              className="border-b border-gray-200 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-900 cursor-pointer"
            >
              <td className="px-6 py-4 text-sm font-mono text-gray-900 dark:text-gray-100">
                {execution.trace_id}
              </td>
              <td className="px-6 py-4 text-sm text-gray-700 dark:text-gray-300">
                {execution.phase}
              </td>
              <td className="px-6 py-4 text-sm">
                <StatusBadge status={execution.status} />
              </td>
              <td className="px-6 py-4 text-sm text-gray-700 dark:text-gray-300">
                {new Date(execution.created_at).toLocaleString()}
              </td>
              <td className="px-6 py-4 text-sm font-mono text-gray-700 dark:text-gray-300">
                {getControlDecisionDisplay(execution.control_decision)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
