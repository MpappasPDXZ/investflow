"""Smoke-test Postgres writes: create → read → update → delete ONLY the test row.

Usage:
  cd backend && USE_POSTGRES_STORE=true uv run python -m app.scripts.smoke_postgres_writes

Anchor property: 316 S 50th (00b1f6e9-...).
Every test row is tagged with SMOKE_TEST_{uuid} in a string field.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Tuple

import pandas as pd
from pyiceberg.expressions import EqualTo

from app.core.iceberg import append_data, load_table, read_table, uses_postgres
from app.core.logging import get_logger
from app.schemas.expense import ExpenseCreate, ExpenseType, ExpenseUpdate, TaxCategory
from app.services.expense_service import expense_service
from app.services.document_service import document_service

logger = get_logger(__name__)

NAMESPACE = ("investflow",)
PROPERTY_ID = "00b1f6e9-174f-40a3-b2e9-af1518c6c69a"
SMOKE = f"SMOKE_TEST_{uuid.uuid4().hex[:12]}"


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _read(table: str) -> pd.DataFrame:
    return read_table(NAMESPACE, table)


def _delete_by_id(table: str, row_id: str) -> None:
    load_table(NAMESPACE, table).delete(EqualTo("id", str(row_id)))


def smoke_expenses() -> None:
    name = f"{SMOKE} expense"
    user_id = uuid.uuid4()
    created = expense_service.create_expense(
        user_id=user_id,
        expense_data=ExpenseCreate(
            property_id=uuid.UUID(PROPERTY_ID),
            description=name,
            vendor="Smoke Vendor",
            expense_type=ExpenseType.OTHER,
            tax_category=TaxCategory.OTHER,
            amount=Decimal("1.23"),
            date=date.today(),
            notes=SMOKE,
        ),
    )
    eid = str(created["id"])
    got = expense_service.get_expense(uuid.UUID(eid))
    _assert(got is not None and got.get("description") == name, "expense create/read failed")
    updated = expense_service.update_expense(
        uuid.UUID(eid),
        ExpenseUpdate(description=f"{name} UPDATED", amount=Decimal("2.34")),
    )
    _assert(updated and "UPDATED" in str(updated.get("description")), "expense update failed")
    _assert(expense_service.delete_expense(uuid.UUID(eid)), "expense delete failed")
    _assert(expense_service.get_expense(uuid.UUID(eid)) is None, "expense still present after delete")


def smoke_comps() -> None:
    cid = str(uuid.uuid4())
    now = datetime.utcnow()
    row = {
        "id": cid,
        "property_id": PROPERTY_ID,
        "unit_id": None,
        "address": f"{SMOKE} 123 Smoke St",
        "city": "Lincoln",
        "state": "NE",
        "zip_code": "68510",
        "property_type": "single_family",
        "is_furnished": False,
        "bedrooms": 2,
        "bathrooms": Decimal("1.0"),
        "square_feet": 900,
        "asking_price": Decimal("1200.00"),
        "has_fence": False,
        "has_solid_flooring": False,
        "has_quartz_granite": False,
        "has_ss_appliances": False,
        "has_shaker_cabinets": False,
        "has_washer_dryer": False,
        "garage_spaces": None,
        "date_listed": date.today(),
        "date_rented": date.today() + timedelta(days=30),
        "contacts": 0,
        "is_rented": False,
        "last_rented_price": None,
        "last_rented_year": None,
        "is_subject_property": False,
        "is_active": True,
        "notes": SMOKE,
        "created_at": now,
        "updated_at": now,
    }
    append_data(NAMESPACE, "comps", pd.DataFrame([row]))
    df = _read("comps")
    match = df[df["id"].astype(str) == cid]
    _assert(len(match) == 1, "comps create/read failed")
    # update via delete+append
    row["notes"] = f"{SMOKE} UPDATED"
    row["updated_at"] = datetime.utcnow()
    _delete_by_id("comps", cid)
    append_data(NAMESPACE, "comps", pd.DataFrame([row]))
    df = _read("comps")
    match = df[df["id"].astype(str) == cid]
    _assert(len(match) == 1 and SMOKE in str(match.iloc[0]["notes"]), "comps update failed")
    _delete_by_id("comps", cid)
    df = _read("comps")
    _assert(df[df["id"].astype(str) == cid].empty, "comps delete failed")


def smoke_units() -> None:
    uid = str(uuid.uuid4())
    now = datetime.utcnow()
    row = {
        "id": uid,
        "property_id": PROPERTY_ID,
        "unit_number": f"SMOKE-{SMOKE[-6:]}",
        "bedrooms": 1,
        "bathrooms": Decimal("1.0"),
        "square_feet": 500,
        "current_monthly_rent": Decimal("100.00"),
        "notes": SMOKE,
        "created_at": now,
        "updated_at": now,
        "is_active": True,
    }
    append_data(NAMESPACE, "units", pd.DataFrame([row]))
    df = _read("units")
    _assert(not df[df["id"].astype(str) == uid].empty, "units create/read failed")
    row["notes"] = f"{SMOKE} UPDATED"
    row["updated_at"] = datetime.utcnow()
    _delete_by_id("units", uid)
    append_data(NAMESPACE, "units", pd.DataFrame([row]))
    df = _read("units")
    _assert(SMOKE in str(df[df["id"].astype(str) == uid].iloc[0]["notes"]), "units update failed")
    _delete_by_id("units", uid)
    _assert(_read("units")[_read("units")["id"].astype(str) == uid].empty, "units delete failed")


def smoke_tenants() -> None:
    tid = str(uuid.uuid4())
    now = datetime.utcnow()
    # Discover columns from existing table
    existing = _read("tenants")
    cols = list(existing.columns) if not existing.empty else [
        "id", "property_id", "first_name", "last_name", "email", "phone",
        "status", "notes", "created_at", "updated_at",
    ]
    row: Dict[str, Any] = {c: None for c in cols}
    row.update({
        "id": tid,
        "property_id": PROPERTY_ID,
        "first_name": "Smoke",
        "last_name": SMOKE[-8:],
        "email": f"smoke_{SMOKE[-8:]}@example.com",
        "phone": "555-0100",
        "status": "applicant",
        "notes": SMOKE,
        "created_at": now,
        "updated_at": now,
    })
    # Keep only known cols
    row = {k: row.get(k) for k in cols}
    append_data(NAMESPACE, "tenants", pd.DataFrame([row]))
    df = _read("tenants")
    _assert(not df[df["id"].astype(str) == tid].empty, "tenants create/read failed")
    row["notes"] = f"{SMOKE} UPDATED"
    row["updated_at"] = datetime.utcnow()
    _delete_by_id("tenants", tid)
    append_data(NAMESPACE, "tenants", pd.DataFrame([row]))
    _delete_by_id("tenants", tid)
    _assert(_read("tenants")[_read("tenants")["id"].astype(str) == tid].empty, "tenants delete failed")


def smoke_rents() -> None:
    rid = str(uuid.uuid4())
    now = datetime.utcnow()
    existing = _read("rents")
    cols = list(existing.columns)
    sample = existing.iloc[0].to_dict() if not existing.empty else {}
    row = {c: sample.get(c) for c in cols}
    row.update({
        "id": rid,
        "property_id": PROPERTY_ID,
        "amount": Decimal("1.00"),
        "payment_date": date.today(),
        "rent_period_month": date.today().month,
        "rent_period_year": date.today().year,
        "rent_period_start": date.today().replace(day=1),
        "rent_period_end": date.today(),
        "notes": SMOKE,
        "revenue_description": SMOKE,
        "document_storage_id": None,
        "created_at": now,
        "updated_at": now,
    })
    row = {k: row.get(k) for k in cols}
    append_data(NAMESPACE, "rents", pd.DataFrame([row]))
    df = _read("rents")
    _assert(not df[df["id"].astype(str) == rid].empty, "rents create/read failed")
    row["notes"] = f"{SMOKE} UPDATED"
    row["updated_at"] = datetime.utcnow()
    _delete_by_id("rents", rid)
    append_data(NAMESPACE, "rents", pd.DataFrame([row]))
    _delete_by_id("rents", rid)
    _assert(_read("rents")[_read("rents")["id"].astype(str) == rid].empty, "rents delete failed")


def smoke_documents() -> None:
    props = _read("properties")
    owners = props[props["id"].astype(str) == PROPERTY_ID]
    _assert(not owners.empty, "anchor property missing for document smoke")
    user_id = uuid.UUID(str(owners.iloc[0]["user_id"]))
    doc = document_service.upload_document(
        user_id=user_id,
        file_content=b"%PDF-1.4 smoke",
        filename=f"{SMOKE}.pdf",
        content_type="application/pdf",
        document_type="other",
        property_id=uuid.UUID(PROPERTY_ID),
        display_name=SMOKE,
    )
    did = uuid.UUID(str(doc["id"]))
    got = document_service.get_document(did, user_id)
    _assert(got is not None, "document create/read failed")
    _assert(document_service.soft_delete_document(did, user_id), "document delete failed")


def smoke_scheduled() -> None:
    specs = (
        ("scheduled_expenses", {"item_name": SMOKE, "notes": SMOKE, "annual_cost": Decimal("1.00")}),
        ("scheduled_revenue", {"item_name": SMOKE, "notes": SMOKE, "annual_amount": Decimal("1.00")}),
    )
    for table, overrides in specs:
        existing = _read(table)
        cols = list(existing.columns)
        sid = str(uuid.uuid4())
        now = datetime.utcnow()
        sample = existing.iloc[0].to_dict() if not existing.empty else {}
        row = {c: sample.get(c) for c in cols}
        row.update(overrides)
        row["id"] = sid
        row["property_id"] = PROPERTY_ID
        row["is_active"] = True
        row["created_at"] = now
        row["updated_at"] = now
        row = {k: row.get(k) for k in cols}
        append_data(NAMESPACE, table, pd.DataFrame([row]))
        df = _read(table)
        _assert(not df[df["id"].astype(str) == sid].empty, f"{table} create/read failed")
        row["is_active"] = False
        row["updated_at"] = datetime.utcnow()
        _delete_by_id(table, sid)
        append_data(NAMESPACE, table, pd.DataFrame([row]))
        soft = _read(table)
        match = soft[soft["id"].astype(str) == sid]
        _assert(len(match) == 1 and bool(match.iloc[0]["is_active"]) is False, f"{table} soft-delete failed")
        _delete_by_id(table, sid)
        _assert(_read(table)[_read(table)["id"].astype(str) == sid].empty, f"{table} hard delete failed")


def smoke_landlord_references() -> None:
    table = "tenant_landlord_references"
    existing = _read(table)
    cols = list(existing.columns)
    rid = str(uuid.uuid4())
    now = datetime.utcnow()
    sample = existing.iloc[0].to_dict() if not existing.empty else {}
    row = {c: sample.get(c) for c in cols}
    row.update({
        "id": rid,
        "landlord_name": SMOKE,
        "notes": SMOKE,
        "created_at": now,
        "updated_at": now,
    })
    row = {k: row.get(k) for k in cols}
    append_data(NAMESPACE, table, pd.DataFrame([row]))
    _assert(not _read(table)[_read(table)["id"].astype(str) == rid].empty, "landlord_ref create failed")
    row["notes"] = f"{SMOKE} UPDATED"
    row["updated_at"] = datetime.utcnow()
    _delete_by_id(table, rid)
    append_data(NAMESPACE, table, pd.DataFrame([row]))
    _delete_by_id(table, rid)
    _assert(_read(table)[_read(table)["id"].astype(str) == rid].empty, "landlord_ref delete failed")


def smoke_users() -> None:
    table = "users"
    existing = _read(table)
    cols = list(existing.columns)
    uid = str(uuid.uuid4())
    now = datetime.utcnow()
    sample = existing.iloc[0].to_dict() if not existing.empty else {}
    row = {c: sample.get(c) for c in cols}
    row.update({
        "id": uid,
        "email": f"smoke_{SMOKE[-10:]}@example.com",
        "password_hash": sample.get("password_hash") or "smoke",
        "first_name": "Smoke",
        "last_name": SMOKE[-8:],
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    })
    row = {k: row.get(k) for k in cols}
    append_data(NAMESPACE, table, pd.DataFrame([row]))
    df = _read(table)
    _assert(not df[df["id"].astype(str) == uid].empty, "users create/read failed")
    row["last_name"] = f"{SMOKE}UPD"
    row["updated_at"] = datetime.utcnow()
    _delete_by_id(table, uid)
    append_data(NAMESPACE, table, pd.DataFrame([row]))
    mid = _read(table)
    _assert("UPD" in str(mid[mid["id"].astype(str) == uid].iloc[0]["last_name"]), "users update failed")
    _delete_by_id(table, uid)
    _assert(_read(table)[_read(table)["id"].astype(str) == uid].empty, "users delete failed")


def smoke_leases() -> None:
    table = "leases"
    existing = _read(table)
    if existing.empty:
        logger.warning("leases empty — skipping structural clone smoke")
        return
    cols = list(existing.columns)
    lid = str(uuid.uuid4())
    now = datetime.utcnow()
    row = existing.iloc[0].to_dict()
    row["id"] = lid
    if "notes" in cols:
        row["notes"] = SMOKE
    if "created_at" in cols:
        row["created_at"] = now
    if "updated_at" in cols:
        row["updated_at"] = now
    # Avoid unique collisions on display fields if any
    row = {k: row.get(k) for k in cols}
    append_data(NAMESPACE, table, pd.DataFrame([row]))
    _assert(not _read(table)[_read(table)["id"].astype(str) == lid].empty, "leases create failed")
    _delete_by_id(table, lid)
    _assert(_read(table)[_read(table)["id"].astype(str) == lid].empty, "leases delete failed")


def smoke_walkthroughs() -> None:
    table = "walkthroughs"
    existing = _read(table)
    if existing.empty:
        logger.warning("walkthroughs empty — skipping")
        return
    cols = list(existing.columns)
    wid = str(uuid.uuid4())
    now = datetime.utcnow()
    row = existing.iloc[0].to_dict()
    row["id"] = wid
    if "notes" in cols:
        row["notes"] = SMOKE
    if "created_at" in cols:
        row["created_at"] = now
    if "updated_at" in cols:
        row["updated_at"] = now
    row = {k: row.get(k) for k in cols}
    append_data(NAMESPACE, table, pd.DataFrame([row]))
    _assert(not _read(table)[_read(table)["id"].astype(str) == wid].empty, "walkthroughs create failed")
    _delete_by_id(table, wid)
    _assert(_read(table)[_read(table)["id"].astype(str) == wid].empty, "walkthroughs delete failed")


def smoke_properties_update() -> None:
    """Non-destructive: set notes/name marker then restore original."""
    table = "properties"
    df = _read(table)
    match = df[df["id"].astype(str) == PROPERTY_ID]
    _assert(not match.empty, "anchor property missing")
    original = match.iloc[0].to_dict()
    cols = list(df.columns)
    # Prefer a free-text column
    field = "notes" if "notes" in cols else ("name" if "name" in cols else None)
    if field is None:
        logger.warning("properties has no notes/name — skip update smoke")
        return
    before = original.get(field)
    updated = {k: original.get(k) for k in cols}
    updated[field] = f"{SMOKE} TMP"
    if "updated_at" in cols:
        updated["updated_at"] = datetime.utcnow()
    _delete_by_id(table, PROPERTY_ID)
    append_data(NAMESPACE, table, pd.DataFrame([updated]))
    mid = _read(table)
    mid_row = mid[mid["id"].astype(str) == PROPERTY_ID].iloc[0]
    _assert(SMOKE in str(mid_row[field]), "properties update failed")
    # restore
    restored = {k: original.get(k) for k in cols}
    _delete_by_id(table, PROPERTY_ID)
    append_data(NAMESPACE, table, pd.DataFrame([restored]))
    after = _read(table)
    after_row = after[after["id"].astype(str) == PROPERTY_ID].iloc[0]
    # Allow None/nan equivalence
    _assert(str(after_row[field]) == str(before) or (pd.isna(after_row[field]) and (before is None or pd.isna(before))),
            "properties restore failed")


SMOKES: List[Tuple[str, Callable[[], None]]] = [
    ("expenses", smoke_expenses),
    ("comps", smoke_comps),
    ("units", smoke_units),
    ("tenants", smoke_tenants),
    ("rents", smoke_rents),
    ("documents", smoke_documents),
    ("scheduled", smoke_scheduled),
    ("landlord_references", smoke_landlord_references),
    ("users", smoke_users),
    ("leases", smoke_leases),
    ("walkthroughs", smoke_walkthroughs),
    ("properties_update", smoke_properties_update),
]


def main() -> None:
    _assert(uses_postgres("expenses"), "USE_POSTGRES_STORE / routing not Postgres-only")
    results: List[Dict[str, Any]] = []
    failed = 0
    print(f"SMOKE_TAG={SMOKE}")
    for name, fn in SMOKES:
        try:
            fn()
            results.append({"domain": name, "status": "PASS"})
            print(f"PASS {name}")
        except Exception as e:
            failed += 1
            results.append({"domain": name, "status": "FAIL", "error": str(e)})
            logger.error(f"FAIL {name}: {e}", exc_info=True)
            print(f"FAIL {name}: {e}")
    print("---")
    for r in results:
        print(r)
    if failed:
        raise SystemExit(f"{failed} smoke domain(s) failed")
    print("ALL_WRITE_SMOKES_OK")


if __name__ == "__main__":
    main()
