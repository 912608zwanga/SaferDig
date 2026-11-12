# API (v1)
Interactive OpenAPI at `/docs` in non-production. All `/api/v1/*` routes need `Authorization: Bearer <Supabase access token>`.
`POST /intentions` · `GET /intentions?status=&limit=&offset=` · `GET|DELETE /intentions/{id}` · `POST /verify` · `GET /verification-history`.
Verify: 200 result, 404 not found/not yours, 409 already matched, 410 expired, 422 invalid input, 429 rate limit, 503 data service down.
Intentions are single-use once matched; after a mismatch or needs-review result the user may re-check.
