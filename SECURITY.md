# Security boundaries

The public demo is a simulation. Real integration ingestion uses a server-configured bearer token. Live model credentials are server-only. AI tools are read-only and cannot execute recovery. Recovery requires explicit approval and a current revision.

The operator API is disabled without a token. Public demo inputs cannot fetch arbitrary URLs or mutate real hardware. Sessions are isolated and bounded. Compose binds exposed ports to localhost.

To report an issue, use GitHub's private vulnerability reporting if enabled, or contact the repository owner through their public GitHub profile. Avoid posting credentials or private telemetry in public issues.
