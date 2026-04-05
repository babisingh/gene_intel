# Tinsel — Claude Code Phase Prompts

Use these prompts with Claude Code (`claude`) to drive each development phase.
All commands should be run from the repo root (`artgene-archive/`).

---

## Phase 2 — Real Gate Adapters

```
In packages/tinsel-gates/sentinel_gates/adapters/:

1. Replace mock_esmfold.py with a real ESMFoldAdapter that calls the ESMFold
   API at https://api.esmatlas.com/foldSequence/v1/pdb (POST, plain-text body).
   - Parse the returned PDB to extract per-residue pLDDT from the B-factor column.
   - Compute plddt_mean and plddt_min from that array.
   - Set structure_confidence: "high" if plddt_mean >= 70, "medium" >= 50, else "low".
   - Return ESMFoldResult with status PASS if plddt_mean >= 50, else FAIL.
   - Add ESMFOLD_API_KEY env-var support (Bearer token header).
   - Add integration test in tests/integration/test_esmfold_adapter.py
     (skip unless ESMFOLD_API_KEY is set).

2. Replace mock_ncbi_blast.py with a real NCBIBlastAdapter using the
   NCBI E-utilities API (blastp or blastn based on sequence type).
   - POST to https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi with program=blastp,
     database=nr, format_type=JSON2.
   - Poll for results, parse top 5 hits: accession, description, identity, e_value.
   - FAIL if max_identity >= 90 % against a Select Agent organism
     (use the select_agents.txt allowlist in packages/tinsel-gates/data/).
   - Add NCBI_API_KEY env-var support.

3. Replace mock_toxinpred.py with a real ToxinPredAdapter:
   - POST sequence to https://webs.iiitd.edu.in/raghava/toxinpred/ (scrape or
     use the ToxinPred2 model if a public API exists).
   - Parse toxicity_probability from response.
   - FAIL if probability >= 0.5.

All real adapters must fall back gracefully to ERROR status (not raise) when
the upstream service is unavailable.
```

---

## Phase 3 — Dashboard ScreenForm Component

```
In apps/dashboard/:

1. Create app/components/ScreenForm.tsx
   - Textarea for sequence input (placeholder: "Paste amino-acid or nucleotide sequence…")
   - Text input for sequence_id (placeholder: "e.g. candidate_001")
   - Submit button: "Run Screen"
   - On submit: POST to ${process.env.NEXT_PUBLIC_TINSEL_API_URL}/screen
   - Show loading spinner during request.
   - On success pass result to a GateResultTable component.
   - On error show a red error banner.

2. Create app/components/GateResultTable.tsx
   - Accepts a PipelineResult prop.
   - Renders a table with columns: Gate | Status | Score | Details.
   - Color-code rows: green for PASS, red for FAIL, orange for ERROR, grey for PENDING.
   - Show an overall banner: "CLEARED" (green) or "FLAGGED" (red) based on overall_status.

3. Wire ScreenForm into app/page.tsx.

4. Add Tailwind CSS:
   - npm install -D tailwindcss postcss autoprefixer
   - npx tailwindcss init -p
   - Configure tailwind.config.js for the app/ directory.
   - Add @tailwind directives to app/globals.css.

5. Write Vitest unit tests for GateResultTable in __tests__/GateResultTable.test.tsx.
```

---

## Phase 4 — Authentication & Rate-Limiting

```
In packages/tinsel-api/tinsel_api/:

1. Add JWT authentication middleware using python-jose and passlib.
   - POST /auth/token accepts {username, password} and returns a JWT.
   - Store users in a simple in-memory dict for now (swap for DB in Phase 6).
   - Protect POST /screen with Depends(get_current_user).
   - Add TINSEL_SECRET_KEY env-var (min 32 chars, validated at startup).

2. Add per-IP rate limiting with slowapi (wraps limits library):
   - 10 requests / minute per API key for /screen.
   - Return 429 with Retry-After header on limit exceeded.

3. Write pytest tests in packages/tinsel-api/tests/:
   - test_auth.py: valid login, invalid password, expired token, missing token.
   - test_rate_limit.py: mock clock, confirm 11th request → 429.
```

---

## Phase 5 — Audit Log & Async Queue

```
1. In packages/tinsel-core/tinsel/models.py add:
   class AuditEntry(BaseModel):
       entry_id: str                 # UUID
       sequence_id: str
       sequence_hash: str            # SHA-256 of sequence
       submitted_by: str             # username
       submitted_at: datetime
       overall_status: GateStatus
       gate_results: List[GateResult]

2. In packages/tinsel-api/:
   - Add a background task (FastAPI BackgroundTasks) that writes AuditEntry
     to a SQLite DB (packages/tinsel-api/data/audit.db) after every /screen call.
   - Add GET /audit endpoint (admin-only JWT role) that returns paginated audit entries.
   - Add DELETE /audit/{entry_id} (admin-only) for GDPR erasure.

3. Replace synchronous pipeline.run() with an async queue backed by
   asyncio.Queue:
   - POST /screen enqueues the job and returns a job_id immediately (202 Accepted).
   - GET /screen/{job_id} polls for result (returns 200 with result or 202 still pending).
   - Worker coroutine drains the queue and writes results to SQLite.
```

---

## Phase 6 — Production Hardening & Deployment

```
1. Docker
   - Write packages/tinsel-api/Dockerfile (python:3.12-slim, non-root user,
     COPY only necessary files, CMD uvicorn tinsel_api.main:app).
   - Write apps/dashboard/Dockerfile (node:20-alpine, multi-stage: builder + runner,
     NEXT_PUBLIC_ args passed at build time).
   - Add healthcheck targets to docker-compose.yml.

2. AWS CDK (TypeScript) in infra/:
   - Lambda function for tinsel-api (Mangum handler already wired).
   - API Gateway HTTP API → Lambda.
   - CloudFront + S3 for Next.js static export.
   - Secrets Manager for all API keys.
   - Write cdk.json and bin/tinsel.ts.

3. Observability
   - Add opentelemetry-sdk to tinsel-api; export traces to OTEL_EXPORTER_OTLP_ENDPOINT.
   - Instrument pipeline.run() with a span per gate.
   - Add Sentry.init() with SENTRY_DSN env-var.

4. CI/CD additions to .github/workflows/ci.yml:
   - deploy job (needs: [test-tinsel-core, lint, build-dashboard]):
     - Runs only on push to main.
     - npm run build in apps/dashboard.
     - cdk deploy --require-approval never in infra/.
```
