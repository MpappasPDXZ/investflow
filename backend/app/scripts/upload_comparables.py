#!/usr/bin/env python3
"""
Upload rental comparables for 501 NE 67th St, Kansas City, MO 64118

Run with: cd backend && uv run python -m app.scripts.upload_comparables
"""
import sys
from pathlib import Path
from datetime import date
from decimal import Decimal

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

# Property ID for 501 NE 67th St
PROPERTY_ID = "72144430-08ed-41de-b264-34af5181bd03"

# Comparable data from spreadsheet
COMPARABLES = [
    {
        "address": "501 NE 67th St",
        "city": "Kansas City",
        "state": "MO",
        "zip_code": "64118",
        "bedrooms": 3,
        "bathrooms": Decimal("1.0"),
        "square_feet": 988,
        "asking_price": Decimal("1595"),
        "has_fence": True,
        "has_solid_flooring": True,
        "has_quartz_granite": True,
        "has_ss_appliances": True,
        "has_shaker_cabinets": True,
        "has_washer_dryer": True,
        "garage_spaces": 2,
        "date_listed": date(2024, 12, 1),  # Approximate - adjust as needed
        "contacts": None,
        "last_rented_price": None,
        "last_rented_year": None,
        "is_subject_property": True,
        "notes": "Subject property"
    },
    {
        "address": "2403 NE Pursell",
        "city": "Kansas City",
        "state": "MO",
        "zip_code": "64118",
        "bedrooms": 3,
        "bathrooms": Decimal("2.0"),
        "square_feet": 1310,
        "asking_price": Decimal("1750"),
        "has_fence": None,
        "has_solid_flooring": True,
        "has_quartz_granite": True,
        "has_ss_appliances": None,
        "has_shaker_cabinets": None,
        "has_washer_dryer": None,
        "garage_spaces": 1,
        "date_listed": date(2025, 8, 28),
        "contacts": 34,
        "last_rented_price": None,
        "last_rented_year": None,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "6105 N Forest Ave",
        "city": "Kansas City",
        "state": "MO",
        "zip_code": "64118",
        "bedrooms": 3,
        "bathrooms": Decimal("1.0"),
        "square_feet": 1000,
        "asking_price": Decimal("1695"),
        "has_fence": False,
        "has_solid_flooring": True,
        "has_quartz_granite": True,
        "has_ss_appliances": True,
        "has_shaker_cabinets": True,
        "has_washer_dryer": True,
        "garage_spaces": 1,
        "date_listed": date(2025, 10, 3),
        "contacts": 22,
        "last_rented_price": Decimal("1625"),
        "last_rented_year": None,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "5612 N Euclid Ave",
        "city": "Kansas City",
        "state": "MO",
        "zip_code": "64118",
        "bedrooms": 3,
        "bathrooms": Decimal("2.0"),
        "square_feet": 1225,
        "asking_price": Decimal("1910"),
        "has_fence": False,
        "has_solid_flooring": True,
        "has_quartz_granite": None,
        "has_ss_appliances": True,
        "has_shaker_cabinets": None,
        "has_washer_dryer": None,
        "garage_spaces": None,
        "date_listed": date(2025, 11, 21),
        "contacts": 5,
        "last_rented_price": Decimal("1525"),
        "last_rented_year": None,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "5707 N Woodland Ave",
        "city": "Kansas City",
        "state": "MO",
        "zip_code": "64118",
        "bedrooms": 3,
        "bathrooms": Decimal("1.0"),
        "square_feet": 1225,
        "asking_price": Decimal("1450"),
        "has_fence": True,
        "has_solid_flooring": True,
        "has_quartz_granite": None,
        "has_ss_appliances": None,
        "has_shaker_cabinets": None,
        "has_washer_dryer": None,
        "garage_spaces": None,
        "date_listed": date(2025, 8, 26),
        "contacts": 112,
        "last_rented_price": None,
        "last_rented_year": None,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "6017 N Howard Ave",
        "city": "Kansas City",
        "state": "MO",
        "zip_code": "64118",
        "bedrooms": 3,
        "bathrooms": Decimal("2.0"),
        "square_feet": 1400,
        "asking_price": Decimal("2000"),
        "has_fence": False,
        "has_solid_flooring": None,
        "has_quartz_granite": None,
        "has_ss_appliances": True,
        "has_shaker_cabinets": None,
        "has_washer_dryer": None,
        "garage_spaces": 2,
        "date_listed": date(2025, 12, 10),
        "contacts": None,
        "last_rented_price": None,
        "last_rented_year": None,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "5700 N Highland Ave",
        "city": "Kansas City",
        "state": "MO",
        "zip_code": "64118",
        "bedrooms": 3,
        "bathrooms": Decimal("1.0"),
        "square_feet": 923,
        "asking_price": Decimal("1570"),
        "has_fence": False,
        "has_solid_flooring": True,
        "has_quartz_granite": True,
        "has_ss_appliances": True,
        "has_shaker_cabinets": True,
        "has_washer_dryer": True,
        "garage_spaces": 1,
        "date_listed": date(2025, 9, 27),
        "contacts": 53,
        "last_rented_price": Decimal("1520"),
        "last_rented_year": None,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "5708 N Euclid Ave",
        "city": "Kansas City",
        "state": "MO",
        "zip_code": "64118",
        "bedrooms": 3,
        "bathrooms": Decimal("1.0"),
        "square_feet": 925,
        "asking_price": Decimal("1550"),
        "has_fence": False,
        "has_solid_flooring": True,
        "has_quartz_granite": None,
        "has_ss_appliances": None,
        "has_shaker_cabinets": None,
        "has_washer_dryer": None,
        "garage_spaces": 1,
        "date_listed": date(2025, 10, 23),
        "contacts": 30,
        "last_rented_price": None,
        "last_rented_year": None,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "2701 NE 67th Ter",
        "city": "Kansas City",
        "state": "MO",
        "zip_code": "64118",
        "bedrooms": 4,
        "bathrooms": Decimal("2.0"),
        "square_feet": 1300,
        "asking_price": Decimal("1900"),
        "has_fence": True,
        "has_solid_flooring": True,
        "has_quartz_granite": None,
        "has_ss_appliances": None,
        "has_shaker_cabinets": None,
        "has_washer_dryer": None,
        "garage_spaces": 2,
        "date_listed": date(2025, 9, 14),
        "contacts": 76,
        "last_rented_price": None,
        "last_rented_year": None,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "5507 N Lydia Ave",
        "city": "Gladstone",
        "state": "MO",
        "zip_code": "64118",
        "bedrooms": 3,
        "bathrooms": Decimal("1.5"),
        "square_feet": 1075,
        "asking_price": Decimal("1695"),
        "has_fence": True,
        "has_solid_flooring": True,
        "has_quartz_granite": None,
        "has_ss_appliances": None,
        "has_shaker_cabinets": None,
        "has_washer_dryer": None,
        "garage_spaces": 1,
        "date_listed": date(2025, 11, 24),
        "contacts": 15,
        "last_rented_price": Decimal("1595"),
        "last_rented_year": None,
        "is_subject_property": False,
        "notes": None
    },
]


def main():
    """Upload comparables to Iceberg table"""
    import uuid
    import pandas as pd
    from datetime import timezone
    from app.core.iceberg import get_catalog, table_exists, append_data
    from app.api.comparables import get_comparable_schema, NAMESPACE, TABLE_NAME
    
    logger.info(f"Uploading {len(COMPARABLES)} comparables for property {PROPERTY_ID}")
    
    # Ensure table exists
    if not table_exists(NAMESPACE, TABLE_NAME):
        logger.info(f"Creating {TABLE_NAME} table")
        catalog = get_catalog()
        schema = get_comparable_schema()
        catalog.create_table(
            identifier=f"{NAMESPACE[0]}.{TABLE_NAME}",
            schema=schema
        )
        logger.info(f"✅ Created {TABLE_NAME} table")
    
    # Create records
    records = []
    now = pd.Timestamp.now(tz=timezone.utc).floor('us')
    
    for comp in COMPARABLES:
        record = {
            "id": str(uuid.uuid4()),
            "property_id": PROPERTY_ID,
            "unit_id": None,
            "address": comp["address"],
            "city": comp["city"],
            "state": comp["state"],
            "zip_code": comp["zip_code"],
            "bedrooms": comp["bedrooms"],
            "bathrooms": float(comp["bathrooms"]),
            "square_feet": comp["square_feet"],
            "asking_price": float(comp["asking_price"]),
            "has_fence": comp["has_fence"],
            "has_solid_flooring": comp["has_solid_flooring"],
            "has_quartz_granite": comp["has_quartz_granite"],
            "has_ss_appliances": comp["has_ss_appliances"],
            "has_shaker_cabinets": comp["has_shaker_cabinets"],
            "has_washer_dryer": comp["has_washer_dryer"],
            "garage_spaces": comp["garage_spaces"],
            "date_listed": comp["date_listed"],
            "contacts": comp["contacts"],
            "last_rented_price": float(comp["last_rented_price"]) if comp["last_rented_price"] else None,
            "last_rented_year": comp["last_rented_year"],
            "is_subject_property": comp["is_subject_property"],
            "is_active": True,
            "notes": comp["notes"],
            "created_at": now,
            "updated_at": now,
        }
        records.append(record)
    
    # Convert to DataFrame and append
    df = pd.DataFrame(records)
    append_data(NAMESPACE, TABLE_NAME, df)
    
    logger.info(f"✅ Successfully uploaded {len(records)} comparables")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Uploaded {len(records)} comparables for 501 NE 67th St")
    print(f"{'='*60}")
    for comp in COMPARABLES:
        marker = "★" if comp["is_subject_property"] else " "
        print(f"{marker} {comp['address']}: ${comp['asking_price']}/mo, {comp['square_feet']} SF")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()


