"""
Upload lease data for 316 S 50th Ave and generate PDF
"""
import sys
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import pandas as pd
import pyarrow as pa

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.core.config import settings
from app.core.iceberg import get_catalog
from app.services.lease_defaults import apply_lease_defaults, get_default_moveout_costs_json
from app.services.lease_generator_service import LeaseGeneratorService
from app.scripts.create_data import create_leases_schema, create_lease_tenants_schema


def create_lease_tables():
    """Create lease and lease_tenants tables if they don't exist"""
    catalog = get_catalog()
    namespace = "investflow"
    
    # Create leases table
    try:
        catalog.load_table(f"{namespace}.leases")
        print("✓ leases table already exists")
    except Exception:
        print("Creating leases table...")
        schema = create_leases_schema()
        catalog.create_table(
            identifier=f"{namespace}.leases",
            schema=schema
        )
        print("✓ leases table created")
    
    # Create lease_tenants table
    try:
        catalog.load_table(f"{namespace}.lease_tenants")
        print("✓ lease_tenants table already exists")
    except Exception:
        print("Creating lease_tenants table...")
        schema = create_lease_tenants_schema()
        catalog.create_table(
            identifier=f"{namespace}.lease_tenants",
            schema=schema
        )
        print("✓ lease_tenants table created")


def get_316_property_data(catalog):
    """Get property data for 316 S 50th Ave"""
    try:
        properties_table = catalog.load_table("investflow.properties")
        properties_df = properties_table.scan().to_pandas()
        
        # Find 316 S 50th Ave
        property_row = properties_df[
            (properties_df["address"].str.contains("316", na=False)) & 
            (properties_df["address"].str.contains("50th", na=False))
        ]
        
        if len(property_row) == 0:
            print("Property 316 S 50th Ave not found. Creating mock property data...")
            # Return mock data matching NE_res_agreement.tex
            return {
                "id": str(uuid.uuid4()),
                "address": "316 S 50th Ave",
                "city": "Omaha",
                "state": "NE",
                "zip_code": "68132",
                "description": "3-bedroom, 2-bath townhouse (approx. 1,500 sq. ft.) with basement and attic",
                "year_built": 1929,
                "bedrooms": 3,
                "bathrooms": 2
            }
        
        property_data = property_row.iloc[0].to_dict()
        print(f"✓ Found property: {property_data.get('address')}")
        return property_data
        
    except Exception as e:
        print(f"Error loading property data: {e}")
        print("Using mock property data...")
        return {
            "id": str(uuid.uuid4()),
            "address": "316 S 50th Ave",
            "city": "Omaha",
            "state": "NE",
            "zip_code": "68132",
            "description": "3-bedroom, 2-bath townhouse (approx. 1,500 sq. ft.) with basement and attic",
            "year_built": 1929,
            "bedrooms": 3,
            "bathrooms": 2
        }


def create_316_lease_data(property_id: str) -> dict:
    """
    Create lease data for 316 S 50th Ave matching NE_res_agreement.tex
    """
    now = datetime.now()
    lease_id = str(uuid.uuid4())
    
    # Base lease data matching the template
    lease_data = {
        "id": lease_id,
        "user_id": "11111111-1111-1111-1111-111111111111",  # Will be replaced with actual user
        "property_id": property_id,
        "unit_id": None,
        "state": "NE",
        "status": "draft",
        "lease_version": 1,
        
        # Dates
        "lease_date": None,  # To be filled in
        "commencement_date": date.today() + timedelta(days=30),  # 30 days from now
        "termination_date": date.today() + timedelta(days=30 + 365),  # 1 year lease
        "auto_convert_month_to_month": False,
        "signed_date": None,
        
        # Financial Terms (from template)
        "monthly_rent": Decimal("2500.00"),
        "rent_due_day": 1,
        "rent_due_by_day": 5,
        "rent_due_by_time": "6pm",
        "payment_method": None,  # To be specified
        "prorated_first_month_rent": None,
        
        # Late Charges (from Section 4 of template)
        "late_fee_day_1_10": Decimal("75.00"),  # By 11th
        "late_fee_day_11": Decimal("150.00"),    # By 16th
        "late_fee_day_16": Decimal("225.00"),    # By 21st
        "late_fee_day_21": Decimal("300.00"),    # After 21st
        
        # NSF (from Section 5)
        "nsf_fee": Decimal("60.00"),
        
        # Security Deposit (from Section 6)
        "security_deposit": Decimal("2500.00"),
        "deposit_return_days": 14,  # Nebraska
        
        # Occupants (from Section 11)
        "max_occupants": 3,
        "max_adults": 2,
        "max_children": True,
        
        # Utilities (from Section 15)
        "utilities_tenant": "Gas, Sewer, Water, and Electricity",
        "utilities_landlord": "Trash",
        
        # Pets (from Section 16)
        "pets_allowed": True,
        "pet_fee_one": Decimal("350.00"),
        "pet_fee_two": Decimal("700.00"),
        "max_pets": 2,
        
        # Parking (from Section 33)
        "parking_spaces": 2,
        "parking_small_vehicles": 2,
        "parking_large_trucks": 1,
        
        # Keys (from Section 34)
        "front_door_keys": 1,
        "back_door_keys": 1,
        "key_replacement_fee": Decimal("100.00"),
        
        # Shared Driveway (from Section 19)
        "has_shared_driveway": True,
        "shared_driveway_with": "314 S 50th Ave",
        "snow_removal_responsibility": "tenant",
        
        # Garage (from Section 38)
        "has_garage": True,
        "garage_outlets_prohibited": True,
        
        # Special Spaces
        "has_attic": True,
        "attic_usage": "Bonus room is for office/gym/playroom, not a separate sleeping unit",
        "has_basement": True,
        
        # Appliances (from Section 38)
        "appliances_provided": "Stainless Steel Fridge, Stove, Dishwasher, Microwave, Washer/Dryer provided",
        
        # Lead Paint (from Section 38)
        "lead_paint_disclosure": True,
        "lead_paint_year_built": 1929,
        
        # Early Termination (from Section 38)
        "early_termination_allowed": True,
        "early_termination_notice_days": 60,
        "early_termination_fee_months": 2,
        "early_termination_fee_amount": Decimal("5000.00"),  # 2 months rent
        
        # Move-Out Costs (from Section 39) - JSON
        "moveout_costs": get_default_moveout_costs_json(),
        
        # Missouri-specific (not applicable for NE)
        "methamphetamine_disclosure": False,
        "owner_name": "S&M Axios Heartland Holdings, LLC",
        "owner_address": "c/o Sarah Pappas, 1606 S 208th St, Elkhorn, NE 68022",
        "manager_name": None,
        "manager_address": None,
        "deposit_account_info": None,
        "moveout_inspection_rights": False,
        "military_termination_days": None,
        
        # Metadata
        "generated_pdf_document_id": None,
        "template_used": "NE_residential_v1",
        "notes": "Generated from NE_res_agreement.tex template for 316 S 50th Ave",
        "created_at": now,
        "updated_at": now,
        "is_active": True,
    }
    
    # Apply state defaults (though we've set most values explicitly)
    lease_data = apply_lease_defaults(lease_data, "NE")
    
    return lease_data


def create_316_tenants(lease_id: str) -> list:
    """Create tenant data (placeholder tenants)"""
    now = datetime.now()
    
    tenants = [
        {
            "id": str(uuid.uuid4()),
            "lease_id": lease_id,
            "tenant_order": 1,
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone": "402-555-1234",
            "signed_date": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(uuid.uuid4()),
            "lease_id": lease_id,
            "tenant_order": 2,
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jane.doe@example.com",
            "phone": "402-555-5678",
            "signed_date": None,
            "created_at": now,
            "updated_at": now,
        }
    ]
    
    return tenants


def upload_lease_to_iceberg(lease_data: dict, tenants: list):
    """Upload lease and tenant data to Iceberg tables"""
    catalog = get_catalog()
    
    # Upload lease
    print("\nUploading lease data...")
    leases_table = catalog.load_table("investflow.leases")
    lease_df = pd.DataFrame([lease_data])
    lease_arrow = pa.Table.from_pandas(lease_df, schema=leases_table.schema().as_arrow())
    leases_table.append(lease_arrow)
    print(f"✓ Lease {lease_data['id']} uploaded")
    
    # Upload tenants
    print("\nUploading tenant data...")
    tenants_table = catalog.load_table("investflow.lease_tenants")
    tenants_df = pd.DataFrame(tenants)
    tenants_arrow = pa.Table.from_pandas(tenants_df, schema=tenants_table.schema().as_arrow())
    tenants_table.append(tenants_arrow)
    print(f"✓ {len(tenants)} tenants uploaded")


def generate_lease_pdf(lease_data: dict, tenants: list, property_data: dict, output_path: str = None):
    """Generate PDF from lease data"""
    print("\n" + "="*60)
    print("GENERATING LEASE PDF")
    print("="*60)
    
    generator = LeaseGeneratorService()
    
    # Generate LaTeX content
    latex_content = generator._build_latex_document(lease_data, tenants, property_data)
    
    # Save LaTeX file first
    tex_output = f"/tmp/lease_316_s_50th_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tex"
    Path(tex_output).write_text(latex_content, encoding='utf-8')
    print(f"\n✓ LaTeX file generated!")
    print(f"  Location: {tex_output}")
    
    try:
        pdf_bytes = generator._compile_pdf(latex_content)
        
        # Save PDF
        if output_path is None:
            output_path = f"/tmp/lease_316_s_50th_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        output_file = Path(output_path)
        output_file.write_bytes(pdf_bytes)
        
        print(f"\n✓ PDF generated successfully!")
        print(f"  Location: {output_file}")
        print(f"  Size: {len(pdf_bytes):,} bytes")
        
        return str(output_file)
        
    except FileNotFoundError as e:
        print(f"\n⚠ PDF compilation skipped: pdflatex not found locally")
        print(f"  LaTeX file saved to: {tex_output}")
        print(f"  To generate PDF, install LaTeX or build in Docker")
        return tex_output
    except Exception as e:
        print(f"\n✗ PDF generation failed: {e}")
        print(f"  LaTeX file saved to: {tex_output}")
        return tex_output


def main():
    """Main execution"""
    print("="*60)
    print("316 S 50TH AVE LEASE UPLOAD SCRIPT")
    print("="*60)
    
    # Step 1: Create tables if needed
    print("\nStep 1: Creating lease tables...")
    create_lease_tables()
    
    # Step 2: Get property data
    print("\nStep 2: Loading property data...")
    catalog = get_catalog()
    property_data = get_316_property_data(catalog)
    print(f"  Address: {property_data.get('address')}")
    print(f"  City: {property_data.get('city')}, {property_data.get('state')}")
    print(f"  Description: {property_data.get('description')}")
    
    # Step 3: Create lease data
    print("\nStep 3: Creating lease data...")
    lease_data = create_316_lease_data(property_data["id"])
    print(f"  Lease ID: {lease_data['id']}")
    print(f"  Monthly Rent: ${lease_data['monthly_rent']}")
    print(f"  Security Deposit: ${lease_data['security_deposit']}")
    print(f"  Term: {lease_data['commencement_date']} to {lease_data['termination_date']}")
    
    # Step 4: Create tenant data
    print("\nStep 4: Creating tenant data...")
    tenants = create_316_tenants(lease_data["id"])
    for tenant in tenants:
        print(f"  Tenant {tenant['tenant_order']}: {tenant['first_name']} {tenant['last_name']}")
    
    # Step 5: Upload to Iceberg
    print("\nStep 5: Uploading to Iceberg...")
    try:
        upload_lease_to_iceberg(lease_data, tenants)
    except Exception as e:
        print(f"Warning: Upload to Iceberg failed: {e}")
        print("Continuing with PDF generation...")
    
    # Step 6: Generate PDF
    print("\nStep 6: Generating PDF...")
    pdf_path = generate_lease_pdf(lease_data, tenants, property_data)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"✓ Lease created for: {property_data['address']}")
    print(f"✓ Lease ID: {lease_data['id']}")
    print(f"✓ Tenants: {len(tenants)}")
    print(f"✓ PDF saved to: {pdf_path}")
    print("\nNext step: Compare generated PDF to NE_res_agreement.tex")
    print("="*60)


if __name__ == "__main__":
    main()

