#!/usr/bin/env python3
"""
Transfer property ownership to a different user
"""
import sys
from pathlib import Path
import pandas as pd
import pyarrow as pa

# Add the backend directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.iceberg import read_table, load_table, table_exists

NAMESPACE = ("investflow",)
PROPERTIES_TABLE = "properties"
USERS_TABLE = "users"

def transfer_property(property_address: str, new_owner_email: str):
    """Transfer property ownership by address"""
    print(f"🏠 Transferring property at '{property_address}' to user '{new_owner_email}'...")
    
    # Get the new owner's user ID
    if not table_exists(NAMESPACE, USERS_TABLE):
        print("❌ Users table does not exist")
        return False
    
    users_df = read_table(NAMESPACE, USERS_TABLE)
    user_rows = users_df[users_df["email"] == new_owner_email]
    
    if len(user_rows) == 0:
        print(f"❌ User with email '{new_owner_email}' not found")
        print(f"Available emails: {users_df['email'].tolist()}")
        return False
    
    new_user_id = str(user_rows.iloc[0]["id"])
    print(f"✅ Found new owner: {new_user_id}")
    
    # Get the property
    if not table_exists(NAMESPACE, PROPERTIES_TABLE):
        print("❌ Properties table does not exist")
        return False
    
    props_df = read_table(NAMESPACE, PROPERTIES_TABLE)
    print(f"📋 Found {len(props_df)} total properties")
    
    # Find property by address (check address_line1)
    prop_mask = props_df["address_line1"].str.contains(property_address, case=False, na=False)
    
    if not prop_mask.any():
        print(f"❌ Property with address containing '{property_address}' not found")
        print(f"Available properties:")
        for idx, row in props_df.iterrows():
            print(f"  - {row['address_line1']}, {row['city']}, {row['state']} {row['zip_code']} (Owner: {row['user_id']})")
        return False
    
    # Update the user_id
    print(f"📝 Updating property ownership...")
    props_df.loc[prop_mask, "user_id"] = new_user_id
    props_df.loc[prop_mask, "updated_at"] = pd.Timestamp.now()
    
    # Convert timestamps to microseconds
    for col in props_df.columns:
        if pd.api.types.is_datetime64_any_dtype(props_df[col]):
            props_df[col] = props_df[col].astype('datetime64[us]')
    
    # Load table and overwrite
    table = load_table(NAMESPACE, PROPERTIES_TABLE)
    table_schema = table.schema().as_arrow()
    
    # Reorder columns to match schema
    schema_column_order = [field.name for field in table_schema]
    props_df = props_df[[col for col in schema_column_order if col in props_df.columns]]
    
    # Convert to PyArrow and cast to schema
    arrow_table = pa.Table.from_pandas(props_df, preserve_index=False)
    arrow_table = arrow_table.cast(table_schema)
    
    # Overwrite the table
    print("💾 Saving changes...")
    table.overwrite(arrow_table)
    
    print("✅ Property ownership transferred successfully!")
    
    # Show the updated property
    updated_prop = props_df[prop_mask].iloc[0]
    print(f"\n📍 Property Details:")
    print(f"   Address: {updated_prop['address_line1']}, {updated_prop['city']}, {updated_prop['state']} {updated_prop['zip_code']}")
    print(f"   New Owner ID: {updated_prop['user_id']}")
    print(f"   Display Name: {updated_prop.get('display_name', 'N/A')}")
    
    return True

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python transfer_property_ownership.py <property_address> <new_owner_email>")
        print("Example: python transfer_property_ownership.py '316 S 50th' matt@example.com")
        sys.exit(1)
    
    property_address = sys.argv[1]
    new_owner_email = sys.argv[2]
    
    success = transfer_property(property_address, new_owner_email)
    sys.exit(0 if success else 1)






