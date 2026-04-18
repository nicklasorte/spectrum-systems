import { ExecutionStatus } from './types';

interface StatusBadgeProps {
  status: ExecutionStatus;
  label?: string;
}

export default function StatusBadge({ status, label }: StatusBadgeProps) {
  const getStatusColor = (status: ExecutionStatus): string => {
    switch (status) {
      case 'PASS':
      case 'ALLOW':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'FAIL':
      case 'BLOCK':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      case 'RUN':
      case 'PENDING':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200';
    }
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium ${getStatusColor(
        status
      )}`}
    >
      {label || status}
    </span>
  );
}
