# Lease Generation UI & API Proposal

## Navigation Structure Change

### Current Sidebar Structure
```
Property
├── Add Property
└── View Properties

Rent
├── Log Rent
└── View Rent

Expense
├── Add Expense
├── View Expenses
└── Export Expenses

Vault
├── Add New
├── Documents
└── Photos
```

### Proposed Sidebar Structure
```
Property
├── Add Property
└── View Properties

Leases ⭐ NEW
├── Create Lease
└── View Leases

Rent
├── Log Rent
└── View Rent

Expense
├── Add Expense
├── View Expenses
└── Export Expenses

Vault
├── Add New
├── Documents
└── Photos
```

**Rationale**: Place Leases between Property and Rent since:
1. You need a property before creating a lease
2. Rent payments typically follow from an active lease
3. Logical workflow: Property → Lease → Rent → Expenses

---

## Screen-to-Table Mapping

### Create Lease Flow (Multi-Step Form)

#### Step 1: Property Selection
**UI Fields** → **Backend Tables**

| Field | Type | Maps To | Required |
|-------|------|---------|----------|
| Select Property | Dropdown | `leases.property_id` | ✓ |
| Select Unit (if multi-unit) | Dropdown | `leases.unit_id` | - |

**Data Source**: `GET /api/v1/properties` (current user's properties)

---

#### Step 2: Lease Terms
**UI Fields** → **Backend Tables**

| Field | Type | Maps To | Required | Default |
|-------|------|---------|----------|---------|
| State | Select (NE/MO) | `leases.state` | ✓ | From property |
| Commencement Date | Date | `leases.commencement_date` | ✓ | - |
| Termination Date | Date | `leases.termination_date` | ✓ | +1 year |
| Auto Month-to-Month | Checkbox | `leases.auto_convert_month_to_month` | - | false |
| Monthly Rent | Currency | `leases.monthly_rent` | ✓ | - |
| Security Deposit | Currency | `leases.security_deposit` | ✓ | = Monthly Rent |
| Payment Method | Text | `leases.payment_method` | - | - |
| Prorated First Month | Currency | `leases.prorated_first_month_rent` | - | Auto-calc |

**State-Specific Defaults Applied**:
- `deposit_return_days`: 14 (NE) or 30 (MO)
- `late_fee_*`: State-specific fee schedule
- `nsf_fee`: $60 (NE) or $50 (MO)

---

#### Step 3: Tenants
**UI Fields** → **Backend Tables**

**Dynamic List of Tenants** (minimum 1, unlimited max)

| Field | Type | Maps To | Required |
|-------|------|---------|----------|
| First Name | Text | `lease_tenants.first_name` | ✓ |
| Last Name | Text | `lease_tenants.last_name` | ✓ |
| Email | Email | `lease_tenants.email` | - |
| Phone | Tel | `lease_tenants.phone` | - |
| Order | Number | `lease_tenants.tenant_order` | ✓ (auto) |

**UI Features**:
- "Add Another Tenant" button
- "Remove" button (if > 1 tenant)
- Drag-to-reorder for signature order

---

#### Step 4: Occupancy & Pets
**UI Fields** → **Backend Tables**

| Field | Type | Maps To | Required | Default |
|-------|------|---------|----------|---------|
| Max Occupants | Number | `leases.max_occupants` | - | 3 |
| Max Adults | Number | `leases.max_adults` | - | 2 |
| Allow Minor Children | Checkbox | `leases.max_children` | - | true |
| **Pets** | | | | |
| Pets Allowed | Checkbox | `leases.pets_allowed` | - | true |
| Max Pets | Number | `leases.max_pets` | - | 2 |
| One Pet Fee | Currency | `leases.pet_fee_one` | - | $350 (NE) |
| Two Pet Fee | Currency | `leases.pet_fee_two` | - | $700 (NE) |

---

#### Step 5: Property Features
**UI Fields** → **Backend Tables**

| Field | Type | Maps To | Required | Default |
|-------|------|---------|----------|---------|
| **Utilities** | | | | |
| Tenant Pays | Multi-select | `leases.utilities_tenant` | - | Gas, Water, Electric |
| Landlord Pays | Multi-select | `leases.utilities_landlord` | - | Trash |
| **Parking** | | | | |
| Parking Spaces | Number | `leases.parking_spaces` | - | 2 |
| Small Vehicle Limit | Number | `leases.parking_small_vehicles` | - | 2 |
| Large Truck Limit | Number | `leases.parking_large_trucks` | - | 1 |
| **Keys** | | | | |
| Front Door Keys | Number | `leases.front_door_keys` | - | 1 |
| Back Door Keys | Number | `leases.back_door_keys` | - | 1 |
| Key Replacement Fee | Currency | `leases.key_replacement_fee` | - | $100 |
| **Special Features** | | | | |
| Shared Driveway | Checkbox | `leases.has_shared_driveway` | - | false |
| Shared With Address | Text | `leases.shared_driveway_with` | - | - |
| Has Garage | Checkbox | `leases.has_garage` | - | false |
| Garage Outlets Prohibited | Checkbox | `leases.garage_outlets_prohibited` | - | false |
| Has Attic | Checkbox | `leases.has_attic` | - | false |
| Attic Usage | Text | `leases.attic_usage` | - | - |
| Has Basement | Checkbox | `leases.has_basement` | - | false |
| Appliances Provided | Textarea | `leases.appliances_provided` | - | - |

---

#### Step 6: Move-Out Costs
**UI Fields** → **Backend Tables**

**Dynamic List of Move-Out Cost Items** (editable, add/remove)

| Field | Type | Maps To | Required |
|-------|------|---------|----------|
| Item Name | Text | `moveout_costs[].item` | ✓ |
| Description | Textarea | `moveout_costs[].description` | - |
| Amount | Currency | `moveout_costs[].amount` | ✓ |
| Order | Number | `moveout_costs[].order` | ✓ (auto) |

**Stored as**: JSON array in `leases.moveout_costs`

**Default Items**:
1. Hardwood Floor Cleaning - $100
2. Trash Removal Fee - $150
3. Heavy Cleaning - $400
4. Wall Repairs - $150

**UI Features**:
- "Add Cost Item" button
- "Remove" button per item
- Drag-to-reorder
- "Reset to Defaults" button

---

#### Step 7: Additional Terms
**UI Fields** → **Backend Tables**

| Field | Type | Maps To | Required | Default |
|-------|------|---------|----------|---------|
| Lead Paint Disclosure | Checkbox | `leases.lead_paint_disclosure` | - | auto (if <1978) |
| Year Built | Number | `leases.lead_paint_year_built` | - | From property |
| Early Termination Allowed | Checkbox | `leases.early_termination_allowed` | - | true |
| Notice Days | Number | `leases.early_termination_notice_days` | - | 60 |
| Termination Fee (months) | Number | `leases.early_termination_fee_months` | - | 2 |
| Termination Fee Amount | Currency | `leases.early_termination_fee_amount` | - | Auto-calc |
| Snow Removal | Select | `leases.snow_removal_responsibility` | - | tenant |
| Notes | Textarea | `leases.notes` | - | - |

---

#### Step 8: Missouri-Specific (if state = MO)
**UI Fields** → **Backend Tables**

| Field | Type | Maps To | Required |
|-------|------|---------|----------|
| Methamphetamine Disclosure | Checkbox | `leases.methamphetamine_disclosure` | ✓ (MO) |
| Owner Name | Text | `leases.owner_name` | ✓ (MO) |
| Owner Address | Text | `leases.owner_address` | ✓ (MO) |
| Manager Name | Text | `leases.manager_name` | - |
| Manager Address | Text | `leases.manager_address` | - |
| Deposit Account Info | Text | `leases.deposit_account_info` | - |
| Move-out Inspection Rights | Checkbox | `leases.moveout_inspection_rights` | ✓ (MO) |

---

#### Step 9: Review & Generate
**Display Summary**:
- All lease terms in readable format
- Tenant list
- Property details
- Total fees breakdown
- State-specific disclosures

**Actions**:
- "Edit" buttons for each section (jump back to step)
- "Save as Draft" button → `status: 'draft'`
- "Generate PDF" button → `status: 'pending_signature'`

---

## View Leases Screen

### Table Columns

| Column | Data Source | Sortable | Filterable |
|--------|-------------|----------|------------|
| Property | `properties.display_name` | ✓ | ✓ |
| Tenants | `lease_tenants[]` (comma-separated) | - | ✓ |
| Start Date | `leases.commencement_date` | ✓ | ✓ |
| End Date | `leases.termination_date` | ✓ | ✓ |
| Monthly Rent | `leases.monthly_rent` | ✓ | - |
| Status | `leases.status` | ✓ | ✓ |
| Actions | - | - | - |

### Status Badge Colors

| Status | Color | Description |
|--------|-------|-------------|
| `draft` | Gray | Saved but not generated |
| `pending_signature` | Yellow | PDF generated, awaiting signatures |
| `active` | Green | Signed and active |
| `expired` | Red | Past termination date |
| `terminated` | Red | Early termination |

### Row Actions
- **View**: Opens modal with full lease details + download PDF link
- **Edit**: Navigates to edit form (only if `status: 'draft'`)
- **Regenerate PDF**: Re-generates PDF (if lease data changed)
- **Download PDF**: Downloads PDF from ADLS
- **Download LaTeX**: Downloads LaTeX source from ADLS
- **Duplicate**: Creates new draft lease with same terms
- **Terminate**: Marks lease as terminated (requires reason + date)

---

## API Endpoints

### Base URL: `/api/v1/leases`

#### 1. `POST /api/v1/leases` - Create Lease
**Request Body**:
```json
{
  "property_id": "uuid",
  "unit_id": "uuid | null",
  "state": "NE | MO",
  "commencement_date": "2025-01-15",
  "termination_date": "2026-01-15",
  "monthly_rent": 2500.00,
  "security_deposit": 2500.00,
  "tenants": [
    {
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com",
      "phone": "402-555-1234"
    }
  ],
  "pets_allowed": true,
  "pet_fee_one": 350.00,
  "has_shared_driveway": true,
  "shared_driveway_with": "314 S 50th Ave",
  "moveout_costs": [
    {
      "item": "Hardwood Floor Cleaning",
      "description": "Fee if not clean",
      "amount": 100.00,
      "order": 1
    }
  ],
  // ... all other optional fields
}
```

**Response** (201 Created):
```json
{
  "id": "uuid",
  "property_id": "uuid",
  "status": "draft",
  "state": "NE",
  "commencement_date": "2025-01-15",
  "termination_date": "2026-01-15",
  "monthly_rent": 2500.00,
  "security_deposit": 2500.00,
  "deposit_return_days": 14,
  "late_fee_day_1_10": 75.00,
  // ... all fields with defaults applied
  "tenants": [
    {
      "id": "uuid",
      "lease_id": "uuid",
      "tenant_order": 1,
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com",
      "phone": "402-555-1234"
    }
  ],
  "created_at": "2025-12-14T12:00:00Z",
  "updated_at": "2025-12-14T12:00:00Z"
}
```

---

#### 2. `GET /api/v1/leases` - List Leases
**Query Parameters**:
- `property_id` (optional): Filter by property
- `status` (optional): Filter by status
- `state` (optional): Filter by state
- `active_only` (optional): Only active leases (default: false)

**Response** (200 OK):
```json
{
  "leases": [
    {
      "id": "uuid",
      "property": {
        "id": "uuid",
        "display_name": "316 S 50th Ave",
        "address": "316 S 50th Ave, Omaha, NE"
      },
      "tenants": [
        {"first_name": "John", "last_name": "Doe"}
      ],
      "commencement_date": "2025-01-15",
      "termination_date": "2026-01-15",
      "monthly_rent": 2500.00,
      "status": "active",
      "pdf_url": "https://investflowadls.blob.core.windows.net/..."
    }
  ],
  "total": 10
}
```

---

#### 3. `GET /api/v1/leases/{lease_id}` - Get Lease Details
**Response** (200 OK):
```json
{
  "id": "uuid",
  "property": {
    "id": "uuid",
    "display_name": "316 S 50th Ave",
    "address": "316 S 50th Ave, Omaha, NE",
    "city": "Omaha",
    "state": "NE",
    "zip_code": "68132",
    "year_built": 1929
  },
  "unit": null,
  "state": "NE",
  "status": "active",
  "lease_version": 1,
  // ... all lease fields ...
  "tenants": [
    {
      "id": "uuid",
      "lease_id": "uuid",
      "tenant_order": 1,
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com",
      "phone": "402-555-1234",
      "signed_date": "2025-01-10"
    }
  ],
  "moveout_costs": [
    {
      "item": "Hardwood Floor Cleaning",
      "description": "Fee if not clean",
      "amount": 100.00,
      "order": 1
    }
  ],
  "generated_pdf_document_id": "leases/generated/user_id/lease_id/lease.pdf",
  "pdf_url": "https://investflowadls.blob.core.windows.net/...",
  "latex_url": "https://investflowadls.blob.core.windows.net/...",
  "created_at": "2025-12-14T12:00:00Z",
  "updated_at": "2025-12-14T12:00:00Z"
}
```

---

#### 4. `PUT /api/v1/leases/{lease_id}` - Update Lease
**Request Body**: Same as Create (partial updates allowed)

**Response** (200 OK): Same as Get Lease Details

**Business Rules**:
- Can only update if `status: 'draft'`
- If `status: 'active'` or `'pending_signature'`, create new version instead
- Updating increments `lease_version`

---

#### 5. `DELETE /api/v1/leases/{lease_id}` - Delete Lease
**Response** (204 No Content)

**Business Rules**:
- Can only delete if `status: 'draft'`
- Soft delete: Sets `is_active: false`
- Also soft-deletes associated tenants

---

#### 6. `POST /api/v1/leases/{lease_id}/generate-pdf` - Generate PDF
**Request Body**:
```json
{
  "regenerate": false  // If true, regenerate even if PDF exists
}
```

**Response** (200 OK):
```json
{
  "lease_id": "uuid",
  "pdf_url": "https://investflowadls.blob.core.windows.net/...",
  "latex_url": "https://investflowadls.blob.core.windows.net/...",
  "pdf_blob_name": "leases/generated/user_id/lease_id/lease.pdf",
  "generated_at": "2025-12-14T12:00:00Z",
  "status": "pending_signature"
}
```

**Process**:
1. Validate lease is complete
2. Retrieve property and tenant data
3. Generate LaTeX from template
4. Compile to PDF (TinyTeX)
5. Save both to ADLS
6. Update `leases.generated_pdf_document_id`
7. Update `leases.status` to `'pending_signature'`
8. Return signed SAS URLs

---

#### 7. `POST /api/v1/leases/{lease_id}/terminate` - Terminate Lease
**Request Body**:
```json
{
  "termination_date": "2025-06-15",
  "reason": "Tenant requested early termination",
  "early_termination_fee_paid": true
}
```

**Response** (200 OK):
```json
{
  "lease_id": "uuid",
  "status": "terminated",
  "original_termination_date": "2026-01-15",
  "actual_termination_date": "2025-06-15",
  "reason": "Tenant requested early termination"
}
```

---

#### 8. `GET /api/v1/leases/{lease_id}/pdf` - Download PDF
**Response** (200 OK):
- Content-Type: `application/pdf`
- Returns PDF bytes OR
- Returns redirect to ADLS SAS URL (24-hour expiry)

---

#### 9. `GET /api/v1/leases/{lease_id}/tenants` - List Tenants
**Response** (200 OK):
```json
{
  "tenants": [
    {
      "id": "uuid",
      "lease_id": "uuid",
      "tenant_order": 1,
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com",
      "phone": "402-555-1234",
      "signed_date": null
    }
  ]
}
```

---

#### 10. `PUT /api/v1/leases/{lease_id}/tenants/{tenant_id}` - Update Tenant
**Request Body**:
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "phone": "402-555-1234",
  "signed_date": "2025-01-10"
}
```

**Response** (200 OK): Updated tenant object

---

## Frontend Components Structure

```
frontend/app/(dashboard)/leases/
├── page.tsx                    # View Leases (table)
├── create/
│   └── page.tsx               # Multi-step form
├── [id]/
│   ├── page.tsx               # View single lease
│   └── edit/
│       └── page.tsx           # Edit lease (if draft)

frontend/components/
├── LeaseForm/
│   ├── Step1PropertySelection.tsx
│   ├── Step2LeaseTerms.tsx
│   ├── Step3Tenants.tsx
│   ├── Step4OccupancyPets.tsx
│   ├── Step5PropertyFeatures.tsx
│   ├── Step6MoveOutCosts.tsx
│   ├── Step7AdditionalTerms.tsx
│   ├── Step8MissouriSpecific.tsx
│   └── Step9ReviewGenerate.tsx
├── LeaseTable.tsx              # List view
├── LeaseStatusBadge.tsx        # Status indicator
└── LeaseActions.tsx            # Action buttons

frontend/lib/hooks/
└── use-leases.ts               # API hooks for leases
```

---

## Data Validation Rules

### Frontend Validation
1. **Dates**: End date must be after start date
2. **Amounts**: All currency > 0
3. **Tenants**: At least 1 tenant required
4. **State**: Required, affects which fields show
5. **Property**: Must be selected

### Backend Validation
1. **User owns property**: Verify `property.user_id` matches current user
2. **Unit belongs to property**: If unit_id provided, verify it exists
3. **Date logic**: Commencement < Termination
4. **State-specific**: Enforce MO required fields if state = MO
5. **Security deposit limits**: 
   - NE: ≤ 1 month rent
   - MO: ≤ 2 months rent

---

## ADLS Blob Organization

```
documents/
└── leases/
    └── generated/
        └── {user_id}/
            └── {lease_id}/
                ├── lease_316_S_50th_Ave_20251214_120000.pdf
                ├── lease_316_S_50th_Ave_20251214_120000.tex
                ├── lease_316_S_50th_Ave_20251215_083000.pdf  (v2)
                └── lease_316_S_50th_Ave_20251215_083000.tex  (v2)
```

**Metadata on each blob**:
```json
{
  "user_id": "uuid",
  "lease_id": "uuid",
  "property_id": "uuid",
  "lease_version": "1",
  "generated_at": "2025-12-14T12:00:00Z",
  "document_type": "lease_pdf" | "lease_latex"
}
```

---

## Summary

✅ **Navigation**: Add "Leases" section between Property and Rent  
✅ **Screens**: Multi-step create form + table view  
✅ **Mapping**: All form fields mapped to `leases` and `lease_tenants` tables  
✅ **API**: 10 RESTful endpoints for full CRUD + PDF generation  
✅ **Storage**: All files in ADLS with proper organization  
✅ **State Rules**: NE/MO specific validations and defaults  
✅ **Workflow**: Draft → Generate PDF → Pending Signature → Active  

**Next Steps**:
1. Build API endpoints in `backend/app/api/leases.py`
2. Create Pydantic schemas in `backend/app/schemas/lease.py`
3. Build frontend components
4. Test end-to-end flow

