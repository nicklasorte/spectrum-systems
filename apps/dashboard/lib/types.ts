export interface EntropySnapshot {
  snapshot_id: string;
  timestamp: string;
  control_decisions: string[];
  metrics: {
    decision_divergence: {
      current: number;
      threshold: number;
      trend?: 'rising' | 'falling' | 'stable';
    };
    exception_rate: {
      current: number;
      threshold: number;
      trend?: 'rising' | 'falling' | 'stable';
    };
    trace_coverage: {
      current: number;
      slo: number;
      met: boolean;
    };
    calibration_drift: {
      current: number;
      threshold: number;
    };
    override_hotspots: {
      count: number;
      locations?: string[];
    };
    failure_to_eval_rate: {
      current: number;
      threshold: number;
    };
  };
}

export interface MetricCardProps {
  title: string;
  value: string;
  threshold?: string;
  trend?: string;
  status: 'good' | 'warning' | 'critical';
  onClick?: () => void;
}

export interface TrendData {
  date: string;
  divergence: number;
  exceptions: number;
}
