'use client';

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

interface TrendData {
  date: string;
  divergence: number;
  exceptions: number;
}

export function TrendChart({ data }: { data: TrendData[] }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip
          formatter={(value: number) => `${(value * 100).toFixed(2)}%`}
          contentStyle={{ backgroundColor: '#fff', border: '1px solid #ccc' }}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="divergence"
          stroke="#dc2626"
          name="Decision Divergence"
          dot={false}
          strokeWidth={2}
        />
        <Line
          type="monotone"
          dataKey="exceptions"
          stroke="#f97316"
          name="Exception Rate"
          dot={false}
          strokeWidth={2}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
