#!/usr/bin/env python3
"""
Build a ZIP per expense-export Excel file for CPA upload.

Each ZIP contains:
- 999_[property_slug]_00.csv  Directory (Excel data exported to CSV, same base name as before)
- 999_[property_slug]_01.pdf  First receipt (links to first line item)
- 999_[property_slug]_02.pdf  Second receipt, etc.
- The original Excel file (classification source)

ZIP is written next to the Excel file. Run once per Excel to produce two ZIPs for two properties.

Usage:
  # Start Lakekeeper first (Iceberg catalog on localhost:8181), then:
  uv run python -m app.scripts.build_expense_library --excel "../999 - 316 S 50th - 00.xlsx"
  uv run python -m app.scripts.build_expense_library --excel "../999 - 501 NE 67th - 00.xlsx"
  The Excel/CSV "ID" column is the expense row id (from the app Export button). Receipts are resolved via investflow.expenses.document_storage_id -> vault.

Requires: Lakekeeper (and .env with AZURE_* and LAKEKEEPER__*). From backend dir:
  docker compose up -d lakekeeper
"""
import argparse
import os
import re
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path

# Add backend to path when run as script
_backend_dir = Path(__file__).resolve().parent.parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# Load .env from backend dir so Azure/LAKEKEEPER credentials are available regardless of cwd
_env_file = _backend_dir / ".env"
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_file)

import pandas as pd
from pyiceberg.expressions import EqualTo

from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

# Column names to try for vault document ID (GUID), in order
ID_COLUMN_CANDIDATES = ("ID", "Document ID", "document_storage_id", "document_id", "Id", "id")
DEFAULT_ID_COLUMN = "ID"

# UUID regex (with or without dashes)
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
)


def _parse_doc_id(raw: object) -> uuid.UUID | None:
    """Parse a value as UUID; accept 32 hex chars without dashes, or paths like expenses/uuid or expenses/uuid.ext."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()
    if not s:
        return None
    # Path form: expenses/d4c8912c-70bc-4a9f-a59e-9986c217d651 or expenses/d4c8912c-...-d651.pdf
    if s.startswith("expenses/"):
        segment = s.removeprefix("expenses/").strip()
        if segment:
            # Strip common extension for blob path
            for ext in (".pdf", ".png", ".jpg", ".jpeg", ".webp"):
                if segment.lower().endswith(ext):
                    segment = segment[: -len(ext)]
                    break
            parsed = _parse_uuid_string(segment)
            if parsed is not None:
                return parsed
    return _parse_uuid_string(s)


def _parse_uuid_string(s: str) -> uuid.UUID | None:
    """Parse a string as UUID (with or without dashes)."""
    try:
        return uuid.UUID(s)
    except ValueError:
        pass
    s_clean = s.replace("-", "").replace(" ", "")
    if len(s_clean) == 32 and all(c in "0123456789abcdefABCDEF" for c in s_clean):
        return uuid.UUID(f"{s_clean[:8]}-{s_clean[8:12]}-{s_clean[12:16]}-{s_clean[16:20]}-{s_clean[20:]}")
    return None


def _detect_id_column(df: pd.DataFrame, explicit: str | None) -> str:
    """Return column name that contains document IDs; try candidates or explicit."""
    if explicit and explicit in df.columns:
        return explicit
    for cand in ID_COLUMN_CANDIDATES:
        if cand not in df.columns:
            continue
        non_null = df[cand].dropna().astype(str).str.strip()
        if non_null.empty:
            continue
        # Prefer column where most values parse as doc IDs (UUID or expenses/uuid)
        like_uuid = non_null.apply(lambda x: _parse_doc_id(x) is not None)
        if like_uuid.any():
            return cand
    if explicit:
        raise ValueError(f"Column '{explicit}' not found. Available: {list(df.columns)}")
    raise ValueError(
        f"No column looks like document IDs (tried {ID_COLUMN_CANDIDATES}). Available: {list(df.columns)}"
    )


def _get_catalog():
    """Lazy import so catalog is only required when script actually runs (after parsing args)."""
    try:
        from app.core.iceberg import get_catalog
        return get_catalog()
    except Exception as e:
        err_msg = str(e).lower()
        if "connection refused" in err_msg or "8181" in err_msg or "connection" in err_msg:
            raise SystemExit(
                "Cannot reach Iceberg catalog (localhost:8181). Start Lakekeeper first:\n"
                "  cd backend && docker compose up -d lakekeeper\n"
                "Then run this script again."
            ) from e
        raise


def _get_services():
    """Lazy import of document_service and adls_service (they connect to catalog/Azure at import)."""
    try:
        from app.services.adls_service import adls_service
        from app.services.document_service import document_service
        return document_service, adls_service
    except Exception as e:
        err_msg = str(e).lower()
        if "connection refused" in err_msg or "8181" in err_msg or "connection" in err_msg:
            raise SystemExit(
                "Cannot reach Iceberg catalog (localhost:8181). Start Lakekeeper first:\n"
                "  cd backend && docker compose up -d lakekeeper\n"
                "Then run this script again."
            ) from e
        raise


def lookup_user_id_for_document(doc_id: uuid.UUID) -> uuid.UUID | None:
    """Get the vault document's owner user_id by document id (no auth filter)."""
    catalog = _get_catalog()
    table = catalog.load_table("investflow.vault")
    scan = table.scan(row_filter=EqualTo("id", str(doc_id)))
    arrow_table = scan.to_arrow()
    if len(arrow_table) == 0:
        return None
    row = arrow_table.to_pylist()[0]
    return uuid.UUID(row["user_id"])


def lookup_document_storage_id_for_expense(expense_id: uuid.UUID) -> uuid.UUID | None:
    """
    Get document_storage_id (vault id) for an expense from investflow.expenses.
    The expenses screen Export uses expense.id as the ID column, so we resolve
    expense_id -> document_storage_id to fetch the receipt from the vault.
    """
    try:
        catalog = _get_catalog()
        table = catalog.load_table("investflow.expenses")
        scan = table.scan(row_filter=EqualTo("id", str(expense_id)))
        arrow_table = scan.to_arrow()
    except Exception as e:
        err_str = str(e).lower()
        if "authentication" in err_str or "authorization" in err_str or "auth" in err_str:
            raise SystemExit(
                "Azure Storage authentication failed when reading Iceberg tables. "
                "Check your .env: refresh AZURE_STORAGE_CONNECTION_STRING or SAS token if expired, "
                "and ensure Lakekeeper/catalog use the same credentials."
            ) from e
        raise
    if len(arrow_table) == 0:
        return None
    row = arrow_table.to_pylist()[0]
    raw = row.get("document_storage_id")
    if raw is None or (isinstance(raw, str) and (raw == "" or raw == "None")):
        return None
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        return None


def _get_document_blob(
    doc_id: uuid.UUID,
    user_id: uuid.UUID,
    document_service,
    adls_service,
    *,
    raw_id: str | None = None,
) -> tuple[bytes, str, str, str] | None:
    """
    Get blob (content, content_type, filename, blob_name) for a document.
    blob_name is the storage path (for Document_ID column). Returns (content, content_type, filename, blob_name) or None.
    """
    doc_id_str = str(doc_id)
    # 1) Standard lookup by vault id
    doc_meta = document_service.get_document(doc_id, user_id)
    if doc_meta and doc_meta.get("blob_name"):
        blob_name = doc_meta["blob_name"]
        content, content_type, filename = adls_service.download_blob(blob_name)
        return (content, content_type, filename, blob_name)

    # 2) Fallback: scan vault for this user; match by blob_name or file_name
    catalog = _get_catalog()
    table = catalog.load_table("investflow.vault")
    scan = table.scan(row_filter=EqualTo("user_id", str(user_id)))
    arrow_table = scan.to_arrow()
    for row in arrow_table.to_pylist():
        if not row.get("blob_name"):
            continue
        blob_name_val = row["blob_name"] or ""
        file_name_val = (row.get("file_name") or "") if row.get("file_name") is not None else ""
        # Match by full path (file_name or blob_name is e.g. expenses/d4c8912c-...)
        if raw_id and (blob_name_val == raw_id or file_name_val == raw_id):
            content, content_type, filename = adls_service.download_blob(blob_name_val)
            return (content, content_type, filename, blob_name_val)
        if raw_id and (blob_name_val.endswith(raw_id) or blob_name_val.rstrip("/").endswith(raw_id.strip("/"))):
            content, content_type, filename = adls_service.download_blob(blob_name_val)
            return (content, content_type, filename, blob_name_val)
        # Match by UUID in blob_name (e.g. expenses/user_id/UUID.pdf)
        if doc_id_str in blob_name_val or doc_id_str.replace("-", "") in blob_name_val.replace("-", ""):
            content, content_type, filename = adls_service.download_blob(blob_name_val)
            return (content, content_type, filename, blob_name_val)
    return None


def lookup_user_id_by_email(email: str) -> uuid.UUID | None:
    """Get user_id from investflow.users by email (no password used)."""
    if not email or not email.strip():
        return None
    catalog = _get_catalog()
    table = catalog.load_table("investflow.users")
    scan = table.scan(row_filter=EqualTo("email", email.strip()))
    arrow_table = scan.to_arrow()
    if len(arrow_table) == 0:
        return None
    row = arrow_table.to_pylist()[0]
    raw_id = row.get("id")
    if raw_id is None:
        return None
    return uuid.UUID(str(raw_id))


def _read_first_sheet_from_xlsx_zip(excel_path: Path) -> pd.DataFrame | None:
    """Read first worksheet from xlsx (zip) when openpyxl reports 0 worksheets. Returns None on failure.
    Supports both schema namespaces (openxmlformats and purl.oclc.org OOXML strict)."""
    import xml.etree.ElementTree as ET

    def _local(elem: ET.Element) -> str:
        return elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

    def _find_all(parent: ET.Element, local_name: str) -> list[ET.Element]:
        return [c for c in parent if _local(c) == local_name]

    def _find_one(parent: ET.Element, local_name: str) -> ET.Element | None:
        for c in parent:
            if _local(c) == local_name:
                return c
        return None

    try:
        with zipfile.ZipFile(excel_path, "r") as zf:
            names = zf.namelist()
            shared_strings = []
            if "xl/sharedStrings.xml" in names:
                with zf.open("xl/sharedStrings.xml") as f:
                    tree = ET.parse(f)
                    root = tree.getroot()
                    for si in _find_all(root, "si"):
                        t = _find_one(si, "t")
                        if t is not None and t.text:
                            shared_strings.append(t.text)
                        else:
                            parts = [n for n in si.iter() if _local(n) == "t"]
                            shared_strings.append("".join(n.text or "" for n in parts))
            sheet_path = "xl/worksheets/sheet1.xml"
            if sheet_path not in names:
                return None
            with zf.open(sheet_path) as f:
                tree = ET.parse(f)
                root = tree.getroot()
                sheet_data = _find_one(root, "sheetData")
                if sheet_data is None:
                    return None
                rows = []
                for row_elem in _find_all(sheet_data, "row"):
                    row_idx = int(row_elem.get("r", 0))
                    cells = {}
                    for c in _find_all(row_elem, "c"):
                        r = c.get("r", "")
                        v_elem = _find_one(c, "v")
                        val = ""
                        if v_elem is not None and v_elem.text is not None:
                            if c.get("t") == "s":
                                try:
                                    val = shared_strings[int(v_elem.text)]
                                except (ValueError, IndexError):
                                    val = v_elem.text
                            else:
                                val = v_elem.text
                        col = "".join(x for x in r if x.isalpha())
                        col_num = 0
                        for ch in col:
                            col_num = col_num * 26 + (ord(ch.upper()) - ord("A") + 1)
                        cells[col_num] = val
                    rows.append((row_idx, cells))
                if not rows:
                    return None
                rows.sort(key=lambda x: x[0])
                max_col = max(max(c.keys()) for _, c in rows if c) if rows else 0
                if max_col == 0:
                    return None
                data = []
                for _, cells in rows:
                    data.append([cells.get(i, "") for i in range(1, max_col + 1)])
                if not data:
                    return None
                return pd.DataFrame(data[1:], columns=data[0])
    except Exception:
        return None


def _read_excel(excel_path: Path) -> pd.DataFrame:
    """Read first sheet of an Excel file; handle workbooks with invalid sheet spec (0 worksheets)."""
    import warnings
    try:
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("ignore", UserWarning)
            return pd.read_excel(excel_path, engine="openpyxl", sheet_name=0)
    except ValueError as e:
        if "0 worksheets" not in str(e):
            raise
    # Fallback: open with openpyxl and build DataFrame from first sheet
    from openpyxl import load_workbook
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("ignore", UserWarning)
        wb = load_workbook(excel_path, read_only=True, data_only=True)
    if not wb.sheetnames:
        wb.close()
        # Some workbooks report 0 sheets with read_only=True; try read_only=False
        wb = load_workbook(excel_path, read_only=False, data_only=True)
        if wb.sheetnames:
            pass  # use normal path below
        elif getattr(wb, "worksheets", None) and len(wb.worksheets) > 0:
            # "Invalid specification for 0" was removed but worksheet data exists
            ws = wb.worksheets[0]
            rows = list(ws.iter_rows(values_only=True))
            wb.close()
            if not rows:
                raise ValueError(f"First worksheet is empty: {excel_path}")
            return pd.DataFrame(rows[1:], columns=rows[0])
        else:
            wb.close()
            # Read first sheet from xlsx zip when openpyxl reports 0 worksheets
            df = _read_first_sheet_from_xlsx_zip(excel_path)
            if df is not None:
                return df
            raise ValueError(f"Excel file has no worksheets: {excel_path}")
    sheet_name = wb.sheetnames[0]
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        raise ValueError(f"First sheet '{sheet_name}' is empty: {excel_path}")
    df = pd.DataFrame(rows[1:], columns=rows[0])
    return df


def slug_from_excel_path(excel_path: Path) -> str:
    """Derive property slug from Excel filename for PDF naming.
    e.g. '999 - 316 S 50th - 00.xlsx' -> '316_S_50th'
         '999 - 501 NE 67th - 00.xlsx' -> '501_NE_67th'
    """
    stem = excel_path.stem
    # Pattern: "999 - <address> - 00"
    m = re.match(r"^999\s*-\s*(.+?)\s*-\s*00\s*$", stem, re.IGNORECASE)
    if m:
        middle = m.group(1).strip()
    else:
        middle = stem
    return middle.replace(" ", "_").replace("/", "_")


def get_extension_from_content(content_type: str, filename: str) -> str:
    """Prefer .pdf for application/pdf, else use filename extension, else .pdf as fallback."""
    if content_type and "pdf" in content_type.lower():
        return "pdf"
    if filename and "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return "pdf"


# Directory CSV columns (order and export header names). Tax Classification = Expense Category in app export.
DIRECTORY_CSV_HEADERS = [
    "Document_ID",
    "Amount",
    "Property",
    "Date",
    "Description",
    "Vendor",
    "Tax Classification",
    "Notes",
    "Has Receipt",
]


def _get_row_val(row_dict: dict, *candidate_keys: str) -> str:
    """Get value from row dict by first matching key (case-insensitive). Returns stripped string."""
    for cand in candidate_keys:
        for k, v in row_dict.items():
            key = str(k).strip()
            if key == cand or key.lower() == cand.lower():
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    return ""
                return str(v).strip()
    return ""


def run(
    excel_path: Path,
    user_id: uuid.UUID | None = None,
    id_column: str = DEFAULT_ID_COLUMN,
    limit: int | None = None,
    email: str | None = None,
) -> Path:
    """
    Read Excel/CSV export from the expenses screen, download receipts, build directory CSV, create ZIP next to Excel.
    The Export button uses expense.id as the "ID" column; we resolve expense_id -> document_storage_id from
    investflow.expenses, then fetch the receipt blob from the vault.
    Returns path to the created ZIP file.
    If user_id is not provided, it is looked up from the first expense that has a receipt (document_storage_id).
    If limit is set (e.g. 4), only the first limit rows are processed (for a quick test run).
    If email is provided, user_id can be looked up from investflow.users by email (no password used).
    """
    excel_path = excel_path.resolve()
    if not excel_path.is_file():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    slug = slug_from_excel_path(excel_path)
    logger.info("Property slug for filenames: %s", slug)

    # Read Excel
    df = _read_excel(excel_path)
    if df.empty:
        raise ValueError("Excel has no data")

    # Normalize column names: strip whitespace
    df.columns = [str(c).strip() for c in df.columns]
    id_col = _detect_id_column(df, id_column)
    logger.info("Using document ID column: %s", id_col)

    rows_with_id = []
    for _, row in df.iterrows():
        raw_id = row.get(id_col)
        doc_id = _parse_doc_id(raw_id)
        if doc_id is None:
            continue
        raw_id_str = str(raw_id).strip() if raw_id is not None else ""
        rows_with_id.append((doc_id, row.to_dict(), raw_id_str))

    if not rows_with_id:
        raise ValueError("No rows with a valid document ID found")

    if limit is not None and limit > 0:
        rows_with_id = rows_with_id[:limit]
        logger.info("Limiting to first %d rows", len(rows_with_id))

    # Resolve user_id from vault if not provided.
    # Export uses expense.id as ID column -> resolve expense_id -> document_storage_id -> vault user_id.
    document_service, adls_service = _get_services()
    if user_id is None:
        for expense_id, _, _ in rows_with_id:
            doc_id = lookup_document_storage_id_for_expense(expense_id)
            if doc_id is not None:
                user_id = lookup_user_id_for_document(doc_id)
                if user_id is not None:
                    logger.info("Using user_id from vault (expense %s -> document %s): %s", expense_id, doc_id, user_id)
                    break
        if user_id is None:
            # Fallback: try treating ID as vault doc id (e.g. re-export with document_storage_id column)
            for doc_id, _, _ in rows_with_id:
                user_id = lookup_user_id_for_document(doc_id)
                if user_id is not None:
                    logger.info("Using user_id from vault (document %s): %s", doc_id, user_id)
                    break
        if user_id is None and email:
            user_id = lookup_user_id_by_email(email)
            if user_id is not None:
                logger.info("Using user_id from email lookup: %s", user_id)
        if user_id is None:
            env_uid = os.environ.get("EXPENSE_LIBRARY_USER_ID")
            if env_uid:
                try:
                    user_id = uuid.UUID(env_uid.strip())
                    logger.info("Using user_id from EXPENSE_LIBRARY_USER_ID: %s", user_id)
                except ValueError:
                    pass
            if user_id is None:
                raise ValueError(
                    "Could not determine user from expenses (no receipt-linked expense found in vault). "
                    "Pass --user-id, --email your@email.com, or set EXPENSE_LIBRARY_USER_ID."
                )

    logger.info("Found %d rows with valid document IDs", len(rows_with_id))

    with tempfile.TemporaryDirectory(prefix="expense_lib_") as tmp:
        tmp_path = Path(tmp)
        receipt_filenames = []
        csv_rows: list[dict[str, str]] = []

        for idx, (expense_id, row_dict, raw_id_str) in enumerate(rows_with_id, start=1):
            document_id = ""  # filename in ZIP, e.g. 999_316_S_50th_01.pdf
            try:
                # Export uses expense.id as ID -> resolve to vault document_storage_id for receipt
                doc_id = lookup_document_storage_id_for_expense(expense_id)
                if doc_id is None:
                    logger.warning("No receipt for expense %s (row %d), skipping", expense_id, idx)
                    receipt_filenames.append("")
                else:
                    result = _get_document_blob(doc_id, user_id, document_service, adls_service, raw_id=raw_id_str or None)
                    if result is None:
                        logger.warning("Document not found for expense %s (vault %s, row %d), skipping", expense_id, doc_id, idx)
                        receipt_filenames.append("")
                    else:
                        content, content_type, filename, _blob_name = result
                        ext = get_extension_from_content(content_type, filename)
                        receipt_name = f"999_{slug}_{idx:02d}.{ext}"
                        document_id = receipt_name
                        out_file = tmp_path / receipt_name
                        out_file.write_bytes(content)
                        receipt_filenames.append(receipt_name)
                        logger.info("Downloaded receipt %s", receipt_name)
            except Exception as e:
                logger.warning("Unexpected error for row %d (expense %s): %s", idx, expense_id, e)
                receipt_filenames.append("")

            # Document_ID = filename in ZIP (e.g. 999_316_S_50th_01.pdf) so it matches uploaded files
            csv_rows.append({
                "Document_ID": document_id,
                "Amount": _get_row_val(row_dict, "Amount"),
                "Property": _get_row_val(row_dict, "Property"),
                "Date": _get_row_val(row_dict, "Date"),
                "Description": _get_row_val(row_dict, "Description"),
                "Vendor": _get_row_val(row_dict, "Vendor"),
                "Tax Classification": _get_row_val(row_dict, "Expense Category", "Tax Classification"),
                "Notes": _get_row_val(row_dict, "Notes"),
                "Has Receipt": _get_row_val(row_dict, "Has Receipt"),
            })

        # Directory CSV: only Document_ID, Amount, Property, Date, Description, Vendor, Tax Classification, Notes, Has Receipt
        dir_csv_name = f"999_{slug}_00.csv"
        dir_csv_path = tmp_path / dir_csv_name
        dir_df = pd.DataFrame(csv_rows, columns=DIRECTORY_CSV_HEADERS)
        dir_df.to_csv(dir_csv_path, index=False)
        logger.info("Wrote directory CSV: %s", dir_csv_name)

        # Create ZIP next to Excel
        zip_name = f"999_{slug}_00.zip"
        zip_path = excel_path.parent / zip_name
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(dir_csv_path, dir_csv_name)
            for name in receipt_filenames:
                if name:
                    f = tmp_path / name
                    if f.exists():
                        zf.write(f, name)
            zf.write(excel_path, excel_path.name)
        logger.info("Created ZIP: %s", zip_path)
        return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build expense library ZIP (directory PDF + receipts) from an Excel export."
    )
    parser.add_argument(
        "--excel",
        type=Path,
        required=True,
        help="Path to the expense export Excel file (e.g. 999 - 316 S 50th - 00.xlsx)",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="User UUID (optional; looked up from vault using first document ID in Excel)",
    )
    parser.add_argument(
        "--id-column",
        type=str,
        default=DEFAULT_ID_COLUMN,
        help="Excel column name containing the vault document GUID (default: ID)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process only the first N rows (e.g. 4 for a quick test)",
    )
    parser.add_argument(
        "--email",
        type=str,
        default=None,
        help="Look up user_id from investflow.users by this email (no password used)",
    )
    args = parser.parse_args()
    user_uuid = uuid.UUID(args.user_id) if args.user_id else None
    zip_path = run(
        args.excel,
        user_id=user_uuid,
        id_column=args.id_column,
        limit=args.limit,
        email=args.email,
    )
    print(f"Created: {zip_path}")


if __name__ == "__main__":
    main()
