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
        security_deposit = self._format_currency(lease_data.get("security_deposit") or Decimal("0"))
        late_fee_1 = self._format_currency(lease_data.get("late_fee_day_1_10") or Decimal("0"))
        late_fee_2 = self._format_currency(lease_data.get("late_fee_day_11") or Decimal("0"))
        late_fee_3 = self._format_currency(lease_data.get("late_fee_day_16") or Decimal("0"))
        nsf_fee = self._format_currency(lease_data.get("nsf_fee") or Decimal("0"))
        
        # Tenant names
        tenant_names = ", ".join([f"{t.get('first_name', '')} {t.get('last_name', '')}" for t in tenants])
        
        # Property info
        property_address = property_data.get("address", "")
        property_city = property_data.get("city", "")
        property_state = property_data.get("state", "")
        full_address = f"{property_address}, {property_city}, {property_state}"
        
        # Build document
        latex = r'''\documentclass[11pt,letterpaper]{article}
\usepackage[margin=1in]{geometry}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{fancyhdr}
\usepackage{tabularx}

% Formatting
\setlength{\parindent}{0pt}
\setlength{\parskip}{6pt}
\titleformat{\section}{\bfseries}{}{0em}{\uppercase}
\titleformat{\subsection}{\bfseries}{\thesubsection.}{0.5em}{}

% Header/Footer
\pagestyle{fancy}
\fancyhf{}
\rhead{Lease Agreement: ''' + property_address + r'''}
\cfoot{Page \thepage}

\begin{document}

\begin{center}
{\LARGE\bfseries RESIDENTIAL LEASE AGREEMENT}
\end{center}

\vspace{1em}

\noindent This Lease Agreement (``Lease'') is entered into on \underline{\hspace{3cm}}, by and between:

\noindent\textbf{LANDLORD:} S\&M Axios Heartland Holdings, LLC (``Landlord'')\\
\textbf{TENANT(S):} ''' + tenant_names + r''' (collectively ``Tenant'')

This Lease creates joint and several liability in the case of multiple Tenants. The Parties agree as follows:

\section{1. PREMISES}
Landlord hereby leases the Premises located at: \textbf{''' + full_address + r'''} (``Premises''). Description: ''' + property_data.get("description", "Residential property") + r'''.

\section{2. LEASE TERM}
The Lease shall begin on \underline{\hspace{3cm}} (``Commencement Date'') and end on \underline{\hspace{3cm}} (``Termination Date''). Upon expiration, this Lease shall [ ] convert to month-to-month or [ ] terminate, unless renewed in writing.

\section{3. LEASE PAYMENTS (RENT)}
Tenant agrees to pay Landlord as rent for the Premises the amount of \textbf{\$''' + monthly_rent + r'''} per month. Rent is due in advance on the 1st day of each month. \textbf{Rent is due by the 5th of every month, by 6pm.}
\begin{itemize}
    \item \textbf{Payment Method:} Rent shall be paid via \underline{\hspace{5cm}}.
    \item \textbf{Prorated Rent:} If the Commencement Date is not the 1st of the month, the first month's rent shall be prorated based on \$''' + monthly_rent + r''' / 365 per day (rounded up to the nearest dollar) to \$\underline{\hspace{2cm}}.
\end{itemize}

\section{4. LATE CHARGES}
'''
        
        # Add late fee structure based on state
        if lease_data.get("state") == "NE" and lease_data.get("late_fee_day_16"):
            latex += r'''If any amount under this Lease is late, Tenant agrees to pay a late fee of \textbf{\$''' + late_fee_1 + r'''}. If payment and late fee is not paid by the \textbf{11th}, Tenant agrees to pay a late fee of \textbf{\$''' + late_fee_2 + r'''}. If payment and late fee is not paid by the \textbf{16th}, Tenant agrees to pay a late fee of \textbf{\$''' + late_fee_3 + r'''}. If payment and late fee is not paid by the \textbf{21st}. If late fees and rent are not paid in full prior to and/or along with next month's rent by due date of the 5th, automatic eviction notice will be given.'''
        else:
            latex += r'''If rent is not paid by the due date, Tenant agrees to pay a late fee of \textbf{\$''' + late_fee_1 + r'''}. If payment remains unpaid after the 11th, an additional late fee of \textbf{\$''' + late_fee_2 + r'''} will be assessed.'''
        
        latex += r'''

\section{5. INSUFFICIENT FUNDS}
Tenant agrees to pay the charge of \textbf{\$''' + nsf_fee + r'''} for each check given by Tenant to Landlord that is returned to Landlord for lack of sufficient funds.

\section{6. SECURITY DEPOSIT}
At the signing of this Lease, Tenant shall deposit with Landlord the sum of \textbf{\$''' + security_deposit + r'''} as a Security Deposit. This deposit secures the performance of this Lease. Landlord may use the deposit to cover unpaid rent or damages beyond normal wear and tear. The deposit shall be returned within ''' + str(lease_data.get("deposit_return_days", 14)) + r''' days after termination of the tenancy, less itemized deductions, per ''' + lease_data.get("state", "NE") + r''' law.

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
        
        # Add pet section
        if lease_data.get("pets_allowed"):
            pet_fee_one = self._format_currency(lease_data.get("pet_fee_one", Decimal("0")))
            pet_fee_two = self._format_currency(lease_data.get("pet_fee_two", Decimal("0")))
            latex += r'''Tenant shall not keep any Pets on the Premises without the prior written consent of the Landlord. Non-refundable Pet Fee required: \textbf{\$''' + pet_fee_one + r'''} for one pet, \textbf{\$''' + pet_fee_two + r'''} for two pets. Max pet occupancy ''' + str(lease_data.get("max_pets", 2)) + r''' pets. Fee is non-refundable. It is Tenant's responsibility to properly clean-up/dispose of all waste from pets on property. Replacement of a registered pet (up to the maximum occupancy) does not incur an additional fee.'''
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
        
        # Add maintenance specifics if applicable
        maintenance_items = []
        if lease_data.get("has_shared_driveway"):
            maintenance_items.append(r'''\item \textbf{Shared Driveway:} Tenant shall NOT block the shared driveway with ''' + lease_data.get("shared_driveway_with", "neighboring property") + r'''.''')
        if lease_data.get("snow_removal_responsibility") == "tenant":
            maintenance_items.append(r'''\item \textbf{Snow Removal:} Tenant is responsible for snow removal on walkways/driveway.''')
        
        if maintenance_items:
            latex += r'''\begin{itemize}
''' + "\n".join(maintenance_items) + r'''
\end{itemize}
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
Tenant shall be entitled to use \textbf{''' + str(lease_data.get("parking_spaces", 2)) + r'''} parking space(s) for the parking of motor vehicle(s). Note: Parking capacity allows for ''' + str(lease_data.get("parking_small_vehicles", 2)) + r''' small vehicles per unit. Large trucks are limited to \textbf{''' + str(lease_data.get("parking_large_trucks", 1)) + r'''} off-street space to ensure access for the neighboring unit.

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
        
        # Create temporary directory for this compilation
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            tex_file = tmpdir_path / "lease.tex"
            pdf_file = tmpdir_path / "lease.pdf"
            
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
                raise Exception(f"LaTeX compilation failed: {e.stderr.decode()}")
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
        user_id: str
    ) -> str:
        """Save LaTeX source to ADLS"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        property_address = property_data.get("address", "unknown").replace(" ", "_").replace("/", "_")
        filename = f"lease_{property_address}_{timestamp}.tex"
        
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
        user_id: str
    ) -> str:
        """Save PDF to ADLS"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        property_address = property_data.get("address", "unknown").replace(" ", "_").replace("/", "_")
        filename = f"lease_{property_address}_{timestamp}.pdf"
        
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

