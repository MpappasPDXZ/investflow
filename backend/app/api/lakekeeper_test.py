"""Test endpoints for Lakekeeper integration"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from app.services.lakekeeper_service import get_lakekeeper_service
from app.services.pyiceberg_service import get_pyiceberg_service
from app.core.logging import get_logger

router = APIRouter(prefix="/lakekeeper", tags=["lakekeeper-test"])
logger = get_logger(__name__)


@router.get("/test/connection")
async def test_lakekeeper_connection(
    lakekeeper=Depends(get_lakekeeper_service)
):
    """Test connection to Lakekeeper and get warehouse information"""
    try:
        warehouses = await lakekeeper.get_warehouses()
        warehouse_id = await lakekeeper.get_warehouse_id()
        
        return {
            "status": "success",
            "message": "Successfully connected to Lakekeeper",
            "warehouses": warehouses,
            "default_warehouse_id": warehouse_id,
            "warehouse_count": len(warehouses)
        }
    except Exception as e:
        logger.error(f"Failed to connect to Lakekeeper: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to Lakekeeper: {str(e)}"
        )


@router.get("/test/warehouses")
async def test_get_warehouses(
    lakekeeper=Depends(get_lakekeeper_service)
):
    """Get all warehouses from Lakekeeper"""
    try:
        warehouses = await lakekeeper.get_warehouses()
        return {
            "status": "success",
            "warehouses": warehouses
        }
    except Exception as e:
        logger.error(f"Failed to get warehouses: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get warehouses: {str(e)}"
        )


@router.get("/test/namespaces")
async def test_list_namespaces(
    warehouse_name: str = "lakekeeper",
    lakekeeper=Depends(get_lakekeeper_service)
):
    """List namespaces in a warehouse"""
    try:
        warehouse_id = await lakekeeper.get_warehouse_id(warehouse_name)
        if not warehouse_id:
            raise HTTPException(
                status_code=404,
                detail=f"Warehouse '{warehouse_name}' not found"
            )
        
        namespaces = await lakekeeper.list_namespaces(warehouse_id)
        return {
            "status": "success",
            "warehouse_id": warehouse_id,
            "warehouse_name": warehouse_name,
            "namespaces": namespaces,
            "namespace_count": len(namespaces)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list namespaces: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list namespaces: {str(e)}"
        )


@router.get("/test/pyiceberg")
async def test_pyiceberg_connection():
    """Test PyIceberg connection and catalog configuration"""
    try:
        pyiceberg = get_pyiceberg_service()
        catalog = pyiceberg.get_catalog()
        
        # Test listing namespaces
        namespaces = catalog.list_namespaces()
        
        return {
            "status": "success",
            "message": "PyIceberg connection successful",
            "catalog_name": catalog.name,
            "warehouse": pyiceberg._warehouse_name,
            "namespaces": [list(ns) for ns in namespaces],
            "namespace_count": len(list(namespaces))
        }
    except Exception as e:
        logger.error(f"Failed to test PyIceberg: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test PyIceberg: {str(e)}"
        )


@router.get("/test/integration")
async def test_full_integration(
    warehouse_name: str = "lakekeeper",
    lakekeeper=Depends(get_lakekeeper_service)
):
    """
    Test the complete integration flow:
    1. Connect to Lakekeeper
    2. Get warehouse info
    3. List namespaces
    4. Test PyIceberg connection
    5. Verify PyIceberg catalog configuration
    """
    try:
        results = {
            "status": "success",
            "steps": {}
        }
        
        # Step 1: Test Lakekeeper connection
        logger.info("Step 1: Testing Lakekeeper connection...")
        warehouses = await lakekeeper.get_warehouses()
        warehouse_id = await lakekeeper.get_warehouse_id(warehouse_name)
        
        if not warehouse_id:
            raise HTTPException(
                status_code=404,
                detail=f"Warehouse '{warehouse_name}' not found"
            )
        
        results["steps"]["lakekeeper_connection"] = {
            "status": "success",
            "warehouse_id": warehouse_id,
            "warehouse_name": warehouse_name,
            "warehouse_count": len(warehouses)
        }
        
        # Step 2: List namespaces
        logger.info("Step 2: Listing namespaces...")
        namespaces = await lakekeeper.list_namespaces(warehouse_id)
        results["steps"]["list_namespaces"] = {
            "status": "success",
            "namespaces": namespaces,
            "namespace_count": len(namespaces)
        }
        
        # Step 3: Test PyIceberg connection
        logger.info("Step 3: Testing PyIceberg connection...")
        pyiceberg = get_pyiceberg_service()
        catalog = pyiceberg.get_catalog()
        pyiceberg_namespaces = catalog.list_namespaces()
        results["steps"]["pyiceberg_connection"] = {
            "status": "success",
            "catalog_name": catalog.name,
            "namespaces": [list(ns) for ns in pyiceberg_namespaces],
            "namespace_count": len(list(pyiceberg_namespaces))
        }
        
        # Summary
        results["summary"] = {
            "all_steps_passed": all(
                step.get("status") == "success" 
                for step in results["steps"].values()
            ),
            "total_steps": len(results["steps"])
        }
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Integration test failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Integration test failed: {str(e)}"
        )


@router.get("/test/query-table")
async def test_query_table(
    namespace: str = "test_namespace",
    table_name: str = "test_table",
    warehouse_name: str = "lakekeeper",
    limit: int = 10,
    lakekeeper=Depends(get_lakekeeper_service)
):
    """
    Test querying an Iceberg table through the complete flow:
    1. Get table metadata from Lakekeeper
    2. Query table using PyIceberg
    """
    try:
        # Get warehouse ID
        warehouse_id = await lakekeeper.get_warehouse_id(warehouse_name)
        if not warehouse_id:
            raise HTTPException(
                status_code=404,
                detail=f"Warehouse '{warehouse_name}' not found"
            )
        
        # Get table metadata
        logger.info(f"Getting table metadata for {namespace}.{table_name}...")
        namespace_list = namespace.split(".")
        table_info = await lakekeeper.get_table(warehouse_id, namespace_list, table_name)
        
        metadata_location = table_info.get("metadata-location")
        if not metadata_location:
            raise HTTPException(
                status_code=404,
                detail=f"Table {namespace}.{table_name} has no metadata location"
            )
        
        # Query table using PyIceberg
        logger.info(f"Querying table using PyIceberg...")
        pyiceberg = get_pyiceberg_service()
        namespace_tuple = tuple(namespace_list)
        df = pyiceberg.read_table(namespace_tuple, table_name, limit=limit)
        
        return {
            "status": "success",
            "table": f"{namespace}.{table_name}",
            "warehouse_id": warehouse_id,
            "metadata_location": metadata_location,
            "row_count": len(df),
            "columns": list(df.columns) if not df.empty else [],
            "sample_data": df.head(limit).to_dict("records") if not df.empty else []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query table: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query table: {str(e)}"
        )
