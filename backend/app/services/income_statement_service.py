"""
Income Statement PDF Generator Service
Generates a compact, pixel-perfect income statement PDF using LaTeX.
Shows revenue by unit by month and expenses by IRS Schedule E category by month.
"""
import subprocess
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from pyiceberg.expressions import EqualTo, And

from app.core.iceberg import get_catalog, table_exists, read_table_filtered, read_table
from app.core.logging import get_logger

logger = get_logger(__name__)

NAMESPACE = ("investflow",)

TAX_CATEGORY_LABELS = {
    "advertising": "Advertising",
    "auto_travel": "Auto \\& Travel",
    "cleaning": "Cleaning \\& Maint",
    "commissions": "Commissions",
    "insurance": "Insurance",
    "legal_professional": "Legal \\& Prof Fees",
    "management_fees": "Management Fees",
    "mortgage_interest": "Mortgage Interest",
    "other_interest": "Other Interest",
    "repairs": "Repairs",
    "supplies": "Supplies",
    "taxes": "Taxes",
    "utilities": "Utilities",
    "capital_improvement": "Capital Improvements",
    "other": "Other",
}

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _tex_escape(s: str) -> str:
    """Escape special LaTeX characters"""
    if not s:
        return ""
    replacements = {
        "&": "\\&",
        "%": "\\%",
        "$": "\\$",
        "#": "\\#",
        "_": "\\_",
        "{": "\\{",
        "}": "\\}",
        "~": "\\textasciitilde{}",
        "^": "\\textasciicircum{}",
    }
    for char, replacement in replacements.items():
        s = s.replace(char, replacement)
    return s


def _fmt(amount: float) -> str:
    """Format dollar amount to nearest dollar with commas, no decimal.
    Negative amounts shown in accounting format: ($1,234)"""
    if amount == 0:
        return "-"
    if amount < 0:
        return f"(\\${abs(amount):,.0f})"
    return f"\\${amount:,.0f}"


def _fmt_raw(amount: float) -> str:
    """Format amount for totals row (always show, even zero).
    Negative amounts shown in accounting format: ($1,234)"""
    if amount < 0:
        return f"(\\${abs(amount):,.0f})"
    return f"\\${amount:,.0f}"


def _fmt_noi(amount: float) -> str:
    """Format NOI cell: red text if negative, black if positive."""
    if amount < 0:
        return f"\\textcolor{{red}}{{(\\${abs(amount):,.0f})}}"
    return f"\\${amount:,.0f}"


class IncomeStatementService:
    """Generates income statement PDFs for a property"""

    def __init__(self):
        self.catalog = get_catalog()

    def generate_pdf(
        self,
        property_id: str,
        fiscal_year: int,
    ) -> bytes:
        """
        Generate an income statement PDF for a property and fiscal year.

        Returns PDF bytes.
        """
        property_data = self._get_property(property_id)
        units = self._get_units(property_id)
        revenue_data = self._get_revenue(property_id, fiscal_year)
        expense_data = self._get_expenses(property_id, fiscal_year)

        latex = self._build_latex(property_data, units, revenue_data, expense_data, fiscal_year)
        return self._compile_pdf(latex)

    def _get_property(self, property_id: str) -> Dict[str, Any]:
        df = read_table_filtered(NAMESPACE, "properties", EqualTo("id", property_id))
        if len(df) == 0:
            raise ValueError(f"Property {property_id} not found")
        row = df.iloc[0]
        return {
            "display_name": row.get("display_name") or "",
            "address_line1": row.get("address_line1") or "",
            "city": row.get("city") or "",
            "state": row.get("state") or "",
            "zip_code": row.get("zip_code") or "",
        }

    def _get_units(self, property_id: str) -> List[Dict[str, Any]]:
        if not table_exists(NAMESPACE, "units"):
            return []
        df = read_table_filtered(NAMESPACE, "units", EqualTo("property_id", property_id))
        if len(df) == 0:
            return []

        tenant_map = self._get_tenant_map(property_id)

        units = []
        for _, row in df.iterrows():
            if row.get("is_active") is False:
                continue
            unit_id = str(row["id"])
            units.append({
                "id": unit_id,
                "unit_number": row.get("unit_number") or unit_id[:6],
                "tenant_name": tenant_map.get(unit_id, ""),
            })
        units.sort(key=lambda u: u["unit_number"])
        return units

    def _get_tenant_map(self, property_id: str) -> Dict[str, str]:
        """Build unit_id -> tenant display name from active leases."""
        import json as _json
        if not table_exists(NAMESPACE, "leases"):
            return {}
        df = read_table_filtered(NAMESPACE, "leases", EqualTo("property_id", property_id))
        if len(df) == 0:
            return {}

        # Collect all candidate leases per unit, pick the most recent by lease_start
        candidates: Dict[str, list] = defaultdict(list)
        for _, row in df.iterrows():
            is_active = row.get("is_active")
            if is_active is not None and pd.notna(is_active) and not bool(is_active):
                continue
            unit_id = str(row.get("unit_id")) if pd.notna(row.get("unit_id")) else None
            if not unit_id:
                continue
            lease_start = row.get("lease_start")
            lease_start_str = str(lease_start) if pd.notna(lease_start) else "0000-01-01"
            candidates[unit_id].append((lease_start_str, row))

        result: Dict[str, str] = {}
        for unit_id, lease_rows in candidates.items():
            lease_rows.sort(key=lambda x: x[0], reverse=True)
            _, best_row = lease_rows[0]
            tenants_json = best_row.get("tenants")
            if not tenants_json or (isinstance(tenants_json, float) and pd.isna(tenants_json)):
                continue
            try:
                tenant_list = _json.loads(tenants_json) if isinstance(tenants_json, str) else tenants_json
                names = []
                for t in tenant_list:
                    first = t.get("first_name", "")
                    last = t.get("last_name", "")
                    name = f"{first} {last}".strip()
                    if name:
                        names.append(name)
                if names:
                    result[unit_id] = ", ".join(names)
            except (TypeError, ValueError):
                continue
        return result

    def _get_revenue(self, property_id: str, year: int) -> pd.DataFrame:
        if not table_exists(NAMESPACE, "rents"):
            return pd.DataFrame()
        df = read_table(NAMESPACE, "rents")
        df = df[df["property_id"] == property_id]
        if "rent_period_year" in df.columns:
            df = df[df["rent_period_year"].notna() & (df["rent_period_year"] == year)]
        if len(df) == 0:
            return pd.DataFrame()
        return df

    def _get_expenses(self, property_id: str, year: int) -> List[Dict[str, Any]]:
        import uuid as _uuid
        from app.services.expense_service import expense_service
        expenses, _ = expense_service.list_expenses(
            property_id=_uuid.UUID(property_id),
            start_date=date(year, 1, 1),
            end_date=date(year, 12, 31),
            limit=5000,
        )
        return expenses

    def _build_latex(
        self,
        prop: Dict[str, Any],
        units: List[Dict[str, Any]],
        revenue_df: pd.DataFrame,
        expenses: List[Dict[str, Any]],
        year: int,
    ) -> str:
        # Build address string
        addr_parts = [prop["address_line1"]]
        city_state = []
        if prop["city"]:
            city_state.append(prop["city"])
        if prop["state"]:
            city_state.append(prop["state"])
        if city_state:
            addr_parts.append(", ".join(city_state))
        if prop["zip_code"]:
            addr_parts[-1] += f" {prop['zip_code']}"
        address = ", ".join(p for p in addr_parts if p)

        num_months = 12
        col_spec = "l" + "r" * num_months + "r"  # account name + 12 months + total

        # ---- REVENUE SECTION ----
        # Group revenue by (unit_id, revenue_description) -> month -> amount
        rev_by_unit: Dict[str, Dict[str, Dict[int, float]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        if len(revenue_df) > 0:
            for _, row in revenue_df.iterrows():
                unit_id = str(row.get("unit_id")) if pd.notna(row.get("unit_id")) else "property"
                month = int(row["rent_period_month"]) if pd.notna(row.get("rent_period_month")) else None
                if month is None:
                    continue
                raw_desc = str(row.get("revenue_description") or "Rent") if pd.notna(row.get("revenue_description")) else "Rent"
                desc = raw_desc.replace("Monthly Rent", "Rent")
                is_non_irs = bool(row.get("is_non_irs_revenue")) if pd.notna(row.get("is_non_irs_revenue")) else False
                if is_non_irs:
                    continue
                amount = float(row["amount"]) if pd.notna(row.get("amount")) else 0
                rev_by_unit[unit_id][desc][month] += amount

        # Build unit label map (include tenant name if available)
        unit_label_map = {}
        for u in units:
            label = f"Unit {u['unit_number']}"
            if u.get("tenant_name"):
                label += f" -- {u['tenant_name']}"
            unit_label_map[u["id"]] = label
        unit_label_map["property"] = "Property"

        # Sort unit keys: property first, then units in order
        unit_keys = sorted(rev_by_unit.keys(), key=lambda k: ("0" if k == "property" else unit_label_map.get(k, k)))

        revenue_rows_latex = []
        revenue_month_totals = defaultdict(float)
        revenue_grand_total = 0.0

        for unit_key in unit_keys:
            descs = rev_by_unit[unit_key]
            unit_label = unit_label_map.get(unit_key, unit_key[:8])
            if len(unit_keys) > 1 or unit_key != "property":
                revenue_rows_latex.append(f"    \\multicolumn{{{num_months + 2}}}{{l}}{{\\textbf{{{_tex_escape(unit_label)}}}}} \\\\")
            for desc in sorted(descs.keys()):
                months = descs[desc]
                cells = []
                row_total = 0
                for m in range(1, 13):
                    val = round(months.get(m, 0))
                    revenue_month_totals[m] += val
                    row_total += val
                    cells.append(_fmt(val))
                revenue_grand_total += row_total
                revenue_rows_latex.append(
                    f"    \\quad {_tex_escape(desc)} & " + " & ".join(cells) + f" & {_fmt(row_total)} \\\\"
                )

        # Revenue totals row
        rev_total_cells = [_fmt_raw(revenue_month_totals.get(m, 0)) for m in range(1, 13)]
        rev_total_row = f"    \\textbf{{Total Revenue}} & " + " & ".join(rev_total_cells) + f" & \\textbf{{{_fmt_raw(revenue_grand_total)}}} \\\\"

        # ---- EXPENSE SECTION ----
        # Group expenses by tax_category -> month -> amount
        exp_by_cat: Dict[str, Dict[int, float]] = defaultdict(lambda: defaultdict(float))
        for exp in expenses:
            exp_date = exp.get("date")
            if not exp_date:
                continue
            if hasattr(exp_date, 'month'):
                month = exp_date.month
            else:
                try:
                    month = int(str(exp_date).split("-")[1])
                except (IndexError, ValueError):
                    continue
            cat = exp.get("tax_category") or "repairs"
            amount = float(exp.get("amount", 0))
            exp_by_cat[cat][month] += amount

        # Build expense rows in Schedule E order
        schedule_e_order = [
            "advertising", "auto_travel", "cleaning", "commissions", "insurance",
            "legal_professional", "management_fees", "mortgage_interest", "other_interest",
            "repairs", "supplies", "taxes", "utilities", "capital_improvement", "other",
        ]

        expense_rows_latex = []
        expense_month_totals = defaultdict(float)
        expense_grand_total = 0.0

        for cat in schedule_e_order:
            months = exp_by_cat.get(cat)
            if not months:
                continue
            label = TAX_CATEGORY_LABELS.get(cat, cat)
            cells = []
            row_total = 0
            for m in range(1, 13):
                val = round(months.get(m, 0))
                expense_month_totals[m] += val
                row_total += val
                cells.append(_fmt(val))
            expense_grand_total += row_total
            expense_rows_latex.append(
                f"    {label} & " + " & ".join(cells) + f" & {_fmt(row_total)} \\\\"
            )

        # Expense totals row
        exp_total_cells = [_fmt_raw(expense_month_totals.get(m, 0)) for m in range(1, 13)]
        exp_total_row = f"    \\textbf{{Total Expenses}} & " + " & ".join(exp_total_cells) + f" & \\textbf{{{_fmt_raw(expense_grand_total)}}} \\\\"

        # ---- NOI ROW ----
        noi_cells = []
        for m in range(1, 13):
            noi = revenue_month_totals.get(m, 0) - expense_month_totals.get(m, 0)
            noi_cells.append(f"\\textbf{{{_fmt_noi(noi)}}}")
        noi_total = revenue_grand_total - expense_grand_total
        noi_total_fmt = _fmt_noi(noi_total)
        noi_row = f"    \\textbf{{Net Operating Income}} & " + " & ".join(noi_cells) + f" & \\textbf{{{noi_total_fmt}}} \\\\"
        noi_color = "noirow" if noi_total >= 0 else "noiloss"

        # Month header
        month_headers = " & ".join([f"\\textbf{{{MONTH_ABBR[m-1]}}}" for m in range(1, 13)])

        # ---- ASSEMBLE LATEX ----
        latex = f"""\\documentclass[8pt,landscape]{{article}}
\\usepackage[landscape,margin=0.35in,top=0.4in,bottom=0.3in]{{geometry}}
\\usepackage{{booktabs}}
\\usepackage{{array}}
\\usepackage{{xcolor}}
\\usepackage{{colortbl}}
\\usepackage{{tabularx}}
\\usepackage{{helvet}}
\\renewcommand{{\\familydefault}}{{\\sfdefault}}
\\usepackage[T1]{{fontenc}}

\\definecolor{{headerblue}}{{HTML}}{{1a365d}}
\\definecolor{{headerbg}}{{HTML}}{{e2e8f0}}
\\definecolor{{totalrow}}{{HTML}}{{f1f5f9}}
\\definecolor{{noirow}}{{HTML}}{{dcfce7}}
\\definecolor{{noiloss}}{{HTML}}{{fee2e2}}

\\pagestyle{{empty}}
\\setlength{{\\tabcolsep}}{{3pt}}
\\renewcommand{{\\arraystretch}}{{1.15}}

\\begin{{document}}

% Title
\\noindent
\\begin{{minipage}}{{\\textwidth}}
\\textbf{{\\large Income Statement --- {_tex_escape(address)}}} \\hfill \\textbf{{Fiscal Year {year}}}
\\end{{minipage}}

\\vspace{{6pt}}
\\noindent\\rule{{\\textwidth}}{{0.5pt}}
\\vspace{{4pt}}

% Main table
{{\\footnotesize
\\noindent
\\begin{{tabular*}}{{\\textwidth}}{{@{{\\extracolsep{{\\fill}}}}{col_spec}@{{}}}}
\\toprule
\\rowcolor{{headerbg}}
\\textbf{{Account}} & {month_headers} & \\textbf{{Total}} \\\\
\\midrule

% --- REVENUE ---
\\rowcolor{{headerbg}}
\\multicolumn{{{num_months + 2}}}{{l}}{{\\textbf{{Revenue}}}} \\\\
{chr(10).join(revenue_rows_latex)}
\\midrule
\\rowcolor{{totalrow}}
{rev_total_row}

\\addlinespace[4pt]

% --- EXPENSES ---
\\rowcolor{{headerbg}}
\\multicolumn{{{num_months + 2}}}{{l}}{{\\textbf{{Operating Expenses (Schedule E)}}}} \\\\
{chr(10).join(expense_rows_latex)}
\\midrule
\\rowcolor{{totalrow}}
{exp_total_row}

\\addlinespace[2pt]
\\midrule
\\rowcolor{{{noi_color}}}
{noi_row}

\\bottomrule
\\end{{tabular*}}
}}

\\end{{document}}
"""
        return latex

    def _compile_pdf(self, latex_content: str) -> bytes:
        """Compile LaTeX to PDF using pdflatex"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            tex_file = tmpdir_path / "income_statement.tex"
            pdf_file = tmpdir_path / "income_statement.pdf"

            tex_file.write_text(latex_content, encoding="utf-8")

            try:
                for _ in range(2):
                    result = subprocess.run(
                        ["pdflatex", "-interaction=nonstopmode",
                         "-output-directory", str(tmpdir_path), str(tex_file)],
                        capture_output=True,
                        timeout=30,
                    )

                if not pdf_file.exists():
                    log_file = tmpdir_path / "income_statement.log"
                    log_content = log_file.read_text() if log_file.exists() else "No log"
                    logger.error(f"pdflatex failed. Log:\n{log_content[-2000:]}")
                    raise RuntimeError(f"PDF compilation failed: {result.stderr.decode()[-500:]}")

                return pdf_file.read_bytes()
            except subprocess.TimeoutExpired:
                raise RuntimeError("PDF compilation timed out")


income_statement_service = IncomeStatementService()
