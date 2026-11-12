# IntentGuard
*Make sure the payment matches your intention.* A **simulated** prototype: it never connects to a bank or moves money.

Stack: Next.js (Vercel) · FastAPI (Render) · Supabase Postgres + Auth with RLS.

## Status
Backend, migration, tests and CI are done. Frontend is **not built yet**. See `docs/known-limitations.md`.

## Backend quick start
```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # fill in Supabase values
pytest -q && ruff check .
uvicorn app.main:app --reload   # http://localhost:8000/docs
```
## Database
Run `supabase/migrations/20261112000000_init.sql` in the Supabase SQL editor (or `supabase db push`).
The backend forwards the user's JWT to Supabase, so RLS is enforced; no service-role key is needed.

## Deploy
- **Render:** New Web Service from the repo (or `render.yaml`), root `backend`, health check `/health`; set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `ALLOWED_ORIGINS` (your Vercel URL, no wildcard).
- **Vercel:** import repo, root `frontend`, set the three `NEXT_PUBLIC_*` variables.
- **Supabase:** Auth > URL configuration: add your Vercel URL as Site URL and redirect.
Nothing has been deployed yet.
