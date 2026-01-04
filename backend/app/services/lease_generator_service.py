"""
Lease Generator Service
Generates PDF lease agreements from templates using LaTeX.
All temporary and final files are stored in ADLS.
"""
import json
import subprocess
import tempfile
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from app.services.adls_service import adls_service


class LeaseGeneratorService:
    """Service for generating PDF lease agreements from data"""

    def __init__(self):
        self.adls = adls_service
        self.temp_folder = "leases/temp"  # ADLS folder for temporary files
        self.final_folder = "leases/generated"  # ADLS folder for final PDFs

    def generate_lease_pdf(
        self,
        lease_data: Dict[str, Any],
        tenants: List[Dict[str, Any]],
        property_data: Dict[str, Any],
        user_id: str
    ) -> Tuple[bytes, str, str]:
        """
        Generate PDF lease from lease data and store in ADLS.

        Args:
            lease_data: Dictionary with lease terms
            tenants: List of tenant dictionaries
            property_data: Property information
            user_id: User ID for ADLS folder organization

        Returns:
            Tuple of (pdf_bytes, pdf_blob_name, latex_blob_name)
        """
        # Generate LaTeX content
        latex_content = self._build_latex_document(lease_data, tenants, property_data)

        # Save LaTeX to ADLS
        latex_blob_name = self._save_latex_to_adls(
            latex_content,
            lease_data,
            property_data,
            user_id
        )

        # Compile to PDF
        pdf_bytes = self._compile_pdf(latex_content)

        # Save PDF to ADLS
        pdf_blob_name = self._save_pdf_to_adls(
            pdf_bytes,
            lease_data,
            property_data,
            user_id
        )

        return pdf_bytes, pdf_blob_name, latex_blob_name

    def _build_latex_document(
        self,
        lease_data: Dict[str, Any],
        tenants: List[Dict[str, Any]],
        property_data: Dict[str, Any]
    ) -> str:
        """Build complete LaTeX document from lease data"""

        # ============================================================================
        # EXTRACT ALL VARIABLES - GROUPED BY TYPE
        # ============================================================================

        # --- STRING VARIABLES ---
        tenant_names = ", ".join([f"{t.get('first_name', '')} {t.get('last_name', '')}" for t in tenants])
        owner_name = self._escape_latex(lease_data.get("owner_name", "S&M Axios Heartland Holdings, LLC"))
        manager_name = self._escape_latex(lease_data.get("manager_name", "Sarah Pappas"))
        manager_address = self._escape_latex(lease_data.get("manager_address", "1606 S 208th St, Elkhorn, NE 68022"))
        payment_method = self._escape_latex(lease_data.get("payment_method", "TurboTenant"))
        full_address = property_data.get("address", "")
        property_address = full_address  # For header
        property_description = property_data.get("description", "Residential property")
        state = lease_data.get("state", "NE")
        utilities_tenant = lease_data.get("utilities_tenant", "Gas, Sewer, Water, and Electricity")
        utilities_provided_by_owner_city = lease_data.get("utilities_provided_by_owner_city", "")
        shared_driveway_with = lease_data.get("shared_driveway_with", "neighboring property")
        appliances_provided = lease_data.get("appliances_provided", "") or ""
        attic_usage = lease_data.get("attic_usage", "") or ""
        holding_fee_date = lease_data.get("holding_fee_date", "") or ""
        notes = (lease_data.get("notes") or "").strip()

        # Rent due fields
        rent_due_day = lease_data.get("rent_due_day", 1)
        rent_due_by_day = lease_data.get("rent_due_by_day", 5)
        rent_due_by_time = lease_data.get("rent_due_by_time", "6pm")

        # Format day numbers with ordinal suffix
        def ordinal(n):
            if 10 <= n % 100 <= 20:
                suffix = 'th'
            else:
                suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
            return f"{n}{suffix}"

        rent_due_day_str = ordinal(int(rent_due_day))
        rent_due_by_day_str = ordinal(int(rent_due_by_day))
        year_built_raw = property_data.get("year_built", "1978")
        try:
            year_built_float = float(year_built_raw)
            year_built_int = int(year_built_float)
            year_built_s = str(year_built_int)
        except (ValueError, TypeError):
            year_built_s = "1978"

        # --- DATE VARIABLES ---
        # Map lease_start/lease_end to commencement_date/termination_date for backward compatibility
        commencement_date = self._parse_date(lease_data.get("lease_start") or lease_data.get("commencement_date"))
        termination_date = self._parse_date(lease_data.get("lease_end") or lease_data.get("termination_date"))
        lease_date = self._parse_date(lease_data.get("lease_date"))

        # Format dates for display
        commencement_str = commencement_date.strftime("%B %d, %Y") if commencement_date else "\\underline{\\hspace{3cm}}"
        termination_str = termination_date.strftime("%B %d, %Y") if termination_date else "\\underline{\\hspace{3cm}}"
        lease_date_str = lease_date.strftime("%B %d, %Y") if lease_date else "\\underline{\\hspace{3cm}}"

        # --- DECIMAL VARIABLES (for calculations) ---
        # Convert late fees to Decimal, handling strings, numbers, and None
        def _to_decimal(value):
            if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
                return Decimal("0")
            try:
                return Decimal(str(value))
            except (ValueError, TypeError):
                return Decimal("0")

        monthly_rent_decimal = Decimal(str(lease_data.get("monthly_rent") or "0"))

        # Prorated rent: use prorated_first_month_rent if show_prorated_rent is true
        show_prorated_rent = lease_data.get("show_prorated_rent", False)
        prorated_rent_decimal = Decimal("0")
        if show_prorated_rent and lease_data.get("prorated_first_month_rent"):
            prorated_rent_decimal = _to_decimal(lease_data.get("prorated_first_month_rent"))

        # --- CURRENCY VARIABLES (formatted strings) ---
        monthly_rent = self._format_currency(lease_data.get("monthly_rent") or Decimal("0"))
        security_deposit = self._format_currency(lease_data.get("security_deposit") or Decimal("0"))
        holding_fee_amount = self._format_currency(lease_data.get("holding_fee_amount") or Decimal("0"))

        late_fee_1_val = _to_decimal(lease_data.get("late_fee_day_1_10"))
        late_fee_2_val = _to_decimal(lease_data.get("late_fee_day_11"))
        late_fee_3_val = _to_decimal(lease_data.get("late_fee_day_16"))
        late_fee_4_val = _to_decimal(lease_data.get("late_fee_day_21"))

        late_fee_1 = self._format_currency(late_fee_1_val)
        late_fee_2 = self._format_currency(late_fee_2_val)
        late_fee_3 = self._format_currency(late_fee_3_val)
        late_fee_4 = self._format_currency(late_fee_4_val)

        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🔍 [LATE FEES] late_fee_1={late_fee_1}, late_fee_2={late_fee_2}, late_fee_3={late_fee_3}, late_fee_4={late_fee_4}")
        logger.info(f"🔍 [LATE FEES] Using 4-tier structure: {late_fee_3 != '0.00' or late_fee_4 != '0.00'}")
        nsf_fee = self._format_currency(_to_decimal(lease_data.get("nsf_fee")))
        prorated_rent_str = self._format_currency(prorated_rent_decimal) if prorated_rent_decimal > 0 else "\\underline{\\hspace{2cm}}"
        pet_fee = self._format_currency(lease_data.get("pet_fee") or Decimal("0"))
        key_replacement_fee = self._format_currency(lease_data.get("key_replacement_fee", Decimal("100")))
        garage_door_opener_fee = self._format_currency(lease_data.get("garage_door_opener_fee") or Decimal("0"))
        early_termination_fee_amount = self._format_currency(lease_data.get("early_termination_fee_amount", Decimal("0")))

        # --- INTEGER VARIABLES ---
        max_occupants = lease_data.get("max_occupants", 3)
        max_adults = lease_data.get("max_adults", 2)
        max_pets = lease_data.get("max_pets", 0)
        deposit_return_days = 30 if state == "MO" else 14
        front_keys = int(lease_data.get("front_door_keys", 0) or 0)
        back_keys = int(lease_data.get("back_door_keys", 0) or 0)
        garage_back_keys = int(lease_data.get("garage_back_door_keys", 0) or 0)
        garage_spaces = int(lease_data.get("garage_spaces", 0) or 0)
        offstreet_parking_spots = int(lease_data.get("offstreet_parking_spots", 0) or 0)
        parking_spaces = int(lease_data.get("parking_spaces", 0) or 0)
        early_termination_notice_days = lease_data.get("early_termination_notice_days", 60)
        early_termination_fee_months = lease_data.get("early_termination_fee_months", 2)
        year_built = lease_data.get("disclosure_lead_paint") or lease_data.get("lead_paint_year_built") or property_data.get("year_built") or 1978
        # Convert year_built to int then string (handle float, string, None, NaN)
        try:
            if year_built is None:
                year_built = "1978"
            elif hasattr(pd, 'isna') and pd.isna(year_built):
                year_built = "1978"
            else:
                year_built = str(int(float(year_built)))  # Convert to int first, then string to avoid ".0"
        except (ValueError, TypeError):
            year_built = "1978"

        # --- BOOLEAN VARIABLES ---
        include_holding_fee = lease_data.get("include_holding_fee_addendum", False)
        pets_allowed = lease_data.get("pets_allowed", False)
        tenant_mowing = lease_data.get("tenant_lawn_mowing", True)
        tenant_snow = lease_data.get("tenant_snow_removal", True)
        tenant_lawn_care = lease_data.get("tenant_lawn_care", False)
        has_shared_driveway = lease_data.get("has_shared_driveway", False)
        has_garage_door_opener = bool(lease_data.get("has_garage_door_opener", False))
        is_multi_family = lease_data.get("unit_id") is not None and lease_data.get("unit_id") != ""
        early_termination_allowed = lease_data.get("early_termination_allowed", False)
        garage_outlets_prohibited = lease_data.get("garage_outlets_prohibited", False)
        lead_paint_disclosure = lease_data.get("lead_paint_disclosure", False)
        has_attic = lease_data.get("has_attic", False)
        auto_convert_month_to_month = lease_data.get("auto_convert_month_to_month", False)

        # Check if property is in Omaha
        property_city = property_data.get("city", "").lower()
        property_address_lower = property_data.get("address", "").lower()
        is_omaha = (property_city == "omaha" or "omaha" in property_address_lower) and state == "NE"

        # --- LIST/ARRAY VARIABLES ---
        pets_array = self._parse_pets_array(lease_data.get("pets"))
        pet_descriptions = self._format_pet_descriptions(pets_array) if pets_array else ""

        # ============================================================================
        # BUILD LATEX DOCUMENT USING EXTRACTED VARIABLES
        # ============================================================================

        # Build document
        latex = r'''\documentclass[11pt,letterpaper]{article}
\usepackage[margin=1in]{geometry}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{fancyhdr}
\usepackage{tabularx}
\usepackage{lastpage}
\usepackage{xcolor}
\usepackage{pifont}
\usepackage{tikz}
\usepackage{graphicx}
\newcommand{\cmark}{\tikz[baseline=-0.5ex]{\node[circle, fill=teal!20, draw=teal, inner sep=1pt, font=\scriptsize] {\textcolor{teal}{\ding{51}}}}}
\newcommand{\xmark}{\textcolor{gray!50}{\ding{55}}}

% Formatting
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}
\titleformat{\section}{\bfseries}{}{0em}{\uppercase}
\titleformat{\subsection}{\bfseries}{\thesubsection.}{0.5em}{}

% Header/Footer
\pagestyle{fancy}
\fancyhf{}
\lhead{\includegraphics[height=0.4in]{n_logo.jpeg}}
\rhead{Lease Agreement: ''' + property_address + r'''}
\cfoot{Page \thepage\ of \pageref{LastPage}}

\begin{document}

\begin{center}
{\LARGE\bfseries RESIDENTIAL LEASE AGREEMENT}
\end{center}

\vspace{1em}

\noindent This Lease Agreement (``Lease'') is entered into on ''' + lease_date_str + r''', by and between:

\noindent\textbf{LANDLORD:} S\&M Axios Heartland Holdings, LLC (``Landlord'')\\
\textbf{TENANT(S):} ''' + tenant_names + r''' (collectively ``Tenant'')

This Lease creates joint and several liability in the case of multiple Tenants. The Parties agree as follows:

\section{1. PREMISES}
Landlord hereby leases the Premises located at: \textbf{''' + full_address + r'''} (``Premises''). Description: ''' + property_description + r'''.

\section{2. LEASE TERM AND RENEWAL}
The Lease shall begin on \textbf{''' + commencement_str + r'''} (``Commencement Date'') and end on \textbf{''' + termination_str + r'''} (``Termination Date'').''' + (r'''

\textbf{Automatic Month-to-Month Conversion:} Unless either party provides written notice of intent to terminate at least thirty (30) days prior to the Termination Date (or any subsequent month-end during a month-to-month tenancy), this Lease shall automatically convert to a month-to-month tenancy upon the same terms and conditions, except as modified herein.

\textbf{Rent Adjustment During Month-to-Month:} Landlord may adjust the monthly rent upon thirty (30) days' prior written notice to Tenant. The adjusted rent shall take effect on the first day of the month following the expiration of the notice period.

\textbf{Termination of Month-to-Month Tenancy:} Either party may terminate the month-to-month tenancy by providing at least thirty (30) days' written notice prior to the end of any monthly rental period. Such notice shall be delivered in accordance with Section 29 (Notice) of this Lease.''' if auto_convert_month_to_month else '') + r'''

\section{3. LEASE PAYMENTS (RENT)}
Tenant agrees to pay Landlord as rent for the Premises the amount of \textbf{\$''' + monthly_rent + r'''} per month. Rent is due on the \textbf{''' + rent_due_day_str + r''' day of each month}. Rent paid by the \textbf{''' + rent_due_by_day_str + r''' of the month by ''' + rent_due_by_time + r'''} is not considered late.
\begin{itemize}
    \item \textbf{Payment Method:} Rent shall be paid exclusively via \textbf{''' + payment_method + r'''}. If Tenant experiences any technical issues with ''' + payment_method + r''', Tenant must notify Landlord immediately via email or text message. In the event there is a technical issue that cannot be resolved before rent is due, Landlord will accept payment by \textbf{check} made payable to \textbf{''' + owner_name + r'''}.''' + (r'''
    \item \textbf{Prorated Rent:} This lease is prorated for the partial month between the Commencement Date and the end of the month and shall be for \textbf{\$''' + prorated_rent_str + r'''}. ''' if show_prorated_rent else '') + r'''
\end{itemize}

\section{4. LATE CHARGES}
'''

        # Add late fee structure - show full 4-tier if day 16 or day 21 fees are set, otherwise show 2-tier
        # This applies to both single-family and multi-family properties
        if late_fee_3 != "0.00" or late_fee_4 != "0.00":
            # Full 4-tier structure (NE standard)
            latex += r'''If rent is not paid by the \textbf{''' + rent_due_by_day_str + r''' at ''' + rent_due_by_time + r'''}, a late fee of \textbf{\$''' + late_fee_1 + r'''} will be assessed. If rent and late fee are not paid by the \textbf{11th}, the late fee increases to \textbf{\$''' + late_fee_2 + r'''}. If not paid by the \textbf{16th}, the late fee increases to \textbf{\$''' + late_fee_3 + r'''}. If not paid by the \textbf{21st}, the late fee increases to \textbf{\$''' + late_fee_4 + r'''}. If rent and all late fees are not paid in full prior to the next month's rent due date (the ''' + rent_due_by_day_str + r'''), an automatic eviction notice will be given.'''
        else:
            # Simplified 2-tier structure (MO or when only first two tiers are set)
            latex += r'''If rent is not paid by the due date, Tenant agrees to pay a late fee of \textbf{\$''' + late_fee_1 + r'''}. If payment remains unpaid after the 11th, an additional late fee of \textbf{\$''' + late_fee_2 + r'''} will be assessed.'''

        latex += r'''

\section{5. INSUFFICIENT FUNDS (NSF)}
Payments made via \textbf{''' + payment_method + r'''} are processed electronically and will either complete successfully or be declined at the time of transaction; therefore, NSF fees do not apply to ''' + payment_method + r''' payments. However, if Tenant pays by \textbf{check} (as permitted under Section 3 for technical issues only), and such check is returned to Landlord due to insufficient funds, stop payment, or closed account, Tenant agrees to pay a fee of \textbf{\$''' + nsf_fee + r'''} for each returned check. This NSF fee is \textit{in addition to} any applicable late fees assessed under Section 4.

\textit{Example: If Tenant pays January rent by check on the 4th and the check is returned for insufficient funds on the 8th, Tenant owes: (1) the original rent amount, (2) the applicable late fee (since rent was not successfully paid by the ''' + rent_due_by_day_str + r''' at ''' + rent_due_by_time + r'''), and (3) the \$''' + nsf_fee + r''' NSF fee.}

\section{6. SECURITY DEPOSIT}
At the signing of this Lease, Tenant shall deposit with Landlord the sum of \textbf{\$''' + security_deposit + r'''} as a Security Deposit. This deposit secures the performance of this Lease. Landlord may use the deposit to cover unpaid rent or damages beyond normal wear and tear. The deposit shall be returned within ''' + str(deposit_return_days) + r''' days after termination of the tenancy, less itemized deductions, per ''' + state + r''' law.''' + (r'''

\textit{Note: A Holding Fee of \textbf{\$''' + holding_fee_amount + r'''} was previously collected pursuant to the Holding Fee Agreement dated ''' + (holding_fee_date if holding_fee_date else "prior to lease execution") + r'''. This Holding Fee has been credited in full toward the Security Deposit shown above.}''' if include_holding_fee else "") + r'''

\section{7. DEFAULTS}
If Tenant fails to perform any obligation under this Lease, Tenant shall be in default.
\begin{itemize}
    \item \textbf{Non-Payment:} Landlord may deliver a \textbf{7-Day Notice to Pay or Quit}.
    \item \textbf{Other Breaches:} Landlord may deliver a ''' + (r'''\textbf{30-Day Notice with 14-day cure period}''' if state == "NE" else r'''\textbf{14/30 Day Notice}''') + r''' to cure or quit.
    \item \textbf{Illegal Activity:} Landlord may deliver a \textbf{5-Day Unconditional Notice to Quit}.
\end{itemize}
Landlord may re-enter and take possession as permitted by law. Tenant remains liable for unpaid rent and damages.

\section{8. QUIET ENJOYMENT}
Tenant shall be entitled to quiet enjoyment of the Premises as long as Tenant pays rent and performs all obligations under this Lease.

\section{9. POSSESSION AND SURRENDER}
Tenant shall be entitled to possession on the first day of the Lease Term. At expiration, Tenant shall surrender the Premises in as good a state and condition as they were at the commencement of this Agreement, reasonable use and wear and tear thereof excepted. For purposes of this Agreement, Tenant has "surrendered" the Premises when: (i) the move-out date has passed and no one is living in the Premises in Landlord's reasonable judgment; or (ii) the keys and access devices listed in this Agreement have been turned in to Landlord, whichever happens first. Surrender, abandonment, or judicial eviction ends Tenant's right of possession for all purposes, and gives Landlord the immediate right to clean up, make repairs in, and relet the Premises; determine any Security Deposit deductions; and remove property left in the Premises.''' + (r'''

\textit{Note: Under Nebraska Revised Statutes § 76-1430, Nebraska has specific statutory procedures for handling abandoned property. Nebraska requires landlords to store abandoned property for 30 days and provide notice before disposal.}''' if lease_data.get("state") == "NE" else "") + r'''

\section{10. USE OF PREMISES}
The Premises shall be used as a private residence only. No business or trade may be conducted without prior written consent. Tenant will comply with all laws, rules, ordinances, statutes and orders regarding the use of the Premises.

\subsection*{10.1 COMPLIANCE WITH LAWS}
Tenant shall not violate any law or ordinance (federal, state, or local), or commit or permit any waste or nuisance in or about the Premises, or in any way annoy any other person residing within three hundred (300) feet of the Premises. Such actions shall be a material and irreparable violation of the Agreement and good cause for termination of Agreement.

\section{11. OCCUPANTS}
Tenant agrees that no more than \textbf{''' + str(lease_data.get("max_occupants", 3)) + r'''} persons OR \textbf{''' + str(lease_data.get("max_adults", 2)) + r''' adults and their minor children} may reside on the Premises, without prior written consent of the Landlord. Guests staying longer than 7 consecutive days or 14 days in a 6-month period require written consent. Unauthorized occupants shall constitute a material breach of this Lease, subject to termination under Section 7.

\section{12. CONDITION OF PREMISES}
Tenant or Tenant's agent has inspected the Premises, the fixtures, the grounds, building and improvements and acknowledges that the Premises are in good and acceptable condition and are habitable. If at any time during the term of this Lease, in Tenant's opinion, the conditions change, Tenant shall promptly provide reasonable notice to Landlord.''' + (r'''

\textit{Important Nebraska Tenant Rights: Under Nebraska Revised Statutes § 76-1427, Nebraska tenants have explicit statutory rights regarding habitability issues. After providing written notice and allowing reasonable time for the landlord to remedy, tenants may: (1) withhold rent until habitability issues are fixed, or (2) repair and deduct costs from rent (capped at one month's rent per 12-month period). These rights are in addition to any other remedies available under Nebraska law.}''' if state == "NE" else "") + r'''

\section{13. ASSIGNMENT AND SUBLEASE}
Tenant shall not assign or sublease any interest in this lease without prior written consent of the Landlord, which consent shall not be unreasonably withheld. Any assignment or sublease without Landlord's written prior consent shall, at Landlord's option, terminate this Lease.

\section{14. DANGEROUS MATERIALS}
Tenant shall not keep or have on or around the Premises any item of a dangerous, flammable or explosive character that might unreasonably increase the risk of fire or explosion on or around the Premises or that might be considered hazardous by any responsible insurance company.

\section{15. UTILITIES AND SERVICES}
Tenant will be responsible for all utilities and services required on the Premises (including ''' + utilities_tenant + r''').''' + (r''' Landlord or City will provide: \textbf{''' + self._escape_latex(utilities_provided_by_owner_city) + r'''}.''' if utilities_provided_by_owner_city else r''' No utilities are provided by Landlord or City.''') + r'''

\section{16. PETS}
'''

        # Add pet section using new pet_fee and pets array format
        # Check if pets are listed (regardless of fee) OR if pets are allowed with max_pets
        has_pets_listed = bool(pets_array and len(pets_array) > 0)

        if has_pets_listed or (pets_allowed and max_pets > 0):
            if pet_descriptions:
                # Pets are listed - show them
                pet_count = len(pets_array)
                pet_plural_desc = 's' if pet_count != 1 else ''
                pet_verb = 'is' if pet_count == 1 else 'are'

                # Check if pet fee is greater than 0 (use the already formatted pet_fee string)
                # pet_fee is already formatted as currency string, check the original value
                pet_fee_value = lease_data.get("pet_fee") or Decimal("0")
                has_pet_fee = pet_fee_value > 0

                if has_pet_fee:
                    # Has pet fee
                    base_desc = (r'''Pet Fee is \textbf{\$''' + pet_fee + r'''} and includes ''' +
                                str(pet_count) + r''' pet''' + pet_plural_desc + r''': ''' +
                                pet_descriptions + r'''. Pets are replaceable at no cost to the tenant. All pets must be approved if breed is changed or weight is increased. It is Tenant's responsibility to properly clean-up/dispose of all waste from pets on property.''')
                else:
                    # No pet fee but pets are listed
                    base_desc = (r'''The following pet''' + pet_plural_desc + r''' ''' + pet_verb + r''' allowed on the Premises: ''' +
                                pet_descriptions + r'''. All pets must be approved if breed is changed or weight is increased. It is Tenant's responsibility to properly clean-up/dispose of all waste from pets on property.''')

                if lease_data.get("state") == "NE" and has_pet_fee:
                    ne_note_desc = r'''

\textit{Important: This is a non-refundable pet fee, not a pet deposit. Under Nebraska Revised Statutes § 76-1410, pet deposits (refundable amounts held as security) are capped at 25\% of one month's rent. However, this provision does not apply to non-refundable pet fees, which are separate consideration for the privilege of keeping pets on the Premises and are not subject to the deposit cap limitations.}'''
                else:
                    ne_note_desc = ""
                latex += base_desc + ne_note_desc
            else:
                # Fallback if no pet details provided but pets are allowed
                pet_plural = 's' if max_pets != 1 else ''
                if lease_data.get("state") == "NE":
                    fee_note = r'''This is a non-refundable pet fee, not a pet deposit.'''
                    ne_note = (r'''

\textit{Important: This is a non-refundable pet fee, not a pet deposit. Under Nebraska Revised Statutes § 76-1410, pet deposits (refundable amounts held as security) are capped at 25\% of one month's rent. However, this provision does not apply to non-refundable pet fees, which are separate consideration for the privilege of keeping pets on the Premises and are not subject to the deposit cap limitations.}''')
                else:
                    fee_note = r'''Fee is non-refundable.'''
                    ne_note = r'''

'''
                latex += r'''Pet Fee is \textbf{\$''' + pet_fee + r'''} for up to ''' + str(max_pets) + r''' pet''' + pet_plural + r'''. ''' + fee_note + r''' Pets are replaceable at no cost to the tenant. All pets must be approved if breed is changed or weight is increased. It is Tenant's responsibility to properly clean-up/dispose of all waste from pets on property.''' + ne_note
        else:
            latex += r'''No pets allowed on the Premises without prior written consent of the Landlord.'''

        # Add smoking section
        latex += r'''

\subsection*{16.1 SMOKING}
Smoking is not permitted inside or outside the Premises.

For the purposes of clarifying and restricting its use, the term "Smoking" is defined to include the use of cigarettes, pipes, cigars, electronic vaporizing or aerosol devices, or other devices intended for the inhalation of tobacco, marijuana, or similar substances. Tenant understands and agrees that any damage caused by Smoking shall not constitute ordinary wear and tear. Landlord may deduct from the Security Deposit all damages and/or costs for the cleaning or repairing of any damage caused by or related to Smoking, including but not limited to: deodorizing the Premises, sealing and painting the walls and ceiling, and/or repairing or replacing the carpet and pads.

\section{17. ALTERATIONS AND IMPROVEMENTS}
Tenant agrees not to make any improvements or alterations to the Premises without prior written consent of the Landlord. If any alterations, improvements or changes are made to or built on or around the Premises, with the exception of fixtures and personal property that can be removed without damage to the Premises, they shall become the property of Landlord and shall remain at the expiration of the Lease, unless otherwise agreed in writing.

\section{18. DAMAGE TO PREMISES}
If the Premises or part of the Premises are damaged or destroyed by fire or other casualty not due to Tenant's negligence, the rent will be abated during the time that the Premises are uninhabitable. If Landlord decides not to repair or rebuild the Premises, then this Lease shall terminate, and the rent shall be prorated up to the time of the damage. Any unearned rent paid in advance shall be refunded to Tenant.

\section{19. MAINTENANCE AND REPAIR}
Tenant will, at Tenant's sole expense, keep and maintain the Premises in good, clean and sanitary condition and repair during the term of this Lease and any renewal thereof. Tenant shall be responsible to make all repairs to the Premises, fixtures, appliances and equipment therein that may have been damaged by Tenant's misuse, waste, or neglect, or that of the Tenant's family, agent, or visitor. Tenant agrees that no painting will be done on or about the Premises without the prior written consent of Landlord. Tenant shall promptly notify Landlord of any damage, defect or destruction of the Premises, or in the event of the failure of any of the appliances or equipment. Landlord will use its best efforts to repair or replace any such damaged or defective area, appliance or equipment. If issue is not a water emergency, an acceptable time for maintenance to return call/text of issue is 24 hours.
'''

        # Add maintenance responsibilities with checkboxes
        mowing_responsible = "Tenant" if tenant_mowing else "Landlord"
        snow_responsible = "Tenant" if tenant_snow else "Landlord"
        lawn_care_responsible = "Tenant" if tenant_lawn_care else "Landlord"

        latex += r'''
\textbf{Exterior Maintenance Responsibilities:}
\begin{itemize}[leftmargin=2em]
    \item \textbf{Lawn Mowing:} \cmark\ ''' + mowing_responsible + r''' is responsible. \\
    \textit{Maintain grass at a height not to exceed eight (8) inches in compliance with local municipal ordinances. During the growing season (April through October), lawn shall be mowed weekly or as often as necessary to maintain a neat, well-kept appearance. Includes weed control and removal of leaves and debris from the lawn and landscaped areas.}

    \item \textbf{Snow Removal:} \cmark\ ''' + snow_responsible + r''' is responsible. \\
    \textit{Clear snow and ice from all sidewalks, driveway, and walkways within twenty-four (24) hours of snowfall cessation to ensure safe passage and compliance with local ordinances.}

    \item \textbf{Lawn Care:} \cmark\ ''' + lawn_care_responsible + r''' is responsible. \\
    \textit{General lawn and landscape maintenance including: ''' + (r'''seasonal activation and winterization of sprinkler/irrigation systems (if sprinkler system is available), ''' if lawn_care_responsible == "Tenant" else "") + r'''watering as needed, overseeding bare or damaged areas, and fertilization. \textbf{Note:} Lawn care responsibilities do not include lawn mowing, which is addressed separately above.}
\end{itemize}
'''

        # Add shared driveway notice if applicable
        if has_shared_driveway:
            latex += r'''
\textbf{Shared Driveway Notice:} Tenant shall NOT block the shared driveway with ''' + self._escape_latex(shared_driveway_with) + r'''.
'''

        # Continue with remaining sections
        latex += self._generate_remaining_sections(
            state=state,
            is_multi_family=is_multi_family,
            garage_spaces=garage_spaces,
            offstreet_parking_spots=offstreet_parking_spots,
            parking_spaces=parking_spaces,
            front_keys=front_keys,
            back_keys=back_keys,
            garage_back_keys=garage_back_keys,
            key_replacement_fee=key_replacement_fee,
            has_garage_door_opener=has_garage_door_opener,
            garage_door_opener_fee=garage_door_opener_fee,
            appliances_provided=appliances_provided,
            has_attic=has_attic,
            attic_usage=attic_usage,
            lead_paint_disclosure=lead_paint_disclosure,
            year_built=year_built,
            early_termination_allowed=early_termination_allowed,
            early_termination_fee_amount=early_termination_fee_amount,
            early_termination_notice_days=early_termination_notice_days,
            early_termination_fee_months=early_termination_fee_months,
            garage_outlets_prohibited=garage_outlets_prohibited,
            is_omaha=is_omaha,
            owner_name=owner_name,
            manager_name=manager_name,
            manager_address=manager_address
        )

        # Add move-out costs section
        latex += self._generate_moveout_section(lease_data)

        # Add Section 40 - Descriptive Headings
        latex += r'''

\section{40. DESCRIPTIVE HEADINGS}
The descriptive headings used herein are for convenience of reference only, and they are not intended to have any effect whatsoever in determining the rights or obligations of the Landlord or Tenant.
'''

        # Add notes section if notes exist and are more than one word
        if notes and len(notes.split()) > 1:
            latex += r'''
\section{40.5. ADDITIONAL TERMS AND CONDITIONS}
''' + self._escape_latex(notes) + r'''
'''

        # Add signatures
        latex += self._generate_signatures(tenants, manager_name=manager_name)

        latex += r'''
\end{document}
'''

        return latex

    def _generate_remaining_sections(
        self,
        state: str,
        is_multi_family: bool,
        garage_spaces: int,
        offstreet_parking_spots: int,
        parking_spaces: int,
        front_keys: int,
        back_keys: int,
        garage_back_keys: int,
        key_replacement_fee: str,
        has_garage_door_opener: bool,
        garage_door_opener_fee: str,
        appliances_provided: str,
        has_attic: bool,
        attic_usage: str,
        lead_paint_disclosure: bool,
        year_built: str,
        early_termination_allowed: bool,
        early_termination_fee_amount: str,
        early_termination_notice_days: int,
        early_termination_fee_months: int,
        garage_outlets_prohibited: bool,
        is_omaha: bool,
        owner_name: str,
        manager_name: str,
        manager_address: str
    ) -> str:
        """Generate sections 20-38"""
        latex = r'''
\section{20. RIGHT OF INSPECTION}
Tenant agrees to make the premises available to Landlord or Landlord's agents for the purposes of inspection, making repairs or improvements, or to supply agreed services or show the premises to prospective buyers or tenants, or in case of emergency. Except in case of emergency, Landlord shall give Tenant ''' + (r'''at least 24 hours' notice of intent to enter.''' if state == "NE" else r'''reasonable notice of intent to enter. For these purposes, twenty-four (24) hour notice shall be deemed reasonable.''') + r''' Tenant shall not, without Landlord's prior written consent, add, alter or re-key any locks to the premises. At all times Landlord shall be provided with a key or keys capable of unlocking all such locks and gaining entry. Tenant further agree to notify Landlord in writing if Tenant installs any burglar alarm system, including instructions on how to disarm it in case of emergency entry.

\section{21. ABANDONMENT}
If Tenant abandons the Premises or any personal property during the term of this Lease, Landlord may at its option enter the Premises by any legal means without liability to Tenant and may at Landlord's option terminate the Lease. Abandonment is defined as absence of the Tenants from the premises, for at least 30 consecutive days without notice to Landlord. If Tenant abandons the premises while the rent is outstanding for more than 15 days and there is no reasonable evidence, other than the presence of the Tenants' personal property, that the Tenant is occupying the unit, Landlord may at Landlord's option terminate this agreement and regain possession in the manner prescribed by law. Landlord will dispose of all abandoned personal property on the Premises in any manner allowed by law.

\section{22. EXTENDED ABSENCES}
In the event Tenant will be away from the premises for more than 30 consecutive days, Tenant agrees to notify Landlord in writing of such absence. During such absence, Landlord may enter the premises at times reasonably necessary to maintain the property and inspect for damages and needed repairs.

\section{23. SECURITY}
Tenant understands that Landlord does not provide any security alarm system or other security for Tenant or the Premises. In the event any alarm system is provided, Tenant understands that such alarm system is not warranted to be complete in all respects or to be sufficient to protect Tenant or the Premises. Tenant releases Landlord from any loss, damage, claim or injury resulting from the failure of any alarm system, security or from the lack of any alarm system or security.

\subsection*{23.1 NO REPRESENTATIONS}
Tenant acknowledges that Landlord has not made any representations, written or oral, concerning the safety of the community or the effectiveness or operability of any security devices or security measures. Tenant acknowledges that Landlord does not warrant or guarantee the safety or security of Tenant or his or her guests or invitees against the criminal or wrongful acts of third parties. Each Tenant, guest, invitee and Additional Occupant(s) is responsible for protecting his or her own person and property.

\section{24. SEVERABILITY}
If any part or parts of this Lease shall be held unenforceable for any reason, the remainder of this Agreement shall continue in full force and effect. If any provision of this Lease is deemed invalid or unenforceable by any court of competent jurisdiction, and if limiting such provision would make the provision valid, then such provision shall be deemed to be construed as so limited.

\section{25. INSURANCE}
Landlord and Tenant shall each be responsible to maintain appropriate insurance for their respective interests in the Premises and property located on the Premises. Tenant understands that Landlord will not provide any insurance coverage for Tenant's property. Landlord will not be responsible for any loss of Tenant's property, whether by theft, fire, riots, strikes, acts of God, or otherwise. Landlord encourages Tenant to obtain renter's insurance or other similar coverage to protect against risk of loss.

\section{26. BINDING EFFECT}
This Lease binds the parties and their heirs/successors.

\subsection*{26.1 SUBORDINATION OF LEASE}
This Lease and Tenant's interest hereunder are, and shall be, subordinate, junior, and inferior to any and all mortgages, liens, or encumbrances now or hereafter placed on the Premises by Landlord, all advances made under any such mortgages, liens, or encumbrances (including, but not limited to, future advances), the interest payable on such mortgages, liens, or encumbrances and any and all renewals, extensions, or modifications of such mortgages, liens, or encumbrances.

\section{27. GOVERNING LAW}
This Lease shall be governed by and construed in accordance with the laws of the State of ''' + ("Nebraska" if state == "NE" else "Missouri") + r'''. All Parties to this Lease, including Third Party Guarantors, if any, expressly consent to the venue of the courts of the county in which the Premises is located.

\section{28. ENTIRE AGREEMENT}
This Lease constitutes the entire agreement between the parties and supersedes any prior understanding or representation of any kind preceding the date of this Agreement. There are no other promises, conditions, understandings or other agreements, whether oral or written, relating to the subject matter of this Lease. This Lease may be modified in writing and must be signed by both Landlord and Tenant.

Further, Tenant represents that he or she has relied solely on his or her own judgment, experience, and expertise in entering into this Agreement with Landlord.

\section{29. NOTICE}
Any notice required or otherwise given pursuant to this Lease shall be in writing and mailed certified return receipt requested, postage prepaid, or delivered by overnight delivery service, if to Tenant, at the Premise and if to Landlord, at the address for payment of rent. Either party may change such addresses from time to time by providing notice as set forth above.
\begin{itemize}
    \item \textbf{Landlord:} ''' + owner_name + r''', c/o ''' + manager_name + r''', ''' + manager_address + r'''.
    \item \textbf{Tenant:} At the Premises.
\end{itemize}

\section{30. CUMULATIVE RIGHTS}
Landlord's rights are cumulative and not exclusive.

\section{31. WAIVER}
Failure to enforce a provision does not waive the right to enforce it later. No indulgence, waiver, election, or non-election by Landlord under this Lease shall affect Tenant's duties and liabilities hereunder.

\section{32. DISPLAY OF SIGNS}
Landlord may display ``For Rent'' signs during the last 60 days of the Lease.

\subsection*{32.1 TIME}
Time is of the essence to the terms of this Lease.

\section{33. PARKING}
'''

        # Build assigned spaces description
        parking_parts = []
        if garage_spaces > 0:
            garage_text = f"{garage_spaces} garage space" if garage_spaces == 1 else f"{garage_spaces} garage spaces"
            parking_parts.append(garage_text)
        if offstreet_parking_spots > 0:
            offstreet_text = f"{offstreet_parking_spots} off-street parking space" if offstreet_parking_spots == 1 else f"{offstreet_parking_spots} off-street parking spaces"
            parking_parts.append(offstreet_text)

        if parking_parts:
            assigned_spaces = " and ".join(parking_parts)
        elif parking_spaces > 0:
            assigned_spaces = f"{parking_spaces} parking space" if parking_spaces == 1 else f"{parking_spaces} parking spaces"
        else:
            assigned_spaces = "designated parking area"

        # Build parking assignment text based on property type
        if is_multi_family:
            latex += r'''\textbf{Assigned Parking:} Tenant is assigned \textbf{''' + assigned_spaces + r'''} for the exclusive use of Tenant's operable, properly registered, and insured motor vehicle(s).'''
        else:
            # Single-family: Include garage, driveway, and acknowledge street parking availability
            parking_location_parts = []
            if garage_spaces > 0:
                parking_location_parts.append(f"{garage_spaces} garage space" if garage_spaces == 1 else f"{garage_spaces} garage spaces")
            parking_location_parts.append("the driveway")
            parking_location_text = " and ".join(parking_location_parts)
            latex += r'''\textbf{Assigned Parking:} Tenant is assigned \textbf{''' + parking_location_text + r'''} for the exclusive use of Tenant's operable, properly registered, and insured motor vehicle(s). In addition, Tenant may park on the public street adjacent to the Premises, subject to all applicable municipal parking regulations, restrictions, and time limits. Landlord makes no representation or warranty regarding the availability, legality, or safety of street parking, and Tenant assumes all risk and responsibility for vehicles parked on public streets.'''

        latex += r'''

\textbf{Permitted Vehicles:} Only passenger vehicles, including automobiles, motorcycles, and non-commercial pickup trucks, are permitted. The parking of trailers, boats, campers, recreational vehicles, buses, or commercial vehicles is prohibited without prior written consent from Landlord.

\textbf{Parking Regulations:}
\begin{itemize}[nosep, leftmargin=2em]
'''

        # Differentiate parking restrictions based on property type
        if is_multi_family:
            # Multi-family: Tenant must respect shared spaces and assigned parking
            latex += r'''    \item Tenant shall park only in assigned space(s) and shall not obstruct shared driveways, fire lanes, sidewalks, or access to other tenants' assigned parking spaces.'''
        else:
            # Single-family: Tenant has exclusive use of driveway, can use street parking with municipal compliance
            latex += r'''    \item Tenant shall park in the assigned garage space(s) and/or driveway. When parking on the public street, Tenant must comply with all municipal parking regulations, including but not limited to time restrictions, permit requirements, and snow removal ordinances. Tenant shall not obstruct fire lanes, sidewalks, or public access areas, whether parking on the Premises or on public streets.'''

        latex += r'''
    \item Vehicles must be maintained in operable condition and free of fluid leaks. Vehicles with expired registration or in inoperable condition are subject to towing at Tenant's expense.
    \item Vehicle maintenance, repairs, or washing in the parking area is prohibited except for minor cleaning.
\end{itemize}
'''

        # Add multi-family specific blocking language
        if is_multi_family:
            latex += r'''
\textbf{Shared Access -- IMPORTANT:} This property has shared parking and/or driveway access with neighboring unit(s). Tenant shall NOT park in a manner that blocks, impedes, or restricts access to any other tenant's assigned parking space(s) or the shared driveway. Violations may result in towing at Tenant's expense without prior notice and may constitute a material breach of this Lease.
'''

        latex += r'''
\textbf{Liability:} Landlord is not responsible for any damage, theft, or loss of vehicles or personal property within the parking area. Tenant assumes all risk associated with parking on the Premises.

\section{34. KEYS}
'''
        # Build keys list
        keys_list = []
        if front_keys > 0:
            keys_list.append(r'''\textbf{''' + str(front_keys) + r'''} key to the Front Door''')
        if back_keys > 0:
            keys_list.append(r'''\textbf{''' + str(back_keys) + r'''} key to the Back Door''')
        if garage_back_keys > 0:
            keys_list.append(r'''\textbf{''' + str(garage_back_keys) + r'''} key to the Garage Back Door''')

        if keys_list:
            if len(keys_list) == 1:
                keys_text = keys_list[0]
            elif len(keys_list) == 2:
                keys_text = keys_list[0] + r''' and ''' + keys_list[1]
            else:
                keys_text = ", ".join(keys_list[:-1]) + r''', and ''' + keys_list[-1]
            latex += r'''Tenant will be given ''' + keys_text + r'''. Mailbox is unlocked and fixed to the dwelling. Tenant shall be charged \textbf{\$''' + key_replacement_fee + r'''} per key if all keys are not returned to Landlord following termination of the Lease.'''
        else:
            latex += r'''Tenant will be given keys as specified by Landlord. Mailbox is unlocked and fixed to the dwelling. Tenant shall be charged \textbf{\$''' + key_replacement_fee + r'''} per key if all keys are not returned to Landlord following termination of the Lease.'''

        # Add garage door opener information if applicable
        if has_garage_door_opener:
            if garage_door_opener_fee != "0.00":
                latex += r''' Tenant will be provided with a garage door opener remote. Tenant shall be charged \textbf{\$''' + garage_door_opener_fee + r'''} for replacement of the garage door opener remote if it is not returned to Landlord following termination of the Lease.'''
            else:
                latex += r''' Tenant will be provided with a garage door opener remote. Tenant shall return the garage door opener remote to Landlord following termination of the Lease.'''

        latex += r'''

\section{35. LIQUID-FILLED FURNITURE}
Tenant shall not use or have any liquid-filled furniture, including but not limited to waterbeds, on the premises without Landlord's prior written consent.

\section{36. INDEMNIFICATION}
To the extent permitted by law, Tenant will indemnify and hold Landlord and Landlord's property, including the Premises, free and harmless from any liability for losses, claims, injury to or death of any person, including Tenant, or for damage to property arising from Tenant using and occupying the Premises or from the acts or omissions of any person or persons, including Tenant, in or about the premises with Tenant's express or implied consent except Landlord's act or negligence.

\section{37. LEGAL FEES}
In the event of any legal action by the parties arising out of this Lease, the losing party shall pay the prevailing party reasonable attorneys' fees and costs in addition to all other relief.

\section{38. ADDITIONAL TERMS}
\begin{itemize}
'''

        # Add additional terms
        if appliances_provided:
            latex += r'''    \item \textbf{Appliances:} Landlord will provide the following appliances: ''' + appliances_provided + r'''.
'''
        if has_attic and attic_usage:
            latex += r'''    \item \textbf{Attic Usage:} ''' + attic_usage + r'''.
'''
        if lead_paint_disclosure:
            # Only include lead paint disclosure if property was built before 1978
            try:
                year_built_int = int(year_built)
                if year_built_int < 1978:
                    latex += r'''    \item \textbf{Lead-Based Paint:} Housing built before 1978 may contain lead-based paint. The Premises was built in ''' + year_built + r'''. Landlord discloses the known presence of lead-based paint and/or lead-based paint hazards. Tenant acknowledges receipt of the EPA pamphlet ``Protect Your Family from Lead in Your Home''.
'''
                # If built 1978 or later, no disclosure needed (federal law only requires disclosure for pre-1978)
            except (ValueError, TypeError):
                # If year_built can't be parsed, include disclosure to be safe
                latex += r'''    \item \textbf{Lead-Based Paint:} Housing built before 1978 may contain lead-based paint. The Premises was built in ''' + year_built + r'''. Landlord discloses the known presence of lead-based paint and/or lead-based paint hazards. Tenant acknowledges receipt of the EPA pamphlet ``Protect Your Family from Lead in Your Home''.
'''
        latex += r'''    \item \textbf{Tenant Representations:} Application info via MySmartMove.com is warranted as true; falsification is default.
'''

        if early_termination_allowed:
            latex += r'''    \item \textbf{Early Termination:} Tenant may terminate early with ''' + str(early_termination_notice_days) + r''' days' notice AND payment of a ''' + str(early_termination_fee_months) + r'''-month rent fee (\textbf{\$''' + early_termination_fee_amount + r'''}). The Security Deposit shall NOT be applied toward this fee.
'''

        if garage_outlets_prohibited:
            latex += r'''    \item \textbf{Garage Outlets:} Tenant is strictly prohibited from using the electrical outlets in the garage for any purpose.
'''

        # Add Omaha-specific requirements if property is in Omaha
        if is_omaha:
            latex += r'''    \item \textbf{Omaha Landlord Registration:} This rental property is registered with the City of Omaha as required by Omaha Municipal Code. Landlord confirms compliance with all local registration requirements.
    \item \textbf{Omaha Fair Housing:} This Lease complies with Omaha's Fair Housing Ordinance, which extends protections beyond federal and Nebraska state law to include sexual orientation and gender identity. Landlord and Tenant acknowledge compliance with Omaha's expanded anti-discrimination protections.
    \item \textbf{Smoke Detectors:} Omaha Municipal Code requires specific smoke detector installation and maintenance. Tenant agrees to: (1) test smoke detectors monthly, (2) notify Landlord immediately if any smoke detector is not functioning, (3) not remove, disable, or tamper with smoke detectors, and (4) allow Landlord access for smoke detector inspection and maintenance as required by law.
'''

        latex += r'''\end{itemize}
'''

        return latex

    def _generate_moveout_section(self, lease_data: Dict[str, Any]) -> str:
        """Generate Section 39 - Move-Out Costs"""
        latex = r'''
\section{39. MOVE-OUT COST SCHEDULE}
Tenant agrees that the actual cost of cleaning and repairs is difficult to ascertain. The parties agree that the following schedule represents a reasonable estimate of such costs (Liquidated Damages) and will be deducted from the Security Deposit if applicable:
\begin{itemize}
'''

        # Parse moveout_costs JSON
        try:
            moveout_costs = json.loads(lease_data.get("moveout_costs", "[]"))
            # Sort by order
            moveout_costs = sorted(moveout_costs, key=lambda x: x.get("order", 999))

            for cost_item in moveout_costs:
                item_name = cost_item.get("item", "")
                description = cost_item.get("description", "")
                amount = cost_item.get("amount", "0")

                # Convert string amount to Decimal if needed
                if isinstance(amount, str):
                    amount = Decimal(amount)
                amount_str = self._format_currency(amount)

                if description:
                    latex += r'''    \item \textbf{''' + item_name + r''':} ''' + description + r''' \textbf{\$''' + amount_str + r'''}.
'''
                else:
                    latex += r'''    \item \textbf{''' + item_name + r''':} \textbf{\$''' + amount_str + r'''}.
'''
        except (json.JSONDecodeError, TypeError):
            # Fallback if JSON parsing fails
            latex += r'''    \item Contact landlord for move-out cost schedule.
'''

        latex += r'''\end{itemize}
'''

        return latex

    def _generate_signatures(self, tenants: List[Dict[str, Any]], manager_name: str = "Sarah Pappas") -> str:
        """Generate signature section"""
        latex = r'''
\vspace{3em}

\noindent\textbf{SIGNATURES}

\vspace{1em}

\noindent THE TENANT UNDERSTANDS THAT THE EXECUTION OF THIS LEASE ENTAILS AN IMPORTANT DECISION THAT HAS LEGAL IMPLICATIONS. TENANT IS ADVISED TO SEEK HIS OR HER OWN COUNSEL, LEGAL OR OTHERWISE, REGARDING THE EXECUTION OF THIS LEASE. TENANT HEREBY ACKNOWLEDGES THAT HE OR SHE HAS READ THIS LEASE, UNDERSTANDS IT, AGREES TO IT, AND HAS BEEN GIVEN A COPY. ELECTRONIC SIGNATURES MAY BE USED TO EXECUTE THIS LEASE. IF USED, THE PARTIES ACKNOWLEDGE THAT ONCE THE ELECTRONIC SIGNATURE PROCESS IS COMPLETED, THE ELECTRONIC SIGNATURES ON THIS LEASE WILL BE AS BINDING AS IF THE SIGNATURES WERE PHYSICALLY SIGNED BY HAND.

\vspace{3em}

\noindent\begin{tabularx}{\textwidth}{@{}X X@{}}
\rule{7cm}{0.4pt} & \rule{7cm}{0.4pt} \\
\textbf{Landlord:} S\&M Axios Heartland Holdings, LLC & \textbf{Date} \\
\textit{By: ''' + self._escape_latex(manager_name) + r''', Member} & \\[3em]
'''

        # Add signature lines for each tenant
        for tenant in tenants:
            tenant_name = f"{tenant.get('first_name', '')} {tenant.get('last_name', '')}"
            latex += r'''\rule{7cm}{0.4pt} & \rule{7cm}{0.4pt} \\
\textbf{Tenant:} ''' + tenant_name + r''' & \textbf{Date} \\[3em]
'''

        latex += r'''\end{tabularx}
'''

        return latex

    def _compile_pdf(self, latex_content: str) -> bytes:
        """
        Compile LaTeX to PDF using pdflatex.
        Uses local temp directory for compilation, but final files stored in ADLS.
        """
        import shutil

        # Create temporary directory for this compilation
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            tex_file = tmpdir_path / "lease.tex"
            pdf_file = tmpdir_path / "lease.pdf"

            # Copy logo to temp directory for LaTeX to find
            logo_src = Path(__file__).parent.parent / "assets" / "n_logo.jpeg"
            if logo_src.exists():
                shutil.copy(logo_src, tmpdir_path / "n_logo.jpeg")

            # Write LaTeX to file
            tex_file.write_text(latex_content, encoding="utf-8")

            # Compile with pdflatex (run twice for proper references)
            try:
                subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(tmpdir_path), str(tex_file)],
                    check=True,
                    capture_output=True,
                    timeout=30
                )
                subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(tmpdir_path), str(tex_file)],
                    check=True,
                    capture_output=True,
                    timeout=30
                )
            except subprocess.CalledProcessError as e:
                # pdflatex writes errors to stdout, not stderr
                error_output = e.stdout.decode() if e.stdout else ""
                # Extract the error portion (usually after "!")
                if "!" in error_output:
                    error_lines = []
                    in_error = False
                    for line in error_output.split('\n'):
                        if line.startswith('!'):
                            in_error = True
                        if in_error:
                            error_lines.append(line)
                            if len(error_lines) >= 5:  # Limit error lines
                                break
                    error_output = '\n'.join(error_lines)
                raise Exception(f"LaTeX compilation failed:\n{error_output}")
            except subprocess.TimeoutExpired:
                raise Exception("LaTeX compilation timed out")

            # Read PDF content
            if not pdf_file.exists():
                raise Exception("PDF file was not generated")

            return pdf_file.read_bytes()

    def _save_latex_to_adls(
        self,
        latex_content: str,
        lease_data: Dict[str, Any],
        property_data: Dict[str, Any],
        user_id: str,
        suffix: str = ""
    ) -> str:
        """Save LaTeX source to ADLS"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        property_address = property_data.get("address", "unknown").replace(" ", "_").replace("/", "_")
        filename = f"lease_{property_address}{suffix}_{timestamp}.tex"

        # Upload to ADLS
        blob_name = f"{self.final_folder}/{user_id}/{lease_data['id']}/{filename}"
        blob_client = self.adls.blob_service_client.get_blob_client(
            container=self.adls.container_name,
            blob=blob_name
        )

        blob_client.upload_blob(
            latex_content.encode('utf-8'),
            overwrite=True,
            metadata={
                "user_id": user_id,
                "lease_id": lease_data['id'],
                "property_id": lease_data['property_id'],
                "generated_at": datetime.utcnow().isoformat(),
                "document_type": "lease_latex"
            }
        )

        return blob_name

    def _save_pdf_to_adls(
        self,
        pdf_bytes: bytes,
        lease_data: Dict[str, Any],
        property_data: Dict[str, Any],
        user_id: str,
        suffix: str = ""
    ) -> str:
        """Save PDF to ADLS"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        property_address = property_data.get("address", "unknown").replace(" ", "_").replace("/", "_")
        filename = f"lease_{property_address}{suffix}_{timestamp}.pdf"

        # Upload to ADLS
        blob_name = f"{self.final_folder}/{user_id}/{lease_data['id']}/{filename}"
        blob_client = self.adls.blob_service_client.get_blob_client(
            container=self.adls.container_name,
            blob=blob_name
        )

        from azure.storage.blob import ContentSettings
        blob_client.upload_blob(
            pdf_bytes,
            overwrite=True,
            content_settings=ContentSettings(content_type="application/pdf"),
            metadata={
                "user_id": user_id,
                "lease_id": lease_data['id'],
                "property_id": lease_data['property_id'],
                "generated_at": datetime.utcnow().isoformat(),
                "document_type": "lease_pdf"
            }
        )

        return blob_name

    @staticmethod
    def _format_currency(amount: Decimal | None) -> str:
        """Format Decimal as currency string (no $)"""
        if amount is None:
            amount = Decimal("0")
        return f"{amount:,.2f}"

    @staticmethod
    def _escape_latex(text: str) -> str:
        """Escape special LaTeX characters in text"""
        if not text:
            return ""
        # Order matters - backslash must be first
        replacements = [
            ('\\', r'\textbackslash{}'),
            ('&', r'\&'),
            ('%', r'\%'),
            ('$', r'\$'),
            ('#', r'\#'),
            ('_', r'\_'),
            ('{', r'\{'),
            ('}', r'\}'),
            ('~', r'\textasciitilde{}'),
            ('^', r'\textasciicircum{}'),
        ]
        for char, replacement in replacements:
            text = text.replace(char, replacement)
        return text

    @staticmethod
    def _parse_pets_array(pets_data: Any) -> List[Dict[str, Any]]:
        """Parse pets from various formats (JSON string or list)"""
        if pets_data is None:
            return []

        if isinstance(pets_data, str):
            try:
                return json.loads(pets_data)
            except (json.JSONDecodeError, TypeError):
                return []

        if isinstance(pets_data, list):
            return pets_data

        return []

    @classmethod
    def _format_pet_descriptions(cls, pets: List[Dict[str, Any]]) -> str:
        """
        Format pets array into readable description grouped by type.

        Example output: "1-Dog (Pancho) 15lbs, 2-Cats (Sunshine and Blue)"
        """
        if not pets:
            return ""

        # Group pets by type
        dogs = []
        cats = []
        others = []

        for pet in pets:
            pet_type = pet.get("type", "other").lower()
            # Escape names for LaTeX
            name = cls._escape_latex((pet.get("name") or "").strip())
            weight = (pet.get("weight") or "").strip()
            breed = cls._escape_latex((pet.get("breed") or "").strip())

            pet_info = {"name": name, "weight": weight, "breed": breed}

            if pet_type == "dog":
                dogs.append(pet_info)
            elif pet_type == "cat":
                cats.append(pet_info)
            else:
                others.append(pet_info)

        parts = []

        # Format dogs
        if dogs:
            count = len(dogs)
            names = [d["name"] for d in dogs if d["name"]]
            weights = [d["weight"] for d in dogs if d["weight"]]

            desc = f"{count}-Dog" if count == 1 else f"{count}-Dogs"

            if names:
                if len(names) == 1:
                    desc += f" ({names[0]})"
                else:
                    desc += f" ({', '.join(names[:-1])} and {names[-1]})"

            # Add weight info for dogs
            if weights:
                if len(weights) == 1:
                    desc += f" {weights[0]}lbs"
                elif len(weights) == len(dogs):
                    # All dogs have weights
                    weight_strs = [f"{w}lbs" for w in weights]
                    desc += f" ({', '.join(weight_strs)})"

            parts.append(desc)

        # Format cats
        if cats:
            count = len(cats)
            names = [c["name"] for c in cats if c["name"]]

            desc = f"{count}-Cat" if count == 1 else f"{count}-Cats"

            if names:
                if len(names) == 1:
                    desc += f" ({names[0]})"
                else:
                    desc += f" ({', '.join(names[:-1])} and {names[-1]})"

            parts.append(desc)

        # Format others
        if others:
            count = len(others)
            names = [o["name"] for o in others if o["name"]]

            desc = f"{count}-Other Pet" if count == 1 else f"{count}-Other Pets"

            if names:
                if len(names) == 1:
                    desc += f" ({names[0]})"
                else:
                    desc += f" ({', '.join(names[:-1])} and {names[-1]})"

            parts.append(desc)

        return ", ".join(parts)

    @staticmethod
    def _parse_date(date_value: Any) -> Optional[date]:
        """Parse date from various formats"""
        if date_value is None:
            return None

        if isinstance(date_value, date):
            return date_value

        if isinstance(date_value, datetime):
            return date_value.date()

        if isinstance(date_value, pd.Timestamp):
            return date_value.date()

        if isinstance(date_value, str):
            try:
                # Try parsing as ISO format
                return datetime.fromisoformat(date_value.replace('Z', '+00:00')).date()
            except:
                try:
                    # Try pandas parsing
                    return pd.Timestamp(date_value).date()
                except:
                    return None

        return None

    def _build_holding_fee_addendum(
        self,
        lease_data: Dict[str, Any],
        tenants: List[Dict[str, Any]],
        property_data: Dict[str, Any]
    ) -> str:
        """Build LaTeX content for Holding Fee Addendum"""
        # Extract data
        holding_fee_amount = self._format_currency(lease_data.get("holding_fee_amount") or lease_data.get("security_deposit") or Decimal("0"))
        holding_fee_date = lease_data.get("holding_fee_date", "")
        security_deposit = self._format_currency(lease_data.get("security_deposit") or Decimal("0"))

        # Format holding fee date
        if holding_fee_date:
            parsed_date = self._parse_date(holding_fee_date)
            holding_fee_date_str = parsed_date.strftime("%B %d, %Y") if parsed_date else holding_fee_date
        else:
            holding_fee_date_str = "[Date of Collection]"

        # Property address
        full_address = property_data.get("full_address", property_data.get("address", ""))

        # Tenant names
        tenant_names = ", ".join([f"{t.get('first_name', '')} {t.get('last_name', '')}".strip() for t in tenants])

        # Owner info
        owner_name = self._escape_latex(lease_data.get("owner_name", "S&M Axios Heartland Holdings, LLC"))

        # Anticipated move-in date - use lease_start (with fallback to commencement_date for backward compatibility)
        move_in_date = lease_data.get("lease_start") or lease_data.get("commencement_date")
        if move_in_date:
            parsed_date = self._parse_date(move_in_date)
            move_in_date_str = parsed_date.strftime("%B %d, %Y") if parsed_date else str(move_in_date)
        else:
            move_in_date_str = "[Move-In Date]"

        # State for return requirements
        state = lease_data.get("state", "NE")

        latex = r'''\documentclass[11pt]{article}
\usepackage[margin=0.85in]{geometry}
\usepackage{fancyhdr}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{lastpage}

\usepackage{graphicx}

\pagestyle{fancy}
\fancyhf{}
\lhead{\includegraphics[height=0.4in]{n_logo.jpeg}}
\rhead{Holding Fee Agreement: ''' + self._escape_latex(full_address) + r'''}
\cfoot{Page \thepage\ of \pageref{LastPage}}

\titleformat{\section}{\normalfont\large\bfseries}{}{0em}{}
\titlespacing*{\section}{0pt}{0.8em}{0.4em}
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}

\begin{document}

\begin{center}
\textbf{\Large HOLDING FEE AGREEMENT}
\end{center}

\vspace{0.5em}

\textbf{DATE:} ''' + holding_fee_date_str + r''' \hfill \textbf{ANTICIPATED MOVE-IN:} ''' + move_in_date_str + r'''

\textbf{LANDLORD:} ''' + owner_name + r'''

\textbf{PROSPECTIVE TENANT(S):} ''' + self._escape_latex(tenant_names) + r'''

\textbf{PROPERTY:} ''' + self._escape_latex(full_address) + r'''

\section{1. PURPOSE}

Prospective Tenant has applied to rent the above-referenced Property. By signing this Agreement and paying the Holding Fee specified below, Prospective Tenant requests that Landlord remove the Property from the rental market and hold it exclusively for Prospective Tenant pending execution of a Residential Lease Agreement.

\section{2. HOLDING FEE}

Prospective Tenant agrees to pay a Holding Fee of \textbf{\$''' + holding_fee_amount + r'''} (the "Holding Fee") upon execution of this Agreement.

\section{3. CONVERSION TO SECURITY DEPOSIT}

Upon execution of a Residential Lease Agreement and move-in to the Property, the Holding Fee shall be \textbf{credited in full} toward the Security Deposit required under the Lease. The total Security Deposit under the Lease will be \textbf{\$''' + security_deposit + r'''}.

\section{4. TENANT CANCELLATION}

If Prospective Tenant fails or refuses to:
\begin{itemize}[leftmargin=2em, nosep]
    \item Execute the Residential Lease Agreement by the Anticipated Move-In Date; or
    \item Take possession of the Property by the Anticipated Move-In Date; or
    \item Otherwise withdraws from this transaction for any reason;
\end{itemize}

Then the Holding Fee shall be \textbf{retained by Landlord as liquidated damages}. The parties agree that the Holding Fee represents a reasonable estimate of Landlord's damages for lost rental opportunity, marketing costs, and administrative expenses incurred in holding the Property off the market.

\section{5. LANDLORD CANCELLATION}

If Landlord fails to offer the Lease, or if the Property becomes unavailable through no fault of Prospective Tenant, the Holding Fee shall be \textbf{refunded in full} within fourteen (14) days.

\section{6. REMAINING BALANCE}

Prior to receiving keys and taking possession of the Property, Prospective Tenant must pay:
\begin{itemize}[leftmargin=2em, nosep]
    \item The remaining balance of the Security Deposit (if Holding Fee is less than Security Deposit): \textbf{\$''' + self._format_currency(max(Decimal("0"), (lease_data.get("security_deposit") or Decimal("0")) - (lease_data.get("holding_fee_amount") or Decimal("0")))) + r'''}
    \item First month's rent (or prorated rent, if applicable)
\end{itemize}

\section{7. NO TENANCY CREATED}

This Agreement does not create a landlord-tenant relationship. Prospective Tenant has no right to occupy the Property until a Residential Lease Agreement is fully executed and all required payments are received.

\section{8. GOVERNING LAW}

This Agreement shall be governed by the laws of the State of ''' + ("Nebraska" if state == "NE" else "Missouri") + r'''.

\vspace{1em}

\textbf{AGREED AND ACCEPTED:}

\vspace{0.8em}

\begin{tabular}{p{3in}p{0.5in}p{2in}}
\rule{3in}{0.4pt} & & \rule{2in}{0.4pt} \\
Landlord Signature & & Date \\[0.8em]
\rule{3in}{0.4pt} & & \rule{2in}{0.4pt} \\
Prospective Tenant Signature & & Date \\
\end{tabular}

\vspace{1em}

\textit{Receipt of Holding Fee in the amount of \$''' + holding_fee_amount + r''' is acknowledged.}

\end{document}
'''
        return latex

    def generate_holding_fee_addendum_pdf(
        self,
        lease_data: Dict[str, Any],
        tenants: List[Dict[str, Any]],
        property_data: Dict[str, Any],
        user_id: str
    ) -> Tuple[bytes, str, str]:
        """
        Generate PDF for Holding Fee Addendum.

        Returns:
            Tuple of (pdf_bytes, pdf_blob_name, latex_blob_name)
        """
        # Generate LaTeX content
        latex_content = self._build_holding_fee_addendum(lease_data, tenants, property_data)

        # Save LaTeX to ADLS
        latex_blob_name = self._save_latex_to_adls(
            latex_content,
            lease_data,
            property_data,
            user_id,
            suffix="_holding_fee"
        )

        # Compile to PDF
        pdf_bytes = self._compile_pdf(latex_content)

        # Save PDF to ADLS
        pdf_blob_name = self._save_pdf_to_adls(
            pdf_bytes,
            lease_data,
            property_data,
            user_id,
            suffix="_holding_fee"
        )

        return pdf_bytes, pdf_blob_name, latex_blob_name

