#!/usr/bin/env python3
"""
Validate that all fields saved in create_lease are properly used in the lease PDF generation.
"""
from app.core.iceberg import read_table
from app.services.lease_generator_service import LeaseGeneratorService
import inspect
import re

# Read the most recent lease
leases_df = read_table(('investflow',), 'leases_full')
leases_df = leases_df.sort_values('created_at', ascending=False)
latest_lease = leases_df.iloc[0]

print("=" * 80)
print("LEASE FIELD VALIDATION")
print("=" * 80)
print(f"\nLease ID: {latest_lease.get('id')}")
print(f"Created: {latest_lease.get('created_at')}")
print(f"State: {latest_lease.get('state')}")

# Get all fields from the lease
lease_fields = set(latest_lease.index)

# Read the lease generator service to find what fields it uses
generator_code = inspect.getsource(LeaseGeneratorService._build_latex_document)

# Extract all lease_data.get() calls
used_fields = set()
pattern = r'lease_data\.get\(["\']([^"\']+)["\']'
matches = re.findall(pattern, generator_code)
used_fields.update(matches)

# Also check for direct access patterns
pattern2 = r'lease_data\[["\']([^"\']+)["\']'
matches2 = re.findall(pattern2, generator_code)
used_fields.update(matches2)

print(f"\n=== FIELD ANALYSIS ===")
print(f"Total fields in lease: {len(lease_fields)}")
print(f"Fields used in PDF generator: {len(used_fields)}")

# Fields saved but not used
saved_not_used = lease_fields - used_fields - {'id', 'user_id', 'property_id', 'unit_id', 
                                                'lease_number', 'lease_version', 'created_at', 
                                                'updated_at', 'is_active', 'generated_pdf_document_id',
                                                'template_used', 'status'}

# Fields used but might not be saved
used_not_saved = used_fields - lease_fields

print(f"\n=== FIELDS SAVED BUT NOT USED IN PDF ({len(saved_not_used)}) ===")
for field in sorted(saved_not_used):
    val = latest_lease.get(field)
    if val is not None:
        print(f"  {field}: {val}")

print(f"\n=== FIELDS USED IN PDF BUT NOT IN LEASE ({len(used_not_saved)}) ===")
for field in sorted(used_not_saved):
    print(f"  {field}")

print(f"\n=== FIELDS USED IN PDF ({len(used_fields)}) ===")
for field in sorted(used_fields):
    val = latest_lease.get(field)
    status = "✓" if field in lease_fields else "✗"
    print(f"  {status} {field}: {val}")

print("\n" + "=" * 80)

