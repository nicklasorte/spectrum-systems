import {
  Execution,
  TraceDetail,
} from '@/components/dashboard/types';

export async function fetchExecutions(
  limit: number = 20,
  offset: number = 0
): Promise<Execution[]> {
  try {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    const response = await fetch(`/api/executions?${params}`);
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    const data = await response.json();
    return data.executions;
  } catch (error) {
    console.error('Failed to fetch executions:', error);
    throw error;
  }
}

export async function fetchTraceDetail(
  trace_id: string
): Promise<TraceDetail> {
  try {
    const response = await fetch(`/api/executions/${trace_id}`);
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`Failed to fetch trace detail for ${trace_id}:`, error);
    throw error;
  }
}
