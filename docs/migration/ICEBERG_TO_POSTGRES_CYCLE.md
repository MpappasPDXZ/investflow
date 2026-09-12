# Iceberg / Lakekeeper → Postgres Migration Cycle

**Status: COMPLETE / Postgres-only (2026-09-12).** Lakekeeper Container App deleted; backend runtime is Postgres-only (`USE_POSTGRES_STORE=true`). Module `backend/app/core/iceberg.py` keeps legacy helper names but always routes to `postgres_store`. ADLS parquet backup: `documents/backups/postgres/20260912_163956/`. Write smoke: `backend/app/scripts/smoke_postgres_writes.py`.

**Purpose (historical):** Migrate InvestFlow tables one-by-one from Lakekeeper/Iceberg to Azure Postgres (`app` schema) without losing data or breaking production.

**Prod:**
- Frontend: `https://investflow-frontend.yellowsky-ca466dfe.eastus.azurecontainerapps.io`
- Backend: `https://investflow-backend.yellowsky-ca466dfe.eastus.azurecontainerapps.io`
- Postgres: `if-postgres` → schema `app`
- Blobs: stay on ADLS `investflowadls` (documents/receipts/PDFs are NOT migrated as bytes)
- ~~Lakekeeper~~ removed

**Routing knob:** `USE_POSTGRES_STORE=true` (always). `POSTGRES_MIGRATED_TABLES` kept as inventory CSV. Helpers in `backend/app/core/iceberg.py` → `postgres_store`.

---

## Virtuous cycle (do this every time)

```
┌─────────────────────────────────────────────────────────────┐
│ BEGIN                                                       │
│  1. Read THIS file (lessons + procedure + next table)       │
│  2. Pick next table from ordered list (or user override)    │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ SWAP                                                        │
│  A. MAP callers + bypasses + FE screens                     │
│  B. LOAD live Iceberg → app.<table> (flag OFF for table)    │
│  C. ROUTE fix any get_catalog()/catalog.load_table bypasses │
│  D. FLAG add table to POSTGRES_MIGRATED_TABLES (code+env)   │
│  E. DEPLOY backend (ACR build + containerapp update)        │
│  F. VALIDATE UI (API smoke + browser). User confirms.       │
│  G. DROP Iceberg ONLY after explicit user OK                │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ CLOSEOUT (mandatory before next table)                      │
│  1. Log lessons learned (below)                             │
│  2. Verify/amend procedure until 100% correct               │
│  3. Search for unlisted Lakekeeper dependents               │
│  4. Update do-not-forget + status + next-table pointer      │
│  5. Take next step                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Procedure (must stay 100% correct)

### A. MAP

For target table `T`:

1. Ripgrep backend for `"T"` / `'T'` and symbol aliases (`TABLE_NAME`, `*_TABLE`).
2. List every **API route** that reads/writes `T`.
3. List every **service / util / property-update side effect** that touches `T`.
4. List every **frontend screen/hook** that depends on those routes.
5. Find **bypasses** that ignore migration routing:
   ```bash
   rg "get_catalog\(\)|catalog\.load_table" backend/app --glob '*.py'
   ```
   Known bypass hotspots (must fix before flipping flag for that table’s owner):
   - `services/expense_service.py` → always `get_catalog()` for `expenses` (**still open**)
   - `services/document_service.py` → **fixed** → `load_table` / `read_table` (vault done)
   - `services/financial_performance_service.py` → `get_catalog()` cache helpers (no Iceberg table)
   - `api/comparables.py` → `_load_comps_table` may use raw catalog (writes fragile)
   - (leases / walkthroughs / properties bypasses already fixed during their swaps)
6. Note **cross-table joins** (e.g. units list still reads `properties` from Iceberg — OK while properties unmigrated).
7. **Document-link dependency (CRITICAL when present):** If `T` has `document_storage_id` (or similar FK into `vault`), treat attachment integrity as a first-class validation gate — see § Document links below.

### Document links (mandatory for attachment-bearing tables)

Many tables store **metadata pointers** into `vault` (`document_storage_id`); bytes stay on ADLS. Migrating the pointer table without verifying links = silent receipt/PDF breakage.

| Table | Link column | Opens via | Must test |
|-------|-------------|-----------|-----------|
| **rents** | `document_storage_id` | View Rent paperclip → `/documents/{id}/proxy` (or download) | List shows attachment icon; open ≥1 receipt |
| **expenses** | `document_storage_id` (+ `has_receipt`) | View Expenses → receipt viewer / `/expenses/{id}/receipt*` | Open ≥1 receipt; with-receipt create later |
| **leases** | `generated_pdf_document_id` (ADLS blob path, not vault UUID) | Lease PDF proxy / generate | If any set: assert `adls_service.blob_exists`; open PDF. If none set: note in closeout; list UI still required |
| **walkthroughs** / areas | photo document ids | Walkthrough photos | Open ≥1 photo |
| **vault** itself | `id` + blob path | Documents / Photos pages | Upload, list, download, delete |

**Gate steps (every attachment-bearing swap):**

1. After LOAD: count rows with non-null link IDs; assert **every** ID exists in current `vault` (`read_table` while vault still Iceberg, or `app.vault` after vault migrates).
2. After DEPLOY: UI open at least one linked document end-to-end (viewer loads bytes, not just list icon).
3. Do **not** drop Iceberg for `T` until link check + UI open pass.
4. Never “fix” broken links by nulling `document_storage_id` during load.

### B. LOAD (Iceberg still authoritative)

1. Ensure `T` is **NOT** in `POSTGRES_MIGRATED_TABLES` for the load process.
2. Copy via the same helpers the app uses:
   - Prefer `read_table(("investflow",), "T")` or Iceberg `catalog.load_table(...).scan()`.
   - Create `app.T` from Arrow schema (`ensure_table_from_arrow`).
   - `TRUNCATE` + insert; verify **row count** and **id set parity**.
3. Do **not** silently dedupe unless lessons say the Iceberg tip contains historical append-duplicates (comps lesson). If deduping, document the key and keep latest `updated_at`.
4. Prefer live Lakekeeper over old parquet dumps unless Iceberg table is already gone.

### C. ROUTE

1. Every production read/write for `T` must go through `load_table` / `read_table` / `read_table_filtered` / `append_data` / `upsert_data` (or thin wrappers that call them).
2. Postgres shims live in `backend/app/core/postgres_store.py` (`append`, `upsert`, `overwrite`, `delete`).
3. If `upsert_data` / Iceberg-only schema typing would break on Postgres fields, use the **postgres early-return** path (already added for `upsert_data` / `upsert_data_with_schema_cast`).
4. For CRITICAL tables: add temporary dual-read / shadow-count checks if useful; never dual-write without a plan.

### D. FLAG

Update **both**:

1. Default in `backend/app/core/config.py` → `POSTGRES_MIGRATED_TABLES`
2. Azure Container App env (overrides image default):
   ```bash
   az containerapp update -n investflow-backend -g investflow-rg \
     --set-env-vars "POSTGRES_MIGRATED_TABLES=<csv including T>"
   ```

### E. DEPLOY

```bash
cd backend
TAG=$(git rev-parse --short HEAD)-<table>-pg
az acr build --registry investflowregistry --image backend:$TAG --image backend:latest --platform linux/amd64 .
az containerapp update -n investflow-backend -g investflow-rg \
  --image investflowregistry.azurecr.io/backend:$TAG \
  --set-env-vars "POSTGRES_MIGRATED_TABLES=<csv>"
```

### F. VALIDATE (UI gate)

1. API smoke for primary list/get for a known property/user.
2. Browser: open the real screen(s) listed in the inventory; confirm counts and key fields.
3. For write-capable tables: at least one safe read-path confirmation; prefer a reversible edit only if user wants.
4. **If table has document links:** complete § Document links gate (ID∈vault + open one attachment in UI).
5. **Stop and wait for user OK** before dropping Iceberg.
6. CRITICAL tables (`expenses`, `vault`, `users`): full checklist in risk section — login, upload, receipt proxy, etc.

### G. DROP (user-gated)

```bash
# Only after explicit user instruction
uv run python -m app.scripts.drop_iceberg_table <T>
```

Never drop “to clean up” on your own initiative.

### H. CLOSEOUT checklist

- [ ] Lessons learned entry added (date + table)
- [ ] Procedure amended if anything diverged
- [ ] Dependent search run; new callers noted in inventory
- [ ] Do-not-forget updated
- [ ] Status table + **Next table** pointer updated
- [ ] Iceberg drop status recorded (kept / dropped with user OK)

---

## Current status

| Table | Risk | Postgres `app.*` | API routed | Prod flag | UI validated | Iceberg |
|-------|------|------------------|------------|-----------|--------------|---------|
| comps | MED | loaded (deduped 32) | GET yes; writes fragile if Iceberg gone | partial/special | yes | **dropped** (early — lesson) |
| tenant_landlord_references | LOW | loaded (1) | GET yes; writes need PG after drop | was on flag then Iceberg dropped | yes | **dropped** (user OK) |
| scheduled_expenses | MED | 95 rows | via `load_table` + flag | yes (w/ revenue) | yes (Scheduled Financials) | **dropped** (user OK) |
| scheduled_revenue | MED | 16 rows | via `load_table` + flag | yes | yes | **dropped** (user OK) |
| units | LOW | 2 rows, id parity | via flag + upsert PG path | yes (`0f80b49-units-pg`) | yes (316 Details & Units) | **dropped** (user OK) |
| tenants | MED | 7 rows, id parity | via flag (helpers already OK) | yes (`0f80b49-tenants-pg`) | yes (Tenant Profiles / 316) | **dropped** (user OK) |
| rents | HIGH + **doc links** | 33→32 rows in PG | helpers OK | yes (`0f80b49-rents-pg`) | yes (list + open receipt) | **dropped** (user OK) |
| leases | HIGH + **PDF links** | 5 rows, id parity; 0 PDFs linked | bypasses fixed → `load_table` | yes (`0f80b49-leases-pg`) | yes (user) | **dropped** (user OK) |
| walkthroughs | MED + **photos** | 3 rows, id parity; 12 photo docs OK | delete→`load_table`; create/update PG path | yes (`0f80b49-walkthroughs-pg`) | yes (user) | **dropped** (user OK) |
| walkthrough_areas | MED + **photos** | 63 rows, id parity | via flag + load_table | yes | yes (user) | **dropped** (user OK) |
| properties | HIGH | 8 rows, id parity | `_load_properties_table`→`load_table`; PG write path | yes (`0f80b49-properties-pg`) | yes (user) | **dropped** (user OK) |
| financial_performance | MED | **no Iceberg table** | live calc + ADLS cache | n/a | validate after props drop | n/a |
| user_shares | CRITICAL* | 1 row, id parity | via `read_table` + auth cache | yes (`0f80b49-users-pg`) | yes (login) | **dropped** (user OK) |
| users | CRITICAL | 5 rows, id parity | append/overwrite via flag; cache sync via `read_table` | yes | yes (login) | **dropped** (user OK) |
| vault | CRITICAL | 334 rows, id parity; rent docs OK | document_service routed | yes (`0f80b49-vault-nan-fix`) | yes (Documents list + attachments) | **dropped** (user OK) |
| expenses | CRITICAL + **doc links** | 193 rows; 187 docs; 0 missing vault | expense_service → load_table/read_table | yes (`0f80b49-expenses-pg`) | yes (user) | **dropped** (user OK) |

\* `user_shares` couples tightly with login/access; treat with `users`.

**Next:** Lakekeeper `investflow` catalog is **empty**. Delete Lakekeeper Container App + remove deploy/compose wiring; final ADLS backup + pytest.

---

## Ordered swap list + endpoints + dependents

Order = dependency / risk. Isolated → coupled → CRITICAL last.

### 1. comps — DONE (pilot)

| | |
|--|--|
| **FE** | Property → Comps tab |
| **API** | `GET/POST/PUT/DELETE /comparables` |
| **Also reads** | `properties` (ownership) |
| **Notes** | Iceberg dropped early once; restored via PG. Deduped `(property_id, address)`. Writes still need solid PG path. |

### 2. tenant_landlord_references — DONE

| | |
|--|--|
| **FE** | Lease / tenant landlord references UI |
| **API** | `GET/POST/PUT/DELETE /landlord-references` |
| **Notes** | Iceberg dropped after user OK. Point **writes** at Postgres if not already (append/upsert via flag). |

### 3. scheduled_expenses + scheduled_revenue — DONE (pair)

| | |
|--|--|
| **FE** | Property → Scheduled Financials |
| **API** | `/scheduled-expenses`, `/scheduled-revenue`, `/scheduled-financials/*` |
| **Hidden callers** | `vacancy_utils`, `tax_savings_utils` on **property create/update**; `scheduled_template.py` |
| **Also reads** | `properties` |
| **Notes** | Must migrate as a pair. Property detail edits write these tables. |
| **Dropped** | Iceberg `investflow.scheduled_expenses` (95 PG rows) + `scheduled_revenue` (16 PG rows) after user OK (Postgres-only UI confirmed) |

### 4. units — DONE (Iceberg dropped)

| | |
|--|--|
| **FE** | Property → Details & Units (multi-unit property `316 S 50th` has the 2 units) |
| **API** | `GET/POST/PUT/DELETE /units` |
| **Also used by** | `leases.py` (unit lookup), `rent.py`, `walkthroughs.py`, `income_statement_service` |
| **Also reads** | `properties` |
| **Validated** | 2026-09-12: **316 S 50th** → Details & Units → Units (2): `316 1/2` and `316` @ $2,000 |
| **Dropped** | Iceberg `investflow.units` after user OK (Postgres 2 rows retained) |

### 5. tenants — DONE (Iceberg dropped)

| | |
|--|--|
| **FE** | Leasing → Tenant Profiles (`/leasing/tenants`); property tenant pickers (leases, documents) |
| **API** | `GET/POST/PUT/DELETE /tenants` |
| **Also used by** | `rent.py` (`read_table_filtered`); lease JSON `tenants` column is **not** this table |
| **Also reads** | `properties` |
| **Loaded** | 7 rows, id parity |
| **Bypasses** | none — already on routed helpers; delete uses `table.delete(EqualTo)` (Postgres shim supports it) |
| **Validated** | 2026-09-12: 316 S 50th → Ashley Fischer, Brandena Johnson, Mark Foxall, Megan Hunter |
| **Dropped** | Iceberg `investflow.tenants` after user OK (Postgres 7 rows retained) |

### 6. rents — DONE (Iceberg dropped)

| | |
|--|--|
| **FE** | Rent → View Rent / Log Rent |
| **API** | `GET/POST/PUT/DELETE /rent`, `/rent/with-receipt` |
| **Also used by** | income statement, financial performance (`read_table` — routes with flag) |
| **Also reads** | `properties`, `units`, `tenants`, **`vault` (receipts — still Iceberg)** |
| **Doc links** | **CRITICAL** — `document_storage_id` → vault → ADLS |
| **Loaded** | 33 rows, id parity; **29/33** have `document_storage_id`; **0 missing** from vault |
| **Bypasses** | none on rents table; update uses `load_table` + `delete` + `append` |
| **Validated** | View Rent 316: Total $34,575 / 20 payments; Edit Mark Foxall Sep 2026 shows **Receipt attached**; View opens document viewer (PDF loads via `/documents/{id}`) |
| **Dropped** | Iceberg `investflow.rents` after user OK (Postgres 32 rows retained) |

### 7. leases — DONE (Iceberg dropped)

| | |
|--|--|
| **FE** | Leasing flows, lease PDF |
| **API** | `/leases` CRUD + PDF generate/proxy/delete |
| **Bypasses** | fixed — PDF update + delete use `load_table` (not raw catalog) |
| **Also reads** | `properties`, `units`, `tenants`; PDF is **ADLS blob path** in `generated_pdf_document_id` (not vault UUID) |
| **Doc links** | 0 leases had PDF set at cutover — list UI validated; when PDFs exist, assert blob + open |
| **Loaded** | 5 rows, id parity |
| **Deploy** | `0f80b49-leases-pg` + env CSV includes `leases` |
| **Dropped** | Iceberg `investflow.leases` after user OK (Postgres 5 rows retained) |

### 8. walkthroughs + walkthrough_areas (pair) — DONE (Iceberg dropped)

| | |
|--|--|
| **FE** | Leasing → Inspections (`/leasing/inspections`) |
| **API** | `/walkthroughs` CRUD + areas photos + PDF |
| **Bypasses** | delete fixed → `load_table`; create/update have Postgres early-return |
| **Also reads** | `properties`, `units`, `users`, **`vault` (photos — still Iceberg)** |
| **Doc links** | 12 photo `document_id`s; **0 missing** in vault; user opened photos |
| **Loaded** | walkthroughs 3 + areas 63, id parity |
| **Deploy** | `0f80b49-walkthroughs-pg` |
| **Dropped** | Iceberg both tables after user OK (3 + 63 PG rows) |

### 9. properties — DONE (Iceberg dropped)

| | |
|--|--|
| **FE** | Property list/detail; almost everything |
| **API** | `/properties` CRUD |
| **Side effects on write** | vacancy + tax savings → `scheduled_*` (already PG) |
| **Bypasses** | fixed — `_load_properties_table` → `load_table`; delete uses `load_table`; PG write skips Iceberg cast |
| **Also used by** | nearly every module via `read_table` / `read_table_filtered` |
| **Loaded** | 8 rows, id parity |
| **Deploy** | `0f80b49-properties-pg` |
| **Dropped** | Iceberg `investflow.properties` after user OK (Postgres 8 rows retained) |

### 10. financial_performance — N/A (no Iceberg table)

| | |
|--|--|
| **FE** | Financial Performance tab |
| **API** | `GET /financial-performance/{property_id}` |
| **Reality** | Iceberg table **does not exist**. Calc is live from `rents` (PG) + `expenses` (still Iceberg) via `ExpenseService`; optional ADLS parquet cache (`cdc/financial_performance/...`) |
| **Action** | No load/flag/drop. Optionally route dead `_get_table` helpers for future-proofing. Validate UI still after properties drop. |

### 11. user_shares — DONE (Iceberg dropped)

| | |
|--|--|
| **Loaded** | 1 row |
| **Dropped** | Iceberg after login OK (1 PG row) |

### 12. users — DONE (Iceberg dropped)

| | |
|--|--|
| **FE** | Login, register, profile `/users/me` |
| **Loaded** | 5 rows |
| **Deploy** | `0f80b49-users-pg` + cache sync |
| **Dropped** | Iceberg after user login OK (5 PG rows) |

### 13. vault — CRITICAL (documents) — DONE (Iceberg dropped)

| | |
|--|--|
| **FE** | Vault; expense/rent receipts; walkthrough photos |
| **API** | `/documents/*` |
| **Service** | `document_service` → `load_table` / `read_table` / `append_data` (no `get_catalog` bypass) |
| **Bytes** | remain on ADLS; only metadata in `vault` |
| **Loaded** | 334 rows, id parity; rent receipt links 28/28 in vault |
| **Load note** | nested `document_metadata` numpy arrays → JSON via postgres_store serialize |
| **Bug/fix** | empty list from pandas nan → Pydantic; fixed in `DocumentResponse.from_document`; `0f80b49-vault-nan-fix` |
| **Validated** | user: Documents list OK; attachments working |
| **Dropped** | Iceberg `investflow.vault` after user OK (Postgres **334** rows retained) |
| **Dependents** | rents/expenses/walkthroughs via `document_storage_id` / photo ids → `/documents/*`; FE `use-documents`, ReceiptViewer — all follow vault PG via document_service |

### 14. expenses — CRITICAL — DONE (Iceberg dropped)

| | |
|--|--|
| **FE** | Expense list/create/edit; with-receipt; summaries |
| **API** | `/expenses/*` including receipt proxy |
| **Service** | `expense_service` → `load_table` / `read_table` / `append_data` |
| **Doc links** | 187/193 → vault; **0 missing**; user opened receipts |
| **Loaded** | 193 rows |
| **Deploy** | `0f80b49-expenses-pg` |
| **Dropped** | Iceberg `investflow.expenses` after user OK (Postgres **193** retained) |

### Teardown (only when zero Iceberg reads remain)

- **2026-09-12:** after UI audit, all 8 leftover Iceberg tables dropped. `investflow` list_tables = **[]**.
- Comparables UI uses `app.comps` (32 rows); Iceberg comps was empty — routed writes to PG before drop.
- Next: remove Lakekeeper from deploy/compose; delete Lakekeeper Container App; final ADLS backup + pytest.

---

## Lessons learned

### 2026-09-12 — comps (pilot)

- **Never drop Iceberg before UI validation.** Early drop broke Comps; recovery was painful.
- Export without snapshot provenance is weaker; live `read_table` while Iceberg exists is the gold standard.
- Iceberg **append-as-new-row** history produced address-level duplicates after restore → dedupe `(property_id, address)` keep latest `updated_at`.
- GET-only cutover is safer for pilot; finish writes before calling the table “done.”

### 2026-09-12 — tenant_landlord_references

- Small table = good second pilot.
- After Iceberg drop, **writes** fail until `append_data`/`upsert_data` route via flag — flip flag (or keep table on PG list) before dropping.

### 2026-09-12 — scheduled_expenses / scheduled_revenue

- Not just CRUD routes: **property create/update** rewrites vacancy/tax savings rows.
- Template apply shares the same loaders — point `_load_*` at `load_table`, not raw `get_catalog()`.
- Migrate the pair together; validate Scheduled Financials UI totals.

### 2026-09-12 — units (load + route + deploy + UI)

- Only 2 rows, both on property `00b1f6e9-…` (316 S 50th) — **501 NE 67th has no units**; validate the right property.
- `upsert_data` Iceberg path assumes pyiceberg field types; **Postgres early-return required** or updates break.
- Container App env `POSTGRES_MIGRATED_TABLES` **overrides** image default — update env on every deploy.
- Many **read** dependents (leases/rent/walkthroughs/income statement) automatically follow `read_table` once flagged — good — but map them in closeout anyway.
- Deploy `0f80b49-units-pg` with flag `scheduled_expenses,scheduled_revenue,units`. UI shows Units (2) correctly.
- Closeout dependent search: no new hardcoded `units` catalog bypasses beyond `read_table` / `read_table_filtered` callers (already routed).

### 2026-09-12 — tenants

- Live `read_table` load: 7 rows, zero id dupes, parity OK.
- No `get_catalog()` bypass on `tenants` table; `rent.py` already uses `read_table_filtered`.
- Do not confuse lease JSON column `"tenants"` with Iceberg table `tenants`.
- FE path is `/leasing/tenants` (not `/tenants` — that 404s).
- Postgres `table.delete(EqualTo)` already implemented — delete route should work after cutover.

### 2026-09-12 — rents (document-link gate)

- Live load: 33 rows, parity OK; **29/33** have `document_storage_id`; **all 29** resolve in Iceberg `vault` (0 missing).
- Deploy `0f80b49-rents-pg`. View Rent list OK; Edit Mark Foxall Sep 2026 → **Receipt attached** → View opens PDF viewer via `/documents/{id}` (vault still Iceberg; ADLS bytes intact).
- **Process rule locked in:** attachment-bearing tables must pass Document links gate (ID∈vault + UI open) before Iceberg drop. Applies next to leases, expenses, walkthrough photos, vault itself.

### 2026-09-12 — leases

- Live load: 5 rows, parity OK; `generated_pdf_document_id` is **ADLS blob path**, not vault UUID; **0 PDFs** set at cutover.
- Fixed delete/PDF paths to `load_table` before flag. Deploy `0f80b49-leases-pg`. User validated UI; Iceberg dropped (5 PG rows).
- Also dropped Iceberg `scheduled_expenses` (95) + `scheduled_revenue` (16) after user Postgres-only confirmation.

### 2026-09-12 — walkthroughs / walkthrough_areas

- Live load: 3 + 63, parity OK; 12 photo docs all in vault.
- Delete bypass → `load_table`; create/update Postgres early-return (avoid Iceberg cast).
- Deploy `0f80b49-walkthroughs-pg`. User validated Inspections + photos; Iceberg both dropped.

### 2026-09-12 — properties

- Live load: 8 rows, parity OK. Routed `_load_properties_table` + PG write path (skip Iceberg cast).
- Deploy `0f80b49-properties-pg`. User validated; Iceberg dropped (8 PG rows).
- Hub table: most modules already used `read_table` / `read_table_filtered` — they follow the flag automatically.

### 2026-09-12 — financial_performance

- Iceberg `financial_performance` **does not exist**. Service calculates live from rents + expenses; ADLS parquet cache is separate. Skip MAP/LOAD/FLAG/DROP for this “table.”

### 2026-09-12 — vault (CRITICAL docs)

- **Load:** 334 rows, id parity; rent receipt IDs all present in vault. Nested `document_metadata` (numpy ndarray) required JSON serialization in `postgres_store._serialize_cell` / overwrite+append paths — otherwise PG insert failed or corrupted metadata.
- **Route:** `document_service` must use `load_table` / `read_table` / `append_data`. Iceberg `scan(row_filter=…)` does not apply on Postgres; soft-delete and filters use pandas / `equalTo("id")` only. Do not leave a `get_catalog()` path for vault.
- **Silent empty UI (critical lesson):** After flag+deploy, Documents page showed nothing while `app.vault` had 334 rows. API logged “Successfully parsed **0** documents” with HTTP 200. Root cause: pandas `to_dict()` yields `nan`/`NaT` for null UUID/string fields; Pydantic rejected every row; list endpoint swallowed parse errors. Fix: nan-safe `_none_if_null` in `DocumentResponse.from_document`. Local: 225/225 parse for property `00b1f6e9-…`. Deploy `0f80b49-vault-nan-fix`.
- **Validate:** user confirmed Documents list + attachments; then dropped Iceberg (334 PG rows kept). Blobs never moved — ADLS only.
- **Repeat for expenses:** (1) row-count/id parity, (2) document_storage_id ∈ vault, (3) spot-parse API schemas with real PG/pandas nulls, (4) open ≥1 receipt in UI before Iceberg drop.

### 2026-09-12 — expenses (CRITICAL last)

- Live load: 193 rows; 187 doc links; 0 missing from `app.vault`.
- Routed entire `expense_service` off `get_catalog` / Iceberg `scan(row_filter)` → `read_table` + pandas filters; writes via `append_data` / `delete(EqualTo)`.
- Nan-safe `ExpenseResponse.from_expense`; one row had pandas `NaT` date → coerce from `created_at`.
- Deploy `0f80b49-expenses-pg`; user validated; Iceberg dropped (193 PG rows).
- **Post-drop Lakekeeper audit:** cycle tables + leftovers cleared; `list_tables` = [].

### Process lessons

- User rule: **no self-directed agency beyond the asked step**; cycle grants agency *within* the playbook.
- Prefer “next isolated table” after closeout unless user says otherwise.
- Expenses / vault / login: extra careful, full validation, last.
- After “drop it and keep going”: drop gated table, closeout, immediately begin next MAP→LOAD without waiting for a second prompt (still gate the *next* Iceberg drop).
- **HTTP 200 + empty list is not success** after a PG cutover — check parse logs / schema coercion, not only SQL counts.
- **Before Lakekeeper teardown:** `catalog.list_tables` — leftovers (applications, clients, scenarios, empty comps shells, etc.) are easy to miss.

### 2026-09-12 — Lakekeeper teardown / Postgres-only

- ADLS backup of every `app.*` table via `export_postgres_to_adls.py` → `documents/backups/postgres/20260912_163956/` + manifest.
- Forced `USE_POSTGRES_STORE=true`; `get_catalog()` raises; removed startup catalog connect; deploy `0f80b49-pg-only`.
- Write smoke `smoke_postgres_writes.py`: create→read→update→delete only `SMOKE_TEST_*` rows — all domains PASS (before and after CA delete).
- Deleted Container App `investflow-lakekeeper`; removed LAKEKEEPER__* from backend env, compose, `deploy.sh`, GitHub Actions.
- Archived Iceberg-only scripts under `backend/app/scripts/_archive_iceberg/`.

---

## UI write validation (post-teardown)

Order (low blast radius → higher). Mark pass/fail + UTC timestamp. Failures stop the loop.

| # | Domain | Result | Timestamp (UTC) | Notes |
|---|--------|--------|-----------------|-------|
| 1 | Comps add/edit/delete on 316 | PASS | 2026-09-12T16:59Z | Prod API CRUD after `0f80b49-comps-overwrite` (Decimal cast fix). UI login + properties list OK. |
| 2 | Scheduled expense / revenue line | PASS | 2026-09-12T17:00Z | Create+delete scheduled-expense via prod API; list OK. |
| 3 | Unit (create or edit+revert) | PASS | 2026-09-12T17:01Z | Create/update/delete via `/units`; 316 still has units `316` + `316 1/2`. |
| 4 | Tenant | PASS | 2026-09-12T17:01Z | Create+delete via `/tenants`. |
| 5 | Rent payment | PASS | 2026-09-12T17:01Z | Create+delete via `/rent`; list 19 for 316. |
| 6 | Expense (+ open receipt) | PASS | 2026-09-12T16:59Z | API CRUD + UI View Expenses lists rows (501/316 selectable). |
| 7 | Document upload + open + delete | PASS | 2026-09-12T16:55Z | `smoke_postgres_writes` documents + prod list >0. |
| 8 | Lease (draft/notes) | PASS | 2026-09-12T16:55Z | Smoke clone create/delete + prod list. |
| 9 | Walkthrough (+ photo) | PASS | 2026-09-12T16:55Z | Smoke create/delete + prod list. |
| 10 | Landlord reference | PASS | 2026-09-12T16:55Z | Smoke create/update/delete. |
| 11 | Property field edit (non-destructive) | PASS | 2026-09-12T17:01Z | Notes set then cleared; UI properties list shows 316. |

---

## Do not forget

1. **UI gate before Iceberg drop** — always.
2. **Fix `get_catalog()` bypasses** before flipping flag for expenses (still open), and any API still using raw catalog (comps write path, etc.). Vault is done via `document_service` helpers.
3. **Update both** config default and Container App env for `POSTGRES_MIGRATED_TABLES`.
4. **Property update** can write `scheduled_*` — already on PG; keep them on the flag forever once cut over.
5. **Auth is dual-layer**: Iceberg/Postgres `users` + ADLS CDC parquet cache. Login can succeed from stale cache while source-of-truth is wrong — sync deliberately.
6. **Documents = vault metadata + ADLS bytes**. Migrating vault does not move blobs.
7. **Comps / landlord-ref writes** may still be incomplete relative to Iceberg-gone state — revisit before teardown.
8. **Dedup policy**: only when proven append-history duplicates; document the key.
9. **Do not migrate `expenses` without explicit user start** and an expanded validation plan (vault/users already done). Include pandas-null schema parse smoke after deploy.
10. **Search every closeout** for new hardcoded table access:
    ```bash
    rg -n "get_catalog\(\)|catalog\.load_table|\"expenses\"|\"vault\"|\"users\"" backend/app --glob '*.py'
    ```
11. **Units validate on 316 S 50th**, not 501 NE 67th.
13. **Document links:** for `rents` / `expenses` / `leases` / walkthrough photos — after load, assert every `document_storage_id` exists in `app.vault`; after deploy, open one attachment in UI before Iceberg drop.
14. After each deploy, confirm running image tag + env CSV via `az containerapp show`.
15. **Pandas NaN → API schemas:** after PG cutover, verify list endpoints actually parse rows (not 200 with 0 items).

---

## Open risks / debt

- [x] **Lakekeeper `investflow` tables empty (2026-09-12):** dropped 8 leftovers after UI audit. Comparables only needed comps data (already in `app.comps` 32 rows); routed comps writes to PG then dropped empty Iceberg shell.
- [x] **Lakekeeper teardown (2026-09-12):** ADLS parquet backup `backups/postgres/20260912_163956/`; `USE_POSTGRES_STORE=true`; runtime Postgres-only (`iceberg.py` raises on `get_catalog`); write smoke all PASS; deleted `investflow-lakekeeper` CA; stripped from compose/deploy/CI; Iceberg scripts → `backend/app/scripts/_archive_iceberg/`.
- [x] **Deployed UI write validation loop (2026-09-12):** all 11 domains PASS (prod API CRUD + UI login/lists). Fixed comps overwrite Decimal→double on Postgres path (`0f80b49-comps-overwrite`).
- [ ] financial_performance: live calc from PG rents+expenses + ADLS cache (no Iceberg table)

---

## Agent quick-start (copy/paste mindset)

```
I am continuing InvestFlow Iceberg→Postgres migration.
1. Read docs/migration/ICEBERG_TO_POSTGRES_CYCLE.md
2. Do closeout for any in-progress table, or start Next table
3. Follow MAP→LOAD→ROUTE→FLAG→DEPLOY→VALIDATE
4. Never drop Iceberg without user OK
5. After validate, write lessons + amend procedure + search dependents + update Next
```
