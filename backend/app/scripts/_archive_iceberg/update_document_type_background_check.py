#!/usr/bin/env python3
"""
Update document_type to "background_check" for tenant documents

This script:
1. Finds the tenant by name
2. Gets their property_id
3. Finds all documents for that tenant on that property with document_type = "other"
4. Updates them to document_type = "background_check"
"""

import sys
from pathlib import Path

# Add parent directory to path to import app modules
script_dir = Path(__file__).parent
backend_dir = script_dir.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.iceberg import get_catalog, read_table, load_table
from app.services.document_service import document_service
from pyiceberg.expressions import EqualTo, And
import uuid

NAMESPACE = ("investflow",)
PROPERTIES_TABLE = "properties"
TENANTS_TABLE = "tenants"
VAULT_TABLE = "vault"

def main():
    print("=" * 80)
    print("Update document_type to 'background_check' for tenant documents")
    print("=" * 80)
    print()
    
    # Configuration - list of tenants to update
    TENANTS_TO_UPDATE = [
        {"first_name": "Matthew", "last_name": "Bausch", "property_search": None},  # Will search all properties
        {"first_name": "Brandena", "last_name": None, "property_search": None},  # Will search all properties
        {"first_name": "Megan", "last_name": "Hunter", "property_search": None},  # Will search all properties
    ]
    
    # Load data once
    print("Loading tenant and property data...")
    tenants_df = read_table(NAMESPACE, TENANTS_TABLE)
    properties_df = read_table(NAMESPACE, PROPERTIES_TABLE)
    vault_table = load_table(NAMESPACE, VAULT_TABLE)
    print()
    
    total_updated = 0
    total_processed = 0
    
    # Process each tenant
    for tenant_config in TENANTS_TO_UPDATE:
        first_name = tenant_config["first_name"]
        last_name = tenant_config.get("last_name")
        property_search = tenant_config.get("property_search")
        
        print("=" * 80)
        print(f"Processing: {first_name} {last_name or ''}".strip())
        print("=" * 80)
        print()
        
        # Step 1: Find the tenant
        print(f"Step 1: Finding tenant '{first_name} {last_name or ''}'...".strip())
        
        # Build search criteria
        if last_name:
            tenant_matches = tenants_df[
                (tenants_df['first_name'].str.contains(first_name, case=False, na=False)) &
                (tenants_df['last_name'].str.contains(last_name, case=False, na=False))
            ]
        else:
            tenant_matches = tenants_df[
                tenants_df['first_name'].str.contains(first_name, case=False, na=False)
            ]
        
        if len(tenant_matches) == 0:
            print(f"❌ Tenant '{first_name} {last_name or ''}' not found!".strip())
            print()
            continue
        
        # Process each matching tenant
        for idx, tenant_match in tenant_matches.iterrows():
            tenant_id = tenant_match['id']
            property_id = tenant_match['property_id']
            tenant_name = f"{tenant_match.get('first_name', '')} {tenant_match.get('last_name', '')}"
            
            # Get property name
            prop = properties_df[properties_df['id'] == property_id]
            property_name = prop.iloc[0].get('display_name') or prop.iloc[0].get('address_line1', 'Unknown') if len(prop) > 0 else 'Unknown'
            
            print(f"✅ Found tenant: {tenant_name} (ID: {tenant_id})")
            print(f"✅ On property: {property_name} (ID: {property_id})")
            print()
            
            # Step 2: Find all background check related documents for this tenant
            print("Step 2: Finding background check documents...")
            
            # Find all documents for this tenant on this property
            scan_all = vault_table.scan(
                row_filter=And(
                    EqualTo("property_id", str(property_id)),
                    EqualTo("tenant_id", str(tenant_id))
                )
            )
            arrow_table_all = scan_all.to_arrow()
            all_tenant_docs = arrow_table_all.to_pylist()
            
            # Filter to background check related documents
            # These include: eviction_report, criminal_check, income_insights, identity_report, credit_report, and "other"
            background_check_types = [
                "eviction_report",
                "criminal_check", 
                "income_insights",
                "identity_report",
                "credit_report",
                "other"
            ]
            
            documents = []
            for doc in all_tenant_docs:
                doc_type = doc.get('document_type', 'other')
                file_name = doc.get('display_name', '') or doc.get('file_name', '')
                
                # Include if it's one of the background check types OR if it's a TransUnion/SmartMove document
                if doc_type in background_check_types:
                    documents.append(doc)
                elif 'TransUnion' in file_name or 'SmartMove' in file_name:
                    documents.append(doc)
            
            print(f"✅ Found {len(documents)} background check documents to update")
            print()
            
            if len(documents) == 0:
                print("No background check documents found to update.")
                print()
                continue
            
            # Display documents to be updated
            print("Documents to update:")
            for i, doc in enumerate(documents, 1):
                display_name = doc.get('display_name') or doc.get('file_name', 'Unknown')
                print(f"  {i}. {display_name} (ID: {doc['id']}, type: {doc.get('document_type', 'unknown')})")
            print()
            
            # Step 3: Update each document
            print("Step 3: Updating documents...")
            updated_count = 0
            
            for doc in documents:
                doc_id = uuid.UUID(doc['id'])
                user_id = uuid.UUID(doc['user_id'])
                
                try:
                    # Use document_service.update_document to update the document_type
                    updated = document_service.update_document(
                        document_id=doc_id,
                        property_id=uuid.UUID(property_id),
                        user_id=user_id,
                        document_type="background_check"
                    )
                    
                    if updated:
                        updated_count += 1
                        display_name = doc.get('display_name') or doc.get('file_name', 'Unknown')
                        print(f"  ✅ Updated: {display_name}")
                    else:
                        print(f"  ❌ Failed to update: {doc.get('display_name') or doc.get('file_name', 'Unknown')}")
                except Exception as e:
                    print(f"  ❌ Error updating {doc.get('display_name') or doc.get('file_name', 'Unknown')}: {e}")
            
            total_updated += updated_count
            total_processed += len(documents)
            
            print()
            print(f"✅ Successfully updated {updated_count} out of {len(documents)} documents for {tenant_name}")
            print()
    
    print("=" * 80)
    print(f"✅ SUMMARY: Successfully updated {total_updated} out of {total_processed} documents across all tenants")
    print("=" * 80)

if __name__ == "__main__":
    main()
