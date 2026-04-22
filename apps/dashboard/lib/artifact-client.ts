/**
 * Artifact Store HTTP Client
 * Handles API communication, retries, caching
 */

export interface EntropySnapshot {
  artifact_type: string;
  snapshot_id: string;
  timestamp: string;
  week_ending?: string;
  metrics: Record<string, any>;
  control_decisions: string[];
  recommendation: string;
  is_fallback?: boolean;
}

export interface QueryResult {
  error?: string;
  data?: any[];
  [key: string]: any;
}

export class ArtifactStoreClient {
  private baseUrl: string;
  private timeout: number;
  private cache: Map<string, { data: any; timestamp: number }>;
  private cacheMaxAge: number = 30000; // 30s

  constructor(baseUrl: string, timeout: number = 5000) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.timeout = timeout;
    this.cache = new Map();
  }

  async getEntropySnapshot(): Promise<EntropySnapshot> {
    const cacheKey = 'entropy-latest';

    // Check cache
    const cached = this.cache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < this.cacheMaxAge) {
      return cached.data;
    }

    try {
      const response = await this.fetchWithRetry(
        `${this.baseUrl}/api/entropy/latest-snapshot`,
        { method: 'GET' }
      );

      this.cache.set(cacheKey, {
        data: response,
        timestamp: Date.now()
      });

      return response;
    } catch (error) {
      throw new Error(`Failed to fetch entropy snapshot: ${error}`);
    }
  }

  async executeQuery(
    queryName: string,
    params: Record<string, any> = {}
  ): Promise<QueryResult> {
    const cacheKey = `query-${queryName}-${JSON.stringify(params)}`;

    const cached = this.cache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < this.cacheMaxAge) {
      return cached.data;
    }

    try {
      const queryParams = new URLSearchParams(params);
      const response = await this.fetchWithRetry(
        `${this.baseUrl}/api/queries/${queryName}?${queryParams}`,
        { method: 'GET' }
      );

      this.cache.set(cacheKey, {
        data: response,
        timestamp: Date.now()
      });

      return response;
    } catch (error) {
      throw new Error(`Query ${queryName} failed: ${error}`);
    }
  }

  private async fetchWithRetry(
    url: string,
    options: RequestInit,
    retries: number = 3
  ): Promise<any> {
    for (let attempt = 0; attempt < retries; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), this.timeout);

        const response = await fetch(url, {
          ...options,
          signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        return await response.json();
      } catch (error) {
        if (attempt === retries - 1) throw error;
        await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
      }
    }
  }

  clearCache(): void {
    this.cache.clear();
  }
}
