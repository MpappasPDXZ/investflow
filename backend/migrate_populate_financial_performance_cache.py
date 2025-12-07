"""
ONE-TIME Migration: Populate financial performance cache from historical data

This script calculates and caches financial performance (P&L) for ALL properties
by reading historical expenses and rent data. The cache is stored as parquet in ADLS.

Run this ONCE after deploying the new cache service:
    cd backend
    python migrate_populate_financial_performance_cache.py
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.financial_performance_cache_service import financial_performance_cache
from app.core.logging import get_logger

logger = get_logger(__name__)


def main():
    """Run the migration"""
    print("=" * 80)
    print("FINANCIAL PERFORMANCE CACHE POPULATION")
    print("=" * 80)
    print()
    print("This will:")
    print("  1. Calculate P&L for all properties from historical data")
    print("  2. Store results as parquet in ADLS (cdc/financial_performance/)")
    print("  3. Enable fast lookups for dashboard display")
    print()
    print("This may take a few minutes depending on data volume...")
    print()
    
    try:
        # Initialize the cache service
        financial_performance_cache.initialize()
        
        # Populate from historical data
        count = financial_performance_cache.populate_from_historical_data()
        
        print()
        print("=" * 80)
        print(f"✅ SUCCESS: Processed {count} properties")
        print("=" * 80)
        print()
        print("Cache location: documents/cdc/financial_performance/financial_performance_current.parquet")
        print()
        print("The cache will now be updated automatically when:")
        print("  - Expenses are added/updated/deleted")
        print("  - Rent payments are added/deleted")
        print()
        
    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ ERROR: {e}")
        print("=" * 80)
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

