'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useLeases, MoveOutCostItem } from '@/lib/hooks/use-leases';
import { useProperties } from '@/lib/hooks/use-properties';
import { useTenants } from '@/lib/hooks/use-tenants';
import { useUnits } from '@/lib/hooks/use-units';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ArrowLeft, Loader2, AlertCircle, Save, ChevronDown, ChevronRight, CheckCircle2, Plus, X, Edit2 } from 'lucide-react';
import Link from 'next/link';

export default function LeaseCreatePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const propertyIdFromUrl = searchParams.get('property_id') || '';
  
  const { createLease } = useLeases();
  const { data: propertiesData } = useProperties();
  const properties = propertiesData?.items || [];
  
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Initialize form with defaults based on lease_defaults.py and actual lease patterns
  // Defaults from BASE_LEASE_DEFAULTS and STATE_LEASE_DEFAULTS (MO)
  const [formData, setFormData] = useState<any>({
    property_id: propertyIdFromUrl,
    state: 'MO',
    status: 'draft',
    lease_start: '',
    lease_end: '',
    monthly_rent: '',
    security_deposit: '',
    // From BASE_LEASE_DEFAULTS
    rent_due_day: '1',
    rent_due_by_day: '5',
    rent_due_by_time: '6pm',
    auto_convert_month_to_month: false, // Default False, but lease shows True - user can change
    max_occupants: '3', // Default 3, lease shows 1 - but 3 is more common
    max_adults: '2', // Default 2, lease shows 1 - but 2 is more common
    front_door_keys: '1',
    back_door_keys: '1',
    key_replacement_fee: '100.00', // Default 100, lease shows 50 - use default
    lead_paint_disclosure: true,
    early_termination_allowed: true,
    early_termination_notice_days: '60',
    early_termination_fee_months: '2',
    // From STATE_LEASE_DEFAULTS (MO)
    // Pattern: late_fee_day_11 = 150, late_fee_day_16 = 150 + 75 = 225, late_fee_day_21 = 225 + 75 = 300
    late_fee_day_1_10: '75.00',
    late_fee_day_11: '150.00',
    late_fee_day_16: '225.00', // late_fee_day_11 + 75
    late_fee_day_21: '300.00', // late_fee_day_16 + 75
    nsf_fee: '50.00', // MO default 50, lease shows 60 - use default
    disclosure_methamphetamine: false,
    // Common defaults based on actual lease
    payment_method: 'Turbo Tenant', // Common payment method
    utilities_tenant: 'All', // Default to "All", will auto-update if landlord utilities selected
    utilities_landlord: '', // Default empty
    pet_fee: '0.00', // Default 0, can be set if needed
    garage_spaces: '', // Property-specific
    offstreet_parking_spots: '1', // Common default
    garage_back_door_keys: '1', // If garage door opener, typically 1 key
    garage_door_opener_fee: '100.00', // Common fee
    appliances_provided: '', // Property-specific
    tenant_lawn_mowing: true, // Common default
    tenant_snow_removal: true, // Common default
    tenant_lawn_care: false, // Default False
    has_garage_door_opener: false, // Property-specific
    has_shared_driveway: false, // Property-specific
    show_prorated_rent: false, // Default False
    include_holding_fee_addendum: false, // Default False, lease shows True - user can change
    // Owner/Manager - defaults from actual lease (501 NE 67th Street)
    owner_name: 'S&M Axios Heartland Holdings, LLC',
    manager_name: 'Sarah Pappas',
    manager_address: '1606 S 208th St, Elkhorn, NE 68022',
  });
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['1', '2', '3', '4']));
  
  // Modal states
  const [showMoveoutCostsModal, setShowMoveoutCostsModal] = useState(false);
  const [showTenantsModal, setShowTenantsModal] = useState(false);
  const [showPetsModal, setShowPetsModal] = useState(false);
  
  // Utilities and appliances state
  const [landlordUtilities, setLandlordUtilities] = useState<string[]>([]);
  const [customUtility, setCustomUtility] = useState<string>('');
  const [useCustomUtility, setUseCustomUtility] = useState<boolean>(false);
  const [appliances, setAppliances] = useState<string[]>([]);
  
  // JSON columns state (like landlord_references)
  // Initialize with default moveout costs from lease_defaults.py
  const [moveoutCosts, setMoveoutCosts] = useState<MoveOutCostItem[]>([
    { item: 'Hardwood Floor Cleaning', description: 'Fee if hardwood floors are not returned in clean condition (includes vacuuming)', amount: '100.00', order: 1 },
    { item: 'Trash Removal Fee', description: 'Fee if Tenant fails to remove all trash', amount: '150.00', order: 2 },
    { item: 'Heavy Cleaning', description: 'For dirty appliances, bathrooms, or excessive filth', amount: '400.00', order: 3 },
    { item: 'Wall Repairs', description: 'Flat fee for filling/sanding/painting nail holes or minor wall damage (up to 10 standard holes). Extensive damage billed at cost.', amount: '150.00', order: 4 },
  ]);
  const [tenants, setTenants] = useState<Array<{ first_name: string; last_name: string; email?: string; phone?: string }>>([]);
  const [pets, setPets] = useState<Array<{ type: string; breed?: string; name?: string; weight?: string; isEmotionalSupport?: boolean }>>([]);
  
  // Available options
  const UTILITY_OPTIONS = ['Gas', 'Sewer', 'Water', 'Electricity', 'Trash'];
  const APPLIANCE_OPTIONS = ['Refrigerator', 'Range', 'Dishwasher', 'Microwave', 'Washer', 'Dryer', 'Garbage Disposal'];
  const PET_TYPE_OPTIONS = ['dog', 'cat', 'bird', 'fish', 'reptile'];
  
  // Fetch tenants and units for selected property
  const { data: tenantsData } = useTenants(
    formData.property_id ? { property_id: formData.property_id } : undefined
  );
  const availableTenants = tenantsData?.tenants || [];
  
  const { data: unitsData } = useUnits(formData.property_id || '');
  const units = unitsData?.items || [];
  
  const selectedProperty = properties.find(p => p.id === formData.property_id);
  const selectedUnit = units.find(u => u.id === formData.unit_id);
  
  // Pull monthly_rent from unit (if selected) or property, and set security_deposit to match
  useEffect(() => {
    if (selectedUnit?.current_monthly_rent) {
      // Unit has priority if selected
      const rent = selectedUnit.current_monthly_rent.toString();
      setFormData((prev: any) => ({
        ...prev,
        monthly_rent: rent,
        security_deposit: rent, // security_deposit defaults to monthly_rent
      }));
    } else if (selectedProperty?.current_monthly_rent) {
      // Fall back to property if no unit or unit has no rent
      const rent = selectedProperty.current_monthly_rent.toString();
      setFormData((prev: any) => ({
        ...prev,
        monthly_rent: rent,
        security_deposit: prev.security_deposit || rent, // Only set if not already set
      }));
    }
  }, [selectedUnit?.current_monthly_rent, selectedProperty?.current_monthly_rent, formData.unit_id]);
  
  // Initialize utilities_tenant to "All" by default
  useEffect(() => {
    if (!formData.utilities_tenant) {
      setFormData((prev: any) => ({ ...prev, utilities_tenant: 'All' }));
    }
  }, []);
  
  // Pull disclosure_lead_paint from property year_built when property is selected
  useEffect(() => {
    if (selectedProperty?.year_built && !formData.disclosure_lead_paint) {
      setFormData((prev: any) => ({ ...prev, disclosure_lead_paint: selectedProperty.year_built?.toString() || '' }));
    }
  }, [selectedProperty?.year_built]);
  
  // Update state-specific defaults when state changes
  useEffect(() => {
    if (formData.state === 'MO') {
      // MO-specific defaults - pattern: late_fee_day_11 = 150, late_fee_day_16 = 225 (150+75), late_fee_day_21 = 300 (225+75)
      setFormData((prev: any) => ({
        ...prev,
        late_fee_day_1_10: prev.late_fee_day_1_10 || '75.00',
        late_fee_day_11: prev.late_fee_day_11 || '150.00',
        late_fee_day_16: prev.late_fee_day_16 || '225.00', // late_fee_day_11 + 75
        late_fee_day_21: prev.late_fee_day_21 || '300.00', // late_fee_day_16 + 75
        nsf_fee: prev.nsf_fee || '50.00',
        disclosure_methamphetamine: false,
      }));
    } else if (formData.state === 'NE') {
      // NE-specific defaults - same pattern
      setFormData((prev: any) => ({
        ...prev,
        late_fee_day_1_10: prev.late_fee_day_1_10 || '75.00',
        late_fee_day_11: prev.late_fee_day_11 || '150.00',
        late_fee_day_16: prev.late_fee_day_16 || '225.00', // late_fee_day_11 + 75
        late_fee_day_21: prev.late_fee_day_21 || '300.00', // late_fee_day_16 + 75
        nsf_fee: prev.nsf_fee || '60.00',
        disclosure_methamphetamine: false,
      }));
    }
  }, [formData.state]);
  
  // Auto-calculate late_fee_day_16 and late_fee_day_21 when late_fee_day_11 changes
  useEffect(() => {
    if (formData.late_fee_day_11) {
      const day11 = parseFloat(formData.late_fee_day_11);
      if (!isNaN(day11)) {
        const day16 = day11 + 75; // late_fee_day_11 + 75
        const day21 = day16 + 75; // late_fee_day_16 + 75
        setFormData((prev: any) => ({
          ...prev,
          late_fee_day_16: prev.late_fee_day_16 || day16.toFixed(2),
          late_fee_day_21: prev.late_fee_day_21 || day21.toFixed(2),
        }));
      }
    }
  }, [formData.late_fee_day_11]);
  
  // Helper function to check if a field has a value
  const hasValue = (value: any): boolean => {
    if (value === null || value === undefined) return false;
    if (typeof value === 'string') return value.trim() !== '';
    if (typeof value === 'boolean') return true;
    if (typeof value === 'number') return value !== 0;
    return true;
  };
  
  // Get section stats for completion indicator
  const getSectionStats = (sectionId: string, fields: string[]) => {
    let total = 0;
    let filled = 0;
    
    fields.forEach(field => {
      // Skip checkboxes that don't count
      if (field === 'show_prorated_rent' || field === 'has_shared_driveway') {
        return;
      }
      
      // Section 1: Exclude lease_date from count
      if (sectionId === '1' && field === 'lease_date') {
        return;
      }
      
      // Section 2: Only count shared_driveway_with if has_shared_driveway is checked
      if (sectionId === '2' && field === 'shared_driveway_with') {
        if (formData.has_shared_driveway) {
          total++;
          if (hasValue(formData[field])) filled++;
        }
        return;
      }
      
      // Section 3: If show_prorated_rent is clicked, then prorated_first_month_rent must be filled
      if (sectionId === '3' && field === 'prorated_first_month_rent') {
        if (formData.show_prorated_rent) {
          total++;
          if (hasValue(formData[field])) filled++;
        }
        return;
      }
      
      // Section 4: If include_holding_fee_addendum is clicked, then holding_fee_amount and holding_fee_date must be filled
      if (sectionId === '4' && (field === 'holding_fee_amount' || field === 'holding_fee_date')) {
        if (formData.include_holding_fee_addendum) {
          total++;
          if (hasValue(formData[field])) filled++;
        }
        return;
      }
      
      // Section 6: utilities_landlord and appliances_provided are handled specially
      if (sectionId === '6') {
        if (field === 'utilities_landlord') {
          total++;
          if (landlordUtilities.length > 0 || useCustomUtility) filled++;
          return;
        }
        if (field === 'appliances_provided') {
          total++;
          if (appliances.length > 0 || hasValue(formData[field])) filled++;
          return;
        }
      }
      
      // Section 10: Three fields conditional to if early_termination_allowed is clicked
      if (sectionId === '10' && (field === 'early_termination_notice_days' || field === 'early_termination_fee_amount' || field === 'early_termination_fee_months')) {
        if (formData.early_termination_allowed) {
          total++;
          if (hasValue(formData[field])) filled++;
        }
        return;
      }
      
      // Section 11: moveout_costs is an array
      if (sectionId === '11' && field === 'moveout_costs') {
        total++;
        if (moveoutCosts.length > 0) filled++;
        return;
      }
      
      // Default: count all fields
      total++;
      if (hasValue(formData[field])) filled++;
    });
    
    return { total, filled };
  };
  
  const toggleSection = (sectionId: string) => {
    setExpandedSections(prev => {
      const newSet = new Set(prev);
      if (newSet.has(sectionId)) {
        newSet.delete(sectionId);
      } else {
        newSet.add(sectionId);
      }
      return newSet;
    });
  };
  
  // Handle landlord utilities change
  const handleLandlordUtilitiesChange = (utility: string, checked: boolean) => {
    const newUtilities = checked 
      ? [...landlordUtilities, utility]
      : landlordUtilities.filter(u => u !== utility);
    setLandlordUtilities(newUtilities);
    setFormData({ ...formData, utilities_landlord: newUtilities.join(', ') });
    
    // Auto-generate tenant utilities: "All except [landlord utilities]"
    if (newUtilities.length > 0) {
      setFormData((prev: any) => ({ ...prev, utilities_tenant: `All except ${newUtilities.join(', ')}` }));
    } else {
      setFormData((prev: any) => ({ ...prev, utilities_tenant: 'All' }));
    }
  };
  
  // Handle custom utility change
  const handleCustomUtilityChange = (value: string) => {
    setCustomUtility(value);
    if (useCustomUtility && value) {
      updateUtilitiesString(landlordUtilities, value);
    } else if (!useCustomUtility) {
      updateUtilitiesString(landlordUtilities, '');
    }
  };
  
  // Handle custom utility checkbox
  const handleCustomUtilityToggle = (checked: boolean) => {
    setUseCustomUtility(checked);
    if (checked && customUtility) {
      updateUtilitiesString(landlordUtilities, customUtility);
    } else {
      updateUtilitiesString(landlordUtilities, '');
    }
  };
  
  // Update utilities string helper
  const updateUtilitiesString = (utilities: string[], custom: string) => {
    const allUtilities = custom ? [...utilities, custom] : utilities;
    setFormData({ ...formData, utilities_landlord: allUtilities.join(', ') });
    
    // Auto-generate tenant utilities: "All except [landlord utilities]"
    if (allUtilities.length > 0) {
      setFormData((prev: any) => ({ ...prev, utilities_tenant: `All except ${allUtilities.join(', ')}` }));
    } else {
      setFormData((prev: any) => ({ ...prev, utilities_tenant: 'All' }));
    }
  };
  
  // Handle appliances change
  const handleAppliancesChange = (appliance: string, checked: boolean) => {
    const newAppliances = checked 
      ? [...appliances, appliance]
      : appliances.filter(a => a !== appliance);
    setAppliances(newAppliances);
    setFormData({ ...formData, appliances_provided: newAppliances.join(', ') });
  };
  
  // Initialize utilities and appliances from formData
  useEffect(() => {
    if (formData.utilities_landlord) {
      const utilities = formData.utilities_landlord.split(',').map((u: string) => u.trim()).filter((u: string) => UTILITY_OPTIONS.includes(u));
      setLandlordUtilities(utilities);
    }
    if (formData.appliances_provided) {
      const appliancesList = formData.appliances_provided.split(',').map((a: string) => a.trim()).filter((a: string) => APPLIANCE_OPTIONS.includes(a));
      setAppliances(appliancesList);
    }
  }, [formData.utilities_landlord, formData.appliances_provided]);
  
  // Pull disclosure_lead_paint from property year_built
  useEffect(() => {
    if (selectedProperty?.year_built && !formData.disclosure_lead_paint) {
      setFormData((prev: any) => ({ ...prev, disclosure_lead_paint: selectedProperty.year_built?.toString() || '' }));
    }
  }, [selectedProperty?.year_built]);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      // Validate required fields
      if (!formData.property_id) {
        setError('Property is required');
        setSaving(false);
        return;
      }
      if (!formData.state) {
        setError('State is required');
        setSaving(false);
        return;
      }
      if (!formData.lease_start) {
        setError('Lease start date is required');
        setSaving(false);
        return;
      }
      if (!formData.lease_end) {
        setError('Lease end date is required');
        setSaving(false);
        return;
      }
      if (!formData.monthly_rent || parseFloat(formData.monthly_rent) <= 0) {
        setError('Monthly rent is required and must be greater than 0');
        setSaving(false);
        return;
      }
      if (!formData.security_deposit || parseFloat(formData.security_deposit) < 0) {
        setError('Security deposit is required and must be 0 or greater');
        setSaving(false);
        return;
      }
      
      // Validate state-specific required fields
      if (formData.state === 'MO' && !formData.owner_name) {
        setError('Owner name is required for Missouri leases');
        setSaving(false);
        return;
      }
      
      // Validate tenants are required for create
      if (tenants.length === 0) {
        setError('At least one tenant is required');
        setSaving(false);
        return;
      }

      // Build create payload
      const createPayload: any = {
        property_id: formData.property_id,
        unit_id: formData.unit_id || undefined,
        status: formData.status || 'draft',
        state: formData.state as 'NE' | 'MO',
        lease_start: formData.lease_start,
        lease_end: formData.lease_end,
        monthly_rent: parseFloat(formData.monthly_rent),
        security_deposit: parseFloat(formData.security_deposit),
      };
      
      // Optional dates
      if (formData.lease_date) createPayload.lease_date = formData.lease_date;
      
      // Financial - in LEASES_FIELD_ORDER: rent_due_by_time, payment_method, prorated_first_month_rent
      if (formData.rent_due_by_time) createPayload.rent_due_by_time = formData.rent_due_by_time;
      if (formData.payment_method) createPayload.payment_method = formData.payment_method;
      if (formData.prorated_first_month_rent) createPayload.prorated_first_month_rent = parseFloat(formData.prorated_first_month_rent);
      
      // Late fees - in order: late_fee_day_1_10, late_fee_day_11, late_fee_day_16, late_fee_day_21, nsf_fee
      if (formData.late_fee_day_1_10) createPayload.late_fee_day_1_10 = parseFloat(formData.late_fee_day_1_10);
      if (formData.late_fee_day_11) createPayload.late_fee_day_11 = parseFloat(formData.late_fee_day_11);
      if (formData.late_fee_day_16) createPayload.late_fee_day_16 = parseFloat(formData.late_fee_day_16);
      if (formData.late_fee_day_21) createPayload.late_fee_day_21 = parseFloat(formData.late_fee_day_21);
      if (formData.nsf_fee) createPayload.nsf_fee = parseFloat(formData.nsf_fee);
      
      // Holding fee - in order: holding_fee_amount, holding_fee_date
      if (formData.holding_fee_amount) createPayload.holding_fee_amount = parseFloat(formData.holding_fee_amount);
      if (formData.holding_fee_date) createPayload.holding_fee_date = formData.holding_fee_date;
      
      // Utilities - in order: utilities_tenant, utilities_landlord
      if (formData.utilities_tenant) createPayload.utilities_tenant = formData.utilities_tenant;
      if (formData.utilities_landlord) createPayload.utilities_landlord = formData.utilities_landlord;
      
      // Pets - in order: pet_fee, pets
      if (formData.pet_fee) createPayload.pet_fee = parseFloat(formData.pet_fee);
      // pets will be added below in JSON fields section
      
      // Parking - in order: garage_spaces
      if (formData.garage_spaces) createPayload.garage_spaces = parseFloat(formData.garage_spaces);
      
      // Keys - in order: key_replacement_fee
      if (formData.key_replacement_fee) createPayload.key_replacement_fee = parseFloat(formData.key_replacement_fee);
      
      // Other - in order: shared_driveway_with, garage_door_opener_fee, appliances_provided, early_termination_fee_amount
      if (formData.shared_driveway_with) createPayload.shared_driveway_with = formData.shared_driveway_with;
      if (formData.garage_door_opener_fee) createPayload.garage_door_opener_fee = parseFloat(formData.garage_door_opener_fee);
      if (formData.appliances_provided) createPayload.appliances_provided = formData.appliances_provided;
      
      // Calculate early termination fee if not provided (from lease_defaults.py logic)
      if (formData.early_termination_allowed) {
        if (formData.early_termination_fee_amount) {
          createPayload.early_termination_fee_amount = parseFloat(formData.early_termination_fee_amount);
        } else if (formData.monthly_rent) {
          // Auto-calculate: monthly_rent * early_termination_fee_months (default 2)
          const months = parseInt(formData.early_termination_fee_months) || 2;
          createPayload.early_termination_fee_amount = parseFloat(formData.monthly_rent) * months;
        }
      }
      
      // Owner/Manager - in order: owner_name, manager_name, manager_address
      if (formData.owner_name) createPayload.owner_name = formData.owner_name;
      if (formData.manager_name) createPayload.manager_name = formData.manager_name;
      if (formData.manager_address) createPayload.manager_address = formData.manager_address;
      
      // Notes
      if (formData.notes) createPayload.notes = formData.notes;
      
      // JSON fields - all handled the same way (like landlord_references)
      // Move-out costs: send as array of objects
      if (moveoutCosts.length > 0) {
        createPayload.moveout_costs = moveoutCosts.map(cost => ({
          item: cost.item,
          description: cost.description || '',
          amount: parseFloat(cost.amount.toString()) || 0,
          order: cost.order || 1
        }));
      }
      
      // Tenants: send as array of objects (required for create)
      createPayload.tenants = tenants.map(t => ({
        first_name: t.first_name,
        last_name: t.last_name,
        email: t.email,
        phone: t.phone
      }));
      
      // Pets: send as array of objects
      if (pets.length > 0) {
        createPayload.pets = pets.map(pet => ({
          type: pet.type,
          breed: pet.breed,
          name: pet.name,
          weight: pet.weight,
          isEmotionalSupport: pet.isEmotionalSupport || false
        }));
      }
      
      // Booleans
      createPayload.auto_convert_month_to_month = formData.auto_convert_month_to_month || false;
      createPayload.show_prorated_rent = formData.show_prorated_rent || false;
      createPayload.include_holding_fee_addendum = formData.include_holding_fee_addendum || false;
      createPayload.has_shared_driveway = formData.has_shared_driveway || false;
      createPayload.tenant_lawn_mowing = formData.tenant_lawn_mowing ?? true;
      createPayload.tenant_snow_removal = formData.tenant_snow_removal ?? true;
      createPayload.tenant_lawn_care = formData.tenant_lawn_care || false;
      createPayload.has_garage_door_opener = formData.has_garage_door_opener || false;
      createPayload.lead_paint_disclosure = formData.lead_paint_disclosure ?? true;
      createPayload.early_termination_allowed = formData.early_termination_allowed ?? true;
      createPayload.disclosure_methamphetamine = formData.disclosure_methamphetamine || false;
      
      // Integers
      if (formData.rent_due_day) createPayload.rent_due_day = parseInt(formData.rent_due_day);
      if (formData.rent_due_by_day) createPayload.rent_due_by_day = parseInt(formData.rent_due_by_day);
      if (formData.max_occupants) createPayload.max_occupants = parseInt(formData.max_occupants);
      if (formData.max_adults) createPayload.max_adults = parseInt(formData.max_adults);
      if (formData.offstreet_parking_spots) createPayload.offstreet_parking_spots = parseInt(formData.offstreet_parking_spots);
      if (formData.front_door_keys) createPayload.front_door_keys = parseInt(formData.front_door_keys);
      if (formData.back_door_keys) createPayload.back_door_keys = parseInt(formData.back_door_keys);
      if (formData.garage_back_door_keys) createPayload.garage_back_door_keys = parseInt(formData.garage_back_door_keys);
      if (formData.disclosure_lead_paint) createPayload.disclosure_lead_paint = parseInt(formData.disclosure_lead_paint);
      if (formData.early_termination_notice_days) createPayload.early_termination_notice_days = parseInt(formData.early_termination_notice_days);
      if (formData.early_termination_fee_months) createPayload.early_termination_fee_months = parseInt(formData.early_termination_fee_months);

      const newLease = await createLease(createPayload);
      
      // Invalidate cache to ensure fresh data on the leases list page
      await queryClient.invalidateQueries({ queryKey: ['leases'] });
      
      router.push('/leases?refresh=true');
    } catch (err: any) {
      console.error('Error creating lease:', err);
      setError(err.message || 'Failed to create lease');
    } finally {
      setSaving(false);
    }
  };
  
  // Section field definitions (same as edit page)
  const sectionFields: Record<string, string[]> = {
    '1': ['lease_date', 'owner_name', 'manager_name', 'manager_address', 'tenants'],
    '2': ['property_id', 'unit_id', 'state', 'max_occupants', 'max_adults', 'garage_spaces', 'offstreet_parking_spots', 'has_shared_driveway', 'shared_driveway_with'],
    '3': ['lease_start', 'lease_end', 'auto_convert_month_to_month', 'show_prorated_rent', 'prorated_first_month_rent'],
    '4': ['monthly_rent', 'rent_due_day', 'rent_due_by_day', 'rent_due_by_time', 'payment_method', 'security_deposit', 'include_holding_fee_addendum', 'holding_fee_amount', 'holding_fee_date'],
    '5': ['late_fee_day_1_10', 'late_fee_day_11', 'late_fee_day_16', 'late_fee_day_21', 'nsf_fee'],
    '6': ['utilities_tenant', 'utilities_landlord', 'appliances_provided', 'tenant_lawn_mowing', 'tenant_snow_removal', 'tenant_lawn_care'],
    '7': ['pet_fee', 'pets'],
    '8': ['front_door_keys', 'back_door_keys', 'has_garage_door_opener', 'garage_back_door_keys', 'key_replacement_fee', 'garage_door_opener_fee'],
    '9': ['lead_paint_disclosure', 'disclosure_lead_paint', 'disclosure_methamphetamine'],
    '10': ['early_termination_allowed', 'early_termination_notice_days', 'early_termination_fee_amount', 'early_termination_fee_months'],
    '11': ['moveout_costs', 'notes'],
  };
  
  return (
    <div className="p-4 max-w-6xl mx-auto">
      <div className="mb-4 flex items-center gap-3">
        <Link href="/leases">
          <Button variant="ghost" size="sm" className="h-7 text-xs">
            <ArrowLeft className="h-3 w-3 mr-1" />
            Back
          </Button>
        </Link>
        <h1 className="text-lg font-bold text-gray-900">Create New Lease</h1>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-800 flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {error}
    </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Section 1: Preamble & Identifying Parties */}
        <Card>
          <CardHeader 
            className="py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors"
            onClick={() => toggleSection('1')}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {expandedSections.has('1') ? (
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                )}
                <CardTitle className="text-sm">1. Preamble & Identifying Parties</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                {(() => {
                  const stats = getSectionStats('1', sectionFields['1']);
                  const hasValues = stats.filled > 0;
                  return (
                    <>
                      {hasValues && <CheckCircle2 className="h-4 w-4 text-blue-500" />}
                      <span className="text-xs text-gray-500">
                        {stats.filled}/{stats.total}
                      </span>
                    </>
                  );
                })()}
              </div>
            </div>
          </CardHeader>
          {expandedSections.has('1') && (
            <CardContent className="px-3 pb-3 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="property_id" className="text-xs">Property *</Label>
                  <Select
                    value={formData.property_id}
                    onValueChange={(value) => {
                      setFormData({ ...formData, property_id: value, unit_id: '' });
                    }}
                    required
                  >
                    <SelectTrigger className="text-sm h-8 mt-1">
                      <SelectValue placeholder="Select property" />
                    </SelectTrigger>
                    <SelectContent>
                      {properties.map((prop) => (
                        <SelectItem key={prop.id} value={prop.id}>
                          {prop.display_name || prop.address_line1}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {units.length > 0 && (
                  <div>
                    <Label htmlFor="unit_id" className="text-xs">Unit</Label>
                    <Select
                      value={formData.unit_id || 'none'}
                      onValueChange={(value) => setFormData({ ...formData, unit_id: value === 'none' ? '' : value })}
                    >
                      <SelectTrigger className="text-sm h-8 mt-1">
                        <SelectValue placeholder="Select unit" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">None</SelectItem>
                        {units.filter(u => u.property_id === formData.property_id).map((unit) => (
                          <SelectItem key={unit.id} value={unit.id}>
                            {unit.unit_number || unit.id}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                <div>
                  <Label htmlFor="state" className="text-xs">State *</Label>
                  <Select
                    value={formData.state}
                    onValueChange={(value) => setFormData({ ...formData, state: value })}
                    required
                  >
                    <SelectTrigger className="text-sm h-8 mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="MO">Missouri (MO)</SelectItem>
                      <SelectItem value="NE">Nebraska (NE)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label htmlFor="lease_date" className="text-xs">Lease Date</Label>
                  <Input
                    id="lease_date"
                    type="date"
                    value={formData.lease_date || ''}
                    onChange={(e) => setFormData({ ...formData, lease_date: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="owner_name" className="text-xs">Owner Name {formData.state === 'MO' && '*'}</Label>
                  <Input
                    id="owner_name"
                    value={formData.owner_name || ''}
                    onChange={(e) => setFormData({ ...formData, owner_name: e.target.value })}
                    className="text-sm h-8 mt-1"
                    required={formData.state === 'MO'}
                  />
                </div>
                <div>
                  <Label htmlFor="manager_name" className="text-xs">Manager Name</Label>
                  <Input
                    id="manager_name"
                    value={formData.manager_name || ''}
                    onChange={(e) => setFormData({ ...formData, manager_name: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
              </div>
              
              <div>
                <Label htmlFor="manager_address" className="text-xs">Manager Address</Label>
                <Textarea
                  id="manager_address"
                  value={formData.manager_address || ''}
                  onChange={(e) => setFormData({ ...formData, manager_address: e.target.value })}
                  rows={2}
                  className="text-sm mt-1"
                />
              </div>
              
              <div>
                <Label className="text-xs mb-2">Tenants *</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs mb-2"
                  onClick={() => setShowTenantsModal(true)}
                >
                  <Edit2 className="h-3 w-3 mr-1" />
                  Edit Tenants ({tenants.length})
                </Button>
                {tenants.length > 0 && (
                  <div className="text-xs text-gray-600">
                    {tenants.map(t => `${t.first_name} ${t.last_name}`).join(', ')}
                  </div>
                )}
              </div>
            </CardContent>
          )}
        </Card>

        {/* Continue with all other sections from edit page... */}
        {/* For brevity, I'll add the key sections. The rest should follow the same pattern as edit page */}
        
        {/* Section 2: Property Description */}
        <Card>
          <CardHeader 
            className="py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors"
            onClick={() => toggleSection('2')}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {expandedSections.has('2') ? (
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                )}
                <CardTitle className="text-sm">2. Property Description</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                {(() => {
                  const stats = getSectionStats('2', sectionFields['2']);
                  const hasValues = stats.filled > 0;
                  return (
                    <>
                      {hasValues && <CheckCircle2 className="h-4 w-4 text-blue-500" />}
                      <span className="text-xs text-gray-500">
                        {stats.filled}/{stats.total}
                      </span>
                    </>
                  );
                })()}
              </div>
            </div>
          </CardHeader>
          {expandedSections.has('2') && (
            <CardContent className="px-3 pb-3 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="max_occupants" className="text-xs">Max Occupants</Label>
                  <Input
                    id="max_occupants"
                    type="number"
                    value={formData.max_occupants || ''}
                    onChange={(e) => setFormData({ ...formData, max_occupants: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="max_adults" className="text-xs">Max Adults</Label>
                  <Input
                    id="max_adults"
                    type="number"
                    value={formData.max_adults || ''}
                    onChange={(e) => setFormData({ ...formData, max_adults: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="garage_spaces" className="text-xs">Garage Spaces</Label>
                  <Input
                    id="garage_spaces"
                    type="number"
                    step="0.5"
                    value={formData.garage_spaces || ''}
                    onChange={(e) => setFormData({ ...formData, garage_spaces: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="offstreet_parking_spots" className="text-xs">Off-Street Parking Spots</Label>
                  <Input
                    id="offstreet_parking_spots"
                    type="number"
                    value={formData.offstreet_parking_spots || ''}
                    onChange={(e) => setFormData({ ...formData, offstreet_parking_spots: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="has_shared_driveway"
                  checked={formData.has_shared_driveway || false}
                  onChange={(e) => setFormData({ ...formData, has_shared_driveway: e.target.checked })}
                  className="rounded h-3 w-3"
                />
                <Label htmlFor="has_shared_driveway" className="text-xs">Has Shared Driveway</Label>
              </div>
              
              {formData.has_shared_driveway && (
                <div>
                  <Label htmlFor="shared_driveway_with" className="text-xs">Shared Driveway With</Label>
                  <Input
                    id="shared_driveway_with"
                    value={formData.shared_driveway_with || ''}
                    onChange={(e) => setFormData({ ...formData, shared_driveway_with: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
              )}
            </CardContent>
          )}
        </Card>

        {/* Section 3: Term of Tenancy */}
        <Card>
          <CardHeader 
            className="py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors"
            onClick={() => toggleSection('3')}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {expandedSections.has('3') ? (
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                )}
                <CardTitle className="text-sm">3. Term of Tenancy</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                {(() => {
                  const stats = getSectionStats('3', sectionFields['3']);
                  const hasValues = stats.filled > 0;
                  return (
                    <>
                      {hasValues && <CheckCircle2 className="h-4 w-4 text-blue-500" />}
                      <span className="text-xs text-gray-500">
                        {stats.filled}/{stats.total}
                      </span>
                    </>
                  );
                })()}
              </div>
            </div>
          </CardHeader>
          {expandedSections.has('3') && (
            <CardContent className="px-3 pb-3 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="lease_start" className="text-xs">Lease Start *</Label>
                  <Input
                    id="lease_start"
                    type="date"
                    value={formData.lease_start || ''}
                    onChange={(e) => setFormData({ ...formData, lease_start: e.target.value })}
                    className="text-sm h-8 mt-1"
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="lease_end" className="text-xs">Lease End *</Label>
                  <Input
                    id="lease_end"
                    type="date"
                    value={formData.lease_end || ''}
                    onChange={(e) => setFormData({ ...formData, lease_end: e.target.value })}
                    className="text-sm h-8 mt-1"
                    required
                  />
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="auto_convert_month_to_month"
                  checked={formData.auto_convert_month_to_month || false}
                  onChange={(e) => setFormData({ ...formData, auto_convert_month_to_month: e.target.checked })}
                  className="rounded h-3 w-3"
                />
                <Label htmlFor="auto_convert_month_to_month" className="text-xs">Auto-Convert to Month-to-Month</Label>
              </div>
              
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="show_prorated_rent"
                  checked={formData.show_prorated_rent || false}
                  onChange={(e) => setFormData({ ...formData, show_prorated_rent: e.target.checked })}
                  className="rounded h-3 w-3"
                />
                <Label htmlFor="show_prorated_rent" className="text-xs">Show Prorated Rent</Label>
              </div>
              
              {formData.show_prorated_rent && (
                <div>
                  <Label htmlFor="prorated_first_month_rent" className="text-xs">Prorated First Month Rent</Label>
                  <Input
                    id="prorated_first_month_rent"
                    type="number"
                    step="0.01"
                    value={formData.prorated_first_month_rent || ''}
                    onChange={(e) => setFormData({ ...formData, prorated_first_month_rent: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
              )}
            </CardContent>
          )}
        </Card>

        {/* Section 4: Rent & Financial Obligations */}
        <Card>
          <CardHeader 
            className="py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors"
            onClick={() => toggleSection('4')}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {expandedSections.has('4') ? (
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                )}
                <CardTitle className="text-sm">4. Rent & Financial Obligations</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                {(() => {
                  const stats = getSectionStats('4', sectionFields['4']);
                  const hasValues = stats.filled > 0;
                  return (
                    <>
                      {hasValues && <CheckCircle2 className="h-4 w-4 text-blue-500" />}
                      <span className="text-xs text-gray-500">
                        {stats.filled}/{stats.total}
                      </span>
                    </>
                  );
                })()}
              </div>
            </div>
          </CardHeader>
          {expandedSections.has('4') && (
            <CardContent className="px-3 pb-3 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="monthly_rent" className="text-xs">Monthly Rent *</Label>
                  <Input
                    id="monthly_rent"
                    type="number"
                    step="0.01"
                    value={formData.monthly_rent || ''}
                    onChange={(e) => setFormData({ ...formData, monthly_rent: e.target.value })}
                    className="text-sm h-8 mt-1"
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="security_deposit" className="text-xs">Security Deposit *</Label>
                  <Input
                    id="security_deposit"
                    type="number"
                    step="0.01"
                    value={formData.security_deposit || ''}
                    onChange={(e) => setFormData({ ...formData, security_deposit: e.target.value })}
                    className="text-sm h-8 mt-1"
                    required
                  />
                </div>
                <div>
                  <Label htmlFor="rent_due_day" className="text-xs">Rent Due Day</Label>
                  <Input
                    id="rent_due_day"
                    type="number"
                    min="1"
                    max="31"
                    value={formData.rent_due_day || ''}
                    onChange={(e) => setFormData({ ...formData, rent_due_day: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="rent_due_by_day" className="text-xs">Rent Due By Day</Label>
                  <Input
                    id="rent_due_by_day"
                    type="number"
                    min="1"
                    max="31"
                    value={formData.rent_due_by_day || ''}
                    onChange={(e) => setFormData({ ...formData, rent_due_by_day: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="rent_due_by_time" className="text-xs">Rent Due By Time</Label>
                  <Input
                    id="rent_due_by_time"
                    value={formData.rent_due_by_time || ''}
                    onChange={(e) => setFormData({ ...formData, rent_due_by_time: e.target.value })}
                    placeholder="e.g., 6pm"
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="payment_method" className="text-xs">Payment Method</Label>
                  <Input
                    id="payment_method"
                    value={formData.payment_method || ''}
                    onChange={(e) => setFormData({ ...formData, payment_method: e.target.value })}
                    placeholder="e.g., Turbo Tenant"
                    className="text-sm h-8 mt-1"
                  />
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="include_holding_fee_addendum"
                  checked={formData.include_holding_fee_addendum || false}
                  onChange={(e) => setFormData({ ...formData, include_holding_fee_addendum: e.target.checked })}
                  className="rounded h-3 w-3"
                />
                <Label htmlFor="include_holding_fee_addendum" className="text-xs">Include Holding Fee Addendum</Label>
              </div>
              
              {formData.include_holding_fee_addendum && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor="holding_fee_amount" className="text-xs">Holding Fee Amount</Label>
                    <Input
                      id="holding_fee_amount"
                      type="number"
                      step="0.01"
                      value={formData.holding_fee_amount || ''}
                      onChange={(e) => setFormData({ ...formData, holding_fee_amount: e.target.value })}
                      className="text-sm h-8 mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="holding_fee_date" className="text-xs">Holding Fee Date</Label>
                    <Input
                      id="holding_fee_date"
                      type="date"
                      value={formData.holding_fee_date || ''}
                      onChange={(e) => setFormData({ ...formData, holding_fee_date: e.target.value })}
                      className="text-sm h-8 mt-1"
                    />
                  </div>
                </div>
              )}
            </CardContent>
          )}
        </Card>

        {/* Add remaining sections - I'll add key ones, rest follow same pattern */}
        {/* Section 5: Late Fees & Penalties */}
        <Card>
          <CardHeader 
            className="py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors"
            onClick={() => toggleSection('5')}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {expandedSections.has('5') ? (
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                )}
                <CardTitle className="text-sm">5. Late Fees & Penalties</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                {(() => {
                  const stats = getSectionStats('5', sectionFields['5']);
                  const hasValues = stats.filled > 0;
                  return (
                    <>
                      {hasValues && <CheckCircle2 className="h-4 w-4 text-blue-500" />}
                      <span className="text-xs text-gray-500">
                        {stats.filled}/{stats.total}
                      </span>
                    </>
                  );
                })()}
              </div>
            </div>
          </CardHeader>
          {expandedSections.has('5') && (
            <CardContent className="px-3 pb-3 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="late_fee_day_1_10" className="text-xs">Late Fee Day 1-10</Label>
                  <Input
                    id="late_fee_day_1_10"
                    type="number"
                    step="0.01"
                    value={formData.late_fee_day_1_10 || ''}
                    onChange={(e) => setFormData({ ...formData, late_fee_day_1_10: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="late_fee_day_11" className="text-xs">Late Fee Day 11</Label>
                  <Input
                    id="late_fee_day_11"
                    type="number"
                    step="0.01"
                    value={formData.late_fee_day_11 || ''}
                    onChange={(e) => setFormData({ ...formData, late_fee_day_11: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="late_fee_day_16" className="text-xs">Late Fee Day 16</Label>
                  <Input
                    id="late_fee_day_16"
                    type="number"
                    step="0.01"
                    value={formData.late_fee_day_16 || ''}
                    onChange={(e) => setFormData({ ...formData, late_fee_day_16: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="late_fee_day_21" className="text-xs">Late Fee Day 21</Label>
                  <Input
                    id="late_fee_day_21"
                    type="number"
                    step="0.01"
                    value={formData.late_fee_day_21 || ''}
                    onChange={(e) => setFormData({ ...formData, late_fee_day_21: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="nsf_fee" className="text-xs">NSF Fee</Label>
                  <Input
                    id="nsf_fee"
                    type="number"
                    step="0.01"
                    value={formData.nsf_fee || ''}
                    onChange={(e) => setFormData({ ...formData, nsf_fee: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
              </div>
            </CardContent>
          )}
        </Card>

        {/* Section 6: Utilities, Appliances & Maintenance */}
        <Card>
          <CardHeader 
            className="py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors"
            onClick={() => toggleSection('6')}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {expandedSections.has('6') ? (
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                )}
                <CardTitle className="text-sm">6. Utilities, Appliances & Maintenance</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                {(() => {
                  const stats = getSectionStats('6', sectionFields['6']);
                  const hasValues = stats.filled > 0;
                  return (
                    <>
                      {hasValues && <CheckCircle2 className="h-4 w-4 text-blue-500" />}
                      <span className="text-xs text-gray-500">
                        {stats.filled}/{stats.total}
                      </span>
                    </>
                  );
                })()}
              </div>
            </div>
          </CardHeader>
          {expandedSections.has('6') && (
            <CardContent className="px-3 pb-3 space-y-3">
              <div>
                <Label className="text-xs mb-2">Tenant Utilities</Label>
                <Input
                  value={formData.utilities_tenant || 'All'}
                  readOnly
                  className="text-sm h-8 bg-gray-50"
                />
                <p className="text-xs text-gray-500 mt-1">Auto-generated based on landlord utilities</p>
              </div>
              
              <div>
                <Label className="text-xs mb-2">Landlord Utilities</Label>
                <div className="space-y-2">
                  {UTILITY_OPTIONS.map((utility) => (
                    <label key={utility} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={landlordUtilities.includes(utility)}
                        onChange={(e) => handleLandlordUtilitiesChange(utility, e.target.checked)}
                        className="rounded h-3 w-3"
                      />
                      <span className="text-xs">{utility}</span>
                    </label>
                  ))}
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={useCustomUtility}
                      onChange={(e) => handleCustomUtilityToggle(e.target.checked)}
                      className="rounded h-3 w-3"
                    />
                    <span className="text-xs">Type a free text utility</span>
                  </div>
                  {useCustomUtility && (
                    <Input
                      value={customUtility}
                      onChange={(e) => handleCustomUtilityChange(e.target.value)}
                      placeholder="Enter custom utility"
                      className="text-sm h-8"
                    />
                  )}
                </div>
              </div>
              
              <div>
                <Label className="text-xs mb-2">Tenant Provided Maintenance</Label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formData.tenant_lawn_mowing ?? true}
                      onChange={(e) => setFormData({ ...formData, tenant_lawn_mowing: e.target.checked })}
                      className="rounded h-3 w-3"
                    />
                    <span className="text-xs">Mowing</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formData.tenant_snow_removal ?? true}
                      onChange={(e) => setFormData({ ...formData, tenant_snow_removal: e.target.checked })}
                      className="rounded h-3 w-3"
                    />
                    <span className="text-xs">Snow Removal</span>
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={formData.tenant_lawn_care || false}
                      onChange={(e) => setFormData({ ...formData, tenant_lawn_care: e.target.checked })}
                      className="rounded h-3 w-3"
                    />
                    <span className="text-xs">Lawn Care (tenant provided)</span>
                  </label>
                </div>
              </div>
              
              <div>
                <Label className="text-xs mb-2">Appliances Provided</Label>
                <div className="space-y-2 mb-2">
                  {APPLIANCE_OPTIONS.map((appliance) => (
                    <label key={appliance} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={appliances.includes(appliance)}
                        onChange={(e) => handleAppliancesChange(appliance, e.target.checked)}
                        className="rounded h-3 w-3"
                      />
                      <span className="text-xs">{appliance}</span>
                    </label>
                  ))}
                </div>
                <Input
                  value={formData.appliances_provided || ''}
                  onChange={(e) => {
                    setFormData({ ...formData, appliances_provided: e.target.value });
                    // Sync checkboxes with text input
                    const items = e.target.value.split(',').map((a: string) => a.trim()).filter(Boolean);
                    const matchedAppliances = items.filter((a: string) => APPLIANCE_OPTIONS.includes(a));
                    setAppliances(matchedAppliances);
                  }}
                  placeholder="Comma-separated list (e.g., Refrigerator, Range, Dishwasher)"
                  className="text-sm h-8"
                />
              </div>
            </CardContent>
          )}
        </Card>

        {/* Section 7: Pets */}
        <Card>
          <CardHeader 
            className="py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors"
            onClick={() => toggleSection('7')}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {expandedSections.has('7') ? (
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                )}
                <CardTitle className="text-sm">7. Pets</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                {(() => {
                  const stats = getSectionStats('7', sectionFields['7']);
                  const hasValues = stats.filled > 0;
                  return (
                    <>
                      {hasValues && <CheckCircle2 className="h-4 w-4 text-blue-500" />}
                      <span className="text-xs text-gray-500">
                        {stats.filled}/{stats.total}
                      </span>
                    </>
                  );
                })()}
              </div>
            </div>
          </CardHeader>
          {expandedSections.has('7') && (
            <CardContent className="px-3 pb-3 space-y-3">
              <div>
                <Label htmlFor="pet_fee" className="text-xs">Pet Fee</Label>
                <Input
                  id="pet_fee"
                  type="number"
                  step="0.01"
                  value={formData.pet_fee || ''}
                  onChange={(e) => setFormData({ ...formData, pet_fee: e.target.value })}
                  className="text-sm h-8 mt-1"
                />
              </div>
              
              <div>
                <Label className="text-xs mb-2">Pets</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs mb-2"
                  onClick={() => setShowPetsModal(true)}
                >
                  <Edit2 className="h-3 w-3 mr-1" />
                  Edit Pets ({pets.length})
                </Button>
                {pets.length > 0 && (
                  <div className="text-xs text-gray-600">
                    {pets.map((pet, idx) => {
                      const parts = [pet.type];
                      if (pet.breed) parts.push(`- ${pet.breed}`);
                      if (pet.name) parts.push(`(${pet.name})`);
                      if (pet.weight) parts.push(`${pet.weight}lbs`);
                      if (pet.isEmotionalSupport) parts.push('(emotional support animal)');
                      return <div key={idx}>{parts.join(' ')}</div>;
                    })}
                  </div>
                )}
              </div>
            </CardContent>
          )}
        </Card>

        {/* Section 8: Access & Physical Security */}
        <Card>
          <CardHeader 
            className="py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors"
            onClick={() => toggleSection('8')}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {expandedSections.has('8') ? (
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                )}
                <CardTitle className="text-sm">8. Access & Physical Security</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                {(() => {
                  const stats = getSectionStats('8', sectionFields['8']);
                  const hasValues = stats.filled > 0;
                  return (
                    <>
                      {hasValues && <CheckCircle2 className="h-4 w-4 text-blue-500" />}
                      <span className="text-xs text-gray-500">
                        {stats.filled}/{stats.total}
                      </span>
                    </>
                  );
                })()}
              </div>
            </div>
          </CardHeader>
          {expandedSections.has('8') && (
            <CardContent className="px-3 pb-3 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="front_door_keys" className="text-xs">Front Door Keys</Label>
                  <Input
                    id="front_door_keys"
                    type="number"
                    value={formData.front_door_keys || ''}
                    onChange={(e) => setFormData({ ...formData, front_door_keys: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="back_door_keys" className="text-xs">Back Door Keys</Label>
                  <Input
                    id="back_door_keys"
                    type="number"
                    value={formData.back_door_keys || ''}
                    onChange={(e) => setFormData({ ...formData, back_door_keys: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="garage_back_door_keys" className="text-xs">Garage Back Door Keys</Label>
                  <Input
                    id="garage_back_door_keys"
                    type="number"
                    value={formData.garage_back_door_keys || ''}
                    onChange={(e) => setFormData({ ...formData, garage_back_door_keys: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="key_replacement_fee" className="text-xs">Key Replacement Fee</Label>
                  <Input
                    id="key_replacement_fee"
                    type="number"
                    step="0.01"
                    value={formData.key_replacement_fee || ''}
                    onChange={(e) => setFormData({ ...formData, key_replacement_fee: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="has_garage_door_opener"
                  checked={formData.has_garage_door_opener || false}
                  onChange={(e) => setFormData({ ...formData, has_garage_door_opener: e.target.checked })}
                  className="rounded h-3 w-3"
                />
                <Label htmlFor="has_garage_door_opener" className="text-xs">Has Garage Door Opener</Label>
              </div>
              
              {formData.has_garage_door_opener && (
                <div>
                  <Label htmlFor="garage_door_opener_fee" className="text-xs">Garage Door Opener Fee</Label>
                  <Input
                    id="garage_door_opener_fee"
                    type="number"
                    step="0.01"
                    value={formData.garage_door_opener_fee || ''}
                    onChange={(e) => setFormData({ ...formData, garage_door_opener_fee: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
              )}
            </CardContent>
          )}
        </Card>

        {/* Section 9: Mandatory Disclosures */}
        <Card>
          <CardHeader 
            className="py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors"
            onClick={() => toggleSection('9')}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {expandedSections.has('9') ? (
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                )}
                <CardTitle className="text-sm">9. Mandatory Disclosures</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                {(() => {
                  const stats = getSectionStats('9', sectionFields['9']);
                  const hasValues = stats.filled > 0;
                  return (
                    <>
                      {hasValues && <CheckCircle2 className="h-4 w-4 text-blue-500" />}
                      <span className="text-xs text-gray-500">
                        {stats.filled}/{stats.total}
                      </span>
                    </>
                  );
                })()}
              </div>
            </div>
          </CardHeader>
          {expandedSections.has('9') && (
            <CardContent className="px-3 pb-3 space-y-3">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="lead_paint_disclosure"
                  checked={formData.lead_paint_disclosure ?? true}
                  onChange={(e) => setFormData({ ...formData, lead_paint_disclosure: e.target.checked })}
                  className="rounded h-3 w-3"
                />
                <Label htmlFor="lead_paint_disclosure" className="text-xs">Lead Paint Disclosure</Label>
              </div>
              
              <div>
                <Label htmlFor="disclosure_lead_paint" className="text-xs">Lead Paint Year Built</Label>
                <Input
                  id="disclosure_lead_paint"
                  type="number"
                  value={formData.disclosure_lead_paint || ''}
                  onChange={(e) => setFormData({ ...formData, disclosure_lead_paint: e.target.value })}
                  className="text-sm h-8 mt-1"
                  placeholder={selectedProperty?.year_built?.toString() || ''}
                />
              </div>
              
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="disclosure_methamphetamine"
                  checked={formData.disclosure_methamphetamine || false}
                  onChange={(e) => setFormData({ ...formData, disclosure_methamphetamine: e.target.checked })}
                  className="rounded h-3 w-3"
                />
                <Label htmlFor="disclosure_methamphetamine" className="text-xs">Methamphetamine Disclosure (MO only - if property had meth making)</Label>
              </div>
            </CardContent>
          )}
        </Card>

        {/* Section 10: Early Termination */}
        <Card>
          <CardHeader 
            className="py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors"
            onClick={() => toggleSection('10')}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {expandedSections.has('10') ? (
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                )}
                <CardTitle className="text-sm">10. Early Termination</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                {(() => {
                  const stats = getSectionStats('10', sectionFields['10']);
                  const hasValues = stats.filled > 0;
                  return (
                    <>
                      {hasValues && <CheckCircle2 className="h-4 w-4 text-blue-500" />}
                      <span className="text-xs text-gray-500">
                        {stats.filled}/{stats.total}
                      </span>
                    </>
                  );
                })()}
              </div>
            </div>
          </CardHeader>
          {expandedSections.has('10') && (
            <CardContent className="px-3 pb-3 space-y-3">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="early_termination_allowed"
                  checked={formData.early_termination_allowed ?? true}
                  onChange={(e) => setFormData({ ...formData, early_termination_allowed: e.target.checked })}
                  className="rounded h-3 w-3"
                />
                <Label htmlFor="early_termination_allowed" className="text-xs">Early Termination Allowed</Label>
              </div>
              
              {formData.early_termination_allowed && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor="early_termination_notice_days" className="text-xs">Early Termination Notice Days</Label>
                    <Input
                      id="early_termination_notice_days"
                      type="number"
                      value={formData.early_termination_notice_days || ''}
                      onChange={(e) => setFormData({ ...formData, early_termination_notice_days: e.target.value })}
                      className="text-sm h-8 mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="early_termination_fee_amount" className="text-xs">Early Termination Fee Amount</Label>
                    <Input
                      id="early_termination_fee_amount"
                      type="number"
                      step="0.01"
                      value={formData.early_termination_fee_amount || ''}
                      onChange={(e) => setFormData({ ...formData, early_termination_fee_amount: e.target.value })}
                      className="text-sm h-8 mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="early_termination_fee_months" className="text-xs">Early Termination Fee Months</Label>
                    <Input
                      id="early_termination_fee_months"
                      type="number"
                      value={formData.early_termination_fee_months || ''}
                      onChange={(e) => setFormData({ ...formData, early_termination_fee_months: e.target.value })}
                      className="text-sm h-8 mt-1"
                    />
                  </div>
                </div>
              )}
            </CardContent>
          )}
        </Card>

        {/* Section 11: Move Out & Notes */}
        <Card>
          <CardHeader 
            className="py-2 px-3 cursor-pointer hover:bg-gray-50 transition-colors"
            onClick={() => toggleSection('11')}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {expandedSections.has('11') ? (
                  <ChevronDown className="h-4 w-4 text-gray-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-500" />
                )}
                <CardTitle className="text-sm">11. Move Out & Notes</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                {(() => {
                  const stats = getSectionStats('11', sectionFields['11']);
                  const hasValues = stats.filled > 0;
                  return (
                    <>
                      {hasValues && <CheckCircle2 className="h-4 w-4 text-blue-500" />}
                      <span className="text-xs text-gray-500">
                        {stats.filled}/{stats.total}
                      </span>
                    </>
                  );
                })()}
              </div>
            </div>
          </CardHeader>
          {expandedSections.has('11') && (
            <CardContent className="px-3 pb-3 space-y-3">
              <div>
                <Label className="text-xs mb-2">Move-Out Costs</Label>
                <div className="mb-2">
                  {moveoutCosts.length > 0 ? (
                    <div className="border rounded-md overflow-hidden">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Item</th>
                            <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                            <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Amount</th>
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {moveoutCosts.sort((a, b) => a.order - b.order).map((cost, idx) => (
                            <tr key={idx}>
                              <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-800">{cost.item}</td>
                              <td className="px-3 py-2 text-xs text-gray-600">{cost.description}</td>
                              <td className="px-3 py-2 whitespace-nowrap text-right text-xs text-gray-800">${parseFloat(cost.amount.toString()).toFixed(2)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-xs text-gray-500">No move-out costs configured.</p>
                  )}
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => setShowMoveoutCostsModal(true)}
                >
                  <Edit2 className="h-3 w-3 mr-1" />
                  Edit Move-Out Costs ({moveoutCosts.length})
                </Button>
              </div>
              <div>
                <Label htmlFor="notes" className="text-xs">Notes</Label>
                <Textarea
                  id="notes"
                  value={formData.notes || ''}
                  onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                  rows={3}
                  placeholder="Custom terms or special agreements"
                  className="text-sm mt-1"
                />
              </div>
            </CardContent>
          )}
        </Card>

        {/* Submit Button */}
        <div className="flex justify-end gap-2 pt-4">
          <Link href="/leases">
            <Button type="button" variant="outline" size="sm" className="h-8 text-xs">
              Cancel
            </Button>
          </Link>
          <Button type="submit" size="sm" className="h-8 text-xs" disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Save className="h-3 w-3 mr-1" />
                Create Lease
              </>
            )}
          </Button>
        </div>
      </form>

      {/* Modals - Same as edit page */}
      {/* Moveout Costs Modal */}
      <Dialog open={showMoveoutCostsModal} onOpenChange={setShowMoveoutCostsModal}>
        <DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-sm">Move-Out Costs</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="border rounded overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="text-left p-2 font-semibold">Item</th>
                    <th className="text-left p-2 font-semibold">Description</th>
                    <th className="text-right p-2 font-semibold">Amount</th>
                    <th className="text-center p-2 font-semibold w-16">Order</th>
                    <th className="text-center p-2 font-semibold w-16"></th>
                  </tr>
                </thead>
                <tbody>
                  {moveoutCosts
                    .sort((a, b) => (a.order || 0) - (b.order || 0))
                    .map((cost, idx) => {
                      const originalIdx = moveoutCosts.findIndex(c => c === cost);
                      return (
                        <tr key={idx} className="border-t hover:bg-gray-50">
                          <td className="p-1">
                            <Input
                              value={cost.item}
                              onChange={(e) => {
                                const newCosts = [...moveoutCosts];
                                newCosts[originalIdx].item = e.target.value;
                                setMoveoutCosts(newCosts);
                              }}
                              className="text-xs h-7 border-0 focus:border focus:border-blue-300"
                              placeholder="Item name"
                            />
                          </td>
                          <td className="p-1">
                            <Input
                              value={cost.description || ''}
                              onChange={(e) => {
                                const newCosts = [...moveoutCosts];
                                newCosts[originalIdx].description = e.target.value;
                                setMoveoutCosts(newCosts);
                              }}
                              className="text-xs h-7 border-0 focus:border focus:border-blue-300"
                              placeholder="Description"
                            />
                          </td>
                          <td className="p-1">
                            <Input
                              type="number"
                              step="0.01"
                              value={cost.amount}
                              onChange={(e) => {
                                const newCosts = [...moveoutCosts];
                                newCosts[originalIdx].amount = e.target.value;
                                setMoveoutCosts(newCosts);
                              }}
                              className="text-xs h-7 border-0 focus:border focus:border-blue-300 text-right"
                              placeholder="0.00"
                            />
                          </td>
                          <td className="p-1">
                            <Input
                              type="number"
                              value={cost.order || idx + 1}
                              onChange={(e) => {
                                const newCosts = [...moveoutCosts];
                                newCosts[originalIdx].order = parseInt(e.target.value) || 0;
                                setMoveoutCosts(newCosts);
                              }}
                              className="text-xs h-7 border-0 focus:border focus:border-blue-300 text-center w-12"
                              min="1"
                            />
                          </td>
                          <td className="p-1 text-center">
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-6 w-6 p-0"
                              onClick={() => setMoveoutCosts(moveoutCosts.filter((_, i) => i !== originalIdx))}
                            >
                              <X className="h-3 w-3" />
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
            <div className="flex justify-between items-center">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => setMoveoutCosts([...moveoutCosts, { item: '', description: '', amount: '0', order: moveoutCosts.length + 1 }])}
              >
                <Plus className="h-3 w-3 mr-1" />
                Add Cost
              </Button>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => setShowMoveoutCostsModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => setShowMoveoutCostsModal(false)}
                >
                  Save
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Tenants Modal */}
      <Dialog open={showTenantsModal} onOpenChange={setShowTenantsModal}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-sm">Select Tenants</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {availableTenants.length === 0 ? (
              <p className="text-xs text-gray-500">No tenants found for this property.</p>
            ) : (
              <div className="space-y-2">
                {availableTenants.map((tenant) => {
                  const isSelected = tenants.some(t => 
                    t.first_name === tenant.first_name && t.last_name === tenant.last_name
                  );
                  return (
                    <label
                      key={tenant.id}
                      className="flex items-center space-x-2 p-2 border rounded hover:bg-gray-50 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setTenants([...tenants, {
                              first_name: tenant.first_name,
                              last_name: tenant.last_name,
                              email: tenant.email,
                              phone: tenant.phone
                            }]);
                          } else {
                            setTenants(tenants.filter(t => 
                              !(t.first_name === tenant.first_name && t.last_name === tenant.last_name)
                            ));
                          }
                        }}
                        className="rounded h-3 w-3"
                      />
                      <span className="text-xs">
                        {tenant.first_name} {tenant.last_name}
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
            <div className="flex justify-end gap-2 pt-2 border-t">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => setShowTenantsModal(false)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => {
                  const tenantString = tenants.map(t => `${t.first_name} ${t.last_name}`).join(', ');
                  setFormData({ ...formData, tenants: tenantString });
                  setShowTenantsModal(false);
                }}
              >
                Save
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Pets Modal */}
      <Dialog open={showPetsModal} onOpenChange={setShowPetsModal}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-sm">Pets</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {pets.map((pet, idx) => (
              <div key={idx} className="border p-3 rounded space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <Label className="text-xs">Type</Label>
                    <Select
                      value={pet.type}
                      onValueChange={(value) => {
                        const newPets = [...pets];
                        newPets[idx].type = value;
                        setPets(newPets);
                      }}
                    >
                      <SelectTrigger className="text-sm h-8 mt-1">
                        <SelectValue placeholder="Select type" />
                      </SelectTrigger>
                      <SelectContent>
                        {PET_TYPE_OPTIONS.map((type) => (
                          <SelectItem key={type} value={type}>
                            {type.charAt(0).toUpperCase() + type.slice(1)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-xs">Name</Label>
                    <Input
                      value={pet.name || ''}
                      onChange={(e) => {
                        const newPets = [...pets];
                        newPets[idx].name = e.target.value;
                        setPets(newPets);
                      }}
                      className="text-sm h-8 mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Breed</Label>
                    <Input
                      value={pet.breed || ''}
                      onChange={(e) => {
                        const newPets = [...pets];
                        newPets[idx].breed = e.target.value;
                        setPets(newPets);
                      }}
                      className="text-sm h-8 mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Weight</Label>
                    <Input
                      value={pet.weight || ''}
                      onChange={(e) => {
                        const newPets = [...pets];
                        newPets[idx].weight = e.target.value;
                        setPets(newPets);
                      }}
                      placeholder="e.g., 10lbs"
                      className="text-sm h-8 mt-1"
                    />
                  </div>
                </div>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={pet.isEmotionalSupport || false}
                    onChange={(e) => {
                      const newPets = [...pets];
                      newPets[idx].isEmotionalSupport = e.target.checked;
                      setPets(newPets);
                    }}
                    className="rounded h-3 w-3"
                  />
                  <span>Emotional Support Animal</span>
                </label>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-6 text-xs"
                  onClick={() => setPets(pets.filter((_, i) => i !== idx))}
                >
                  <X className="h-3 w-3 mr-1" />
                  Remove
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 text-xs"
              onClick={() => setPets([...pets, { type: 'dog', name: '', breed: '', weight: '', isEmotionalSupport: false }])}
            >
              <Plus className="h-3 w-3 mr-1" />
              Add Pet
            </Button>
            <div className="flex justify-end gap-2 pt-2 border-t">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => setShowPetsModal(false)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => setShowPetsModal(false)}
              >
                Save
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
