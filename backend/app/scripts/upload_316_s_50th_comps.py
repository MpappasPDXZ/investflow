#!/usr/bin/env python3
"""
Upload rental comparables for 316 S 50th Ave, Omaha, NE 68132

Run with: cd backend && docker-compose exec backend python -m app.scripts.upload_316_s_50th_comps
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

# Property ID for 316 S 50th Ave
PROPERTY_ID = "00b1f6e9-174f-40a3-b2e9-af1518c6c69a"

# Comparable data from spreadsheet
COMPARABLES = [
    # Subject property first
    {
        "address": "316 S 50th Ave",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68132",
        "property_type": "Duplex",
        "is_furnished": False,
        "bedrooms": 3,
        "bathrooms": Decimal("2.0"),
        "square_feet": 1500,
        "asking_price": Decimal("2349"),
        "garage_spaces": 1,
        "date_listed": date(2025, 11, 16),
        "contacts": 7,
        "is_rented": False,
        "is_subject_property": True,
        "notes": "Subject property"
    },
    {
        "address": "5123 Capitol Ave",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68132",
        "property_type": "Duplex",
        "is_furnished": False,
        "bedrooms": 3,
        "bathrooms": Decimal("2.0"),
        "square_feet": 1664,
        "asking_price": Decimal("2595"),
        "garage_spaces": 1,
        "date_listed": date(2025, 9, 22),
        "contacts": None,
        "is_rented": True,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "114 S 50th St",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68132",
        "property_type": "House",
        "is_furnished": False,
        "bedrooms": 3,
        "bathrooms": Decimal("2.0"),
        "square_feet": 1594,
        "asking_price": Decimal("2300"),
        "garage_spaces": 1,
        "date_listed": date(2025, 7, 12),
        "contacts": None,
        "is_rented": True,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "310 S 49th Ave",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68132",
        "property_type": "House",
        "is_furnished": False,
        "bedrooms": 3,
        "bathrooms": Decimal("2.0"),
        "square_feet": 1971,
        "asking_price": Decimal("2300"),
        "garage_spaces": None,
        "date_listed": date(2024, 11, 24),
        "contacts": None,
        "is_rented": True,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "311 N 50th St",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68132",
        "property_type": "Duplex",
        "is_furnished": False,
        "bedrooms": 3,
        "bathrooms": Decimal("2.0"),
        "square_feet": 1369,
        "asking_price": Decimal("2259"),
        "garage_spaces": 1,
        "date_listed": date(2025, 10, 6),
        "contacts": None,
        "is_rented": True,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "309 N 50th St",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68132",
        "property_type": "Duplex",
        "is_furnished": False,
        "bedrooms": 3,
        "bathrooms": Decimal("2.0"),
        "square_feet": 1369,
        "asking_price": Decimal("2259"),
        "garage_spaces": 1,
        "date_listed": date(2025, 8, 6),
        "contacts": None,
        "is_rented": True,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "4853 Burt St",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68132",
        "property_type": "House",
        "is_furnished": False,
        "bedrooms": 4,
        "bathrooms": Decimal("2.0"),
        "square_feet": 1488,
        "asking_price": Decimal("2100"),
        "garage_spaces": 1,
        "date_listed": date(2024, 12, 1),
        "contacts": None,
        "is_rented": True,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "4918 California St",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68132",
        "property_type": "Duplex",
        "is_furnished": False,
        "bedrooms": 3,
        "bathrooms": Decimal("1.0"),
        "square_feet": 1369,
        "asking_price": Decimal("1500"),
        "garage_spaces": 1,
        "date_listed": date(2025, 1, 1),
        "contacts": None,
        "is_rented": True,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "5301 Elmwood Plz",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68106",
        "property_type": "Townhouse",
        "is_furnished": True,
        "bedrooms": 3,
        "bathrooms": Decimal("3.0"),
        "square_feet": 1716,
        "asking_price": Decimal("2750"),
        "garage_spaces": 2,
        "date_listed": date(2025, 11, 1),
        "contacts": 12,
        "is_rented": False,
        "is_subject_property": False,
        "notes": "Furnished"
    },
    {
        "address": "304 N 43rd St",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68131",
        "property_type": "House",
        "is_furnished": False,
        "bedrooms": 5,
        "bathrooms": Decimal("3.0"),
        "square_feet": 2600,
        "asking_price": Decimal("2700"),
        "garage_spaces": None,
        "date_listed": date(2025, 9, 25),
        "contacts": 17,
        "is_rented": False,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "620 N 46th St",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68132",
        "property_type": "Townhouse",
        "is_furnished": False,
        "bedrooms": 3,
        "bathrooms": Decimal("3.0"),
        "square_feet": 2400,
        "asking_price": Decimal("2400"),
        "garage_spaces": 2,
        "date_listed": date(2025, 11, 3),
        "contacts": 5,
        "is_rented": False,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "5161 Jones St",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68106",
        "property_type": "House",
        "is_furnished": False,
        "bedrooms": 5,
        "bathrooms": Decimal("3.0"),
        "square_feet": 3819,
        "asking_price": Decimal("2300"),
        "garage_spaces": 0,
        "date_listed": date(2025, 12, 10),
        "contacts": 4,
        "is_rented": False,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "5567 Mason St",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68106",
        "property_type": "House",
        "is_furnished": False,
        "bedrooms": 4,
        "bathrooms": Decimal("3.0"),
        "square_feet": 1618,
        "asking_price": Decimal("1618"),
        "garage_spaces": 1,
        "date_listed": date(2025, 11, 8),
        "contacts": 11,
        "is_rented": False,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "4632 Farnam St",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68132",
        "property_type": "House",
        "is_furnished": False,
        "bedrooms": 3,
        "bathrooms": Decimal("2.0"),
        "square_feet": 1750,
        "asking_price": Decimal("1650"),
        "garage_spaces": 1,
        "date_listed": date(2025, 10, 7),
        "contacts": 32,
        "is_rented": False,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "525 S 55th St",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68106",
        "property_type": "House",
        "is_furnished": False,
        "bedrooms": 3,
        "bathrooms": Decimal("3.0"),
        "square_feet": 2500,
        "asking_price": Decimal("3000"),
        "garage_spaces": 0,
        "date_listed": date(2025, 10, 16),
        "contacts": 3,
        "is_rented": False,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "4906 Cass St",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68132",
        "property_type": "House",
        "is_furnished": False,
        "bedrooms": 3,
        "bathrooms": Decimal("2.0"),
        "square_feet": 1878,
        "asking_price": Decimal("2200"),
        "garage_spaces": 0,
        "date_listed": date(2025, 5, 3),
        "contacts": None,
        "is_rented": True,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "1727 N 57th Ave",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68104",
        "property_type": "Duplex",
        "is_furnished": False,
        "bedrooms": 3,
        "bathrooms": Decimal("3.0"),
        "square_feet": 1800,
        "asking_price": Decimal("1945"),
        "garage_spaces": 2,
        "date_listed": date(2025, 5, 26),
        "contacts": 40,
        "is_rented": False,
        "is_subject_property": False,
        "notes": None
    },
    {
        "address": "428 N 61st St",
        "city": "Omaha",
        "state": "NE",
        "zip_code": "68132",
        "property_type": "House",
        "is_furnished": False,
        "bedrooms": 3,
        "bathrooms": Decimal("4.0"),
        "square_feet": 2400,
        "asking_price": Decimal("2550"),
        "garage_spaces": 2,
        "date_listed": date(2025, 10, 8),
        "contacts": 12,
        "is_rented": False,
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
        # Column order must match the evolved table schema
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
            "has_fence": None,
            "has_solid_flooring": None,
            "has_quartz_granite": None,
            "has_ss_appliances": None,
            "has_shaker_cabinets": None,
            "has_washer_dryer": None,
            "garage_spaces": comp["garage_spaces"],
            "date_listed": comp["date_listed"],
            "contacts": comp["contacts"],
            "last_rented_price": None,
            "last_rented_year": None,
            "is_subject_property": comp["is_subject_property"],
            "is_active": True,
            "notes": comp["notes"],
            "created_at": now,
            "updated_at": now,
            # New columns added at end of schema
            "is_furnished": comp["is_furnished"],
            "is_rented": comp["is_rented"],
            "property_type": comp["property_type"],
        }
        records.append(record)
    
    # Convert to DataFrame and append
    df = pd.DataFrame(records)
    append_data(NAMESPACE, TABLE_NAME, df)
    
    logger.info(f"✅ Successfully uploaded {len(records)} comparables")
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"Uploaded {len(records)} comparables for 316 S 50th Ave, Omaha, NE 68132")
    print(f"{'='*70}")
    for comp in COMPARABLES:
        marker = "★" if comp["is_subject_property"] else " "
        rented = "✓" if comp["is_rented"] else "✗"
        print(f"{marker} {comp['address']}: {comp['property_type']}, ${comp['asking_price']}/mo, {comp['square_feet']} SF, {rented} Rented")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()

