'use client';

interface ControlDecisionBannerProps {
  decisions: string[];
}

export function ControlDecisionBanner({
  decisions,
}: ControlDecisionBannerProps) {
  const isBlocking = decisions.includes('block');
  const isEscalating = decisions.includes('escalate');

  let bgColor = 'bg-green-50 border-green-200';
  let message =
    'System entropy nominal. Proceed with normal operations.';

  if (isBlocking) {
    bgColor = 'bg-red-50 border-red-200';
    message =
      'CRITICAL: System entropy critical. Block all promotions. Emergency review required.';
  } else if (isEscalating) {
    bgColor = 'bg-yellow-50 border-yellow-200';
    message =
      'WARNING: System entropy elevated. Escalate to governance council. Proceed with caution.';
  }

  return (
    <div className={`p-4 rounded-lg border-2 ${bgColor}`}>
      <h2 className="text-xl font-semibold mb-2">Control Decisions</h2>
      <div className="flex gap-2 flex-wrap mb-3">
        {decisions.map((decision) => (
          <span
            key={decision}
            className="px-3 py-1 bg-white rounded-full font-mono text-sm border border-gray-200"
          >
            {decision.toUpperCase()}
          </span>
        ))}
      </div>
      <p className="text-sm font-medium">{message}</p>
    </div>
  );
}
