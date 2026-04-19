import { PostgresStorageBackend } from "./postgres-backend";

/**
 * Factory for creating PostgreSQL storage backend
 * Config from environment variables
 */

export function createPostgresBackend(): PostgresStorageBackend {
  const config = {
    pgHost: process.env.PG_HOST || "localhost",
    pgPort: parseInt(process.env.PG_PORT || "5432"),
    pgDatabase: process.env.PG_DATABASE || "spectrum_systems",
    pgUser: process.env.PG_USER || "postgres",
    pgPassword: process.env.PG_PASSWORD || "postgres",
    s3Bucket: process.env.S3_BUCKET || "spectrum-artifacts",
    s3Region: process.env.AWS_REGION || "us-east-1",
  };

  return new PostgresStorageBackend(config);
}
