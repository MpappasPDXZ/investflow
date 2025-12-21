'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useProperties } from '@/lib/hooks/use-properties';
import { useTenants } from '@/lib/hooks/use-tenants';
import { useUnits } from '@/lib/hooks/use-units';
import { useLeases, useLeasesList, type LeaseCreate, type Tenant, type MoveOutCostItem, type Lease } from '@/lib/hooks/use-leases';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { FileText, Plus, X, Save, FileCheck, Loader2, ArrowLeft, ExternalLink, UserPlus, Edit, Trash2, Maximize2, Minimize2, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react';

export default function LeasesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const propertyIdFromUrl = searchParams.get('property_id');
  const leaseIdFromUrl = searchParams.get('lease_id');
  
  const { data: propertiesData } = useProperties();
  const { data: tenantsData } = useTenants();
  const { data: leasesData, refetch: refetchLeases } = useLeasesList();
  const { createLease, updateLease, generatePDF, getLease, deleteLease } = useLeases();
  
  // View state
  const [isTableExpanded, setIsTableExpanded] = useState(true);
  const [isEditingLease, setIsEditingLease] = useState(false);
  const [currentLeaseId, setCurrentLeaseId] = useState<string | null>(leaseIdFromUrl);
  
  // Loading/saving states  
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showSavedMessage, setShowSavedMessage] = useState(false);
  
  // PDF viewer
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [holdingFeeUrl, setHoldingFeeUrl] = useState<string | null>(null);
  
  // Move-out costs dialog
  const [isMoveoutCostsExpanded, setIsMoveoutCostsExpanded] = useState(false);
  
  // PDF viewer expanded state (for full-width PDF viewing)
  const [isPdfExpanded, setIsPdfExpanded] = useState(false);
  const [isParamsExpanded, setIsParamsExpanded] = useState(false);
  
  // Extract data from responses
  const properties = propertiesData?.items || [];
  const tenantProfiles = tenantsData?.tenants || [];
  const leases = leasesData?.leases || [];
  
  // Helper to get default dates - start at next 1st of month (today + 7 days, then next 1st)
  const getDefaultStartDate = () => {
    const today = new Date();
    const plus7Days = new Date(today);
    plus7Days.setDate(today.getDate() + 7);
    
    // Go to next 1st of month
    let month = plus7Days.getMonth();
    let year = plus7Days.getFullYear();
    
    // If we're past the 1st, go to next month's 1st
    if (plus7Days.getDate() > 1) {
      month += 1;
      if (month > 11) {
        month = 0;
        year += 1;
      }
    }
    
    const firstOfMonth = new Date(year, month, 1);
    return firstOfMonth.toISOString().split('T')[0];
  };
  
  // Calculate end date based on start date and duration in months
  const calculateEndDate = (startDate: string, months: number) => {
    const start = new Date(startDate);
    const end = new Date(start);
    end.setMonth(end.getMonth() + months);
    // End date is the last day of the previous month (day before anniversary)
    end.setDate(end.getDate() - 1);
    return end.toISOString().split('T')[0];
  };
  
  // Calculate prorated rent for partial month (30-day month basis)
  const calculateProratedRent = (monthlyRent: number, startDate: string) => {
    const start = new Date(startDate);
    const dayOfMonth = start.getDate();
    if (dayOfMonth === 1) return 0; // No proration needed
    const daysRemaining = 30 - dayOfMonth + 1;
    return Math.round((monthlyRent / 30) * daysRemaining * 100) / 100;
  };
  
  const defaultStartDate = getDefaultStartDate();
  
  // Form state with defaults
  const [formData, setFormData] = useState({
    property_id: propertyIdFromUrl || '',
    unit_id: '',
    state: 'NE' as 'NE' | 'MO',
    commencement_date: defaultStartDate,
    termination_date: calculateEndDate(defaultStartDate, 12),
    lease_duration_months: 12,
    auto_convert_month_to_month: false,
    monthly_rent: '',
    show_prorated_rent: false,
    prorated_rent_amount: '',
    prorated_rent_language: '',
    security_deposit: '',
    include_holding_fee_addendum: false,
    holding_fee_amount: '',
    holding_fee_date: '',
    payment_method: 'Check or Online Portal',
    tenants: [] as Tenant[],
    max_occupants: 3,
    max_adults: 2,
    num_children: 0,
    pets_allowed: false,
    pet_fee: '0',
    max_pets: 0,
    pets: [] as Array<{ type: string; breed?: string; name?: string; weight?: string }>,
    utilities_tenant: 'Gas, Sewer, Water, Electricity',
    utilities_landlord: 'Trash',
    parking_spaces: 2,
    parking_small_vehicles: 2,
    parking_large_trucks: 1,
    garage_spaces: 0,
    offstreet_parking_spots: 0,
    shared_parking_arrangement: '',
    include_keys_clause: true,
    has_front_door: true,
    has_back_door: true,
    front_door_keys: 1,
    back_door_keys: 1,
    key_replacement_fee: '86',
    has_shared_driveway: false,
    shared_driveway_with: '',
    has_garage: false,
    garage_outlets_prohibited: false,
    has_attic: false,
    attic_usage: '',
    has_basement: false,
    appliances_provided: '',
    snow_removal_responsibility: 'tenant',
    // Maintenance Responsibilities (true = Tenant, false = Landlord)
    tenant_lawn_mowing: true,
    tenant_snow_removal: true,
    tenant_lawn_care: false,
    lead_paint_disclosure: true,
    lead_paint_year_built: '',
    early_termination_allowed: true,
    early_termination_notice_days: 60,
    early_termination_fee_months: 2,
    moveout_costs: [
      { item: 'General Cleaning Fee', description: 'If unit not clean per move-in condition', amount: '200', order: 1 },
      { item: 'Carpet Cleaning', description: 'Professional carpet cleaning', amount: '75', order: 2 },
      { item: 'Trash Removal Fee', description: 'Per bag/item left behind', amount: '25', order: 3 },
      { item: 'Wall Repairs', description: 'Nail holes, drywall damage beyond normal wear', amount: '150', order: 4 },
      { item: 'Deep Cleaning Fee', description: 'Heavy cleaning of appliances, bathrooms', amount: '400', order: 5 },
      { item: 'Lock Re-Key', description: 'Per lock if keys not returned', amount: '75', order: 6 },
      { item: 'Pet Odor Treatment', description: 'Professional odor removal if needed', amount: '300', order: 7 },
      { item: 'Window/Blinds Cleaning', description: 'Inside and outside windows', amount: '50', order: 8 },
      { item: 'Appliance Deep Clean', description: 'Oven, refrigerator if excessively dirty', amount: '100', order: 9 },
      { item: 'Yard Cleanup', description: 'Lawn mowing, debris removal', amount: '100', order: 10 },
    ] as MoveOutCostItem[],
    methamphetamine_disclosure: false,
    owner_name: 'S&M Axios Heartland Holdings, LLC',
    owner_address: 'c/o Sarah Pappas, 1606 S 208th St, Elkhorn, NE 68022',
    moveout_inspection_rights: false,
    notes: '',
  });
  
  // Fetch units for selected property
  const { data: unitsData } = useUnits(formData.property_id || '');
  
  // Find selected property
  const selectedProperty = formData.property_id 
    ? properties.find((p: any) => p.id === formData.property_id) 
    : null;
  
  // Load lease from URL parameter if provided
  useEffect(() => {
    if (leaseIdFromUrl) {
      handleEditLease({ id: leaseIdFromUrl } as Lease);
    }
  }, [leaseIdFromUrl]);
  
  // Update state when property changes
  useEffect(() => {
    if (formData.property_id && properties.length > 0) {
      const prop = properties.find((p: any) => p.id === formData.property_id);
      if (prop) {
        const updates: any = {
          state: (prop.state || 'NE') as 'NE' | 'MO',
          lead_paint_year_built: prop.year_built?.toString() || '',
        };
        
        // For single-family, populate rent from property
        if (prop.property_type !== 'multi_family' && prop.current_monthly_rent) {
          updates.monthly_rent = prop.current_monthly_rent.toString();
          updates.security_deposit = prop.current_monthly_rent.toString();
        }
        
        setFormData(prev => ({ ...prev, ...updates }));
      }
    }
  }, [formData.property_id, properties]);
  
  // Auto-populate rent from selected unit
  useEffect(() => {
    if (formData.unit_id && unitsData?.items) {
      const selectedUnit = unitsData.items.find(u => u.id === formData.unit_id);
      if (selectedUnit && selectedUnit.current_monthly_rent != null) {
        setFormData(prev => ({
          ...prev,
          monthly_rent: selectedUnit.current_monthly_rent!.toString(),
          security_deposit: selectedUnit.current_monthly_rent!.toString(),
        }));
      }
    }
  }, [formData.unit_id, unitsData]);
  
  // ============== TENANT HELPERS ==============
  const addTenant = () => {
    setFormData(prev => {
      const newTenants = [...prev.tenants, { first_name: '', last_name: '', email: '', phone: '' }];
      const adultCount = newTenants.length;
      return {
        ...prev,
        tenants: newTenants,
        front_door_keys: prev.has_front_door ? adultCount : 0,
        back_door_keys: prev.has_back_door ? adultCount : 0,
      };
    });
  };
  
  const addTenantFromProfile = (tenantId: string) => {
    const tenantProfile = tenantProfiles.find(t => t.id === tenantId);
    if (tenantProfile) {
      setFormData(prev => {
        const newTenants = [
          ...prev.tenants,
          {
            first_name: tenantProfile.first_name,
            last_name: tenantProfile.last_name,
            email: tenantProfile.email || '',
            phone: tenantProfile.phone || '',
          },
        ];
        const adultCount = newTenants.length;
        return {
          ...prev,
          tenants: newTenants,
          front_door_keys: prev.has_front_door ? adultCount : 0,
          back_door_keys: prev.has_back_door ? adultCount : 0,
        };
      });
    }
  };
  
  const removeTenant = (index: number) => {
    setFormData(prev => {
      const newTenants = prev.tenants.filter((_, i) => i !== index);
      const adultCount = Math.max(newTenants.length, 1); // At least 1 key
      return {
        ...prev,
        tenants: newTenants,
        front_door_keys: prev.has_front_door ? adultCount : 0,
        back_door_keys: prev.has_back_door ? adultCount : 0,
      };
    });
  };
  
  const updateTenant = (index: number, field: keyof Tenant, value: string) => {
    setFormData(prev => ({
      ...prev,
      tenants: prev.tenants.map((t, i) => 
        i === index ? { ...t, [field]: value } : t
      ),
    }));
  };
  
  // ============== MOVE-OUT COST HELPERS ==============
  const addMoveoutCost = () => {
    const nextOrder = formData.moveout_costs.length + 1;
    setFormData(prev => ({
      ...prev,
      moveout_costs: [...prev.moveout_costs, { item: '', description: '', amount: '', order: nextOrder }],
    }));
  };
  
  const removeMoveoutCost = (index: number) => {
    setFormData(prev => ({
      ...prev,
      moveout_costs: prev.moveout_costs.filter((_, i) => i !== index),
    }));
  };
  
  const updateMoveoutCost = (index: number, field: keyof MoveOutCostItem, value: string | number) => {
    setFormData(prev => ({
      ...prev,
      moveout_costs: prev.moveout_costs.map((c, i) => 
        i === index ? { ...c, [field]: value } : c
      ),
    }));
  };
  
  // ============== PET HELPERS ==============
  const addPet = () => {
    setFormData(prev => ({
      ...prev,
      pets: [...prev.pets, { type: 'dog', name: '', weight: '', breed: '' }],
    }));
  };
  
  const removePet = (index: number) => {
    setFormData(prev => ({
      ...prev,
      pets: prev.pets.filter((_, i) => i !== index),
    }));
  };
  
  const updatePet = (index: number, field: string, value: string | boolean) => {
    setFormData(prev => ({
      ...prev,
      pets: prev.pets.map((p, i) => 
        i === index ? { ...p, [field]: value } : p
      ),
    }));
  };
  
  // Get bedroom count from selected unit or property
  const getBedroomCount = () => {
    let bedrooms = 2; // default
    if (formData.unit_id && unitsData?.items) {
      const unit = unitsData.items.find(u => u.id === formData.unit_id);
      if (unit?.bedrooms) bedrooms = unit.bedrooms;
    } else if (selectedProperty?.bedrooms) {
      bedrooms = selectedProperty.bedrooms;
    }
    return bedrooms;
  };
  
  // Get max children allowed based on bedrooms
  // Limits: 4 for 3+ bed, 3 for 2 bed, 2 for 1 bed
  const getMaxChildrenForBedrooms = () => {
    const bedrooms = getBedroomCount();
    if (bedrooms >= 3) return 4;
    if (bedrooms === 2) return 3;
    return 2;
  };
  
  // ============== CORE ACTIONS ==============
  
  const handleNewLease = () => {
    console.log('📝 [LEASE] Starting new lease creation');
    setIsEditingLease(true);
    setIsTableExpanded(false);
    setCurrentLeaseId(null);
    setPdfUrl(null);
    setHoldingFeeUrl(null);
    
    // Reset form to defaults
    const newStartDate = getDefaultStartDate();
    setFormData({
      property_id: propertyIdFromUrl || '',
      unit_id: '',
      state: 'NE',
      commencement_date: newStartDate,
      termination_date: calculateEndDate(newStartDate, 12),
      lease_duration_months: 12,
      auto_convert_month_to_month: false,
      monthly_rent: '',
      show_prorated_rent: false,
      prorated_rent_amount: '',
      prorated_rent_language: '',
      security_deposit: '',
      include_holding_fee_addendum: false,
      holding_fee_amount: '',
      holding_fee_date: '',
      payment_method: 'Check or Online Portal',
      tenants: [],
      max_occupants: 3,
      max_adults: 2,
      num_children: 0,
      pets_allowed: false,
      pet_fee: '0',
      max_pets: 0,
      pets: [],
      utilities_tenant: 'Gas, Sewer, Water, Electricity',
      utilities_landlord: 'Trash',
      parking_spaces: 2,
      parking_small_vehicles: 2,
      parking_large_trucks: 1,
      garage_spaces: 0,
      offstreet_parking_spots: 0,
      shared_parking_arrangement: '',
      include_keys_clause: true,
      has_front_door: true,
      has_back_door: true,
      front_door_keys: 1,
      back_door_keys: 1,
      key_replacement_fee: '50',
      has_shared_driveway: false,
      shared_driveway_with: '',
      has_garage: false,
      garage_outlets_prohibited: false,
      has_attic: false,
      attic_usage: '',
      has_basement: false,
      appliances_provided: '',
      snow_removal_responsibility: 'tenant',
      tenant_lawn_mowing: true,
      tenant_snow_removal: true,
      tenant_lawn_care: false,
      lead_paint_disclosure: true,
      lead_paint_year_built: '',
      early_termination_allowed: true,
      early_termination_notice_days: 60,
      early_termination_fee_months: 2,
      moveout_costs: [
        { item: 'General Cleaning Fee', description: 'If unit not clean per move-in condition', amount: '200', order: 1 },
        { item: 'Carpet Cleaning', description: 'Professional carpet cleaning', amount: '75', order: 2 },
        { item: 'Trash Removal Fee', description: 'Per bag/item left behind', amount: '25', order: 3 },
        { item: 'Wall Repairs', description: 'Nail holes, drywall damage beyond normal wear', amount: '150', order: 4 },
        { item: 'Deep Cleaning Fee', description: 'Heavy cleaning of appliances, bathrooms', amount: '400', order: 5 },
        { item: 'Lock Re-Key', description: 'Per lock if keys not returned', amount: '75', order: 6 },
        { item: 'Pet Odor Treatment', description: 'Professional odor removal if needed', amount: '300', order: 7 },
        { item: 'Window/Blinds Cleaning', description: 'Inside and outside windows', amount: '50', order: 8 },
        { item: 'Appliance Deep Clean', description: 'Oven, refrigerator if excessively dirty', amount: '100', order: 9 },
        { item: 'Yard Cleanup', description: 'Lawn mowing, debris removal', amount: '100', order: 10 },
      ],
      methamphetamine_disclosure: false,
      owner_name: 'S&M Axios Heartland Holdings, LLC',
      owner_address: 'c/o Sarah Pappas, 1606 S 208th St, Elkhorn, NE 68022',
      moveout_inspection_rights: false,
      notes: '',
    });
  };
  
  const handleEditLease = async (lease: Lease) => {
    console.log('✏️ [LEASE] Loading lease for editing:', lease.id);
      setLoading(true);
    setIsEditingLease(true);
    setIsTableExpanded(false);
    setCurrentLeaseId(lease.id);
    
    try {
      // Fetch full lease data
      const fullLease = await getLease(lease.id);
      console.log('📋 [LEASE] Loaded lease data:', JSON.stringify(fullLease, null, 2));
      
      // Populate form
      setFormData({
        property_id: fullLease.property_id,
        unit_id: fullLease.unit_id || '',
        state: fullLease.state as 'NE' | 'MO',
        commencement_date: fullLease.commencement_date,
        termination_date: fullLease.termination_date,
        lease_duration_months: (fullLease as any).lease_duration_months || 12,
        auto_convert_month_to_month: fullLease.auto_convert_month_to_month || false,
        monthly_rent: fullLease.monthly_rent?.toString() || '',
        show_prorated_rent: (fullLease as any).show_prorated_rent || false,
        prorated_rent_amount: (fullLease as any).prorated_rent_amount?.toString() || '',
        prorated_rent_language: (fullLease as any).prorated_rent_language || '',
        security_deposit: fullLease.security_deposit?.toString() || '',
        include_holding_fee_addendum: (fullLease as any).include_holding_fee_addendum || false,
        holding_fee_amount: (fullLease as any).holding_fee_amount?.toString() || '',
        holding_fee_date: (fullLease as any).holding_fee_date || '',
        payment_method: fullLease.payment_method || '',
        tenants: fullLease.tenants || [],
        max_occupants: fullLease.max_occupants || 3,
        max_adults: fullLease.max_adults || 2,
        num_children: fullLease.num_children !== undefined ? fullLease.num_children : 0,
        pets_allowed: fullLease.pets_allowed !== undefined ? fullLease.pets_allowed : false,
        pet_fee: (fullLease as any).pet_fee?.toString() || ((fullLease.max_pets || 0) === 1 ? '350' : (fullLease.max_pets || 0) >= 2 ? '500' : '0'),
        max_pets: fullLease.max_pets || 0,
        // Initialize pets array from stored pets or create empty entries if max_pets > 0
        pets: (() => {
          const storedPets = (fullLease as any).pets || [];
          const petCount = fullLease.max_pets || 0;
          if (storedPets.length >= petCount) return storedPets.slice(0, petCount);
          // Need to pad with empty entries
          const result = [...storedPets];
          while (result.length < petCount) {
            result.push({ type: 'dog', name: '', breed: '', weight: '' });
          }
          return result;
        })(),
        utilities_tenant: fullLease.utilities_tenant || '',
        utilities_landlord: fullLease.utilities_landlord || '',
        parking_spaces: fullLease.parking_spaces || 0,
        parking_small_vehicles: fullLease.parking_small_vehicles || 0,
        parking_large_trucks: fullLease.parking_large_trucks || 0,
        garage_spaces: (fullLease as any).garage_spaces || 0,
        offstreet_parking_spots: (fullLease as any).offstreet_parking_spots || 0,
        shared_parking_arrangement: (fullLease as any).shared_parking_arrangement || '',
        include_keys_clause: (fullLease as any).include_keys_clause ?? true,
        has_front_door: (fullLease as any).has_front_door ?? true,
        has_back_door: (fullLease as any).has_back_door ?? true,
        front_door_keys: fullLease.front_door_keys || 0,
        back_door_keys: fullLease.back_door_keys || 0,
        key_replacement_fee: fullLease.key_replacement_fee?.toString() || '',
        has_shared_driveway: fullLease.has_shared_driveway || false,
        shared_driveway_with: fullLease.shared_driveway_with || '',
        has_garage: fullLease.has_garage || false,
        garage_outlets_prohibited: fullLease.garage_outlets_prohibited || false,
        has_attic: fullLease.has_attic || false,
        attic_usage: fullLease.attic_usage || '',
        has_basement: fullLease.has_basement || false,
        appliances_provided: fullLease.appliances_provided || '',
        snow_removal_responsibility: fullLease.snow_removal_responsibility || 'tenant',
        tenant_lawn_mowing: (fullLease as any).tenant_lawn_mowing ?? true,
        tenant_snow_removal: (fullLease as any).tenant_snow_removal ?? true,
        tenant_lawn_care: (fullLease as any).tenant_lawn_care ?? false,
        lead_paint_disclosure: fullLease.lead_paint_disclosure || false,
        lead_paint_year_built: fullLease.lead_paint_year_built?.toString() || '',
        early_termination_allowed: fullLease.early_termination_allowed || false,
        early_termination_notice_days: fullLease.early_termination_notice_days || 60,
        early_termination_fee_months: fullLease.early_termination_fee_months || 2,
        moveout_costs: fullLease.moveout_costs || [],
        methamphetamine_disclosure: fullLease.methamphetamine_disclosure || false,
        owner_name: fullLease.owner_name || 'S&M Axios Heartland Holdings, LLC',
        owner_address: fullLease.owner_address || 'c/o Sarah Pappas, 1606 S 208th St, Elkhorn, NE 68022',
        moveout_inspection_rights: fullLease.moveout_inspection_rights || false,
        notes: fullLease.notes || '',
      });
      
      // Set PDF URL if exists
      if (fullLease.pdf_url) {
        setPdfUrl(fullLease.pdf_url);
      }
    } catch (err) {
      console.error('❌ [LEASE] Error loading lease:', err);
      alert('Failed to load lease');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveParameters = async (): Promise<string | null> => {
    console.log('💾 [LEASE] ========== SAVE START ==========');
    console.log('💾 [LEASE] Current lease ID:', currentLeaseId);
    console.log('💾 [LEASE] Form data:', JSON.stringify(formData, null, 2));
    
    setSaving(true);
    
    try {
      const payload: LeaseCreate = {
        property_id: formData.property_id,
        unit_id: formData.unit_id || undefined,
        state: formData.state,
        commencement_date: formData.commencement_date,
        termination_date: formData.termination_date,
        lease_duration_months: formData.lease_duration_months,
        auto_convert_month_to_month: formData.auto_convert_month_to_month,
        monthly_rent: parseFloat(formData.monthly_rent),
        show_prorated_rent: formData.show_prorated_rent,
        prorated_rent_amount: formData.prorated_rent_amount ? parseFloat(formData.prorated_rent_amount) : undefined,
        prorated_rent_language: formData.prorated_rent_language || undefined,
        security_deposit: parseFloat(formData.security_deposit),
        include_holding_fee_addendum: formData.include_holding_fee_addendum,
        holding_fee_amount: formData.holding_fee_amount ? parseFloat(formData.holding_fee_amount) : undefined,
        holding_fee_date: formData.holding_fee_date || undefined,
        payment_method: formData.payment_method,
        tenants: formData.tenants,
        max_occupants: formData.max_occupants,
        max_adults: formData.max_adults,
        num_children: formData.num_children,
        pets_allowed: formData.pets_allowed,
        pet_fee: formData.pet_fee ? parseFloat(formData.pet_fee) : undefined,
        max_pets: formData.max_pets,
        pets: formData.pets,
        utilities_tenant: formData.utilities_tenant,
        utilities_landlord: formData.utilities_landlord,
        parking_spaces: formData.parking_spaces,
        parking_small_vehicles: formData.parking_small_vehicles,
        parking_large_trucks: formData.parking_large_trucks,
        garage_spaces: formData.garage_spaces,
        offstreet_parking_spots: formData.offstreet_parking_spots,
        shared_parking_arrangement: formData.shared_parking_arrangement,
        include_keys_clause: formData.include_keys_clause,
        has_front_door: formData.has_front_door,
        has_back_door: formData.has_back_door,
        front_door_keys: formData.front_door_keys,
        back_door_keys: formData.back_door_keys,
        key_replacement_fee: formData.key_replacement_fee ? parseFloat(formData.key_replacement_fee) : undefined,
        has_shared_driveway: formData.has_shared_driveway,
        shared_driveway_with: formData.shared_driveway_with,
        has_garage: formData.has_garage,
        garage_outlets_prohibited: formData.garage_outlets_prohibited,
        has_attic: formData.has_attic,
        attic_usage: formData.attic_usage,
        has_basement: formData.has_basement,
        appliances_provided: formData.appliances_provided,
        snow_removal_responsibility: formData.snow_removal_responsibility,
        tenant_lawn_mowing: formData.tenant_lawn_mowing,
        tenant_snow_removal: formData.tenant_snow_removal,
        tenant_lawn_care: formData.tenant_lawn_care,
        lead_paint_disclosure: formData.lead_paint_disclosure,
        lead_paint_year_built: formData.lead_paint_year_built ? parseInt(formData.lead_paint_year_built) : undefined,
        early_termination_allowed: formData.early_termination_allowed,
        early_termination_notice_days: formData.early_termination_notice_days,
        early_termination_fee_months: formData.early_termination_fee_months,
        moveout_costs: formData.moveout_costs.map(c => ({
          ...c,
          amount: parseFloat(c.amount.toString()),
        })),
        methamphetamine_disclosure: formData.methamphetamine_disclosure,
        owner_name: formData.owner_name,
        owner_address: formData.owner_address,
        moveout_inspection_rights: formData.moveout_inspection_rights,
        notes: formData.notes,
      };
      
      console.log('📤 [LEASE] Payload to send:', JSON.stringify(payload, null, 2));
      
      let response: any;
      if (currentLeaseId) {
        console.log('🔄 [LEASE] Updating existing lease:', currentLeaseId);
        response = await updateLease(currentLeaseId, payload);
        console.log('✅ [LEASE] Update response:', JSON.stringify(response, null, 2));
      } else {
        console.log('✨ [LEASE] Creating new lease');
        response = await createLease(payload);
        console.log('✅ [LEASE] Create response:', JSON.stringify(response, null, 2));
        setCurrentLeaseId(response.id);
      }
      
      console.log('💾 [LEASE] ========== SAVE COMPLETE ==========');
      refetchLeases();
      
      // Show success message
      setShowSavedMessage(true);
      // Hide after 5 seconds
      setTimeout(() => setShowSavedMessage(false), 5000);
      
      return response.id;
      
    } catch (err) {
      console.error('❌ [LEASE] Save error:', err);
      alert('Failed to save lease parameters');
      return null;
    } finally {
      setSaving(false);
    }
  };
  
  // Generate PDF only - does NOT save first (requires lease to already be saved)
  const handleGeneratePDF = async () => {
    if (!currentLeaseId) {
      alert('Please save the lease first before generating a PDF.');
      return;
    }
    
    console.log('📄 [LEASE] Generating PDF (without save) for lease:', currentLeaseId);
    setGenerating(true);
    try {
      const response = await generatePDF(currentLeaseId, true);
      console.log('✅ [LEASE] PDF generated:', response);
      setPdfUrl(response.pdf_url);
      setHoldingFeeUrl((response as any).holding_fee_pdf_url || null);
      refetchLeases();
    } catch (err) {
      console.error('❌ [LEASE] PDF generation error:', err);
      alert('Failed to generate PDF');
    } finally {
      setGenerating(false);
    }
  };
  
  const handleDeleteLease = async (leaseId: string) => {
    if (!confirm('Are you sure you want to delete this lease?')) return;
    
    try {
      console.log('🗑️ [LEASE] Deleting lease:', leaseId);
      await deleteLease(leaseId);
      refetchLeases();
      
      // If we're editing the deleted lease, go back to table
      if (currentLeaseId === leaseId) {
        handleBackToTable();
      }
    } catch (err) {
      console.error('❌ [LEASE] Delete error:', err);
      alert('Failed to delete lease');
    }
  };

  const handleBackToTable = () => {
    setIsEditingLease(false);
    setIsTableExpanded(true);
    setCurrentLeaseId(null);
    setPdfUrl(null);
    setHoldingFeeUrl(null);
  };
  
  // ============== HELPER FUNCTIONS ==============
  
  const getPropertyName = (propertyId: string) => {
    const property = properties.find((p: any) => p.id === propertyId);
    return property?.display_name || property?.address_line1 || 'Unknown Property';
  };
  
  const getTenantNames = (tenants: Tenant[]) => {
    if (!tenants || tenants.length === 0) return '—';
    return tenants.map(t => `${t.first_name} ${t.last_name}`).join(', ');
  };
  
  const getStatusBadgeClass = (status: string) => {
    const variants: Record<string, string> = {
      draft: 'bg-gray-100 text-gray-800',
      pending_signature: 'bg-yellow-100 text-yellow-800',
      active: 'bg-green-100 text-green-800',
      expired: 'bg-red-100 text-red-800',
      terminated: 'bg-red-100 text-red-800',
    };
    return variants[status] || variants.draft;
  };
  
  // ============== RENDER ==============
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-200px)]">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">Loading lease...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 h-[calc(100vh-48px)] flex flex-col">
      {/* ========== COLLAPSIBLE LEASE TABLE HEADER ========== */}
      {/* When editing, show minimal header bar; when not editing, show full table */}
      {isEditingLease ? (
        /* Minimal header when editing - just shows Back to Table button */
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-gray-700">
              {currentLeaseId ? 'Editing Lease' : 'New Lease'}
            </h2>
            {selectedProperty && (
              <Badge variant="secondary" className="text-xs">
                {selectedProperty.display_name}
              </Badge>
            )}
        </div>
          <Button
            onClick={handleBackToTable}
            variant="outline"
            size="sm"
            className="h-8 text-xs px-3"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back to Table
          </Button>
      </div>
      ) : (
        /* Full table when not editing */
        <Card className={`mb-4 transition-all duration-200 ${isTableExpanded ? '' : 'pb-0'}`}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 py-3">
            <div className="flex items-center gap-3">
              <CardTitle className="text-sm font-bold">Lease Parameters</CardTitle>
              <Badge variant="secondary" className="text-xs">
                {leases.length} lease{leases.length !== 1 ? 's' : ''}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <Button
                onClick={handleNewLease}
                className="bg-black hover:bg-gray-800 text-white h-8 text-xs px-3"
              >
                <Plus className="h-3 w-3 mr-1.5" />
                New Lease
              </Button>
              <Button
                onClick={() => setIsTableExpanded(!isTableExpanded)}
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
              >
                {isTableExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </Button>
            </div>
          </CardHeader>
          
          {isTableExpanded && (
            <CardContent className="pt-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs w-16">Lease #</TableHead>
                    <TableHead className="text-xs w-16">Official</TableHead>
                    <TableHead className="text-xs">Property</TableHead>
                    <TableHead className="text-xs">Tenants</TableHead>
                    <TableHead className="text-xs">Term</TableHead>
                    <TableHead className="text-xs text-right">Rent</TableHead>
                    <TableHead className="text-xs">Status</TableHead>
                    <TableHead className="text-xs text-right w-24">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {leases.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center py-8 text-gray-500 text-sm">
                        No leases yet. Click "New Lease" to create one.
                      </TableCell>
                    </TableRow>
                  ) : (
                    leases.map((lease) => (
                      <TableRow 
                        key={lease.id} 
                        className={`cursor-pointer hover:bg-gray-50 ${currentLeaseId === lease.id ? 'bg-blue-50' : ''}`}
                        onClick={() => handleEditLease(lease)}
                      >
                        <TableCell className="text-xs font-semibold">#{lease.lease_number}</TableCell>
                        <TableCell className="text-xs">
                          <Checkbox
                            checked={lease.is_official}
                            onClick={(e) => e.stopPropagation()}
                            onCheckedChange={async (checked) => {
                              try {
                                await updateLease(lease.id, { is_official: checked as boolean });
                                refetchLeases();
                              } catch (err) {
                                console.error('Error updating official status:', err);
                              }
                            }}
                            className="h-4 w-4"
                          />
                        </TableCell>
                        <TableCell className="text-xs">{getPropertyName(lease.property_id)}</TableCell>
                        <TableCell className="text-xs">{getTenantNames(lease.tenants)}</TableCell>
                        <TableCell className="text-xs">
                          {new Date(lease.commencement_date).toLocaleDateString()} – {new Date(lease.termination_date).toLocaleDateString()}
                        </TableCell>
                        <TableCell className="text-xs text-right font-medium">${lease.monthly_rent}</TableCell>
                        <TableCell>
                          <Badge className={`text-xs ${getStatusBadgeClass(lease.status)}`}>
                            {lease.status.replace('_', ' ')}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleEditLease(lease)}
                              className="h-7 w-7 p-0"
                              title="Edit"
                            >
                              <Edit className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDeleteLease(lease.id)}
                              className="h-7 w-7 p-0 text-red-600 hover:bg-red-50"
                              title="Delete"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          )}
        </Card>
      )}
      
      {/* ========== 50/50 SPLIT: PARAMETERS FORM + PDF VIEWER ========== */}
      {isEditingLease && (
        <div className={`flex-1 grid gap-4 min-h-0 ${isPdfExpanded || isParamsExpanded ? 'grid-cols-1' : 'grid-cols-2'}`}>
          {/* LEFT: Parameters Form (50%) - Hidden when PDF is expanded */}
          {!isPdfExpanded && (
          <div className="flex flex-col min-h-0" style={{ width: '100%' }}>
            <Card className="flex-1 flex flex-col min-h-0">
              <CardHeader className="py-2 border-b flex-shrink-0 flex flex-row items-center justify-between">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-sm font-bold">
                    {currentLeaseId ? 'Edit Lease' : 'New Lease'}
                  </CardTitle>
                  {isParamsExpanded && (
                    <Badge variant="secondary" className="text-xs">Expanded</Badge>
                  )}
                </div>
                <div className="flex gap-1.5 items-center">
                  {showSavedMessage && !generating && (
                    <Badge variant="secondary" className="text-xs bg-blue-100 text-blue-700 border-blue-200">
                      ✓ Values saved
                    </Badge>
                  )}
                  {generating && (
                    <Badge variant="secondary" className="text-xs bg-amber-100 text-amber-700 border-amber-200">
                      Generating PDF...
                    </Badge>
                  )}
                  <Button
                    onClick={handleSaveParameters}
                    disabled={saving || !formData.property_id || formData.tenants.length === 0}
                    variant="outline"
                    size="sm"
                    className="h-7 text-xs px-2"
                  >
                    {saving ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <>
                        <Save className="h-3 w-3 mr-1" />
                        Save
                      </>
                    )}
                  </Button>
                  <Button
                    onClick={handleGeneratePDF}
                    disabled={saving || generating || !currentLeaseId}
                    size="sm"
                    className="h-7 text-xs px-2 bg-black hover:bg-gray-800"
                    title={!currentLeaseId ? 'Save the lease first' : 'Generate PDF from saved parameters'}
                  >
                    {generating ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <>
                        <FileCheck className="h-3 w-3 mr-1" />
                        Gen PDF
                      </>
                    )}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setIsParamsExpanded(!isParamsExpanded)}
                    className="h-7 w-7 p-0"
                    title={isParamsExpanded ? 'Show PDF' : 'Expand parameters'}
                  >
                    {isParamsExpanded ? (
                      <Minimize2 className="h-3.5 w-3.5" />
                    ) : (
                      <Maximize2 className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
                
                {/* Property Selection */}
                <div className="space-y-2">
                  <Label className="text-xs font-semibold">Property</Label>
              <Select
                    value={formData.property_id}
                    onValueChange={(value) => setFormData({ ...formData, property_id: value, unit_id: '' })}
              >
                <SelectTrigger className="text-sm h-9">
                      <SelectValue placeholder="Select property" />
                </SelectTrigger>
                <SelectContent>
                      {properties.map((p: any) => (
                        <SelectItem key={p.id} value={p.id}>{p.display_name}</SelectItem>
                      ))}
                </SelectContent>
              </Select>
                  
                  {/* Unit dropdown for multi-family */}
                  {selectedProperty?.property_type === 'multi_family' && unitsData?.items && unitsData.items.length > 0 && (
              <Select
                      value={formData.unit_id}
                      onValueChange={(value) => setFormData({ ...formData, unit_id: value })}
              >
                <SelectTrigger className="text-sm h-9">
                        <SelectValue placeholder="Select unit" />
                </SelectTrigger>
                <SelectContent>
                        {unitsData.items.map((unit) => (
                          <SelectItem key={unit.id} value={unit.id}>
                            Unit {unit.unit_number}
                            {unit.bedrooms && ` - ${unit.bedrooms} bed`}
                            {unit.bathrooms && ` / ${unit.bathrooms} bath`}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                  
                  <Select
                    value={formData.state}
                    onValueChange={(value) => setFormData({ ...formData, state: value as 'NE' | 'MO' })}
                  >
                    <SelectTrigger className="text-sm h-9">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                  <SelectItem value="NE">Nebraska</SelectItem>
                  <SelectItem value="MO">Missouri</SelectItem>
                </SelectContent>
              </Select>
            </div>
                
                <Separator />
                
                {/* Lease Duration & Terms */}
                <div className="space-y-2">
                  <Label className="text-xs font-semibold">Lease Duration</Label>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <Label className="text-xs">Start Date</Label>
                      <Input
                        type="date"
                        value={formData.commencement_date}
                        onChange={(e) => {
                          const newStart = e.target.value;
                          setFormData({ 
                            ...formData, 
                            commencement_date: newStart,
                            termination_date: calculateEndDate(newStart, formData.lease_duration_months)
                          });
                        }}
                        className="text-sm h-9"
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Term (Mo's)</Label>
                      <Select
                        value={formData.lease_duration_months.toString()}
                        onValueChange={(value) => {
                          const months = parseInt(value);
                          setFormData({
                            ...formData,
                            lease_duration_months: months,
                            termination_date: calculateEndDate(formData.commencement_date, months)
                          });
                        }}
                      >
                        <SelectTrigger className="text-sm h-9">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Array.from({ length: 36 }, (_, i) => i + 1).map((m) => (
                            <SelectItem key={m} value={m.toString()}>
                              {m} month{m !== 1 ? 's' : ''}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-xs">End Date <span className="text-gray-400">(auto)</span></Label>
                      <Input
                        type="date"
                        value={formData.termination_date}
                        readOnly
                        className="text-sm h-9 bg-gray-100 cursor-not-allowed"
                        title="Auto-calculated from start date + duration"
                      />
                    </div>
                  </div>
                  <p className="text-[10px] text-gray-500">
                    Lease: {new Date(formData.commencement_date).toLocaleDateString()} – {new Date(formData.termination_date).toLocaleDateString()} 
                    ({formData.lease_duration_months} month{formData.lease_duration_months !== 1 ? 's' : ''})
                  </p>
                </div>
                
                <Separator />
                
                {/* Rent & Deposit */}
                <div className="space-y-2">
                  <Label className="text-xs font-semibold">Rent & Deposit</Label>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <Label className="text-xs">Monthly Rent</Label>
                      <Input
                        type="number"
                        step="0.01"
                        value={formData.monthly_rent}
                        onChange={(e) => setFormData({ ...formData, monthly_rent: e.target.value })}
                        className="text-sm h-9"
                        placeholder="2500.00"
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Security Deposit</Label>
                      <Input
                        type="number"
                        step="0.01"
                        value={formData.security_deposit}
                        onChange={(e) => setFormData({ ...formData, security_deposit: e.target.value })}
                        className="text-sm h-9"
                        placeholder="2500.00"
                      />
                    </div>
                  </div>
                  
                  {/* Holding Fee Addendum */}
                  <div className="space-y-2 p-3 border rounded-md bg-muted/30">
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="include_holding_fee"
                        checked={formData.include_holding_fee_addendum}
                        onCheckedChange={(checked) => {
                          const includeHolding = checked as boolean;
                          setFormData({
                            ...formData,
                            include_holding_fee_addendum: includeHolding,
                            holding_fee_amount: includeHolding && !formData.holding_fee_amount 
                              ? formData.security_deposit 
                              : formData.holding_fee_amount,
                          });
                        }}
                      />
                      <Label htmlFor="include_holding_fee" className="text-xs font-medium cursor-pointer">
                        Include Holding Fee Addendum (converts to security deposit)
                      </Label>
                    </div>
                    
                    {formData.include_holding_fee_addendum && (
                      <div className="grid grid-cols-2 gap-3 mt-2">
                        <div>
                          <Label className="text-xs">Holding Fee Amount</Label>
                          <Input
                            type="number"
                            step="0.01"
                            value={formData.holding_fee_amount}
                            onChange={(e) => setFormData({ ...formData, holding_fee_amount: e.target.value })}
                            className="text-sm h-9"
                            placeholder={formData.security_deposit || "Same as security deposit"}
                          />
                          <p className="text-xs text-muted-foreground mt-1">
                            Defaults to security deposit amount
                          </p>
                        </div>
                        <div>
                          <Label className="text-xs">Date Collected</Label>
                          <Input
                            type="date"
                            value={formData.holding_fee_date}
                            onChange={(e) => setFormData({ ...formData, holding_fee_date: e.target.value })}
                            className="text-sm h-9"
                          />
                          <p className="text-xs text-muted-foreground mt-1">
                            When holding fee was received
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                  
                  {/* Prorated Rent */}
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="show_prorated"
                      checked={formData.show_prorated_rent}
                      onCheckedChange={(checked) => {
                        const showProrated = checked as boolean;
                        const startDay = new Date(formData.commencement_date).getDate();
                        const proratedAmount = showProrated && formData.monthly_rent && startDay > 1
                          ? calculateProratedRent(parseFloat(formData.monthly_rent), formData.commencement_date).toString()
                          : '';
                        const proratedLang = showProrated && startDay > 1
                          ? `Tenant shall pay prorated rent of $${proratedAmount} for the partial first month (${startDay}th to end of month, based on 30-day month).`
                          : '';
                        setFormData({
                          ...formData,
                          show_prorated_rent: showProrated,
                          prorated_rent_amount: proratedAmount,
                          prorated_rent_language: proratedLang,
                        });
                      }}
                      className="h-4 w-4"
                    />
                    <Label htmlFor="show_prorated" className="text-xs">
                      Include Prorated Rent 
                      {new Date(formData.commencement_date).getDate() === 1 && (
                        <span className="text-gray-400 ml-1">(not needed - starts on 1st)</span>
                      )}
                    </Label>
                  </div>
                  
                  {formData.show_prorated_rent && new Date(formData.commencement_date).getDate() > 1 && (
                    <div className="p-2 bg-blue-50 border border-blue-200 rounded space-y-2">
                      <div className="flex items-center justify-between">
                        <Label className="text-xs text-blue-800 font-medium">Prorated Rent</Label>
                        <span className="text-xs font-semibold text-blue-800">
                          ${formData.prorated_rent_amount || '0.00'}
                        </span>
                      </div>
                      <p className="text-[10px] text-blue-700">
                        Start on {new Date(formData.commencement_date).getDate()}th → 
                        {30 - new Date(formData.commencement_date).getDate() + 1} days remaining × 
                        (${formData.monthly_rent || 0} ÷ 30)
                      </p>
                      <div>
                        <Label className="text-xs text-blue-800">Lease Language</Label>
                        <textarea
                          value={formData.prorated_rent_language}
                          onChange={(e) => setFormData({ ...formData, prorated_rent_language: e.target.value })}
                          className="w-full px-2 py-1 border border-blue-300 rounded-md text-xs h-14 resize-none bg-white"
                        />
                      </div>
                    </div>
                  )}
                </div>
                
                <Separator />
                
                {/* Tenants */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label className="text-xs font-semibold">Tenants</Label>
                    <Button variant="outline" size="sm" onClick={addTenant} className="h-7 text-xs px-2">
                      <Plus className="h-3 w-3 mr-1" />
                      Add
            </Button>
          </div>
                  
                  {/* Add from profile */}
                  {tenantProfiles.length > 0 && (
                    <Select onValueChange={(value) => value && addTenantFromProfile(value)} value="">
                      <SelectTrigger className="text-sm h-8">
                        <SelectValue placeholder="Add from tenant profile..." />
                      </SelectTrigger>
                      <SelectContent>
                        {tenantProfiles.map((tenant) => (
                          <SelectItem key={tenant.id} value={tenant.id} className="text-sm">
                            {tenant.first_name} {tenant.last_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                  
                  {formData.tenants.length === 0 && (
                    <div className="text-center py-3 text-gray-500 text-xs border rounded bg-gray-50">
                      No tenants added yet
                    </div>
                  )}
                  
                  {formData.tenants.map((tenant, index) => (
                    <div key={index} className="space-y-1 p-2 border rounded bg-gray-50">
                      <div className="flex justify-between items-center">
                        <span className="text-xs font-medium">Tenant {index + 1}</span>
                        <Button variant="ghost" size="sm" onClick={() => removeTenant(index)} className="h-6 w-6 p-0 text-red-600">
                          <X className="h-3 w-3" />
                </Button>
            </div>
                      <div className="grid grid-cols-2 gap-1">
                        <Input placeholder="First name" value={tenant.first_name} onChange={(e) => updateTenant(index, 'first_name', e.target.value)} className="text-xs h-7" />
                        <Input placeholder="Last name" value={tenant.last_name} onChange={(e) => updateTenant(index, 'last_name', e.target.value)} className="text-xs h-7" />
                      </div>
                      <div className="grid grid-cols-2 gap-1">
                        <Input placeholder="Email" type="email" value={tenant.email || ''} onChange={(e) => updateTenant(index, 'email', e.target.value)} className="text-xs h-7" />
                        <Input placeholder="Phone" type="tel" value={tenant.phone || ''} onChange={(e) => updateTenant(index, 'phone', e.target.value)} className="text-xs h-7" />
                      </div>
                    </div>
                  ))}
                </div>
                
                <Separator />
                
                {/* Occupancy */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs font-semibold">Occupancy</Label>
                    <span className="text-[10px] text-gray-500">
                      {getBedroomCount()} bedroom{getBedroomCount() !== 1 ? 's' : ''} → 
                      max {getMaxChildrenForBedrooms()} children
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <Label className="text-xs">Adults</Label>
                      <Select
                        value={formData.max_adults.toString()}
                        onValueChange={(value) => {
                          const adults = parseInt(value);
                          setFormData({ 
                            ...formData, 
                            max_adults: adults,
                            max_occupants: adults + formData.num_children
                          });
                        }}
                      >
                        <SelectTrigger className="text-sm h-8">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {[1, 2, 3, 4, 5, 6].map((n) => (
                            <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-xs">Children (max {getMaxChildrenForBedrooms()})</Label>
                      <Select 
                        value={formData.num_children.toString()}
                        onValueChange={(value) => {
                          const children = parseInt(value);
                          setFormData({ 
                            ...formData, 
                            num_children: children,
                            max_occupants: formData.max_adults + children
                          });
                        }}
                      >
                        <SelectTrigger className="text-sm h-8">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Array.from({ length: getMaxChildrenForBedrooms() + 1 }, (_, i) => (
                            <SelectItem key={i} value={i.toString()}>{i}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-xs">Total Occupants <span className="text-gray-400">(auto)</span></Label>
                      <div className="flex items-center h-8 px-3 bg-gray-100 rounded-md border text-sm font-medium">
                        {formData.max_adults + formData.num_children}
                      </div>
                    </div>
                  </div>
                  <p className="text-[10px] text-gray-500">
                    {formData.max_adults} adult{formData.max_adults !== 1 ? 's' : ''} + {formData.num_children} child{formData.num_children !== 1 ? 'ren' : ''} = {formData.max_adults + formData.num_children} total occupants
                  </p>
                </div>
                
                <Separator />
                
                {/* Pets */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label className="text-xs font-semibold">Pets</Label>
                    <div className="flex items-center gap-2">
                        <Checkbox
                        id="pets_allowed" 
                        checked={formData.pets_allowed} 
                        onCheckedChange={(checked) => setFormData({ ...formData, pets_allowed: checked as boolean })} 
                        className="h-4 w-4" 
                      />
                      <Label htmlFor="pets_allowed" className="text-xs">Allowed</Label>
                    </div>
                  </div>
                  
                  {formData.pets_allowed && (
                    <div className="p-2 bg-amber-50 border border-amber-200 rounded space-y-3">
                      {/* Total Pets & Fee */}
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <Label className="text-xs text-amber-800">Total Pets</Label>
                          <Select
                            value={formData.max_pets.toString()}
                            onValueChange={(value) => {
                              const count = parseInt(value);
                              // Calculate default fee: $350 for 1, $500 for 2+
                              const defaultFee = count === 0 ? '0' : count === 1 ? '350' : '500';
                              // Adjust pets array to match count
                              const currentPets = [...formData.pets];
                              while (currentPets.length < count) {
                                currentPets.push({ type: 'dog', name: '', breed: '', weight: '' });
                              }
                              while (currentPets.length > count) {
                                currentPets.pop();
                              }
                              setFormData({ 
                                ...formData, 
                                max_pets: count,
                                pet_fee: defaultFee,
                                pets: currentPets
                              });
                            }}
                          >
                            <SelectTrigger className="text-xs h-7 bg-white">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {[0,1,2,3,4,5,6,7,8,9,10].map((n) => (
                                <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-xs text-amber-800">Pet Fee <span className="text-[10px] text-amber-600">($350/1, $500 max)</span></Label>
                          <div className="relative">
                            <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-gray-500">$</span>
                            <Input
                              type="number"
                              value={formData.pet_fee || ''}
                              onChange={(e) => setFormData({ ...formData, pet_fee: e.target.value })}
                              className="text-xs h-7 pl-5 bg-white"
                              placeholder="350"
                            />
                          </div>
                        </div>
                      </div>
                      
                      {/* Pet List */}
                      {formData.pets.length > 0 && (
                        <div className="space-y-2">
                          <Label className="text-xs text-amber-800 font-medium">Pet Details</Label>
                          {formData.pets.map((pet, index) => (
                            <div key={index} className="p-2 bg-white border border-amber-100 rounded space-y-1.5">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-medium text-amber-700 w-12">#{index + 1}</span>
                                <Select
                                  value={pet.type}
                                  onValueChange={(value) => updatePet(index, 'type', value)}
                                >
                                  <SelectTrigger className="text-xs h-7 w-20">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="dog">Dog</SelectItem>
                                    <SelectItem value="cat">Cat</SelectItem>
                                    <SelectItem value="other">Other</SelectItem>
                                  </SelectContent>
                                </Select>
                                <Input
                                  placeholder="Name"
                                  value={pet.name || ''}
                                  onChange={(e) => updatePet(index, 'name', e.target.value)}
                                  className="text-xs h-7 flex-1"
                                />
                                {pet.type === 'dog' && (
                                  <>
                                    <Input
                                      placeholder="Breed"
                                      value={pet.breed || ''}
                                      onChange={(e) => updatePet(index, 'breed', e.target.value)}
                                      className="text-xs h-7 w-24"
                                    />
                                    <Input
                                      placeholder="lbs"
                                      value={pet.weight || ''}
                                      onChange={(e) => updatePet(index, 'weight', e.target.value)}
                                      className="text-xs h-7 w-14"
                                    />
                                  </>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                      
                      {/* Generated Clause Preview */}
                      {formData.pets.length > 0 && (
                        <div className="text-[11px] text-amber-700 leading-relaxed bg-amber-100/50 p-2 rounded">
                          <span className="font-medium">Clause: </span>
                          Pet Fee is ${formData.pet_fee || '0'} and includes {formData.pets.length} pet{formData.pets.length !== 1 ? 's' : ''}: 
                          {(() => {
                            // Group pets by type
                            const grouped: Record<string, Array<{name?: string; weight?: string}>> = {};
                            formData.pets.forEach(pet => {
                              const type = pet.type === 'dog' ? 'Dog' : pet.type === 'cat' ? 'Cat' : 'Other';
                              if (!grouped[type]) grouped[type] = [];
                              grouped[type].push({ name: pet.name, weight: pet.type === 'dog' ? pet.weight : undefined });
                            });
                            // Format each group
                            return Object.entries(grouped).map(([type, pets]) => {
                              const count = pets.length;
                              const names = pets.filter(p => p.name).map(p => p.name);
                              const weights = pets.filter(p => p.weight).map(p => `${p.weight}lbs`);
                              let str = `${count}-${type}${count > 1 ? 's' : ''}`;
                              if (names.length > 0) str += ` (${names.join(' and ')})`;
                              if (weights.length > 0) str += ` ${weights.join(', ')}`;
                              return str;
                            }).join(', ');
                          })()}. 
                          Pets are replaceable at no cost. All pets must be approved if breed is changed or weight is increased.
                        </div>
                      )}
                    </div>
                  )}
                </div>
                
                <Separator />
                
                {/* Parking */}
                <div className="space-y-2">
                  <Label className="text-xs font-semibold">Parking</Label>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <Label className="text-xs">Garage Spaces</Label>
                      <Select
                        value={formData.garage_spaces.toString()}
                        onValueChange={(value) => {
                          const garageSpaces = parseInt(value);
                          const newTotal = garageSpaces + formData.offstreet_parking_spots;
                          setFormData({ 
                            ...formData, 
                            garage_spaces: garageSpaces,
                            has_garage: garageSpaces > 0,
                            parking_spaces: newTotal
                          });
                        }}
                      >
                        <SelectTrigger className="text-xs h-7">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {[0,1,2,3,4,5,6,7,8,9].map((n) => (
                            <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-xs">Off-Street Spots</Label>
                      <Select
                        value={formData.offstreet_parking_spots.toString()}
                        onValueChange={(value) => {
                          const offStreet = parseInt(value);
                          const newTotal = formData.garage_spaces + offStreet;
                          setFormData({ 
                            ...formData, 
                            offstreet_parking_spots: offStreet,
                            parking_spaces: newTotal
                          });
                        }}
                      >
                        <SelectTrigger className="text-xs h-7">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {[0,1,2,3,4,5,6,7,8,9].map((n) => (
                            <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-xs">Total <span className="text-gray-400">(editable)</span></Label>
                      <Select
                        value={formData.parking_spaces.toString()}
                        onValueChange={(value) => setFormData({ ...formData, parking_spaces: parseInt(value) })}
                      >
                        <SelectTrigger className="text-xs h-7">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {[0,1,2,3,4,5,6,7,8,9,10,11,12].map((n) => (
                            <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <div>
                    <Label className="text-xs">Parking Notes</Label>
                    <textarea 
                      value={formData.shared_parking_arrangement || ''}
                      onChange={(e) => setFormData({ ...formData, shared_parking_arrangement: e.target.value })}
                      placeholder="e.g., 1 garage spot; parking in front of garage must not block other off-street spots; 1 additional off-street spot allows other tenant to park two mid-size cars."
                      className="w-full px-2 py-1 border border-gray-300 rounded-md text-xs h-14 resize-none"
                    />
                  </div>
                </div>
                
                <Separator />
                
                {/* Shared Driveway */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs font-semibold">Shared Driveway</Label>
                    <div className="flex items-center gap-2">
                      <Checkbox 
                        id="shared_driveway" 
                        checked={formData.has_shared_driveway} 
                        onCheckedChange={(checked) => setFormData({ ...formData, has_shared_driveway: checked as boolean })} 
                          className="h-4 w-4"
                        />
                      <Label htmlFor="shared_driveway" className="text-xs">Enable Clause</Label>
                          </div>
                  </div>
                  {formData.has_shared_driveway && (
                    <div className="p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800 space-y-2">
                      <p className="font-medium">Shared Driveway Language:</p>
                      <p className="text-[11px] leading-relaxed">
                        Shared driveways with non-duplex neighbors must not be blocked except for temporary heavy offloading. 
                        Violations may lead to towing as per posted signage.
                      </p>
                      <div>
                        <Label className="text-xs text-amber-800">Shared With</Label>
                        <Input
                          value={formData.shared_driveway_with || ''}
                          onChange={(e) => setFormData({ ...formData, shared_driveway_with: e.target.value })}
                          placeholder="e.g., Neighbor at 1234 Main St"
                          className="text-xs h-7 bg-white"
                        />
                      </div>
                    </div>
                  )}
                </div>
                
                <Separator />
                
                {/* Maintenance Responsibilities */}
                <div className="space-y-2">
                  <Label className="text-xs font-semibold">Maintenance Responsibilities</Label>
                  <p className="text-[11px] text-muted-foreground">Check boxes to assign responsibility to Tenant. Unchecked = Landlord handles.</p>
                  
                  <div className="grid gap-3 p-2 bg-green-50 border border-green-200 rounded">
                    {/* Lawn Mowing */}
                    <div className="flex items-start gap-2">
                      <Checkbox 
                        id="tenant_lawn_mowing" 
                        checked={formData.tenant_lawn_mowing} 
                        onCheckedChange={(checked) => setFormData({ ...formData, tenant_lawn_mowing: checked as boolean })} 
                        className="h-4 w-4 mt-0.5"
                      />
                      <div className="flex-1">
                        <Label htmlFor="tenant_lawn_mowing" className="text-xs font-medium">Lawn Mowing</Label>
                        <p className="text-[10px] text-muted-foreground">Grass must not exceed 8". Mow weekly Apr-Oct. Includes weed control & leaf removal.</p>
                      </div>
                    </div>
                    
                    {/* Snow Removal */}
                    <div className="flex items-start gap-2">
                      <Checkbox 
                        id="tenant_snow_removal" 
                        checked={formData.tenant_snow_removal} 
                        onCheckedChange={(checked) => setFormData({ ...formData, tenant_snow_removal: checked as boolean })} 
                        className="h-4 w-4 mt-0.5"
                      />
                      <div className="flex-1">
                        <Label htmlFor="tenant_snow_removal" className="text-xs font-medium">Snow Removal</Label>
                        <p className="text-[10px] text-muted-foreground">Clearing snow/ice from sidewalks, driveway, walkways within 24 hours of snowfall.</p>
                      </div>
                    </div>
                    
                    {/* Lawn Care */}
                    <div className="flex items-start gap-2">
                      <Checkbox 
                        id="tenant_lawn_care" 
                        checked={formData.tenant_lawn_care} 
                        onCheckedChange={(checked) => setFormData({ ...formData, tenant_lawn_care: checked as boolean })} 
                        className="h-4 w-4 mt-0.5"
                      />
                      <div className="flex-1">
                        <Label htmlFor="tenant_lawn_care" className="text-xs font-medium">Lawn Care</Label>
                        <p className="text-[10px] text-muted-foreground">Sprinkler on/off, watering, overseeding, and fertilizing.</p>
                      </div>
                    </div>
                  </div>
                </div>
                
                <Separator />
                
                {/* Keys Clause */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs font-semibold">Keys</Label>
                    <div className="flex items-center gap-2">
                      <Checkbox 
                        id="include_keys" 
                        checked={formData.include_keys_clause} 
                        onCheckedChange={(checked) => setFormData({ ...formData, include_keys_clause: checked as boolean })} 
                        className="h-4 w-4" 
                      />
                      <Label htmlFor="include_keys" className="text-xs">Include Clause</Label>
                    </div>
                  </div>
                  {formData.include_keys_clause && (
                    <div className="p-2 bg-blue-50 border border-blue-200 rounded text-xs space-y-2">
                      {/* Door Selection */}
                      <div className="flex gap-4">
                        <div className="flex items-center gap-1.5">
                          <Checkbox 
                            id="has_front_door" 
                            checked={formData.has_front_door} 
                            onCheckedChange={(checked) => {
                              const hasFront = checked as boolean;
                              setFormData({ 
                                ...formData, 
                                has_front_door: hasFront,
                                front_door_keys: hasFront ? formData.tenants.length || 1 : 0
                              });
                            }}
                            className="h-3.5 w-3.5" 
                          />
                          <Label htmlFor="has_front_door" className="text-xs text-blue-800">Front Door</Label>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <Checkbox 
                            id="has_back_door" 
                            checked={formData.has_back_door} 
                            onCheckedChange={(checked) => {
                              const hasBack = checked as boolean;
                              setFormData({ 
                                ...formData, 
                                has_back_door: hasBack,
                                back_door_keys: hasBack ? formData.tenants.length || 1 : 0
                              });
                            }}
                            className="h-3.5 w-3.5" 
                          />
                          <Label htmlFor="has_back_door" className="text-xs text-blue-800">Back Door</Label>
                        </div>
                      </div>
                      
                      {/* Key Counts & Fee */}
                      <div className="grid grid-cols-3 gap-2">
                        {formData.has_front_door && (
                          <div>
                            <Label className="text-xs text-blue-800">Front Keys</Label>
                            <Select
                              value={formData.front_door_keys.toString()}
                              onValueChange={(value) => setFormData({ ...formData, front_door_keys: parseInt(value) })}
                            >
                              <SelectTrigger className="text-xs h-7 bg-white">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {[1,2,3,4,5,6].map((n) => (
                                  <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        )}
                        {formData.has_back_door && (
                          <div>
                            <Label className="text-xs text-blue-800">Back Keys</Label>
                            <Select
                              value={formData.back_door_keys.toString()}
                              onValueChange={(value) => setFormData({ ...formData, back_door_keys: parseInt(value) })}
                            >
                              <SelectTrigger className="text-xs h-7 bg-white">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {[1,2,3,4,5,6].map((n) => (
                                  <SelectItem key={n} value={n.toString()}>{n}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        )}
                        <div>
                          <Label className="text-xs text-blue-800">Lost Key Fee</Label>
                          <div className="relative">
                            <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-gray-500">$</span>
                            <Input
                              type="number"
                              value={formData.key_replacement_fee}
                              onChange={(e) => setFormData({ ...formData, key_replacement_fee: e.target.value })}
                              className="text-xs h-7 pl-5 bg-white"
                            />
                          </div>
                        </div>
                      </div>
                      
                      {/* Summary */}
                      <p className="text-[10px] text-blue-600 leading-relaxed">
                        {formData.has_front_door && `${formData.front_door_keys} front key${formData.front_door_keys !== 1 ? 's' : ''}`}
                        {formData.has_front_door && formData.has_back_door && ' + '}
                        {formData.has_back_door && `${formData.back_door_keys} back key${formData.back_door_keys !== 1 ? 's' : ''}`}
                        {(formData.has_front_door || formData.has_back_door) && ` (1 per adult). Lost key: $${formData.key_replacement_fee}`}
                      </p>
                    </div>
                  )}
                </div>
                
                <Separator />
                
                {/* Property Features */}
                <div className="space-y-2">
                  <Label className="text-xs font-semibold">Property Features</Label>
                  <div className="flex flex-wrap gap-3">
                    {formData.garage_spaces > 0 && (
                      <div className="flex items-center space-x-1.5">
                        <Checkbox id="garage" checked={true} disabled className="h-3.5 w-3.5" />
                        <Label htmlFor="garage" className="text-xs text-gray-500">Garage ({formData.garage_spaces} space{formData.garage_spaces !== 1 ? 's' : ''})</Label>
                      </div>
                    )}
                    <div className="flex items-center space-x-1.5">
                      <Checkbox id="attic" checked={formData.has_attic} onCheckedChange={(checked) => setFormData({ ...formData, has_attic: checked as boolean })} className="h-3.5 w-3.5" />
                      <Label htmlFor="attic" className="text-xs">Attic</Label>
                    </div>
                    <div className="flex items-center space-x-1.5">
                      <Checkbox id="basement" checked={formData.has_basement} onCheckedChange={(checked) => setFormData({ ...formData, has_basement: checked as boolean })} className="h-3.5 w-3.5" />
                      <Label htmlFor="basement" className="text-xs">Basement</Label>
                    </div>
                  </div>
                </div>
                
                <Separator />
                
                {/* Lead Paint Disclosure (required for homes built before 1978) */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs font-semibold">Lead Paint Disclosure</Label>
                    <div className="flex items-center gap-2">
                      <Checkbox 
                        id="lead_paint" 
                        checked={formData.lead_paint_disclosure} 
                        onCheckedChange={(checked) => setFormData({ ...formData, lead_paint_disclosure: checked as boolean })} 
                        className="h-4 w-4"
                      />
                      <Label htmlFor="lead_paint" className="text-xs">Include (Pre-1978)</Label>
                    </div>
                  </div>
                  {formData.lead_paint_disclosure && (
                    <div className="p-2 bg-orange-50 border border-orange-200 rounded text-xs space-y-2">
                      <p className="text-orange-800 text-[11px]">
                        Federal law requires disclosure for homes built before 1978. 
                        Year built: <strong>{formData.lead_paint_year_built || 'Unknown'}</strong>
                      </p>
                      <a 
                        href="/lead-paint-disclosure.pdf" 
                        target="_blank" 
                        className="inline-flex items-center gap-1 text-orange-600 hover:text-orange-800 underline text-[11px]"
                      >
                        <FileText className="h-3 w-3" />
                        View Lead Paint Disclosure Form (PDF)
                      </a>
                    </div>
                  )}
                </div>
                
                <Separator />
                
                {/* Move-Out Costs */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <Label className="text-xs font-semibold">Move-Out Costs ({formData.moveout_costs.length})</Label>
                    <div className="flex gap-1">
                      <Button variant="outline" size="sm" onClick={() => setIsMoveoutCostsExpanded(true)} className="h-6 text-xs px-2" title="Expand">
                        <Maximize2 className="h-3 w-3" />
                            </Button>
                      <Button variant="outline" size="sm" onClick={addMoveoutCost} className="h-6 text-xs px-2">
                        <Plus className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                  <div className="max-h-40 overflow-auto border rounded text-xs">
                    {formData.moveout_costs.slice(0, 5).map((cost, index) => (
                      <div key={index} className="flex items-center justify-between p-1.5 border-b last:border-0">
                        <span className="truncate flex-1">{cost.item}</span>
                        <span className="ml-2">${cost.amount}</span>
                      </div>
                    ))}
                    {formData.moveout_costs.length > 5 && (
                      <div className="p-1.5 text-center text-gray-500">
                        +{formData.moveout_costs.length - 5} more (click expand)
                      </div>
                    )}
                  </div>
                </div>
                
                {/* Missouri-Specific */}
                {formData.state === 'MO' && (
                  <>
                    <Separator />
                    <div className="space-y-2 p-2 bg-amber-50 border border-amber-200 rounded">
                      <Label className="text-xs font-semibold text-amber-800">Missouri Required</Label>
                      <div className="flex items-center space-x-2">
                        <Checkbox id="meth_disclosure" checked={formData.methamphetamine_disclosure} onCheckedChange={(checked) => setFormData({ ...formData, methamphetamine_disclosure: checked as boolean })} className="h-4 w-4" />
                        <Label htmlFor="meth_disclosure" className="text-xs">Methamphetamine Disclosure</Label>
                      </div>
                      <div>
                        <Label className="text-xs">Owner Name *</Label>
                        <Input value={formData.owner_name} onChange={(e) => setFormData({ ...formData, owner_name: e.target.value })} className="text-xs h-7" />
                      </div>
                      <div>
                        <Label className="text-xs">Owner Address *</Label>
                        <textarea value={formData.owner_address} onChange={(e) => setFormData({ ...formData, owner_address: e.target.value })} className="w-full px-2 py-1 border border-gray-300 rounded-md text-xs h-14" />
                      </div>
                    </div>
                  </>
                )}
                
              </CardContent>
            </Card>
          </div>
          )}
          
          {/* RIGHT: PDF Viewer (50% or 100% when expanded) - Hidden when params are expanded */}
          {!isParamsExpanded && (
          <div className="flex flex-col min-h-0">
            <Card className="flex-1 flex flex-col min-h-0">
              <CardHeader className="py-3 border-b flex-shrink-0 flex flex-row items-center justify-between">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-sm font-bold">Generated Lease</CardTitle>
                  {isPdfExpanded && (
                    <Badge variant="secondary" className="text-xs">Expanded</Badge>
                  )}
                </div>
                <div className="flex gap-2">
                  {/* Expand/Collapse PDF button - icon only */}
                            <Button
                    variant="outline"
                              size="sm"
                    onClick={() => setIsPdfExpanded(!isPdfExpanded)}
                    className="h-7 w-7 p-0"
                    title={isPdfExpanded ? 'Show parameters' : 'Expand PDF'}
                  >
                    {isPdfExpanded ? (
                      <Minimize2 className="h-3.5 w-3.5" />
                    ) : (
                      <Maximize2 className="h-3.5 w-3.5" />
                    )}
                            </Button>
                  {/* Documents Dropdown */}
                  {(pdfUrl || holdingFeeUrl || formData.lead_paint_disclosure) && (
                    <Select
                      value=""
                      onValueChange={(value) => {
                        if (value === 'lease_open') window.open(pdfUrl || '', '_blank');
                        else if (value === 'lease_download') {
                          const a = document.createElement('a');
                          a.href = pdfUrl || '';
                          a.download = 'lease.pdf';
                          a.click();
                        }
                        else if (value === 'holding_fee') window.open(holdingFeeUrl || '', '_blank');
                        else if (value === 'lead_paint') window.open('/lead-paint-disclosure.pdf', '_blank');
                      }}
                    >
                      <SelectTrigger className="h-7 text-xs w-[140px]">
                        <FileText className="h-3 w-3 mr-1.5" />
                        <span>Documents</span>
                      </SelectTrigger>
                      <SelectContent>
                        {pdfUrl && (
                          <>
                            <SelectItem value="lease_open" className="text-xs">
                              <span className="flex items-center gap-2">
                                <ExternalLink className="h-3 w-3" /> Open Lease PDF
                              </span>
                            </SelectItem>
                            <SelectItem value="lease_download" className="text-xs">
                              <span className="flex items-center gap-2">
                                <FileText className="h-3 w-3" /> Download Lease PDF
                              </span>
                            </SelectItem>
                          </>
                        )}
                        {holdingFeeUrl && (
                          <SelectItem value="holding_fee" className="text-xs">
                            <span className="flex items-center gap-2">
                              <FileText className="h-3 w-3" /> Holding Fee Addendum
                            </span>
                          </SelectItem>
                        )}
                        {formData.lead_paint_disclosure && (
                          <SelectItem value="lead_paint" className="text-xs">
                            <span className="flex items-center gap-2">
                              <FileText className="h-3 w-3" /> Lead Paint Disclosure
                            </span>
                          </SelectItem>
                        )}
                      </SelectContent>
                    </Select>
                          )}
                        </div>
              </CardHeader>
              <CardContent className="flex-1 p-0 min-h-0">
                {pdfUrl ? (
                  <iframe
                    src={`${pdfUrl}#view=FitH`}
                    className="w-full h-full border-0"
                    title="Lease Preview"
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-400">
                    <div className="text-center">
                      <FileText className="h-16 w-16 mx-auto mb-4 opacity-50" />
                      <p className="text-sm">No PDF generated yet</p>
                      <p className="text-xs mt-1">Save parameters and generate to preview</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
          )}
        </div>
      )}
      
      {/* Move-Out Costs Dialog */}
      <Dialog open={isMoveoutCostsExpanded} onOpenChange={setIsMoveoutCostsExpanded}>
        <DialogContent className="max-w-[90vw] max-h-[90vh] w-full">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between">
              <span>Move-Out Costs</span>
              <Button variant="outline" size="sm" onClick={addMoveoutCost} className="h-8 text-xs px-3">
                <Plus className="h-3.5 w-3.5 mr-1.5" />
                Add Cost
              </Button>
            </DialogTitle>
          </DialogHeader>
          <div className="overflow-auto max-h-[calc(90vh-120px)] border rounded">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="text-left p-3 font-semibold border-b w-1/4">Item</th>
                  <th className="text-left p-3 font-semibold border-b w-2/4">Description</th>
                  <th className="text-right p-3 font-semibold border-b w-32">Amount</th>
                  <th className="text-center p-3 font-semibold border-b w-16"></th>
                </tr>
              </thead>
              <tbody>
                {formData.moveout_costs.map((cost, index) => (
                  <tr key={index} className="border-b hover:bg-gray-50">
                    <td className="p-2">
                      <Input placeholder="Item" value={cost.item} onChange={(e) => updateMoveoutCost(index, 'item', e.target.value)} className="text-sm h-9" />
                    </td>
                    <td className="p-2">
                      <Input placeholder="Description" value={cost.description || ''} onChange={(e) => updateMoveoutCost(index, 'description', e.target.value)} className="text-sm h-9" />
                    </td>
                    <td className="p-2">
                      <Input type="number" placeholder="0" value={cost.amount} onChange={(e) => updateMoveoutCost(index, 'amount', e.target.value)} className="text-sm h-9 text-right" />
                    </td>
                    <td className="p-2 text-center">
                      <Button variant="ghost" size="sm" onClick={() => removeMoveoutCost(index)} className="h-8 w-8 p-0 text-red-600 hover:bg-red-50">
                        <X className="h-4 w-4" />
                      </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
