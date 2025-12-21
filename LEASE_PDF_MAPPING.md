# Lease Parameter to PDF Mapping Plan

This document maps every lease form field to its corresponding section in the generated PDF.
All changes follow a "MadLib" style approach - inserting values into existing legal language.

**Legend:**
- ✅ = Currently implemented in `lease_generator_service.py`
- 🔶 = Partially implemented (needs update)
- ❌ = Not yet implemented (needs adding)

---

## Section 1: PREMISES

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `property_id` → property address | Section 1 header + "located at:" | ✅ | Uses `property_data.address` |
| `unit_id` | Section 1 (implicit via property address) | ✅ | Merged into full address if multi-family |
| Property description | Section 1 "Description:" | ✅ | Uses `property_data.description` |

---

## Section 2: LEASE TERM

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `commencement_date` | "shall begin on **{date}**" | ✅ | Formatted as "Month DD, YYYY" |
| `termination_date` | "and end on **{date}**" | ✅ | Formatted as "Month DD, YYYY" |
| `lease_duration_months` | (Not in PDF) | ❌ | **Used for calculation only** - no PDF output needed |
| `auto_convert_month_to_month` | "[X] convert to month-to-month" | ✅ | Checkbox: [X] or [ ] |

---

## Section 3: LEASE PAYMENTS (RENT)

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `monthly_rent` | "amount of **${rent}** per month" | ✅ | Formatted with commas |
| `payment_method` | "Rent shall be paid via **{method}**" | 🔶 | Currently hardcoded to "TurboTenant or check" - needs form value |
| `show_prorated_rent` | Prorated rent bullet | 🔶 | Currently auto-calculates if start != 1st |
| `prorated_rent_amount` | "prorated...to **${amount}**" | 🔶 | Uses calculation, should use form value if `show_prorated_rent` |
| `prorated_rent_language` | Custom prorated text | ❌ | **NEW:** If provided, replace default prorated text |

**Plan for Prorated Rent:**
```
IF show_prorated_rent:
  IF prorated_rent_language:
    OUTPUT: custom language
  ELSE:
    OUTPUT: default calculation text with prorated_rent_amount
ELSE:
  OMIT prorated rent bullet entirely
```

---

## Section 4: LATE CHARGES

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| (late_fee_day_1_10) | **${fee}** after due date | ✅ | From saved lease data |
| (late_fee_day_11) | **${fee}** after 11th | ✅ | From saved lease data |
| (late_fee_day_16) | **${fee}** after 16th | ✅ | NE only |
| (late_fee_day_21) | **${fee}** after 21st | ✅ | NE only |

---

## Section 5: INSUFFICIENT FUNDS

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| (nsf_fee) | "charge of **${fee}**" | ✅ | From saved lease data |

---

## Section 6: SECURITY DEPOSIT

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `security_deposit` | "sum of **${amount}**" | ✅ | Formatted with commas |
| (deposit_return_days) | "returned within **{days}** days" | ✅ | NE=14, MO=30 |
| `state` | "per **{state}** law" | ✅ | Uses state code |

---

## Section 11: OCCUPANTS

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `max_occupants` | "no more than **{n}** persons" | ✅ | Number |
| `max_adults` | "**{n} adults** and their minor children" | ✅ | Number |
| `num_children` | (Not in PDF directly) | ❌ | **NEW:** Add to occupants section |

**Plan for Occupants:**
```latex
Current: "no more than {max_occupants} persons OR {max_adults} adults and their minor children"

Proposed (if num_children > 0):
"no more than {max_occupants} persons (including {max_adults} adults and {num_children} children)"
```

---

## Section 15: UTILITIES AND SERVICES

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `utilities_tenant` | "(including {list})" | ✅ | Comma-separated list |
| `utilities_landlord` | "Landlord will provide: **{list}**" | ✅ | Comma-separated list |

---

## Section 16: PETS

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `pets_allowed` | Entire section conditional | ✅ | If false: "No pets allowed" |
| `pet_fee` | "Pet Fee is **${fee}**" | 🔶 | Currently uses pet_fee_one/two - needs update to use single pet_fee |
| `max_pets` | "includes **{n}** pets" | 🔶 | Needs update for new clause format |
| `pets` array | Pet descriptions | ❌ | **NEW:** Full pet clause |

**Current Implementation (needs update):**
```latex
Non-refundable Pet Fee required: \$350 for one pet, \$700 for two pets.
Max pet occupancy 2 pets.
```

**Plan for New Pet Clause:**
```latex
IF pets_allowed AND max_pets > 0:
  Pet Fee is ${pet_fee} and includes {max_pets} pets: {pet_descriptions}.
  Pets are replaceable at no cost to the tenant.
  All pets must be approved if breed is changed or weight is increased.
  
  WHERE pet_descriptions = formatted list like:
  - "1-Dog (Pancho) 15lbs, 2-Cats (Sunshine and Blue)"
  - Group by type, include names if provided, include weight for dogs only
ELSE:
  No pets allowed on the Premises without prior written consent of the Landlord.
```

---

## Section 19: MAINTENANCE AND REPAIR

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `has_shared_driveway` | Shared Driveway bullet | ✅ | Conditional inclusion |
| `shared_driveway_with` | "shared driveway with **{property}**" | ✅ | Property address/description |
| `snow_removal_responsibility` | Snow Removal bullet | ✅ | If "tenant": include bullet |

---

## Section 27: GOVERNING LAW

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `state` | "State of **{state}**" | ✅ | Full state name |

---

## Section 29: NOTICE

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `owner_name` | Landlord notice address | 🔶 | Currently hardcoded |
| `owner_address` | Landlord notice address | 🔶 | Currently hardcoded |

**Plan:** Use form values instead of hardcoded address.

---

## Section 33: PARKING

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `garage_spaces` | "**{n} garage space(s)**" | ✅ | Dynamic description |
| `offstreet_parking_spots` | "**{n} off-street parking spot(s)**" | ✅ | Dynamic description |
| `parking_spaces` | Total parking (fallback) | ✅ | Used if no breakdown |
| `parking_small_vehicles` | "capacity allows for **{n}** small vehicles" | ✅ | Note section |
| `parking_large_trucks` | "Large trucks limited to **{n}**" | ✅ | Note section |
| `shared_parking_arrangement` | "Shared Parking Agreement:" | ✅ | Multi-family only |

---

## Section 34: KEYS

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `include_keys_clause` | Entire section conditional | ❌ | **NEW:** If false, omit section or use default |
| `has_front_door` | Front door keys mentioned | ❌ | **NEW:** Conditional |
| `has_back_door` | Back door keys mentioned | ❌ | **NEW:** Conditional |
| `front_door_keys` | "**{n}** key to the Front Door" | ✅ | Number |
| `back_door_keys` | "**{n}** key to the Back Door" | ✅ | Number |
| `key_replacement_fee` | "charged **${fee}** per key" | ✅ | Currency formatted |

**Plan for Keys Clause:**
```latex
IF include_keys_clause:
  "Tenant will be given"
  IF has_front_door: "{front_door_keys} key(s) to the Front Door"
  IF has_front_door AND has_back_door: " and "
  IF has_back_door: "{back_door_keys} key(s) to the Back Door"
  IF has_garage AND garage_spaces > 0: " and 1 garage door opener"
  ". Tenant shall be charged ${key_replacement_fee} per key..."
ELSE:
  Use generic keys statement or omit
```

---

## Section 38: ADDITIONAL TERMS

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `appliances_provided` | "Appliances: **{list}**" | ✅ | Only if provided |
| `has_attic` + `attic_usage` | "Attic Usage: **{usage}**" | ✅ | Only if has_attic |
| `lead_paint_disclosure` | Lead-Based Paint bullet | ✅ | If true |
| `lead_paint_year_built` | "built in **{year}**" | ✅ | Year property was built |
| `early_termination_allowed` | Early Termination bullet | ✅ | If true |
| `early_termination_notice_days` | "**{days}** days' notice" | ✅ | Number |
| `early_termination_fee_months` | "**{months}**-month rent fee" | ✅ | Number |
| `has_garage` | Garage Outlets bullet condition | ✅ | Conditional |
| `garage_outlets_prohibited` | "Garage Outlets: prohibited" | ✅ | If true |
| `has_basement` | (Not in PDF) | ❌ | Could add storage terms |

---

## Section 39: MOVE-OUT COST SCHEDULE

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `moveout_costs` array | List of cost items | ✅ | JSON parsed and formatted |
| - `item` | "**{name}:**" | ✅ | Bold item name |
| - `description` | "{description}" | ✅ | Plain text |
| - `amount` | "**${amount}**" | ✅ | Currency formatted |
| - `order` | Sort order | ✅ | Sorted by order field |

---

## SIGNATURES

| Form Field | PDF Location | Status | Implementation Notes |
|------------|--------------|--------|---------------------|
| `tenants` array | Tenant signature lines | ✅ | One line per tenant |
| `owner_name` | Landlord signature | 🔶 | Currently hardcoded |

---

## Fields NOT in PDF (Metadata Only)

| Form Field | Purpose |
|------------|---------|
| `lease_duration_months` | Used to calculate termination_date |
| `num_children` | Could add to Section 11 |
| `include_keys_clause` | Controls Section 34 visibility |
| `has_front_door` | Controls keys clause structure |
| `has_back_door` | Controls keys clause structure |
| `notes` | Internal notes, not in lease |
| `methamphetamine_disclosure` | Future: MO-specific disclosure |
| `moveout_inspection_rights` | Future: walkthrough rights clause |

---

## Implementation Priority

### Phase 1: Critical Updates (Pet Clause)
1. **Update Section 16 (Pets)** - Use new `pet_fee` and `pets` array format
2. **Format pet descriptions** - Group by type, include names and weights

### Phase 2: Keys Clause Enhancement
1. **Add conditional logic** for `include_keys_clause`
2. **Handle has_front_door/has_back_door** separately
3. **Add garage opener mention** if garage_spaces > 0

### Phase 3: Minor Improvements
1. **Payment method** - Use form value instead of hardcoded
2. **Owner name/address** - Use form values in Notice section
3. **Prorated rent** - Honor `show_prorated_rent` flag and custom language

### Phase 4: Future Enhancements
1. **Basement usage terms** - If has_basement
2. **Children count** - Add to occupants section
3. **Methamphetamine disclosure** - MO-specific
4. **Walkthrough rights** - Optional clause

---

## Code Location

- **Template Generator:** `backend/app/services/lease_generator_service.py`
- **Form State:** `frontend/app/(dashboard)/leases/page.tsx` lines 103-170
- **Backend Schema:** `backend/app/schemas/lease.py`
- **Sample Template:** `NE_res_agreement.tex`

---

**IMPORTANT:** No legal language will be altered without approval. All changes are "MadLib" style - inserting/removing values into existing clause structures.

