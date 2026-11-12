# Known limitations (honest status)
- **Frontend not yet built.** Only backend, schema, CI and docs exist so far.
- **Not run against a real Supabase project.** API tests use an in-memory repository; the SQL migration and PostgREST repository are unexecuted. RLS tests need a Supabase project (or local `supabase start`).
- Rate limiting is in-memory (single Render instance only).
- `pending`/`expired` list filters are applied per page, because expiry is derived at read time.
- No account deletion or recovery endpoints yet (recovery is via Supabase Auth in the frontend).
- No security review or compliance assessment has been done. Simulation only; no bank integration.
