# Migration to Iceberg Tables - Status

## ✅ Completed

### 1. Models Updated
- **File**: `backend/app/models/tables.py`
- **Change**: Updated `PropertyPlan.__tablename__` from `"property_plans"` to `"property_plan"` to match Iceberg table name
- **Note**: SQLAlchemy models are kept for reference, but Iceberg tables use PyIceberg directly

### 2. Property Service Migrated
- **File**: `backend/app/services/property_service.py`
- **Changes**:
  - Removed SQLAlchemy dependencies
  - Now uses `PyIcebergService` for all operations
  - Functions return dictionaries instead of SQLAlchemy models
  - UUIDs are stored as strings in Iceberg (converted to/from UUID objects)
  - All CRUD operations (create, read, update, delete) implemented

### 3. Property Endpoints Updated
- **File**: `backend/app/api/properties.py`
- **Changes**:
  - Removed `db: Session = Depends(get_db)` dependencies
  - Updated to use new service functions
  - Response models work with dictionaries

### 4. Table Names Verified
- All Iceberg table names match `make_app.txt`:
  - ✅ `users`
  - ✅ `properties`
  - ✅ `property_plan` (not `property_plans`)
  - ✅ `document_storage`
  - ✅ `expenses`
  - ✅ `clients`
  - ✅ `rents`
  - ✅ `scenarios`

## 📋 Still To Do

### Services to Migrate
1. **User Service** (`backend/app/services/user_service.py`)
   - Currently uses SQLAlchemy
   - Note: Users table might stay in PostgreSQL for auth, or migrate to Iceberg

2. **Expense Service** (needs to be created)
   - Create `backend/app/services/expense_service.py`
   - Use PyIceberg for CRUD operations

3. **Client Service** (needs to be created)
   - Create `backend/app/services/client_service.py`
   - Use PyIceberg for CRUD operations

4. **Rent Service** (needs to be created)
   - Create `backend/app/services/rent_service.py`
   - Use PyIceberg for CRUD operations

5. **Scenario Service** (needs to be created)
   - Create `backend/app/services/scenario_service.py`
   - Use PyIceberg for CRUD operations
   - Include calculation logic for ROI fields

6. **Property Plan Service** (needs to be created)
   - Create `backend/app/services/property_plan_service.py`
   - Use PyIceberg for CRUD operations

7. **Document Storage Service** (needs to be created)
   - Create `backend/app/services/document_storage_service.py`
   - Use PyIceberg for CRUD operations
   - Handle blob storage integration

### Endpoints to Create/Update
1. **Expense Endpoints** (`backend/app/api/expenses.py`)
2. **Client Endpoints** (`backend/app/api/clients.py`)
3. **Rent Endpoints** (`backend/app/api/rents.py`)
4. **Scenario Endpoints** (`backend/app/api/scenarios.py`)
5. **Property Plan Endpoints** (`backend/app/api/property_plans.py`)
6. **Document Storage Endpoints** (`backend/app/api/documents.py`)

### Schemas to Verify
- All Pydantic schemas in `backend/app/schemas/` should match Iceberg table schemas
- Verify field types match (UUIDs as strings, Decimals, timestamps, etc.)

## 🔧 Implementation Pattern

### Service Pattern (from property_service.py)

```python
from app.services.pyiceberg_service import get_pyiceberg_service

NAMESPACE = ("investflow",)
TABLE_NAME = "properties"

def create_property(user_id: UUID, property_data: PropertyCreate) -> Dict[str, Any]:
    """Create using PyIceberg"""
    pyiceberg = get_pyiceberg_service()
    # Convert to dict, create DataFrame, append
    df = pd.DataFrame([property_dict])
    pyiceberg.append_data(NAMESPACE, TABLE_NAME, df)

def get_property(property_id: UUID, user_id: UUID) -> Optional[Dict[str, Any]]:
    """Read using PyIceberg"""
    pyiceberg = get_pyiceberg_service()
    df = pyiceberg.read_table(NAMESPACE, TABLE_NAME)
    # Filter in pandas, convert to dict

def update_property(...) -> Optional[Dict[str, Any]]:
    """Update using PyIceberg (read all, update, truncate, reload)"""
    # Note: Inefficient but necessary for Iceberg updates
    # Consider using merge capabilities in production

def delete_property(...) -> bool:
    """Soft delete (update is_active to False)"""
    # Use update_property with is_active=False
```

### Endpoint Pattern (from properties.py)

```python
@router.post("", response_model=PropertyResponse, status_code=201)
async def create_property_endpoint(
    property_data: PropertyCreate,
    current_user: dict = Depends(get_current_user)
):
    """No db dependency, uses PyIceberg service"""
    user_id = UUID(current_user["sub"])
    property_dict = create_property(user_id, property_data)
    return PropertyResponse(**property_dict)
```

## ⚠️ Important Notes

1. **UUID Storage**: Iceberg stores UUIDs as strings. Convert to/from UUID objects in service layer.

2. **Updates are Inefficient**: Iceberg doesn't support direct row updates. Current approach:
   - Read all rows for user
   - Update in memory
   - Truncate table
   - Reload all rows
   - Consider partitioning or merge strategies for production

3. **Data Types**: 
   - Decimals stored as Decimal128 in Iceberg
   - Timestamps stored as microseconds (datetime64[us])
   - Integers stored as int32 where specified

4. **User Isolation**: All queries must filter by `user_id` to ensure data isolation.

5. **Soft Deletes**: Use `is_active=False` instead of hard deletes.

## 🧪 Testing

Test the property service:
```bash
docker-compose exec backend python -c "
from app.services.property_service import list_properties
from uuid import UUID
props, total = list_properties(UUID('11111111-1111-1111-1111-111111111111'))
print(f'Found {total} properties')
"
```

## 📚 References

- Iceberg table schemas: `backend/app/scripts/create_data.py`
- PyIceberg service: `backend/app/services/pyiceberg_service.py`
- Property service example: `backend/app/services/property_service.py`
- Property endpoints example: `backend/app/api/properties.py`





