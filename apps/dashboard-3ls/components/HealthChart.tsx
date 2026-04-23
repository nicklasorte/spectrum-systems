'use client';

import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface TrendData {
  date: string;
  health_score: number;
}

export function HealthChart({ data, title = '7-Day Trend' }: { data: TrendData[]; title?: string }) {
  if (!data || data.length === 0) {
    return (
      <div className="bg-gray-50 p-4 rounded text-center text-gray-500">
        No trend data available
      </div>
    );
  }

  const minScore = Math.min(...data.map(d => d.health_score));
  const maxScore = Math.max(...data.map(d => d.health_score));
  const trend = data[data.length - 1].health_score - data[0].health_score;
  const trendLabel = trend > 0 ? 'Up' : trend < 0 ? 'Down' : 'Stable';

  return (
    <div className="bg-white rounded-lg p-6 border border-gray-200">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold">{title}</h3>
          <p className="text-sm text-gray-500">Trend: {trendLabel}</p>
        </div>
        <div className="text-right">
          <p className="text-sm text-gray-600">Range</p>
          <p className="text-sm font-mono">{minScore.toFixed(1)} - {maxScore.toFixed(1)}</p>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 12 }}
            tickFormatter={(value) => value.split('-')[2]}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fontSize: 12 }}
          />
          <Tooltip
            formatter={(value) => `${(value as number).toFixed(1)}%`}
            labelStyle={{ color: '#000' }}
          />
          <Line
            type="monotone"
            dataKey="health_score"
            stroke="#3b82f6"
            dot={{ fill: '#3b82f6', r: 4 }}
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
