# InvestFlow Azure cost analysis

**As of:** 2026-09-12  
**Resource group:** `investflow-rg`  
**Invoice reconciled:** `G182545342` — **$151.18** (Matthew Pappas section)

This note explains the last invoice, what Cost Management showed (~$91), what we deleted after Lakekeeper teardown, and the expected forward run-rate.

---

## Executive summary

| Question | Answer |
|---|---|
| Why was the invoice ~$151 but RG ActualCost ~$91? | A **compute savings plan** commitment ($58.40/mo) sits on the invoice and is easy to miss in resource-grouped Cost Analysis. |
| What did we cut? | Lakekeeper Container App, `if-postgres-restored`, Recovery vault + `lakekeeper` Azure Files share (~$44 trailing). |
| What still dominates? | Savings plan **~$58/mo** until **2027-02-10**, then Postgres (~$20) and ACR Basic (~$5). |
| App scale decision | **`minReplicas: 1`** on backend + frontend so the plan’s compute commitment buys warm apps (no 20–28s cold starts). Auto-renew **off** (confirmed). |

**Forward estimate (plan still active, current footprint):** ~**$85/mo**.  
**After plan expires (Feb 2027), same footprint at min=1:** ~**$45–50/mo**.  
**Same footprint at min=0 after plan expires:** ~**$25–35/mo** (cold starts return).

---

## Invoice G182545342 breakdown

Service period mostly **2026-08-01 → 2026-08-31** (savings plan line: **2026-08-10 → 2026-09-09**).

| Product | Charges | What it was | Going forward |
|---|---:|---|---|
| Compute savings plan, 1 Year | **$58.40** | `$0.08/hr` × ~730h commitment | **Still billing** through 2027-02-10 |
| PostgreSQL Flexible (Burstable) | $25.29 | Compute for **two** B1ms servers | ~half (only `if-postgres`) |
| PostgreSQL Flex storage | $14.72 | Storage for both servers (qty 128) | ~half |
| Azure Container Apps (3 meters) | $19.40 + $9.73 + $10.03 = **$39.16** | Lakekeeper + backend + frontend (always-on) | Lower without Lakekeeper; warm apps covered by plan |
| Container Registry Standard | $5.45 | Mid-period Standard days | Gone (Basic only now) |
| Container Registry Basic | $5.16 | Basic registry unit | ~$5/mo |
| Backup — Azure Files (US East) | $2.99 | `vault-micu37k7` / `lakekeeper` share | **$0** (deleted) |
| ADLS / Block Blob HNS LRS | $0.01 | `investflowadls` | Negligible |
| **Total** | **$151.18** | | |

---

## Cost Management vs invoice

Trailing **ActualCost** for `investflow-rg` (2026-08-13 → 2026-09-12) was about **$91.50**, by resource:

| Resource | Trailing 30d | Status |
|---|---:|---|
| investflow-lakekeeper | $21.52 | Deleted |
| if-postgres | $19.75 | Live |
| if-postgres-restored | $19.75 | Deleted |
| investflow-backend | $11.37 | Live (`minReplicas: 1`) |
| investflowregistry | $10.45 | Live (Basic) |
| investflow-frontend | $5.70 | Live (`minReplicas: 1`) |
| vault-micu37k7 | $2.95 | Deleted |
| investflowadls | $0.01 | Live |
| Log Analytics / KV / App Insights / ACA env | ~$0 | Live |

**$151 − $91 ≈ $60** lines up with the **$58.40 savings plan** (plus timing/rounding across slightly different windows).

---

## Compute savings plan (still active)

| Field | Value |
|---|---|
| Display name | `Compute_SavingsPlan_02-10-2026_07-10` |
| Commitment | **$0.08 USD / hour** → **~$58.40 / month** |
| Term | 1 year (`P1Y`), billed monthly (`P1M`) |
| Benefit start | 2026-02-10 |
| Expiry | **2027-02-10** (~150 days from 2026-09-12) |
| Scope | Resource group `investflow-rg` |
| Auto-renew | **Off** (confirmed 2026-09-12) |
| Utilization (when measured) | ~97% over 30 days with three always-on apps |

Eligible Container Apps usage draws down this commitment. Postgres, ACR, Backup, and blob storage are **not** covered by it.

Mid-term cancel/refund is usually limited; do not purchase another plan for this footprint.

---

## Decisions taken (2026-09-12)

### Scale to `minReplicas: 1`

Cold starts at `minReplicas: 0` were ~20–28s. Idle warm cost for both apps is only **~$17/mo** of on-demand equivalent — well under the **$58** commitment.

| | `min=0` | `min=1` |
|---|---|---|
| Savings plan charge | ~$58 (mostly unused) | ~$58 (covers warm apps) |
| UX | Cold starts | Warm (~0.2s) |
| Approx. total bill | ~$83–85 | ~$83–85 |

Same bill, better product → **keep min=1 until the plan expires.** Auto-renew is off, so the plan ends **2027-02-10** with no extension.

Live Azure updated; deploy pins so CI does not revert:

- `.github/workflows/deploy.yml` → `--min-replicas 1`
- `deploy.sh` → `--min-replicas 1`
- Commit: `fcb9668`

### Deleted cost centers

- Container App `investflow-lakekeeper`
- Flexible Server `if-postgres-restored`
- Recovery Services vault `vault-micu37k7`
- Azure Files share `lakekeeper` on `investflowadls` (including leased backup snapshots)

---

## Live footprint (after teardown)

| Resource | Config | Est. monthly |
|---|---|---|
| Compute savings plan | $0.08/hr until 2027-02-10 | **$58.40** |
| `if-postgres` | Standard_B1ms · 32 GB · eastus2 | **~$20** |
| `investflowregistry` | ACR Basic · eastus | **~$5** |
| `investflow-backend` | 0.5 vCPU / 1 GiB · min=1 · max=3 | Covered by plan (~$11 if PAYG) |
| `investflow-frontend` | 0.25 vCPU / 0.5 GiB · min=1 · max=3 | Covered by plan (~$6 if PAYG) |
| `investflowadls` | Hot LRS · ~0.64 GiB used | ~$0.01 |
| Log Analytics / App Insights / Key Vault / ACA env | Low / consumption | ~$0–1 |

Blobs stay on ADLS; tabular data is Postgres-only (`docs/migration/ICEBERG_TO_POSTGRES_CYCLE.md`).

---

## What to do when the plan expires (Feb 2027)

1. Confirm the savings plan is gone and no renew happened.
2. Re-measure bill for one full month at `minReplicas: 1`.
3. If cold starts are acceptable and you want to cut ~$15–20/mo, set backend/frontend (and deploy pins) back to **`minReplicas: 0`**.
4. Do **not** buy a new compute savings plan unless steady eligible usage clearly exceeds the commitment.

---

## How to re-query costs

```bash
# Trailing ActualCost by resource (investflow-rg)
SUB=$(az account show --query id -o tsv)
# POST Microsoft.CostManagement/query with ResourceGroupName filter
# Group by ResourceId

# Savings plan
az rest --method get \
  --url "https://management.azure.com/providers/Microsoft.BillingBenefits/savingsPlans?api-version=2022-11-01"

# Live scale
az containerapp list -g investflow-rg \
  --query "[].{name:name,min:properties.template.scale.minReplicas}" -o table
```

Invoice source of truth for commitment lines: Azure portal → **Invoices** → download/breakdown (e.g. `G182545342`).
