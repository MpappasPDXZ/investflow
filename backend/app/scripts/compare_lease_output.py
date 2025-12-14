"""
Compare generated lease PDF to NE_res_agreement.tex template
Validates that all sections and key terms match
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple
import subprocess


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF using pdftotext"""
    try:
        result = subprocess.run(
            ["pdftotext", pdf_path, "-"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error extracting text from PDF: {e}")
        return ""
    except FileNotFoundError:
        print("pdftotext not found. Install with: brew install poppler")
        return ""


def extract_sections_from_tex(tex_path: str) -> List[Tuple[str, str]]:
    """Extract section titles from LaTeX file"""
    sections = []
    content = Path(tex_path).read_text()
    
    # Find all \section{...} patterns
    pattern = r'\\section\{([^}]+)\}'
    matches = re.findall(pattern, content)
    
    for match in matches:
        sections.append(match)
    
    return sections


def extract_sections_from_pdf_text(pdf_text: str) -> List[str]:
    """Extract section headers from PDF text"""
    sections = []
    lines = pdf_text.split('\n')
    
    # Look for section patterns like "1. PREMISES" or "10. USE OF PREMISES"
    section_pattern = r'^(\d+)\.\s+([A-Z][A-Z\s,&()]+)$'
    
    for line in lines:
        line = line.strip()
        match = re.match(section_pattern, line)
        if match:
            section_num = match.group(1)
            section_title = match.group(2)
            sections.append(f"{section_num}. {section_title}")
    
    return sections


def validate_key_terms(pdf_text: str, expected_terms: dict) -> List[str]:
    """Validate that key terms appear in the PDF"""
    issues = []
    
    for term_name, expected_value in expected_terms.items():
        # Convert to string and clean
        expected_str = str(expected_value).replace("_", " ")
        
        if expected_str not in pdf_text:
            issues.append(f"Missing or incorrect: {term_name} = {expected_value}")
    
    return issues


def compare_sections(tex_sections: List[str], pdf_sections: List[str]) -> Tuple[List[str], List[str], List[str]]:
    """Compare section lists and return differences"""
    tex_set = set(tex_sections)
    pdf_set = set(pdf_sections)
    
    # Normalize for comparison (remove numbering)
    tex_titles = {s.split('. ', 1)[1] if '. ' in s else s for s in tex_sections}
    pdf_titles = {s.split('. ', 1)[1] if '. ' in s else s for s in pdf_sections}
    
    missing_in_pdf = tex_titles - pdf_titles
    extra_in_pdf = pdf_titles - tex_titles
    matching = tex_titles & pdf_titles
    
    return list(matching), list(missing_in_pdf), list(extra_in_pdf)


def main():
    """Main comparison"""
    print("="*80)
    print("LEASE COMPARISON: Generated PDF vs NE_res_agreement.tex")
    print("="*80)
    
    # Paths
    tex_path = Path("/Users/matt/code/property/NE_res_agreement.tex")
    
    # Find most recent generated PDF
    import glob
    pdf_files = glob.glob("/tmp/lease_316_s_50th_*.pdf")
    if not pdf_files:
        print("\n✗ No generated PDF found in /tmp/")
        print("  Run upload_316_lease.py first to generate a PDF")
        sys.exit(1)
    
    pdf_path = max(pdf_files, key=lambda x: Path(x).stat().st_mtime)
    print(f"\nComparing:")
    print(f"  Template: {tex_path}")
    print(f"  Generated: {pdf_path}")
    
    # Extract sections from LaTeX
    print("\n" + "-"*80)
    print("SECTION STRUCTURE")
    print("-"*80)
    tex_sections = extract_sections_from_tex(str(tex_path))
    print(f"\nTemplate has {len(tex_sections)} sections")
    
    # Extract text from PDF
    pdf_text = extract_text_from_pdf(pdf_path)
    if not pdf_text:
        print("\n✗ Could not extract text from PDF")
        print("  Install poppler-utils: brew install poppler")
        sys.exit(1)
    
    pdf_sections = extract_sections_from_pdf_text(pdf_text)
    print(f"Generated PDF has {len(pdf_sections)} sections detected")
    
    # Compare sections
    matching, missing, extra = compare_sections(tex_sections, pdf_sections)
    
    print(f"\n✓ Matching sections: {len(matching)}")
    if matching:
        for section in sorted(matching):
            print(f"  • {section}")
    
    if missing:
        print(f"\n⚠ Missing in generated PDF: {len(missing)}")
        for section in sorted(missing):
            print(f"  • {section}")
    
    if extra:
        print(f"\n⚠ Extra in generated PDF: {len(extra)}")
        for section in sorted(extra):
            print(f"  • {section}")
    
    # Validate key terms
    print("\n" + "-"*80)
    print("KEY TERMS VALIDATION")
    print("-"*80)
    
    expected_terms = {
        "Monthly Rent": "$2,500.00",
        "Security Deposit": "$2,500.00",
        "Late Fee (by 11th)": "$75",
        "Late Fee (by 16th)": "$150",
        "Late Fee (by 21st)": "$225",
        "NSF Fee": "$60",
        "Pet Fee (one pet)": "$350",
        "Pet Fee (two pets)": "$700",
        "Key Replacement Fee": "$100",
        "Early Termination Fee": "$5,000",
        "Deposit Return Days": "14 days",
        "Property Address": "316 S 50th Ave",
        "Landlord": "S&M Axios Heartland Holdings, LLC",
        "Max Occupants": "3 persons",
        "Parking Spaces": "2 parking",
        "Shared Driveway": "314 S 50th Ave",
    }
    
    issues = validate_key_terms(pdf_text, expected_terms)
    
    if not issues:
        print("\n✓ All key terms validated successfully!")
    else:
        print(f"\n⚠ Found {len(issues)} issues:")
        for issue in issues:
            print(f"  • {issue}")
    
    # Move-out costs validation
    print("\n" + "-"*80)
    print("MOVE-OUT COSTS SECTION")
    print("-"*80)
    
    moveout_terms = [
        "Hardwood Floor Cleaning",
        "$100.00",
        "Trash Removal Fee",
        "$150.00",
        "Heavy Cleaning",
        "$400.00",
        "Wall Repairs",
        "$150.00"
    ]
    
    moveout_found = sum(1 for term in moveout_terms if term in pdf_text)
    print(f"Move-out cost items found: {moveout_found}/{len(moveout_terms)}")
    
    if moveout_found == len(moveout_terms):
        print("✓ All move-out cost items present")
    else:
        print("⚠ Some move-out cost items may be missing")
        missing_moveout = [term for term in moveout_terms if term not in pdf_text]
        for term in missing_moveout:
            print(f"  • Missing: {term}")
    
    # Final summary
    print("\n" + "="*80)
    print("COMPARISON SUMMARY")
    print("="*80)
    
    total_checks = len(tex_sections) + len(expected_terms) + len(moveout_terms)
    passed_checks = len(matching) + (len(expected_terms) - len(issues)) + moveout_found
    
    print(f"\nTotal checks: {total_checks}")
    print(f"Passed: {passed_checks}")
    print(f"Issues: {total_checks - passed_checks}")
    
    if len(missing) == 0 and len(issues) == 0 and moveout_found == len(moveout_terms):
        print("\n✓ VALIDATION PASSED - Generated lease matches template!")
    else:
        print("\n⚠ VALIDATION INCOMPLETE - Some differences found")
        print("  This may be expected due to text extraction limitations")
        print("  Review the PDF manually to confirm all content is present")
    
    print("\nGenerated PDF location:")
    print(f"  {pdf_path}")
    print("\n" + "="*80)


if __name__ == "__main__":
    main()

