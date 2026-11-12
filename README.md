# SaferDig
*Make sure the payment matches your intention.* A **simulated** prototype: it never connects to a bank or moves money.

Stack: Next.js (Vercel) · FastAPI (Render) · Supabase Postgres + Auth with RLS.

## Status
- Backend API and database schema are in place.
- Next.js frontend is implemented in `frontend/`.
- Supabase project and initial database migration are deployed.
- Render and Vercel hosting still require repository access to be granted to those platforms; see deployment steps below.

## Frontend quick start
```bash
cd frontend
npm install
cp .env.example .env.local
# Set the Supabase URL, publishable key, and API base URL
npm run dev
```

## Backend quick start
```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # fill in Supabase values
pytest -q && ruff check .
uvicorn app.main:app --reload   # http://localhost:8000/docs
```

## Database
Supabase project: `lyhozkfvtffdipclhdmo`.
The deployed schema includes `intentions` and `verification_results`, RLS policies, and a verification RPC. The backend forwards the user's JWT to Supabase, so RLS is enforced; no service-role key is needed.

## Deploy
- **Render:** Connect `912608zwanga/SaferDig` in the Render dashboard. Use root directory `backend`, build command `pip install -r requirements.txt`, start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, and health check `/health`. Set `SUPABASE_URL`, `SUPABASE_ANON_KEY` (the Supabase publishable key), `ALLOWED_ORIGINS` (the Vercel URL), and `ENVIRONMENT=production`.
- **Vercel:** Import the same repository, set root directory to `frontend`, and configure `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` (publishable key), and `NEXT_PUBLIC_API_BASE_URL` (the Render API URL).
- **Supabase Auth:** Add the Vercel URL to the Auth URL configuration and allowed redirect URLs.

## Safety
This is a demonstration tool only. It does not connect to banks, verify real payment rails, stop transfers, or guarantee recipient trust. Never enter banking passwords, PINs, or OTPs.
