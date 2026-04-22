'use client';

interface MetricCardProps {
  title: string;
  value: string;
  threshold?: string;
  trend?: string;
  status: 'good' | 'warning' | 'critical';
  onClick?: () => void;
}

export function MetricCard({
  title,
  value,
  threshold,
  trend,
  status,
  onClick,
}: MetricCardProps) {
  const statusColors = {
    good: 'bg-green-50 border-green-200',
    warning: 'bg-yellow-50 border-yellow-200',
    critical: 'bg-red-50 border-red-200',
  };

  const statusBadgeColors = {
    good: 'bg-green-100 text-green-800',
    warning: 'bg-yellow-100 text-yellow-800',
    critical: 'bg-red-100 text-red-800',
  };

  return (
    <div
      className={`p-4 rounded-lg border-2 cursor-pointer transition hover:shadow-md ${statusColors[status]}`}
      onClick={onClick}
    >
      <h3 className="font-semibold text-sm text-gray-700">{title}</h3>
      <div className="text-3xl font-bold mt-2">{value}</div>

      <div className="mt-3 space-y-1 text-xs text-gray-600">
        {threshold && <p>Threshold: {threshold}</p>}
        {trend && (
          <p className="font-mono">
            Trend:{' '}
            <span
              className={trend === 'rising' ? 'text-red-600' : 'text-green-600'}
            >
              {trend === 'rising' ? '↑' : trend === 'falling' ? '↓' : '→'} {trend}
            </span>
          </p>
        )}
      </div>

      <div className="mt-3">
        <span
          className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
            statusBadgeColors[status]
          }`}
        >
          {status.toUpperCase()}
        </span>
      </div>
    </div>
  );
}
