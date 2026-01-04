"""
Walkthrough Generator Service
Generates PDF inspection reports from walkthrough data using LaTeX.
All temporary and final files are stored in ADLS.
"""
import json
import subprocess
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
import pandas as pd
import requests

from app.services.adls_service import adls_service
from app.services.document_service import document_service


# Define floor order for sorting
FLOOR_ORDER = ["Basement", "Floor 1", "Floor 2", "Floor 3", "Attic"]


class WalkthroughGeneratorService:
    """Service for generating PDF walkthrough inspection reports from data"""
    
    def __init__(self):
        self.adls = adls_service
        self.temp_folder = "walkthroughs/temp"  # ADLS folder for temporary files
        self.final_folder = "walkthroughs/generated"  # ADLS folder for final PDFs
    
    def generate_walkthrough_pdf(
        self,
        walkthrough_data: Dict[str, Any],
        areas: List[Dict[str, Any]],
        property_data: Dict[str, Any],
        user_id: str,
        landlord_name: Optional[str] = None
    ) -> Tuple[bytes, str, str]:
        """
        Generate PDF walkthrough report from data and store in ADLS.
        
        Args:
            walkthrough_data: Dictionary with walkthrough information
            areas: List of area dictionaries
            property_data: Property information
            user_id: User ID for ADLS folder organization
        
        Returns:
            Tuple of (pdf_bytes, pdf_blob_name, latex_blob_name)
        """
        # Generate LaTeX content (this will download photos if needed)
        latex_content, photo_files = self._build_latex_document(walkthrough_data, areas, property_data, user_id, landlord_name)
        
        # Save LaTeX to ADLS
        latex_blob_name = self._save_latex_to_adls(
            latex_content,
            walkthrough_data,
            property_data,
            user_id
        )
        
        # Compile to PDF (with photos in temp directory)
        pdf_bytes = self._compile_pdf(latex_content, photo_files)
        
        # Save PDF to ADLS
        pdf_blob_name = self._save_pdf_to_adls(
            pdf_bytes,
            walkthrough_data,
            property_data,
            user_id
        )
        
        return pdf_bytes, pdf_blob_name, latex_blob_name
    
    def _build_latex_document(
        self,
        walkthrough_data: Dict[str, Any],
        areas: List[Dict[str, Any]],
        property_data: Dict[str, Any],
        user_id: str,
        landlord_name: Optional[str] = None
    ) -> Tuple[str, Dict[str, bytes]]:
        """Build complete LaTeX document from walkthrough data"""
        
        # ============================================================================
        # ALL DATA CONVERSIONS AT THE TOP - KEEP IT SIMPLE
        # ============================================================================
        
        # Walkthrough type conversion
        walkthrough_type = walkthrough_data.get("walkthrough_type", "move_in")
        type_display = walkthrough_type.replace('_', ' ').title()
        if type_display == "Move In":
            type_display = "Move-In Inspection"
        elif type_display == "Move Out":
            type_display = "Move-Out Inspection"
        
        # Date conversion - try multiple possible field names
        walkthrough_date = None
        date_value = walkthrough_data.get("walkthrough_date") or walkthrough_data.get("date") or walkthrough_data.get("inspection_date")
        
        # Handle pandas NaN/NaT values
        if date_value is not None and not (isinstance(date_value, float) and pd.isna(date_value)):
            if isinstance(date_value, pd.Timestamp) and pd.isna(date_value):
                date_value = None
            else:
                walkthrough_date = self._parse_date(date_value)
                if walkthrough_date is None:
                    # Log warning if date couldn't be parsed
                    logger = self._get_logger()
                    logger.warning(f"Could not parse date value: {date_value} (type: {type(date_value)})")
        
        walkthrough_date_str = walkthrough_date.strftime("%B %d, %Y") if walkthrough_date else "N/A"
        
        # Inspector name - default to Sarah Pappas if not set
        inspector_name = walkthrough_data.get("inspector_name") or "Sarah Pappas, Member S&M Axios Heartland Holdings LLC"
        inspector_name_escaped = self._escape_latex(inspector_name)
        
        # Tenant name
        tenant_name = walkthrough_data.get("tenant_name", "") or "N/A"
        tenant_name_escaped = self._escape_latex(tenant_name)
        
        # Notes
        notes = walkthrough_data.get("notes", "") or ""
        notes_escaped = self._escape_latex(notes) if notes else ""
        
        # Property address - use denormalized property_display_name from walkthrough first, but ensure zip code is included
        property_address_full = walkthrough_data.get("property_display_name")
        if not property_address_full:
            # Fall back to property_data - build full address with zip code
            property_address_full = property_data.get("display_name")
        
        # Always check property_data for zip code and append if missing
        property_zip = property_data.get("zip_code") or property_data.get("postal_code") or property_data.get("zip", "")
        if property_zip and property_zip not in (property_address_full or ""):
            # Build full address from property_data if we don't have a complete one
            if not property_address_full or property_address_full == "N/A":
                property_address = property_data.get("address", "N/A")
                property_city = property_data.get("city", "")
                property_state = property_data.get("state", "")
                
                property_address_full = f"{property_address}"
                if property_city:
                    property_address_full += f", {property_city}"
                if property_state:
                    property_address_full += f" {property_state}"
                if property_zip:
                    property_address_full += f" {property_zip}"
            else:
                # Append zip code to existing address if not already there
                property_address_full += f" {property_zip}"
        elif not property_address_full:
            # Build from property_data components
            property_address = property_data.get("address", "N/A")
            property_city = property_data.get("city", "")
            property_state = property_data.get("state", "")
            
            property_address_full = f"{property_address}"
            if property_city:
                property_address_full += f", {property_city}"
            if property_state:
                property_address_full += f" {property_state}"
            if property_zip:
                property_address_full += f" {property_zip}"
        
        property_address_full_escaped = self._escape_latex(property_address_full)
        
        # Sort areas by floor order then area_order
        def get_floor_sort_key(area):
            floor = area.get("floor", "Floor 1")
            try:
                return FLOOR_ORDER.index(floor)
            except ValueError:
                return 999  # Put unknown floors at the end
        
        sorted_areas = sorted(areas, key=lambda a: (get_floor_sort_key(a), a.get("area_order", 0)))
        
        # Group areas by floor
        floors_data = {}
        for area in sorted_areas:
            floor = area.get("floor", "Floor 1")
            if floor not in floors_data:
                floors_data[floor] = []
            floors_data[floor].append(area)
        
        # Calculate summary statistics
        total_areas = len(sorted_areas)
        no_issues_count = sum(1 for a in sorted_areas if a.get("inspection_status") == "no_issues")
        issue_as_is_count = sum(1 for a in sorted_areas if a.get("inspection_status") == "issue_noted_as_is")
        landlord_fix_count = sum(1 for a in sorted_areas if a.get("inspection_status") == "issue_landlord_to_fix")
        completed_count = no_issues_count + issue_as_is_count + landlord_fix_count
        progress_percent = (completed_count / total_areas * 100) if total_areas > 0 else 0
        
        # Download photos and build floor sections
        photo_files = {}  # Map of photo_id -> bytes
        floor_sections = []
        
        # Process each floor in order
        for floor_name in FLOOR_ORDER:
            if floor_name not in floors_data:
                continue
            
            floor_areas = floors_data[floor_name]
            area_rows = []
            
            for area in floor_areas:
                area_name = self._escape_latex(area.get("area_name", ""))
                inspection_status = area.get("inspection_status", "no_issues")
                area_notes = area.get("notes", "") or ""
                
                # Determine status color and label
                # Colors: red, investflow blue, yellowish orange, black gray (no green)
                if inspection_status == "no_issues":
                    status_color = "brandblue"
                    status_label = "No Issues"
                elif inspection_status == "issue_noted_as_is":
                    status_color = "statusorange"
                    status_label = "Issue (As-Is)"
                else:  # issue_landlord_to_fix
                    status_color = "statusred"
                    status_label = "Needs Repair"
                
                # Process photos
                photos_latex = ""
                if area.get("photos"):
                    try:
                        photos = json.loads(area["photos"]) if isinstance(area["photos"], str) else area["photos"]
                        if photos:
                            photo_list = []
                            for idx, photo_data in enumerate(photos[:3]):  # Limit to 3 photos per area
                                photo_id = photo_data.get("document_id") or photo_data.get("photo_blob_name", "")
                                if not photo_id:
                                    continue
                                try:
                                    photo_url = None
                                    if photo_data.get("document_id"):
                                        photo_url = document_service.get_document_download_url(
                                            UUID(photo_data["document_id"]),
                                            UUID(user_id)
                                        )
                                    elif photo_data.get("photo_blob_name"):
                                        photo_url = adls_service.get_blob_download_url(photo_data["photo_blob_name"])
                                    
                                    if photo_url:
                                        response = requests.get(photo_url, timeout=10)
                                        if response.status_code == 200:
                                            # Fix image orientation for LaTeX (LaTeX ignores EXIF tags)
                                            # Use PIL to physically rotate pixels to match EXIF orientation
                                            try:
                                                from PIL import Image, ImageOps
                                                from io import BytesIO
                                                
                                                # Open image from downloaded bytes
                                                img = Image.open(BytesIO(response.content))
                                                # Apply EXIF transpose to physically rotate pixels
                                                corrected_img = ImageOps.exif_transpose(img)
                                                
                                                # Save corrected image to bytes
                                                output = BytesIO()
                                                corrected_img.save(output, format='JPEG', quality=95)
                                                corrected_bytes = output.getvalue()
                                            except Exception as e:
                                                # If PIL fails, use original bytes
                                                logger = self._get_logger()
                                                logger.warning(f"Could not fix image orientation for photo {photo_id}: {e}, using original")
                                                corrected_bytes = response.content
                                            
                                            photo_filename = f"photo_{area.get('area_order', 0)}_{idx}.jpg"
                                            photo_files[photo_filename] = corrected_bytes
                                            photo_list.append(photo_filename)
                                except Exception as e:
                                    logger = self._get_logger()
                                    logger.warning(f"Could not download photo {photo_id}: {e}")
                                    continue
                            
                            # Layout photos - if photos exist, show them centered
                            # Use only width to preserve actual image orientation (portrait/landscape)
                            if photo_list:
                                photos_latex = "\\\\[6pt]"
                                for photo_file in photo_list:
                                    photos_latex += f"\\includegraphics[width=0.28\\linewidth,keepaspectratio]{{{photo_file}}} \\hspace{{4pt}}"
                    except Exception as e:
                        logger = self._get_logger()
                        logger.warning(f"Error processing photos for area {area_name}: {e}")
                
                # Build notes text (single notes field)
                notes_text = self._escape_latex(area_notes) if area_notes else ""
                
                # Build area row - using card style
                if notes_text or photos_latex:
                    # Area with notes/photos - show full card
                    area_card = f"""\\begin{{tcolorbox}}[
    colback=white,
    colframe=bordergray,
    boxrule=0.5pt,
    arc=4pt,
    left=10pt,
    right=10pt,
    top=8pt,
    bottom=8pt
]
\\statuscircle{{{status_color}}}\\hspace{{8pt}}\\textbf{{{floor_name} - {area_name}}}\\hfill\\textcolor{{{status_color}}}{{\\small {status_label}}}\\\\[4pt]
\\textit{{{notes_text}}}{photos_latex}
\\end{{tcolorbox}}
\\vspace{{4pt}}
"""
                else:
                    # Area without notes - compact row
                    area_card = f"""\\begin{{tcolorbox}}[
    colback=white,
    colframe=bordergray,
    boxrule=0.5pt,
    arc=4pt,
    left=10pt,
    right=10pt,
    top=6pt,
    bottom=6pt
]
\\statuscircle{{{status_color}}}\\hspace{{8pt}}\\textbf{{{floor_name} - {area_name}}}\\hfill\\textcolor{{{status_color}}}{{\\small {status_label}}}
\\end{{tcolorbox}}
\\vspace{{4pt}}
"""
                area_rows.append(area_card)
            
            # Build floor section
            if area_rows:
                floor_section = f"""
% {floor_name} Section
\\noindent\\textbf{{\\large {self._escape_latex(floor_name)}}}\\\\[8pt]
{"".join(area_rows)}
\\vspace{{8pt}}
"""
                floor_sections.append(floor_section)
        
        # Build floor sections string
        newline = "\n"
        floor_sections_str = newline.join(floor_sections) if floor_sections else "\\textit{No areas to display.}"
        
        latex = f"""\\documentclass[11pt,letterpaper]{{article}}
\\usepackage[margin=0.6in]{{geometry}}
\\usepackage{{fancyhdr}}
\\usepackage{{tabularx}}
\\usepackage{{colortbl}}
\\usepackage{{lastpage}}
\\usepackage{{xcolor}}
\\usepackage{{graphicx}}
\\usepackage{{tikz}}
\\usepackage{{tcolorbox}}
\\usepackage{{enumitem}}
\\usepackage[scaled=0.92]{{helvet}}
\\renewcommand{{\\familydefault}}{{\\sfdefault}}

% Clean formatting
\\setlength{{\\parindent}}{{0pt}}
\\setlength{{\\parskip}}{{4pt}}

% Define colors - only red, investflow blue, yellowish orange, black gray (no green)
\\definecolor{{brandblue}}{{RGB}}{{37, 99, 235}}
\\definecolor{{statusorange}}{{RGB}}{{255, 140, 0}}
\\definecolor{{statusred}}{{RGB}}{{220, 53, 69}}
\\definecolor{{lightgray}}{{RGB}}{{245, 247, 250}}
\\definecolor{{headergray}}{{RGB}}{{240, 242, 245}}
\\definecolor{{bordergray}}{{RGB}}{{200, 205, 212}}
\\definecolor{{textgray}}{{RGB}}{{100, 110, 120}}

% Status indicator circle command (outline only)
\\newcommand{{\\statuscircle}}[1]{{\\tikz\\draw[draw=#1, line width=1.5pt, fill=none] (0,0) circle (4pt);}}

% Header/Footer
\\pagestyle{{fancy}}
\\fancyhf{{}}
\\renewcommand{{\\headrulewidth}}{{0pt}}
\\setlength{{\\headheight}}{{0.5in}}
\\setlength{{\\headsep}}{{0.1in}}
\\lhead{{\\raisebox{{-0.05in}}{{\\includegraphics[height=0.4in]{{n_logo.jpeg}}}}}}
\\rhead{{\\small\\textcolor{{textgray}}{{Inspection Report: {property_address_full_escaped}}}}}
\\cfoot{{\\small\\textcolor{{textgray}}{{Page \\thepage\\ of \\pageref{{LastPage}}}}}}

\\begin{{document}}

% Blue line below header (like leases)
\\vspace{{-0.6cm}}
\\noindent{{\\color{{brandblue}}\\rule{{\\textwidth}}{{2pt}}}}
\\vspace{{-.5cm}}

% Title
\\begin{{center}}
{{\\LARGE\\bfseries PROPERTY INSPECTION REPORT}}\\\\[1pt]
{{\\large\\textcolor{{textgray}}{{{self._escape_latex(type_display)}}}}}
\\end{{center}}

\\vspace{{0.1cm}}

% Info table with gray headers and white cells, left aligned, with gray border
\\noindent
\\begin{{tcolorbox}}[
    colback=white,
    colframe=bordergray,
    boxrule=1pt,
    arc=4pt,
    left=4pt,
    right=4pt,
    top=0pt,
    bottom=8pt
]
\\begin{{tabular}}{{@{{}}p{{4.2cm}}p{{2.5cm}}p{{6.7cm}}p{{3.5cm}}@{{}}}}
\\rowcolor{{headergray}}
\\textbf{{Property}} & \\textbf{{Date}} & \\textbf{{Inspector}} & \\textbf{{Tenant}} \\\\[4pt]
\\rowcolor{{white}}
{property_address_full_escaped} & {self._escape_latex(walkthrough_date_str)} & {inspector_name_escaped} & {tenant_name_escaped} \\\\
\\end{{tabular}}
\\end{{tcolorbox}}

\\vspace{{0.5cm}}

% Summary Cards (3 cards)
\\noindent
\\begin{{minipage}}[t]{{0.32\\textwidth}}
\\begin{{tcolorbox}}[
    colback=white,
    colframe=bordergray,
    boxrule=0.5pt,
    arc=4pt,
    left=10pt,
    right=10pt,
    top=12pt,
    bottom=12pt
]
\\begin{{center}}
\\statuscircle{{brandblue}}\\\\[6pt]
{{\\Huge\\bfseries {no_issues_count}}}\\\\[6pt]
\\textcolor{{textgray}}{{\\small No Issues}}
\\end{{center}}
\\end{{tcolorbox}}
\\end{{minipage}}
\\hfill
\\begin{{minipage}}[t]{{0.32\\textwidth}}
\\begin{{tcolorbox}}[
    colback=white,
    colframe=bordergray,
    boxrule=0.5pt,
    arc=4pt,
    left=10pt,
    right=10pt,
    top=12pt,
    bottom=12pt
]
\\begin{{center}}
\\statuscircle{{statusorange}}\\\\[6pt]
{{\\Huge\\bfseries {issue_as_is_count}}}\\\\[6pt]
\\textcolor{{textgray}}{{\\small Issue (As-Is)}}
\\end{{center}}
\\end{{tcolorbox}}
\\end{{minipage}}
\\hfill
\\begin{{minipage}}[t]{{0.32\\textwidth}}
\\begin{{tcolorbox}}[
    colback=white,
    colframe=bordergray,
    boxrule=0.5pt,
    arc=4pt,
    left=10pt,
    right=10pt,
    top=12pt,
    bottom=12pt
]
\\begin{{center}}
\\statuscircle{{statusred}}\\\\[6pt]
{{\\Huge\\bfseries {landlord_fix_count}}}\\\\[6pt]
\\textcolor{{textgray}}{{\\small Landlord to Fix}}
\\end{{center}}
\\end{{tcolorbox}}
\\end{{minipage}}

\\vspace{{0.5cm}}

% Area Sections by Floor
{floor_sections_str}

% General Notes Section
{self._get_general_notes_section(notes_escaped) if notes_escaped else ""}

\\vspace{{0.6cm}}

% Signatures
\\noindent
\\begin{{minipage}}[t]{{0.48\\textwidth}}
\\textbf{{Landlord/Inspector Signature}}\\\\[1.2cm]
\\rule{{\\linewidth}}{{0.4pt}}\\\\[0.4cm]
\\small Date: \\rule{{2.5cm}}{{0.4pt}}
\\end{{minipage}}
\\hfill
\\begin{{minipage}}[t]{{0.48\\textwidth}}
\\textbf{{Tenant Signature}}\\\\[1.2cm]
\\rule{{\\linewidth}}{{0.4pt}}\\\\[0.4cm]
\\small Date: \\rule{{2.5cm}}{{0.4pt}}
\\end{{minipage}}

\\end{{document}}
"""
        
        return latex, photo_files
    
    def _get_logger(self):
        """Get logger instance"""
        from app.core.logging import get_logger
        return get_logger(__name__)
    
    def _get_general_notes_section(self, notes_escaped: str) -> str:
        """Get general notes section for LaTeX (notes should already be escaped)"""
        if notes_escaped:
            return f"""
\\vspace{{0.4cm}}
\\noindent\\textbf{{General Notes:}}\\\\[4pt]
{notes_escaped}
"""
        return ""
    
    def _parse_date(self, date_value) -> Optional[datetime]:
        """Parse date value to datetime"""
        from datetime import date as date_type
        
        if date_value is None:
            return None
        
        # Handle datetime objects
        if isinstance(date_value, datetime):
            return date_value
        
        # Handle date objects (not datetime)
        if isinstance(date_value, date_type):
            return datetime.combine(date_value, datetime.min.time())
        
        # Handle pandas Timestamp
        if isinstance(date_value, pd.Timestamp):
            return date_value.to_pydatetime()
        
        # Handle string representations
        if isinstance(date_value, str):
            # Try common date formats
            date_formats = [
                "%Y-%m-%d",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%m/%d/%Y",
                "%d/%m/%Y",
            ]
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_value, fmt)
                except:
                    continue
            
            # Try ISO format
            try:
                return datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            except:
                pass
        
        # If it's a number (timestamp), try to convert
        if isinstance(date_value, (int, float)):
            try:
                return datetime.fromtimestamp(date_value)
            except:
                pass
        
        return None
    
    def _escape_latex(self, text: str) -> str:
        """Escape special LaTeX characters in text"""
        if not text:
            return ""
        
        text = str(text)
        # Replace special characters
        replacements = {
            '\\': '\\textbackslash{}',
            '{': '\\{',
            '}': '\\}',
            '$': '\\$',
            '&': '\\&',
            '%': '\\%',
            '#': '\\#',
            '^': '\\textasciicircum{}',
            '_': '\\_',
            '~': '\\textasciitilde{}',
        }
        
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
        
        return text
    
    def _compile_pdf(self, latex_content: str, photo_files: Dict[str, bytes] = None) -> bytes:
        """Compile LaTeX content to PDF bytes with photos"""
        import shutil
        from pathlib import Path
        
        if photo_files is None:
            photo_files = {}
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            tex_file = tmpdir_path / "walkthrough.tex"
            pdf_file = tmpdir_path / "walkthrough.pdf"
            
            # Copy logo to temp directory for LaTeX to find
            logo_src = Path(__file__).parent.parent / "assets" / "n_logo.jpeg"
            if logo_src.exists():
                shutil.copy(logo_src, tmpdir_path / "n_logo.jpeg")
            
            # Save photos to temp directory
            for photo_filename, photo_bytes in photo_files.items():
                photo_path = tmpdir_path / photo_filename
                with open(photo_path, 'wb') as f:
                    f.write(photo_bytes)
            
            # Write LaTeX to file
            tex_file.write_text(latex_content, encoding='utf-8')
            
            # Compile LaTeX to PDF (run twice for proper references)
            try:
                for _ in range(2):
                    result = subprocess.run(
                        ['pdflatex', '-interaction=nonstopmode', '-output-directory', str(tmpdir_path), str(tex_file)],
                        capture_output=True,
                        text=True,
                        timeout=60  # Increased timeout for photo processing
                    )
                    
                    if result.returncode != 0:
                        # Capture both stdout and stderr for better error messages
                        error_output = result.stderr if result.stderr else result.stdout
                        # Also check the log file if it exists
                        log_file = tmpdir_path / f"{tex_file.stem}.log"
                        log_content = ""
                        if log_file.exists():
                            try:
                                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                                    log_content = f.read()
                                    # Extract error lines from log (lines with !)
                                    error_lines = [line for line in log_content.split('\n') if '!' in line or 'Error' in line or 'Fatal' in line]
                                    if error_lines:
                                        error_output += "\n\nLaTeX Log Errors:\n" + "\n".join(error_lines[-10:])  # Last 10 error lines
                            except Exception:
                                pass
                        
                        raise Exception(f"LaTeX compilation failed (return code {result.returncode}):\n{error_output}")
                
                # Read PDF
                if pdf_file.exists():
                    with open(pdf_file, 'rb') as f:
                        pdf_bytes = f.read()
                    return pdf_bytes
                else:
                    raise Exception("PDF file was not generated")
                
            except subprocess.TimeoutExpired:
                raise Exception("LaTeX compilation timed out")
            except FileNotFoundError:
                raise Exception("pdflatex not found. Please install LaTeX.")
            except Exception as e:
                raise Exception(f"Error compiling PDF: {str(e)}")
    
    def _save_latex_to_adls(
        self,
        latex_content: str,
        walkthrough_data: Dict[str, Any],
        property_data: Dict[str, Any],
        user_id: str
    ) -> str:
        """Save LaTeX source to ADLS"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        property_address = property_data.get("address", "unknown").replace(" ", "_").replace("/", "_")
        filename = f"walkthrough_{property_address}_{timestamp}.tex"
        
        blob_name = f"{self.temp_folder}/{user_id}/{walkthrough_data['id']}/{filename}"
        blob_client = self.adls.blob_service_client.get_blob_client(
            container=self.adls.container_name,
            blob=blob_name
        )
        
        from azure.storage.blob import ContentSettings
        blob_client.upload_blob(
            latex_content.encode('utf-8'),
            overwrite=True,
            content_settings=ContentSettings(content_type="text/plain"),
            metadata={
                "user_id": user_id,
                "walkthrough_id": walkthrough_data['id'],
                "property_id": walkthrough_data.get('property_id', ''),
                "generated_at": datetime.utcnow().isoformat(),
                "document_type": "walkthrough_latex"
            }
        )
        
        return blob_name
    
    def _save_pdf_to_adls(
        self,
        pdf_bytes: bytes,
        walkthrough_data: Dict[str, Any],
        property_data: Dict[str, Any],
        user_id: str
    ) -> str:
        """Save PDF to ADLS"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        property_address = property_data.get("address", "unknown").replace(" ", "_").replace("/", "_")
        filename = f"walkthrough_{property_address}_{timestamp}.pdf"
        
        blob_name = f"{self.final_folder}/{user_id}/{walkthrough_data['id']}/{filename}"
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
                "walkthrough_id": walkthrough_data['id'],
                "property_id": walkthrough_data.get('property_id', ''),
                "generated_at": datetime.utcnow().isoformat(),
                "document_type": "walkthrough_pdf"
            }
        )
        
        return blob_name
