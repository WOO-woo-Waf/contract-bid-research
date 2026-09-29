# Runtime input mount

Place local smoke-test inputs in this directory only when using `compose.yaml`.

- Do not commit contracts, tender files, credentials, personal data, or customer data.
- The directory is mounted read-only at `/inputs`.
- The container runs as UID/GID `10001:10001`; input files must be readable by that identity.
- Canonical JSON is intentionally written with restrictive permissions. For private files, prefer an owner-controlled staging volume instead of making them world-readable.

All files in this directory except this README are ignored by Git.
