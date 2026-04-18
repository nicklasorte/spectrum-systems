import { PipelineMetrics } from './types';

interface PipelineOverviewProps {
  metrics: PipelineMetrics;
}

export default function PipelineOverview({ metrics }: PipelineOverviewProps) {
  const cards = [
    {
      label: 'Total Runs',
      value: metrics.total_runs,
      color: 'text-gray-600 dark:text-gray-400',
    },
    {
      label: 'Passed',
      value: metrics.passed,
      color: 'text-green-600 dark:text-green-400',
    },
    {
      label: 'Failed',
      value: metrics.failed,
      color: 'text-red-600 dark:text-red-400',
    },
    {
      label: 'In Progress',
      value: metrics.in_progress,
      color: 'text-blue-600 dark:text-blue-400',
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      {cards.map((card) => (
        <div
          key={card.label}
          className="bg-gray-50 dark:bg-gray-900 rounded-lg p-6 flex flex-col items-center justify-center border border-gray-200 dark:border-gray-800"
        >
          <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-2">
            {card.label}
          </p>
          <p className={`text-3xl font-bold ${card.color}`}>{card.value}</p>
        </div>
      ))}
    </div>
  );
}
