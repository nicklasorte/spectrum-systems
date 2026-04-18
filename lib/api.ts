import {
  Execution,
  TraceDetail,
  PipelineMetrics,
} from '@/components/dashboard/types';

/**
 * Fetch recent executions from dashboard API
 */
export async function fetchExecutions(
  limit: number = 20,
  offset: number = 0
): Promise<{
  executions: Execution[];
  metrics: PipelineMetrics;
  total: number;
}> {
  try {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    const response = await fetch(`/api/executions?${params}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch executions: ${response.statusText}`);
    }
    const data = await response.json();
    return {
      executions: data.executions,
      metrics: data.metrics,
      total: data.total,
    };
  } catch (error) {
    console.error('Failed to fetch executions:', error);
    throw error;
  }
}

/**
 * Fetch detailed trace for a single execution
 */
export async function fetchTraceDetail(
  trace_id: string
): Promise<TraceDetail> {
  try {
    const response = await fetch(`/api/executions/${trace_id}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch trace: ${response.statusText}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`Failed to fetch trace detail for ${trace_id}:`, error);
    throw error;
  }
}
