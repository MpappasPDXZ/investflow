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
        
        # Extract data (handle None values with or)
        monthly_rent = self._format_currency(lease_data.get("monthly_rent") or Decimal("0"))
        monthly_rent_decimal = Decimal(str(lease_data.get("monthly_rent") or "0"))
        security_deposit = self._format_currency(lease_data.get("security_deposit") or Decimal("0"))
        
        # Holding fee info
        include_holding_fee = lease_data.get("include_holding_fee_addendum", False)
        holding_fee_amount = self._format_currency(lease_data.get("holding_fee_amount") or Decimal("0"))
        holding_fee_date = lease_data.get("holding_fee_date", "")
        
        late_fee_1 = self._format_currency(lease_data.get("late_fee_day_1_10") or Decimal("0"))
        late_fee_2 = self._format_currency(lease_data.get("late_fee_day_11") or Decimal("0"))
        late_fee_3 = self._format_currency(lease_data.get("late_fee_day_16") or Decimal("0"))
        late_fee_4 = self._format_currency(lease_data.get("late_fee_day_21") or Decimal("0"))
        nsf_fee = self._format_currency(lease_data.get("nsf_fee") or Decimal("0"))
        
        # Tenant names
        tenant_names = ", ".join([f"{t.get('first_name', '')} {t.get('last_name', '')}" for t in tenants])
        
        # Owner info - escape LaTeX special chars
        owner_name = self._escape_latex(lease_data.get("owner_name", "S&M Axios Heartland Holdings, LLC"))
        
        # Property info - address already includes city/state
        full_address = property_data.get("address", "")
        # For header - just street address without city/state for brevity
        property_address = full_address
        
        # Parse dates
        commencement_date = self._parse_date(lease_data.get("commencement_date"))
        termination_date = self._parse_date(lease_data.get("termination_date"))
        lease_date = self._parse_date(lease_data.get("lease_date"))
        
        # Format dates for display
        commencement_str = commencement_date.strftime("%B %d, %Y") if commencement_date else "\\underline{\\hspace{3cm}}"
        termination_str = termination_date.strftime("%B %d, %Y") if termination_date else "\\underline{\\hspace{3cm}}"
        lease_date_str = lease_date.strftime("%B %d, %Y") if lease_date else "\\underline{\\hspace{3cm}}"
        
        # Calculate prorated rent
        prorated_rent_str = "\\underline{\\hspace{2cm}}"
        if commencement_date and commencement_date.day != 1:
            # Days after the 1st = day - 1 (e.g., 3rd = 2 days)
            days_after_first = commencement_date.day - 1
            # Calculate percentage: (30 - days_after_first) / 30
            prorated_percentage = (Decimal("30") - Decimal(str(days_after_first))) / Decimal("30")
            prorated_rent = (monthly_rent_decimal * prorated_percentage).quantize(Decimal("0.01"))
            prorated_rent_str = self._format_currency(prorated_rent)
        
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
Landlord hereby leases the Premises located at: \textbf{''' + full_address + r'''} (``Premises''). Description: ''' + property_data.get("description", "Residential property") + r'''.

\section{2. LEASE TERM AND RENEWAL}
The Lease shall begin on \textbf{''' + commencement_str + r'''} (``Commencement Date'') and end on \textbf{''' + termination_str + r'''} (``Termination Date'').

\textbf{Automatic Month-to-Month Conversion:} Unless either party provides written notice of intent to terminate at least thirty (30) days prior to the Termination Date (or any subsequent month-end during a month-to-month tenancy), this Lease shall automatically convert to a month-to-month tenancy upon the same terms and conditions, except as modified herein.

\textbf{Rent Adjustment During Month-to-Month:} Landlord may adjust the monthly rent upon thirty (30) days' prior written notice to Tenant. The adjusted rent shall take effect on the first day of the month following the expiration of the notice period.

\textbf{Termination of Month-to-Month Tenancy:} Either party may terminate the month-to-month tenancy by providing at least thirty (30) days' written notice prior to the end of any monthly rental period. Such notice shall be delivered in accordance with Section 29 (Notice) of this Lease.

\section{3. LEASE PAYMENTS (RENT)}
Tenant agrees to pay Landlord as rent for the Premises the amount of \textbf{\$''' + monthly_rent + r'''} per month. Rent is due on the \textbf{1st day of each month}. Rent paid by the \textbf{5th of the month by 6pm} is not considered late.
\begin{itemize}
    \item \textbf{Payment Method:} Rent shall be paid exclusively via \textbf{TurboTenant}. If Tenant experiences any technical issues with TurboTenant, Tenant must notify Landlord immediately via email or text message. In the event there is a technical issue that cannot be resolved before rent is due, Landlord will accept payment by \textbf{check} made payable to \textbf{''' + owner_name + r'''}.''' + (r'''
    \item \textbf{Prorated Rent:} If the Commencement Date is not the 1st of the month, the first month's rent shall be prorated based on \$''' + monthly_rent + r''' $\times$ (30 - days after 1st) / 30 (rounded to the nearest cent) to \textbf{\$''' + prorated_rent_str + r'''}. ''' if lease_data.get("show_prorated_rent") else '') + r'''
\end{itemize}

\section{4. LATE CHARGES}
'''
        
        # Add late fee structure based on state
        if lease_data.get("state") == "NE" and lease_data.get("late_fee_day_16"):
            latex += r'''If rent is not paid by the \textbf{5th at 6pm}, a late fee of \textbf{\$''' + late_fee_1 + r'''} will be assessed. If rent and late fee are not paid by the \textbf{11th}, the late fee increases to \textbf{\$''' + late_fee_2 + r'''}. If not paid by the \textbf{16th}, the late fee increases to \textbf{\$''' + late_fee_3 + r'''}. If not paid by the \textbf{21st}, the late fee increases to \textbf{\$''' + late_fee_4 + r'''}. If rent and all late fees are not paid in full prior to the next month's rent due date (the 5th), an automatic eviction notice will be given.'''
        else:
            latex += r'''If rent is not paid by the due date, Tenant agrees to pay a late fee of \textbf{\$''' + late_fee_1 + r'''}. If payment remains unpaid after the 11th, an additional late fee of \textbf{\$''' + late_fee_2 + r'''} will be assessed.'''
        
        latex += r'''

\section{5. INSUFFICIENT FUNDS (NSF)}
Payments made via \textbf{TurboTenant} are processed electronically and will either complete successfully or be declined at the time of transaction; therefore, NSF fees do not apply to TurboTenant payments. However, if Tenant pays by \textbf{check} (as permitted under Section 3 for technical issues only), and such check is returned to Landlord due to insufficient funds, stop payment, or closed account, Tenant agrees to pay a fee of \textbf{\$''' + nsf_fee + r'''} for each returned check. This NSF fee is \textit{in addition to} any applicable late fees assessed under Section 4.

\textit{Example: If Tenant pays January rent by check on the 4th and the check is returned for insufficient funds on the 8th, Tenant owes: (1) the original rent amount, (2) the applicable late fee (since rent was not successfully paid by the 5th at 6pm), and (3) the \$''' + nsf_fee + r''' NSF fee.}

\section{6. SECURITY DEPOSIT}
At the signing of this Lease, Tenant shall deposit with Landlord the sum of \textbf{\$''' + security_deposit + r'''} as a Security Deposit. This deposit secures the performance of this Lease. Landlord may use the deposit to cover unpaid rent or damages beyond normal wear and tear. The deposit shall be returned within ''' + str(lease_data.get("deposit_return_days", 14)) + r''' days after termination of the tenancy, less itemized deductions, per ''' + lease_data.get("state", "NE") + r''' law.''' + (r'''

\textit{Note: A Holding Fee of \textbf{\$''' + holding_fee_amount + r'''} was previously collected pursuant to the Holding Fee Agreement dated ''' + (holding_fee_date if holding_fee_date else "prior to lease execution") + r'''. This Holding Fee has been credited in full toward the Security Deposit shown above.}''' if include_holding_fee else "") + r'''

\section{7. DEFAULTS}
If Tenant fails to perform any obligation under this Lease, Tenant shall be in default.
\begin{itemize}
    \item \textbf{Non-Payment:} Landlord may deliver a \textbf{7-Day Notice to Pay or Quit}.
    \item \textbf{Other Breaches:} Landlord may deliver a \textbf{14/30 Day Notice} to cure or quit.
    \item \textbf{Illegal Activity:} Landlord may deliver a \textbf{5-Day Unconditional Notice to Quit}.
\end{itemize}
Landlord may re-enter and take possession as permitted by law. Tenant remains liable for unpaid rent and damages.

\section{8. QUIET ENJOYMENT}
Tenant shall be entitled to quiet enjoyment of the Premises as long as Tenant pays rent and performs all obligations under this Lease.

\section{9. POSSESSION AND SURRENDER}
Tenant shall be entitled to possession on the first day of the Lease Term. At expiration, Tenant shall surrender the Premises in good condition, reasonable wear and tear excepted.

\section{10. USE OF PREMISES}
The Premises shall be used as a private residence only. No business or trade may be conducted without prior written consent. Tenant will comply with all laws, rules, ordinances, statutes and orders regarding the use of the Premises.

\section{11. OCCUPANTS}
Tenant agrees that no more than \textbf{''' + str(lease_data.get("max_occupants", 3)) + r'''} persons OR \textbf{''' + str(lease_data.get("max_adults", 2)) + r''' adults and their minor children} may reside on the Premises, without prior written consent of the Landlord. Guests staying longer than 7 consecutive days or 14 days in a 6-month period require written consent. Unauthorized occupants shall constitute a material breach of this Lease, subject to termination under Section 7.

\section{12. CONDITION OF PREMISES}
Tenant or Tenant's agent has inspected the Premises, the fixtures, the grounds, building and improvements and acknowledges that the Premises are in good and acceptable condition and are habitable. If at any time during the term of this Lease, in Tenant's opinion, the conditions change, Tenant shall promptly provide reasonable notice to Landlord.

\section{13. ASSIGNMENT AND SUBLEASE}
Tenant shall not assign or sublease any interest in this lease without prior written consent of the Landlord, which consent shall not be unreasonably withheld. Any assignment or sublease without Landlord's written prior consent shall, at Landlord's option, terminate this Lease.

\section{14. DANGEROUS MATERIALS}
Tenant shall not keep or have on or around the Premises any item of a dangerous, flammable or explosive character that might unreasonably increase the risk of fire or explosion on or around the Premises or that might be considered hazardous by any responsible insurance company.

\section{15. UTILITIES AND SERVICES}
Tenant will be responsible for all utilities and services required on the Premises (including ''' + lease_data.get("utilities_tenant", "Gas, Sewer, Water, and Electricity") + r'''), except Landlord will provide: \textbf{''' + lease_data.get("utilities_landlord", "Trash") + r'''}.

\section{16. PETS}
'''
        
        # Add pet section using new pet_fee and pets array format
        if lease_data.get("pets_allowed") and lease_data.get("max_pets", 0) > 0:
            pet_fee = self._format_currency(lease_data.get("pet_fee") or lease_data.get("pet_fee_one") or Decimal("0"))
            max_pets = lease_data.get("max_pets", 0)
            pets_array = self._parse_pets_array(lease_data.get("pets"))
            
            # Build pet descriptions grouped by type
            pet_descriptions = self._format_pet_descriptions(pets_array)
            
            if pet_descriptions:
                latex += r'''Pet Fee is \textbf{\$''' + pet_fee + r'''} and includes ''' + str(max_pets) + r''' pet''' + ('s' if max_pets != 1 else '') + r''': ''' + pet_descriptions + r'''. Pets are replaceable at no cost to the tenant. All pets must be approved if breed is changed or weight is increased. It is Tenant's responsibility to properly clean-up/dispose of all waste from pets on property.'''
            else:
                # Fallback if no pet details provided
                latex += r'''Pet Fee is \textbf{\$''' + pet_fee + r'''} for up to ''' + str(max_pets) + r''' pet''' + ('s' if max_pets != 1 else '') + r'''. Fee is non-refundable. Pets are replaceable at no cost to the tenant. All pets must be approved if breed is changed or weight is increased. It is Tenant's responsibility to properly clean-up/dispose of all waste from pets on property.'''
        else:
            latex += r'''No pets allowed on the Premises without prior written consent of the Landlord.'''
        
        latex += r'''

\section{17. ALTERATIONS AND IMPROVEMENTS}
Tenant agrees not to make any improvements or alterations to the Premises without prior written consent of the Landlord. If any alterations, improvements or changes are made to or built on or around the Premises, with the exception of fixtures and personal property that can be removed without damage to the Premises, they shall become the property of Landlord and shall remain at the expiration of the Lease, unless otherwise agreed in writing.

\section{18. DAMAGE TO PREMISES}
If the Premises or part of the Premises are damaged or destroyed by fire or other casualty not due to Tenant's negligence, the rent will be abated during the time that the Premises are uninhabitable. If Landlord decides not to repair or rebuild the Premises, then this Lease shall terminate, and the rent shall be prorated up to the time of the damage. Any unearned rent paid in advance shall be refunded to Tenant.

\section{19. MAINTENANCE AND REPAIR}
Tenant will, at Tenant's sole expense, keep and maintain the Premises in good, clean and sanitary condition and repair during the term of this Lease and any renewal thereof. Tenant shall be responsible to make all repairs to the Premises, fixtures, appliances and equipment therein that may have been damaged by Tenant's misuse, waste, or neglect, or that of the Tenant's family, agent, or visitor. Tenant agrees that no painting will be done on or about the Premises without the prior written consent of Landlord. Tenant shall promptly notify Landlord of any damage, defect or destruction of the Premises, or in the event of the failure of any of the appliances or equipment. Landlord will use its best efforts to repair or replace any such damaged or defective area, appliance or equipment. If issue is not a water emergency, an acceptable time for maintenance to return call/text of issue is 24 hours.
'''
        
        # Add maintenance responsibilities with checkboxes
        tenant_mowing = lease_data.get("tenant_lawn_mowing", True)
        tenant_snow = lease_data.get("tenant_snow_removal", True)
        tenant_lawn_care = lease_data.get("tenant_lawn_care", False)
        
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
    \textit{General lawn and landscape maintenance including: seasonal activation and winterization of sprinkler/irrigation systems, watering as needed, overseeding bare or damaged areas, and fertilization.}
\end{itemize}
'''
        
        # Add shared driveway notice if applicable
        if lease_data.get("has_shared_driveway"):
            latex += r'''
\textbf{Shared Driveway Notice:} Tenant shall NOT block the shared driveway with ''' + self._escape_latex(lease_data.get("shared_driveway_with", "neighboring property")) + r'''.
'''
        
        # Continue with remaining sections
        latex += self._generate_remaining_sections(lease_data, property_data)
        
        # Add move-out costs section
        latex += self._generate_moveout_section(lease_data)
        
        # Add signatures
        latex += self._generate_signatures(tenants)
        
        latex += r'''
\end{document}
'''
        
        return latex
    
    def _generate_remaining_sections(self, lease_data: Dict[str, Any], property_data: Dict[str, Any]) -> str:
        """Generate sections 20-38"""
        latex = r'''
\section{20. RIGHT OF INSPECTION}
Tenant agrees to make the premises available to Landlord or Landlord's agents for the purposes of inspection, making repairs or improvements, or to supply agreed services or show the premises to prospective buyers or tenants, or in case of emergency. Except in case of emergency, Landlord shall give Tenant reasonable notice of intent to enter. For these purposes, twenty-four (24) hour notice shall be deemed reasonable. Tenant shall not, without Landlord's prior written consent, add, alter or re-key any locks to the premises. At all times Landlord shall be provided with a key or keys capable of unlocking all such locks and gaining entry. Tenant further agree to notify Landlord in writing if Tenant installs any burglar alarm system, including instructions on how to disarm it in case of emergency entry.

\section{21. ABANDONMENT}
If Tenant abandons the Premises or any personal property during the term of this Lease, Landlord may at its option enter the Premises by any legal means without liability to Tenant and may at Landlord's option terminate the Lease. Abandonment is defined as absence of the Tenants from the premises, for at least 30 consecutive days without notice to Landlord. If Tenant abandons the premises while the rent is outstanding for more than 15 days and there is no reasonable evidence, other than the presence of the Tenants' personal property, that the Tenant is occupying the unit, Landlord may at Landlord's option terminate this agreement and regain possession in the manner prescribed by law. Landlord will dispose of all abandoned personal property on the Premises in any manner allowed by law.

\section{22. EXTENDED ABSENCES}
In the event Tenant will be away from the premises for more than 30 consecutive days, Tenant agrees to notify Landlord in writing of such absence. During such absence, Landlord may enter the premises at times reasonably necessary to maintain the property and inspect for damages and needed repairs.

\section{23. SECURITY}
Tenant understands that Landlord does not provide any security alarm system or other security for Tenant or the Premises. In the event any alarm system is provided, Tenant understands that such alarm system is not warranted to be complete in all respects or to be sufficient to protect Tenant or the Premises. Tenant releases Landlord from any loss, damage, claim or injury resulting from the failure of any alarm system, security or from the lack of any alarm system or security.

\section{24. SEVERABILITY}
If any part or parts of this Lease shall be held unenforceable for any reason, the remainder of this Agreement shall continue in full force and effect. If any provision of this Lease is deemed invalid or unenforceable by any court of competent jurisdiction, and if limiting such provision would make the provision valid, then such provision shall be deemed to be construed as so limited.

\section{25. INSURANCE}
Landlord and Tenant shall each be responsible to maintain appropriate insurance for their respective interests in the Premises and property located on the Premises. Tenant understands that Landlord will not provide any insurance coverage for Tenant's property. Landlord will not be responsible for any loss of Tenant's property, whether by theft, fire, riots, strikes, acts of God, or otherwise. Landlord encourages Tenant to obtain renter's insurance or other similar coverage to protect against risk of loss.

\section{26. BINDING EFFECT}
This Lease binds the parties and their heirs/successors.

\section{27. GOVERNING LAW}
Governed by the laws of the State of ''' + lease_data.get("state", "Nebraska") + r'''.

\section{28. ENTIRE AGREEMENT}
This Lease constitutes the entire agreement between the parties and supersedes any prior understanding or representation of any kind preceding the date of this Agreement. There are no other promises, conditions, understandings or other agreements, whether oral or written, relating to the subject matter of this Lease. This Lease may be modified in writing and must be signed by both Landlord and Tenant.

\section{29. NOTICE}
Any notice required or otherwise given pursuant to this Lease shall be in writing and mailed certified return receipt requested, postage prepaid, or delivered by overnight delivery service, if to Tenant, at the Premise and if to Landlord, at the address for payment of rent. Either party may change such addresses from time to time by providing notice as set forth above.
\begin{itemize}
    \item \textbf{Landlord:} S\&M Axios Heartland Holdings, LLC, c/o Sarah Pappas, 1606 S 208th St, Elkhorn, NE 68022 (Phone: 402-482-6195).
    \item \textbf{Tenant:} At the Premises.
\end{itemize}

\section{30. CUMULATIVE RIGHTS}
Landlord's rights are cumulative and not exclusive.

\section{31. WAIVER}
Failure to enforce a provision does not waive the right to enforce it later.

\section{32. DISPLAY OF SIGNS}
Landlord may display ``For Rent'' signs during the last 60 days of the Lease.

\section{33. PARKING}
'''
        
        # Build parking description dynamically
        garage_spaces = int(lease_data.get("garage_spaces", 0) or 0)
        offstreet_spots = int(lease_data.get("offstreet_parking_spots", 0) or 0)
        total_spaces = int(lease_data.get("parking_spaces", 0) or 0)
        
        # Check if this is a multi-family property (has unit_id)
        is_multi_family = lease_data.get("unit_id") is not None and lease_data.get("unit_id") != ""
        
        # Build assigned spaces description
        parking_parts = []
        if garage_spaces > 0:
            garage_text = f"{garage_spaces} garage space" if garage_spaces == 1 else f"{garage_spaces} garage spaces"
            parking_parts.append(garage_text)
        if offstreet_spots > 0:
            offstreet_text = f"{offstreet_spots} off-street parking space" if offstreet_spots == 1 else f"{offstreet_spots} off-street parking spaces"
            parking_parts.append(offstreet_text)
        
        if parking_parts:
            assigned_spaces = " and ".join(parking_parts)
        elif total_spaces > 0:
            assigned_spaces = f"{total_spaces} parking space" if total_spaces == 1 else f"{total_spaces} parking spaces"
        else:
            assigned_spaces = "designated parking area"
        
        latex += r'''\textbf{Assigned Parking:} Tenant is assigned \textbf{''' + assigned_spaces + r'''} for the exclusive use of Tenant's operable, properly registered, and insured motor vehicle(s).

\textbf{Permitted Vehicles:} Only passenger vehicles, including automobiles, motorcycles, and non-commercial pickup trucks, are permitted. The parking of trailers, boats, campers, recreational vehicles, buses, or commercial vehicles is prohibited without prior written consent from Landlord.

\textbf{Parking Regulations:}
\begin{itemize}[nosep, leftmargin=2em]
    \item Tenant shall park only in assigned space(s) and shall not obstruct driveways, fire lanes, sidewalks, or access to other parking spaces.
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
Tenant will be given \textbf{''' + str(lease_data.get("front_door_keys", 1)) + r'''} key to the Front Door and \textbf{''' + str(lease_data.get("back_door_keys", 1)) + r'''} key to the Back Door. Mailbox is unlocked and fixed to the dwelling. Tenant shall be charged \textbf{\$''' + self._format_currency(lease_data.get("key_replacement_fee", Decimal("100"))) + r'''} per key if all keys are not returned to Landlord following termination of the Lease.

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
        if lease_data.get("appliances_provided"):
            latex += r'''    \item \textbf{Appliances:} ''' + lease_data.get("appliances_provided") + r'''.
'''
        if lease_data.get("has_attic") and lease_data.get("attic_usage"):
            latex += r'''    \item \textbf{Attic Usage:} ''' + lease_data.get("attic_usage") + r'''.
'''
        if lease_data.get("lead_paint_disclosure"):
            year_built = lease_data.get("lead_paint_year_built", property_data.get("year_built", 1978))
            latex += r'''    \item \textbf{Lead-Based Paint:} Housing built before 1978 may contain lead-based paint. The Premises was built in ''' + str(year_built) + r'''. Landlord discloses the known presence of lead-based paint and/or lead-based paint hazards. Tenant acknowledges receipt of the EPA pamphlet ``Protect Your Family from Lead in Your Home''.
'''
        latex += r'''    \item \textbf{Tenant Representations:} Application info via MySmartMove.com is warranted as true; falsification is default.
'''
        
        if lease_data.get("early_termination_allowed"):
            early_term_fee = self._format_currency(lease_data.get("early_termination_fee_amount", Decimal("0")))
            early_term_days = lease_data.get("early_termination_notice_days", 60)
            latex += r'''    \item \textbf{Early Termination:} Tenant may terminate early with ''' + str(early_term_days) + r''' days' notice AND payment of a 2-month rent fee (\textbf{\$''' + early_term_fee + r'''}). The Security Deposit shall NOT be applied toward this fee.
'''
        
        if lease_data.get("garage_outlets_prohibited"):
            latex += r'''    \item \textbf{Garage Outlets:} Tenant is strictly prohibited from using the electrical outlets in the garage for any purpose.
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
    
    def _generate_signatures(self, tenants: List[Dict[str, Any]]) -> str:
        """Generate signature section"""
        latex = r'''
\vspace{2em}

\noindent\textbf{SIGNATURES}

\vspace{1em}

\noindent\begin{tabularx}{\textwidth}{@{}X X@{}}
\rule{7cm}{0.4pt} & \rule{7cm}{0.4pt} \\
\textbf{Landlord:} S\&M Axios Heartland Holdings, LLC & \textbf{Date} \\
\textit{By: Sarah Pappas, Member} & \\[3em]
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
            name = cls._escape_latex(pet.get("name", "").strip())
            weight = pet.get("weight", "").strip()
            breed = cls._escape_latex(pet.get("breed", "").strip())
            
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
        
        # Anticipated move-in date
        commencement_date = lease_data.get("commencement_date")
        if commencement_date:
            parsed_date = self._parse_date(commencement_date)
            move_in_date_str = parsed_date.strftime("%B %d, %Y") if parsed_date else str(commencement_date)
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

