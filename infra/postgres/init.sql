-- Runs automatically on first container start (mounted into
-- /docker-entrypoint-initdb.d by infra/docker-compose.yml).
CREATE EXTENSION IF NOT EXISTS vector;
