import { StorageBackend } from "./types";

export class MemoryStorageBackend implements StorageBackend {
  private data: Map<string, unknown> = new Map();

  async store(key: string, value: unknown): Promise<void> {
    this.data.set(key, value);
  }

  async retrieve(key: string): Promise<unknown | null> {
    return this.data.get(key) ?? null;
  }

  async exists(key: string): Promise<boolean> {
    return this.data.has(key);
  }

  async list(prefix?: string): Promise<string[]> {
    const keys = Array.from(this.data.keys());
    if (!prefix) return keys;
    return keys.filter(k => k.startsWith(prefix));
  }

  async delete(key: string): Promise<void> {
    this.data.delete(key);
  }
}
