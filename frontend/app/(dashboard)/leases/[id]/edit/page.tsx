'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useLeases, useLease, MoveOutCostItem, Tenant } from '@/lib/hooks/use-leases';
import { useProperty } from '@/lib/hooks/use-properties';
import { useTenants } from '@/lib/hooks/use-tenants';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { ArrowLeft, Loader2, AlertCircle, Save, ChevronDown, ChevronRight, CheckCircle2, Plus, X, Edit2 } from 'lucide-react';
import Link from 'next/link';

export default function LeaseEditPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = params.id as string;
  const { data: lease, isLoading } = useLease(id);
  const { updateLease } = useLeases();
  const { data: property } = useProperty(lease?.property_id || '');
  const { data: tenantsData } = useTenants(
    lease?.property_id ? { property_id: lease.property_id } : undefined
  );
  const availableTenants = tenantsData?.tenants || [];
  
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState<any>({});
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set(['1', '2', '3', '4'])); // Default open sections
  
  // Modal states
  const [showMoveoutCostsModal, setShowMoveoutCostsModal] = useState(false);
  const [showTenantsModal, setShowTenantsModal] = useState(false);
  const [showPetsModal, setShowPetsModal] = useState(false);
  
  // Utilities and appliances state
  const [landlordUtilities, setLandlordUtilities] = useState<string[]>([]);
  const [customUtility, setCustomUtility] = useState<string>('');
  const [useCustomUtility, setUseCustomUtility] = useState<boolean>(false);
  const [appliances, setAppliances] = useState<string[]>([]);
  
  // Moveout costs, tenants, and pets state (all JSON columns like landlord_references)
  const [moveoutCosts, setMoveoutCosts] = useState<MoveOutCostItem[]>([]);
  const [tenants, setTenants] = useState<Array<{ first_name: string; last_name: string; email?: string; phone?: string }>>([]);
  const [pets, setPets] = useState<Array<{ type: string; breed?: string; name?: string; weight?: string; isEmotionalSupport?: boolean }>>([]);
  
  // Available options
  const UTILITY_OPTIONS = ['Gas', 'Sewer', 'Water', 'Electricity', 'Trash'];
  const APPLIANCE_OPTIONS = ['Refrigerator', 'Range', 'Dishwasher', 'Microwave', 'Washer', 'Dryer', 'Garbage Disposal'];
  const PET_TYPE_OPTIONS = ['dog', 'cat', 'bird', 'fish', 'reptile'];

  // Helper function to check if a field has a value
  const hasValue = (value: any): boolean => {
    if (value === null || value === undefined) return false;
    if (typeof value === 'string') return value.trim() !== '';
    if (typeof value === 'boolean') return true;
    if (typeof value === 'number') return value !== 0;
    return true;
  };

  // Helper function to count filled vs total fields in a section (with conditional logic)
  const getSectionStats = (sectionId: string, sectionFields: string[]): { filled: number; total: number } => {
    let filled = 0;
    let total = 0;
    
    sectionFields.forEach(field => {
      // Skip checkboxes that shouldn't be counted
      if (field === 'show_prorated_rent' || field === 'has_shared_driveway') {
        return; // Don't count these checkboxes
      }
      
      // Section 1: Exclude lease_date
      if (sectionId === '1' && field === 'lease_date') {
        return;
      }
      
      // Section 2: Only count shared_driveway_with if has_shared_driveway is true
      if (sectionId === '2' && field === 'shared_driveway_with') {
        if (formData.has_shared_driveway) {
          total++;
          if (hasValue(formData[field])) filled++;
        }
        return;
      }
      
      // Section 3: Only count prorated_first_month_rent if show_prorated_rent is true
      if (sectionId === '3' && field === 'prorated_first_month_rent') {
        if (formData.show_prorated_rent) {
          total++;
          if (hasValue(formData[field])) filled++;
        }
        return;
      }
      
      // Section 4: Only count holding fee fields if include_holding_fee_addendum is true
      if (sectionId === '4' && (field === 'holding_fee_amount' || field === 'holding_fee_date')) {
        if (formData.include_holding_fee_addendum) {
          total++;
          if (hasValue(formData[field])) filled++;
        }
        return;
      }
      
      // Section 10: Only count termination fields if early_termination_allowed is true
      if (sectionId === '10' && (field === 'early_termination_notice_days' || field === 'early_termination_fee_amount' || field === 'early_termination_fee_months')) {
        if (formData.early_termination_allowed) {
          total++;
          if (hasValue(formData[field])) filled++;
        }
        return;
      }
      
      // Section 11: Count moveout_costs and notes
      if (sectionId === '11') {
        if (field === 'moveout_costs') {
          total++;
          if (hasValue(formData[field]) || moveoutCosts.length > 0) {
            filled++;
          }
          return;
        }
      }
      
      // Section 6: Special handling for utilities and appliances
      if (sectionId === '6') {
        if (field === 'utilities_tenant') {
          // Always count utilities_tenant (it's auto-generated, but should be present)
          total++;
          if (hasValue(formData[field])) filled++;
          return;
        }
        if (field === 'utilities_landlord') {
          // Count if any landlord utilities are selected (checkboxes or custom)
          total++;
          if (landlordUtilities.length > 0 || (useCustomUtility && customUtility)) {
            filled++;
          }
          return;
        }
        if (field === 'appliances_provided') {
          // Count if any appliances are selected
          total++;
          if (appliances.length > 0 || hasValue(formData[field])) {
            filled++;
          }
          return;
        }
      }
      
      // Count this field
      total++;
      if (hasValue(formData[field])) {
        filled++;
      }
    });
    
    return { filled, total };
  };

  // Toggle section expansion
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

  // Define fields for each section
  const sectionFields: Record<string, string[]> = {
    '1': ['owner_name', 'manager_name', 'manager_address'], // lease_date excluded from count
    '2': ['max_occupants', 'max_adults', 'garage_spaces', 'offstreet_parking_spots', 'has_shared_driveway', 'shared_driveway_with'],
    '3': ['lease_start', 'lease_end', 'auto_convert_month_to_month', 'show_prorated_rent', 'prorated_first_month_rent'],
    '4': ['monthly_rent', 'rent_due_day', 'rent_due_by_day', 'rent_due_by_time', 'payment_method', 'show_prorated_rent', 'prorated_first_month_rent', 'security_deposit', 'include_holding_fee_addendum', 'holding_fee_amount', 'holding_fee_date'],
    '5': ['late_fee_day_1_10', 'late_fee_day_11', 'late_fee_day_16', 'late_fee_day_21', 'nsf_fee'],
    '6': ['utilities_tenant', 'utilities_landlord', 'appliances_provided', 'tenant_lawn_mowing', 'tenant_lawn_care', 'tenant_snow_removal'],
    '7': ['pet_fee', 'pet_description'], // Pets only
    '8': ['front_door_keys', 'back_door_keys', 'has_garage_door_opener', 'garage_back_door_keys', 'key_replacement_fee', 'garage_door_opener_fee'],
    '9': ['lead_paint_disclosure', 'disclosure_lead_paint', 'disclosure_methamphetamine'],
    '10': ['early_termination_allowed', 'early_termination_notice_days', 'early_termination_fee_amount', 'early_termination_fee_months'],
    '11': ['moveout_costs', 'notes'], // System Metadata / Notes
  };
  
  // Handle landlord utilities change
  const handleLandlordUtilitiesChange = (utility: string, checked: boolean) => {
    const newUtilities = checked 
      ? [...landlordUtilities, utility]
      : landlordUtilities.filter(u => u !== utility);
    setLandlordUtilities(newUtilities);
    updateUtilitiesString(newUtilities, useCustomUtility ? customUtility : '');
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
    if (property?.year_built && !formData.disclosure_lead_paint) {
      setFormData((prev: any) => ({ ...prev, disclosure_lead_paint: property.year_built?.toString() || '' }));
    }
  }, [property?.year_built]);
  

  useEffect(() => {
    if (lease) {
      // Initialize form with lease data
      setFormData({
        status: lease.status || 'draft',
        lease_start: lease.lease_start ? new Date(lease.lease_start as string).toISOString().split('T')[0] : '',
        lease_end: lease.lease_end ? new Date(lease.lease_end as string).toISOString().split('T')[0] : '',
        monthly_rent: lease.monthly_rent?.toString() || '',
        security_deposit: lease.security_deposit?.toString() || '',
        rent_due_day: lease.rent_due_day?.toString() || '',
        rent_due_by_day: lease.rent_due_by_day?.toString() || '',
        rent_due_by_time: lease.rent_due_by_time || '',
        payment_method: lease.payment_method || '',
        late_fee_day_1_10: lease.late_fee_day_1_10?.toString() || '',
        late_fee_day_11: lease.late_fee_day_11?.toString() || '',
        late_fee_day_16: lease.late_fee_day_16?.toString() || '',
        late_fee_day_21: lease.late_fee_day_21?.toString() || '',
        nsf_fee: lease.nsf_fee?.toString() || '',
        max_occupants: lease.max_occupants?.toString() || '',
        max_adults: lease.max_adults?.toString() || '',
        utilities_tenant: lease.utilities_tenant || 'All',
        utilities_landlord: lease.utilities_landlord || '',
        pet_fee: lease.pet_fee?.toString() || '',
        garage_spaces: lease.garage_spaces?.toString() || '',
        offstreet_parking_spots: lease.offstreet_parking_spots?.toString() || '',
        front_door_keys: lease.front_door_keys?.toString() || '',
        back_door_keys: lease.back_door_keys?.toString() || '',
        garage_back_door_keys: lease.garage_back_door_keys?.toString() || '',
        key_replacement_fee: lease.key_replacement_fee?.toString() || '',
        shared_driveway_with: lease.shared_driveway_with || '',
        garage_door_opener_fee: lease.garage_door_opener_fee?.toString() || '',
        appliances_provided: lease.appliances_provided || '',
        early_termination_fee_amount: lease.early_termination_fee_amount?.toString() || '',
        owner_name: lease.owner_name || '',
        manager_name: lease.manager_name || '',
        manager_address: lease.manager_address || '',
        notes: lease.notes || '',
        auto_convert_month_to_month: lease.auto_convert_month_to_month || false,
        show_prorated_rent: lease.show_prorated_rent || false,
        include_holding_fee_addendum: lease.include_holding_fee_addendum || false,
        has_shared_driveway: lease.has_shared_driveway || false,
        tenant_lawn_mowing: lease.tenant_lawn_mowing ?? true,
        tenant_snow_removal: lease.tenant_snow_removal ?? true,
        tenant_lawn_care: lease.tenant_lawn_care || false,
        has_garage_door_opener: lease.has_garage_door_opener || false,
        lead_paint_disclosure: lease.lead_paint_disclosure ?? true,
        early_termination_allowed: lease.early_termination_allowed ?? true,
        disclosure_methamphetamine: (lease as any).disclosure_methamphetamine || false,
        disclosure_lead_paint: (lease as any).disclosure_lead_paint?.toString() || '',
        early_termination_notice_days: lease.early_termination_notice_days?.toString() || '',
        early_termination_fee_months: lease.early_termination_fee_months?.toString() || '',
        prorated_first_month_rent: lease.prorated_first_month_rent?.toString() || '',
        holding_fee_amount: lease.holding_fee_amount?.toString() || '',
        holding_fee_date: lease.holding_fee_date || '',
        lease_date: lease.lease_date || '',
      });
      
      // Initialize moveout costs, tenants, and pets from JSON
      try {
        if ((lease as any).moveout_costs) {
          // Try to parse as JSON first
          try {
            const costs = typeof (lease as any).moveout_costs === 'string' 
              ? JSON.parse((lease as any).moveout_costs)
              : (lease as any).moveout_costs;
            if (Array.isArray(costs)) {
              setMoveoutCosts(costs || []);
              // Format for display
              const formattedCosts = costs.map((cost: any) => {
                const parts = [cost.item];
                if (cost.description) parts.push(`- ${cost.description}`);
                parts.push(`$${parseFloat(cost.amount.toString()).toFixed(2)}`);
                return parts.join(' ');
              }).join('\n');
              setFormData((prev: any) => ({ ...prev, moveout_costs: formattedCosts }));
            } else {
              // If it's already formatted text, use it directly
              setFormData((prev: any) => ({ ...prev, moveout_costs: (lease as any).moveout_costs }));
            }
          } catch {
            // If parsing fails, treat as formatted text
            setFormData((prev: any) => ({ ...prev, moveout_costs: (lease as any).moveout_costs }));
          }
        }
      } catch (e) {
        console.error('Error parsing moveout_costs:', e);
      }
      
      // Initialize tenants from JSON column (like landlord_references)
      try {
        if ((lease as any).tenants) {
          const tenantData = typeof (lease as any).tenants === 'string'
            ? JSON.parse((lease as any).tenants)
            : (lease as any).tenants;
          if (Array.isArray(tenantData)) {
            setTenants(tenantData);
            // Also set formData.tenants as comma-separated string for display
            const tenantString = tenantData.map((t: any) => `${t.first_name} ${t.last_name}`).join(', ');
            setFormData((prev: any) => ({ ...prev, tenants: tenantString }));
          }
        }
      } catch (e) {
        console.error('Error parsing tenants:', e);
        setTenants([]);
      }
      
      try {
        if ((lease as any).pets) {
          const petData = typeof (lease as any).pets === 'string'
            ? JSON.parse((lease as any).pets)
            : (lease as any).pets;
          setPets(petData || []);
        }
      } catch (e) {
        console.error('Error parsing pets:', e);
      }
    }
  }, [lease]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      // Validate required fields
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
      if (lease?.state === 'MO' && !formData.owner_name) {
        setError('Owner name is required for Missouri leases');
        setSaving(false);
        return;
      }

      // Build update payload - map frontend field names to backend field names
      // Note: updateLease will handle field ordering automatically
      const updatePayload: any = {};
      
      // Status - in LEASES_FIELD_ORDER: status comes after property_id, unit_id
      // Always include status (defaults to 'draft' if not set)
      updatePayload.status = formData.status || lease?.status || 'draft';
      
      // Required fields - always include (validated above)
      updatePayload.lease_start = formData.lease_start;
      updatePayload.lease_end = formData.lease_end;
      updatePayload.monthly_rent = parseFloat(formData.monthly_rent);
      updatePayload.security_deposit = parseFloat(formData.security_deposit);
      
      // Financial - in LEASES_FIELD_ORDER: rent_due_by_time, payment_method, prorated_first_month_rent
      if (formData.rent_due_by_time) updatePayload.rent_due_by_time = formData.rent_due_by_time;
      if (formData.payment_method) updatePayload.payment_method = formData.payment_method;
      if (formData.prorated_first_month_rent) updatePayload.prorated_first_month_rent = parseFloat(formData.prorated_first_month_rent);
      
      // Late fees - in order: late_fee_day_1_10, late_fee_day_11, late_fee_day_16, late_fee_day_21, nsf_fee
      if (formData.late_fee_day_1_10) updatePayload.late_fee_day_1_10 = parseFloat(formData.late_fee_day_1_10);
      if (formData.late_fee_day_11) updatePayload.late_fee_day_11 = parseFloat(formData.late_fee_day_11);
      if (formData.late_fee_day_16) updatePayload.late_fee_day_16 = parseFloat(formData.late_fee_day_16);
      if (formData.late_fee_day_21) updatePayload.late_fee_day_21 = parseFloat(formData.late_fee_day_21);
      if (formData.nsf_fee) updatePayload.nsf_fee = parseFloat(formData.nsf_fee);
      
      // Holding fee - in order: holding_fee_amount, holding_fee_date
      if (formData.holding_fee_amount) updatePayload.holding_fee_amount = parseFloat(formData.holding_fee_amount);
      if (formData.holding_fee_date) updatePayload.holding_fee_date = formData.holding_fee_date;
      
      // Utilities - in order: utilities_tenant, utilities_landlord
      if (formData.utilities_tenant) updatePayload.utilities_tenant = formData.utilities_tenant;
      if (formData.utilities_landlord) updatePayload.utilities_landlord = formData.utilities_landlord;
      
      // Pets - in order: pet_fee, pet_description
      if (formData.pet_fee) updatePayload.pet_fee = parseFloat(formData.pet_fee);
      
      // Parking - in order: garage_spaces
      if (formData.garage_spaces) updatePayload.garage_spaces = parseFloat(formData.garage_spaces);
      
      // Keys - in order: key_replacement_fee
      if (formData.key_replacement_fee) updatePayload.key_replacement_fee = parseFloat(formData.key_replacement_fee);
      
      // Other - in order: shared_driveway_with, garage_door_opener_fee, appliances_provided, early_termination_fee_amount
      if (formData.shared_driveway_with) updatePayload.shared_driveway_with = formData.shared_driveway_with;
      if (formData.garage_door_opener_fee) updatePayload.garage_door_opener_fee = parseFloat(formData.garage_door_opener_fee);
      if (formData.appliances_provided) updatePayload.appliances_provided = formData.appliances_provided;
      if (formData.early_termination_fee_amount) updatePayload.early_termination_fee_amount = parseFloat(formData.early_termination_fee_amount);
      
      // Owner/Manager - in order: owner_name, manager_name, manager_address
      // owner_name is required for MO leases (validated above), always include if present
      if (formData.owner_name !== undefined) updatePayload.owner_name = formData.owner_name;
      if (formData.manager_name) updatePayload.manager_name = formData.manager_name;
      if (formData.manager_address) updatePayload.manager_address = formData.manager_address;
      
      // Notes
      if (formData.notes !== undefined) updatePayload.notes = formData.notes;
      
      // JSON fields
      // Move-out costs: send as array of objects (backend expects List[MoveOutCostItem])
      // The backend will serialize it to JSON string for storage
      if (moveoutCosts.length > 0) {
        updatePayload.moveout_costs = moveoutCosts.map(cost => ({
          item: cost.item,
          description: cost.description || '',
          amount: parseFloat(cost.amount.toString()) || 0,
          order: cost.order || 1
        }));
      }
      // Tenants: send as array of objects (like landlord_references - JSON column)
      if (tenants.length > 0) {
        updatePayload.tenants = tenants;
      }
      // Pets: send as array of objects, not JSON string (backend expects List[PetInfo])
      if (pets.length > 0) {
        updatePayload.pets = pets.map(pet => ({
          type: pet.type,
          breed: pet.breed,
          name: pet.name,
          weight: pet.weight,
          isEmotionalSupport: pet.isEmotionalSupport || false
        }));
      }
      
      // Booleans - in order: auto_convert_month_to_month, show_prorated_rent, include_holding_fee_addendum, has_shared_driveway
      updatePayload.auto_convert_month_to_month = formData.auto_convert_month_to_month;
      updatePayload.show_prorated_rent = formData.show_prorated_rent;
      updatePayload.include_holding_fee_addendum = formData.include_holding_fee_addendum;
      updatePayload.has_shared_driveway = formData.has_shared_driveway;
      
      // Tenant responsibilities - in order: tenant_lawn_mowing, tenant_snow_removal, tenant_lawn_care
      updatePayload.tenant_lawn_mowing = formData.tenant_lawn_mowing;
      updatePayload.tenant_snow_removal = formData.tenant_snow_removal;
      updatePayload.tenant_lawn_care = formData.tenant_lawn_care;
      
      // Garage - in order: has_garage_door_opener
      updatePayload.has_garage_door_opener = formData.has_garage_door_opener;
      
      // Disclosures - in order: lead_paint_disclosure, early_termination_allowed, disclosure_methamphetamine
      updatePayload.lead_paint_disclosure = formData.lead_paint_disclosure;
      updatePayload.early_termination_allowed = formData.early_termination_allowed;
      updatePayload.disclosure_methamphetamine = formData.disclosure_methamphetamine;
      
      // Rent due - in order: rent_due_day, rent_due_by_day
      if (formData.rent_due_day) updatePayload.rent_due_day = parseInt(formData.rent_due_day);
      if (formData.rent_due_by_day) updatePayload.rent_due_by_day = parseInt(formData.rent_due_by_day);
      
      // Occupants - in order: max_occupants, max_adults
      if (formData.max_occupants) updatePayload.max_occupants = parseInt(formData.max_occupants);
      if (formData.max_adults) updatePayload.max_adults = parseInt(formData.max_adults);
      
      // Parking - in order: offstreet_parking_spots
      if (formData.offstreet_parking_spots) updatePayload.offstreet_parking_spots = parseInt(formData.offstreet_parking_spots);
      
      // Keys - in order: front_door_keys, back_door_keys, garage_back_door_keys
      if (formData.front_door_keys) updatePayload.front_door_keys = parseInt(formData.front_door_keys);
      if (formData.back_door_keys) updatePayload.back_door_keys = parseInt(formData.back_door_keys);
      if (formData.garage_back_door_keys) updatePayload.garage_back_door_keys = parseInt(formData.garage_back_door_keys);
      
      // Lead paint - in order: disclosure_lead_paint
      if (formData.disclosure_lead_paint) updatePayload.disclosure_lead_paint = parseInt(formData.disclosure_lead_paint);
      
      // Early termination - in order: early_termination_notice_days, early_termination_fee_months
      if (formData.early_termination_notice_days) updatePayload.early_termination_notice_days = parseInt(formData.early_termination_notice_days);
      if (formData.early_termination_fee_months) updatePayload.early_termination_fee_months = parseInt(formData.early_termination_fee_months);

      // updateLease will automatically order these fields according to LEASES_FIELD_ORDER
      await updateLease(id, updatePayload);
      
      // Invalidate cache to ensure fresh data on the leases list page
      await queryClient.invalidateQueries({ queryKey: ['leases'] });
      await queryClient.invalidateQueries({ queryKey: ['lease', id] });
      
      router.push('/leases?refresh=true');
    } catch (err: any) {
      console.error('Error updating lease:', err);
      setError(err.message || 'Failed to update lease');
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!lease) {
    return (
      <div className="p-8">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 text-red-600">
              <AlertCircle className="h-5 w-5" />
              <div>
                <h3 className="font-semibold">Lease Not Found</h3>
                <p className="text-sm text-gray-600 mt-1">The lease you're looking for doesn't exist.</p>
              </div>
            </div>
            <div className="mt-4">
              <Link href="/leases">
                <Button variant="outline">
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back to Leases
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link href="/leases">
            <Button variant="ghost" size="sm" className="h-7 text-xs">
              <ArrowLeft className="h-3 w-3 mr-1" />
              Back
            </Button>
          </Link>
          <div>
            <h1 className="text-sm font-bold text-gray-900">Edit Lease</h1>
            <p className="text-xs text-gray-500">{lease.property?.address || 'Lease Details'}</p>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-3 p-3 bg-red-50 border border-red-200 rounded-md">
          <div className="flex items-center gap-2 text-red-800 text-xs">
            <AlertCircle className="h-4 w-4" />
            <span>{error}</span>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit}>
        <div className="space-y-3">
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
                  <Label htmlFor="lease_date" className="text-xs">Lease Date (Signing Date)</Label>
                  <Input
                    id="lease_date"
                    type="date"
                    value={formData.lease_date || ''}
                    onChange={(e) => setFormData({ ...formData, lease_date: e.target.value })}
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="status" className="text-xs">Status</Label>
                  <Select
                    value={formData.status || lease?.status || 'draft'}
                    onValueChange={(value) => setFormData({ ...formData, status: value })}
                  >
                    <SelectTrigger className="text-sm h-8 mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="draft">draft</SelectItem>
                      <SelectItem value="final">final</SelectItem>
                      <SelectItem value="other">other</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="owner_name" className="text-xs">Owner Name *</Label>
                  <Input
                    id="owner_name"
                    value={formData.owner_name || ''}
                    onChange={(e) => setFormData({ ...formData, owner_name: e.target.value })}
                    className="text-sm h-8 mt-1"
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
                <div className="col-span-2">
                  <Label htmlFor="manager_address" className="text-xs">Manager Address</Label>
                  <Textarea
                    id="manager_address"
                    value={formData.manager_address || ''}
                    onChange={(e) => setFormData({ ...formData, manager_address: e.target.value })}
                    rows={2}
                    className="text-sm mt-1"
                  />
                </div>
              </div>
              <div>
                <Label className="text-xs mb-2">Tenants</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs mb-2"
                  onClick={() => setShowTenantsModal(true)}
                >
                  <Edit2 className="h-3 w-3 mr-1" />
                  Edit Tenants
                </Button>
                {formData.tenants && (
                  <div className="text-xs text-gray-600 mt-2">
                    {formData.tenants}
                  </div>
                )}
                {!formData.tenants && lease?.tenants && lease.tenants.length > 0 && (
                  <div className="text-xs text-gray-600 mt-2">
                    {Array.isArray(lease.tenants) 
                      ? lease.tenants.map((t: any) => `${t.first_name} ${t.last_name}`).join(', ')
                      : 'Tenants listed'}
                  </div>
                )}
              </div>
            </CardContent>
            )}
          </Card>

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
                  <Label className="text-xs">Property</Label>
                  <div className="text-xs text-gray-600 mt-2">{lease?.property?.display_name || 'N/A'}</div>
                </div>
                <div>
                  <Label className="text-xs">State</Label>
                  <div className="text-xs text-gray-600 mt-2">{lease?.state || 'N/A'}</div>
                </div>
                <div>
                  <Label htmlFor="max_occupants" className="text-xs">Max Occupants</Label>
                  <Input
                    id="max_occupants"
                    type="number"
                    min="1"
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
                    min="1"
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
                    step="0.1"
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
                <div>
                  <label className="flex items-center space-x-2 text-xs mt-2">
                    <input
                      type="checkbox"
                      checked={formData.has_shared_driveway || false}
                      onChange={(e) => setFormData({ ...formData, has_shared_driveway: e.target.checked })}
                      className="rounded h-3 w-3"
                    />
                    <span>Has Shared Driveway</span>
                  </label>
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
              </div>
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
                    required
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="lease_end" className="text-xs">Lease End *</Label>
                  <Input
                    id="lease_end"
                    type="date"
                    value={formData.lease_end || ''}
                    onChange={(e) => setFormData({ ...formData, lease_end: e.target.value })}
                    required
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <Label className="text-xs">Lease Number</Label>
                  <div className="text-xs text-gray-600 mt-2">{lease?.lease_number || 'N/A'}</div>
                </div>
                <div>
                  <Label className="text-xs">Lease Version</Label>
                  <div className="text-xs text-gray-600 mt-2">{lease?.lease_version || 'N/A'}</div>
                </div>
              </div>
              <div>
                <label className="flex items-center space-x-2 text-xs">
                  <input
                    type="checkbox"
                    checked={formData.auto_convert_month_to_month || false}
                    onChange={(e) => setFormData({ ...formData, auto_convert_month_to_month: e.target.checked })}
                    className="rounded h-3 w-3"
                  />
                  <span>Auto Convert Month-to-Month</span>
                </label>
              </div>
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
                    required
                    className="text-sm h-8 mt-1"
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
                    placeholder="e.g., TurboTenant"
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <label className="flex items-center space-x-2 text-xs mt-2">
                    <input
                      type="checkbox"
                      checked={formData.show_prorated_rent || false}
                      onChange={(e) => setFormData({ ...formData, show_prorated_rent: e.target.checked })}
                      className="rounded h-3 w-3"
                    />
                    <span>Show Prorated Rent</span>
                  </label>
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
                <div>
                  <Label htmlFor="security_deposit" className="text-xs">Security Deposit *</Label>
                  <Input
                    id="security_deposit"
                    type="number"
                    step="0.01"
                    value={formData.security_deposit || ''}
                    onChange={(e) => setFormData({ ...formData, security_deposit: e.target.value })}
                    required
                    className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                  <label className="flex items-center space-x-2 text-xs mt-2">
                    <input
                      type="checkbox"
                      checked={formData.include_holding_fee_addendum || false}
                      onChange={(e) => setFormData({ ...formData, include_holding_fee_addendum: e.target.checked })}
                      className="rounded h-3 w-3"
                    />
                    <span>Include Holding Fee Addendum</span>
                  </label>
                </div>
                {formData.include_holding_fee_addendum && (
                  <>
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
                  </>
                )}
              </div>
            </CardContent>
            )}
          </Card>

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
              <CardContent className="px-3 pb-3">
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
                <div className="text-xs text-gray-600 bg-gray-50 p-2 rounded">
                  {formData.utilities_tenant || 'All'}
                </div>
                <p className="text-xs text-gray-500 mt-1">Auto-generated: All except landlord utilities</p>
                </div>
                <div>
                <Label className="text-xs mb-2">Landlord Utilities</Label>
                <div className="grid grid-cols-2 gap-2 mb-2">
                  {UTILITY_OPTIONS.map(utility => (
                    <label key={utility} className="flex items-center space-x-2 text-xs">
                      <input
                        type="checkbox"
                        checked={landlordUtilities.includes(utility)}
                        onChange={(e) => handleLandlordUtilitiesChange(utility, e.target.checked)}
                        className="rounded h-3 w-3"
                      />
                      <span>{utility}</span>
                    </label>
                  ))}
                </div>
                <div className="border-t pt-2 mt-2">
                  <label className="flex items-center space-x-2 text-xs mb-2">
                    <input
                      type="checkbox"
                      checked={useCustomUtility}
                      onChange={(e) => handleCustomUtilityToggle(e.target.checked)}
                      className="rounded h-3 w-3"
                    />
                    <span>Type a free text utility</span>
                  </label>
                  {useCustomUtility && (
                  <Input
                      value={customUtility}
                      onChange={(e) => handleCustomUtilityChange(e.target.value)}
                      placeholder="Enter custom utility"
                      className="text-sm h-8 mt-1"
                    />
                  )}
                </div>
              </div>
              <div>
                <Label className="text-xs mb-2">Tenant Provided Maintenance</Label>
                <div className="grid grid-cols-2 gap-2">
                  <label className="flex items-center space-x-2 text-xs">
                    <input
                      type="checkbox"
                      checked={formData.tenant_lawn_mowing ?? true}
                      onChange={(e) => setFormData({ ...formData, tenant_lawn_mowing: e.target.checked })}
                      className="rounded h-3 w-3"
                    />
                    <span>Mowing (tenant provided)</span>
                  </label>
                  <label className="flex items-center space-x-2 text-xs">
                    <input
                      type="checkbox"
                      checked={formData.tenant_snow_removal ?? true}
                      onChange={(e) => setFormData({ ...formData, tenant_snow_removal: e.target.checked })}
                      className="rounded h-3 w-3"
                    />
                    <span>Snow Removal (tenant provided)</span>
                  </label>
                  <label className="flex items-center space-x-2 text-xs">
                    <input
                      type="checkbox"
                      checked={formData.tenant_lawn_care || false}
                      onChange={(e) => setFormData({ ...formData, tenant_lawn_care: e.target.checked })}
                      className="rounded h-3 w-3"
                    />
                    <span>Lawn Care (tenant provided)</span>
                  </label>
                </div>
              </div>
              <div>
                <Label className="text-xs mb-2">Appliances Provided</Label>
                <div className="grid grid-cols-2 gap-2 mb-2">
                  {APPLIANCE_OPTIONS.map(appliance => (
                    <label key={appliance} className="flex items-center space-x-2 text-xs">
                      <input
                        type="checkbox"
                        checked={appliances.includes(appliance)}
                        onChange={(e) => handleAppliancesChange(appliance, e.target.checked)}
                        className="rounded h-3 w-3"
                      />
                      <span>{appliance}</span>
                    </label>
                  ))}
                </div>
                <Input
                  value={formData.appliances_provided || ''}
                  onChange={(e) => {
                    setFormData({ ...formData, appliances_provided: e.target.value });
                    // Update appliances state from the text input
                    const appliancesList = e.target.value.split(',').map((a: string) => a.trim()).filter((a: string) => APPLIANCE_OPTIONS.includes(a));
                    setAppliances(appliancesList);
                  }}
                  placeholder="Comma-separated appliances"
                  className="text-sm h-8 mt-1"
                />
              </div>
            </CardContent>
            )}
          </Card>

          {/* Section 7: General Policies & Addenda */}
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
              <div className="grid grid-cols-2 gap-3">
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
                        return (
                          <div key={idx}>
                            {parts.join(' ')}
                </div>
                        );
                      })}
                    </div>
                  )}
                  {pets.length === 0 && formData.pet_description && (
                    <div className="text-xs text-gray-600 mt-2">
                      {formData.pet_description}
                    </div>
                  )}
                </div>
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
              <CardContent className="px-3 pb-3">
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
                  <label className="flex items-center space-x-2 text-xs mt-2">
                    <input
                      type="checkbox"
                      checked={formData.has_garage_door_opener || false}
                      onChange={(e) => setFormData({ ...formData, has_garage_door_opener: e.target.checked })}
                      className="rounded h-3 w-3"
                    />
                    <span>Has Garage Door Opener</span>
                  </label>
                </div>
                {formData.has_garage_door_opener && (
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
                )}
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
              </div>
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
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="flex items-center space-x-2 text-xs">
                    <input
                      type="checkbox"
                      checked={formData.lead_paint_disclosure ?? true}
                      onChange={(e) => setFormData({ ...formData, lead_paint_disclosure: e.target.checked })}
                      className="rounded h-3 w-3"
                    />
                    <span>Lead Paint Disclosure</span>
                  </label>
                </div>
                {formData.lead_paint_disclosure && (
                <div>
                    <Label htmlFor="disclosure_lead_paint" className="text-xs">Lead Paint Year Built</Label>
                  <Input
                      id="disclosure_lead_paint"
                      type="number"
                      min="1800"
                      max="2100"
                      value={formData.disclosure_lead_paint || property?.year_built?.toString() || ''}
                      onChange={(e) => setFormData({ ...formData, disclosure_lead_paint: e.target.value })}
                      className="text-sm h-8 mt-1"
                      placeholder={property?.year_built?.toString() || 'Year built'}
                    />
                    {property?.year_built && (
                      <p className="text-xs text-gray-500 mt-1">From property: {property.year_built}</p>
                    )}
                </div>
                )}
                <div>
                  <label className="flex items-center space-x-2 text-xs">
                    <input
                      type="checkbox"
                      checked={formData.disclosure_methamphetamine || false}
                      onChange={(e) => setFormData({ ...formData, disclosure_methamphetamine: e.target.checked })}
                      className="rounded h-3 w-3"
                    />
                    <span>Methamphetamine Disclosure (MO)</span>
                  </label>
                </div>
              </div>
            </CardContent>
            )}
          </Card>

          {/* Section 10: Termination & Move-Out */}
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
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="flex items-center space-x-2 text-xs mb-2">
                    <input
                      type="checkbox"
                      checked={formData.early_termination_allowed ?? true}
                      onChange={(e) => setFormData({ ...formData, early_termination_allowed: e.target.checked })}
                      className="rounded h-3 w-3"
                    />
                    <span>Early Termination Allowed</span>
                  </label>
                </div>
                {formData.early_termination_allowed && (
                  <>
                    <div>
                      <Label htmlFor="early_termination_notice_days" className="text-xs">Notice Days</Label>
                  <Input
                    id="early_termination_notice_days"
                    type="number"
                    value={formData.early_termination_notice_days || ''}
                    onChange={(e) => setFormData({ ...formData, early_termination_notice_days: e.target.value })}
                        className="text-sm h-8 mt-1"
                  />
                </div>
                <div>
                      <Label htmlFor="early_termination_fee_amount" className="text-xs">Termination Fee Amount</Label>
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
                      <Label htmlFor="early_termination_fee_months" className="text-xs">Termination Fee Months</Label>
                  <Input
                        id="early_termination_fee_months"
                    type="number"
                        value={formData.early_termination_fee_months || ''}
                        onChange={(e) => setFormData({ ...formData, early_termination_fee_months: e.target.value })}
                        className="text-sm h-8 mt-1"
                  />
                </div>
                  </>
                )}
              </div>
            </CardContent>
            )}
          </Card>

          {/* Section 11: Notes */}
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
                  <div className="flex items-center justify-between mb-2">
                    <Label className="text-xs">Move-Out Costs</Label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={() => setShowMoveoutCostsModal(true)}
                    >
                      <Edit2 className="h-3 w-3 mr-1" />
                      Edit
                    </Button>
                  </div>
                  {moveoutCosts.length > 0 ? (
                    <div className="border rounded overflow-hidden">
                      <table className="w-full text-xs">
                        <thead className="bg-gray-50">
                          <tr>
                            <th className="text-left p-2 font-semibold">Item</th>
                            <th className="text-left p-2 font-semibold">Description</th>
                            <th className="text-right p-2 font-semibold">Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {moveoutCosts
                            .sort((a, b) => (a.order || 0) - (b.order || 0))
                            .map((cost, idx) => (
                              <tr key={idx} className="border-t">
                                <td className="p-2">{cost.item}</td>
                                <td className="p-2 text-gray-600">{cost.description || ''}</td>
                                <td className="p-2 text-right font-medium">
                                  ${parseFloat(cost.amount.toString()).toFixed(2)}
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-xs text-gray-500 p-2 border rounded bg-gray-50">
                      No move-out costs configured. Click Edit to add costs.
                    </div>
                  )}
                </div>
                <div>
                  <Label htmlFor="notes" className="text-xs">Notes</Label>
                  <Textarea
                    id="notes"
                    value={formData.notes || ''}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    rows={3}
                    placeholder="Additional notes about this lease..."
                    className="text-sm mt-1"
                  />
                </div>
              </CardContent>
            )}
          </Card>

          {/* Modals */}
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
                      onClick={() => {
                        // Store JSON for backend - always send as JSON string
                        const jsonString = JSON.stringify(moveoutCosts);
                        setFormData((prev: any) => ({ 
                          ...prev, 
                          moveout_costs_json: jsonString
                        }));
                        setShowMoveoutCostsModal(false);
                      }}
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
                                // Add tenant to array
                                setTenants([...tenants, {
                                  first_name: tenant.first_name,
                                  last_name: tenant.last_name,
                                  email: tenant.email,
                                  phone: tenant.phone
                                }]);
                              } else {
                                // Remove tenant from array
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
                      // Update formData.tenants as comma-separated string for display
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
                            {PET_TYPE_OPTIONS.map(type => (
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
                    <label className="flex items-center space-x-2 text-xs">
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
                  onClick={() => setPets([...pets, { type: '', name: '', breed: '', weight: '', isEmotionalSupport: false }])}
                >
                  <Plus className="h-3 w-3 mr-1" />
                  Add Pet
                </Button>
                <div className="flex justify-end gap-2 pt-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs"
                    onClick={() => {
                      // Generate pet description like: "2 pets: 1-Dog - Golden Retriever (George) 100lbs (emotional support animal), 1-Cat (Fluffy)"
                      const petDescriptions = pets.map((pet, idx) => {
                        const parts = [`${idx + 1}-${pet.type}`];
                        if (pet.breed) parts.push(`- ${pet.breed}`);
                        if (pet.name) parts.push(`(${pet.name})`);
                        if (pet.weight) parts.push(pet.weight);
                        if (pet.isEmotionalSupport) parts.push('(emotional support animal)');
                        return parts.join(' ');
                      });
                      const description = pets.length > 0 
                        ? `${pets.length} pet${pets.length > 1 ? 's' : ''}: ${petDescriptions.join(', ')}`
                        : '';
                      setFormData({ ...formData, pets: JSON.stringify(pets), pet_description: description });
                      setShowPetsModal(false);
                    }}
                  >
                    Save
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>

          {/* Submit */}
          <div className="flex justify-end gap-2">
            <Link href="/leases">
              <Button type="button" variant="outline" className="h-7 text-xs px-2">
                Cancel
              </Button>
            </Link>
            <Button type="submit" disabled={saving} className="h-7 text-xs px-2">
              {saving ? (
                <>
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="h-3 w-3 mr-1" />
                  Save Changes
                </>
              )}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}



