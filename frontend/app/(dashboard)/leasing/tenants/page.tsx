'use client';

import { useState, useMemo, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Pencil, Trash2, UserCheck, UserX, Users as UsersIcon, CheckCircle, XCircle, Clock, AlertCircle, Building2, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useTenants, useCreateTenant, useUpdateTenant, useDeleteTenant } from '@/lib/hooks/use-tenants';
import { useProperties } from '@/lib/hooks/use-properties';
import { useUnits } from '@/lib/hooks/use-units';
import type { Tenant } from '@/lib/types';

export default function TenantsPage() {
  const router = useRouter();
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>('');
  const [expandedProperties, setExpandedProperties] = useState<Set<string>>(new Set());
  const [deletingTenantId, setDeletingTenantId] = useState<string | null>(null);

  const { data: propertiesData } = useProperties();
  const { data: tenantsData, isLoading } = useTenants(
    selectedPropertyId ? { property_id: selectedPropertyId } : {}
  );
  const createTenant = useCreateTenant();
  const updateTenant = useUpdateTenant();
  const deleteTenant = useDeleteTenant();

  const [formData, setFormData] = useState<Partial<Tenant>>({
    property_id: selectedPropertyId || '',
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    status: 'applicant',
  });

  // Landlord references stored in JSON column
  const [landlordRefs, setLandlordRefs] = useState<Array<{
    landlord_name: string;
    landlord_phone?: string;
    landlord_email?: string;
    property_address?: string;
    contact_date?: string;
    status?: 'pass' | 'fail' | 'no_info';
    notes?: string;
  }>>([]);

  const [currentRef, setCurrentRef] = useState({
    landlord_name: '',
    landlord_phone: '',
    landlord_email: '',
    property_address: '',
    contact_date: new Date().toISOString().split('T')[0],
    status: 'no_info' as 'pass' | 'fail' | 'no_info',
    notes: '',
  });

  const [editingRefIndex, setEditingRefIndex] = useState<number | null>(null);

  // Update formData property_id when selectedPropertyId changes
  useEffect(() => {
    if (selectedPropertyId && !isEditDialogOpen) {
      setFormData(prev => ({ ...prev, property_id: selectedPropertyId }));
    }
  }, [selectedPropertyId, isEditDialogOpen]);

  const handleCreateTenant = async () => {
    try {
      // Validate required fields
      if (!formData.property_id || !formData.first_name || !formData.last_name) {
        alert('Please fill in all required fields (Property, First Name, Last Name)');
        return;
      }

      // Build tenant data in the EXACT order of the Iceberg table schema
      // Order must match: id, property_id, unit_id, first_name, last_name, email, phone,
      // current_address, current_city, current_state, current_zip, employer_name, status,
      // notes, background_check_status, monthly_income, date_of_birth, landlord_references,
      // credit_score, created_at, updated_at
      const tenantData: any = {
        // Field order matches Iceberg schema exactly
        property_id: formData.property_id,
        unit_id: formData.unit_id && formData.unit_id !== '__none__' ? formData.unit_id : undefined,
        first_name: formData.first_name,
        last_name: formData.last_name,
        email: formData.email || undefined,
        phone: formData.phone ? stripPhoneNumber(formData.phone) || undefined : undefined,
        current_address: formData.current_address || undefined,
        current_city: formData.current_city || undefined,
        current_state: formData.current_state || undefined,
        current_zip: formData.current_zip || undefined,
        employer_name: formData.employer_name || undefined,
        status: formData.status || 'applicant',
        notes: formData.notes || undefined,
        background_check_status: formData.background_check_status || undefined,
        monthly_income: formData.monthly_income ? Number(formData.monthly_income) : undefined,
        date_of_birth: formData.date_of_birth || undefined,
        landlord_references: landlordRefs.length > 0 ? landlordRefs : undefined,
        credit_score: formData.credit_score ? Number(formData.credit_score) : undefined,
      };

      // Remove undefined and null values, but keep empty strings for optional string fields
      // Required fields (property_id, first_name, last_name) should always be included
      Object.keys(tenantData).forEach(key => {
        if (tenantData[key] === undefined || tenantData[key] === null) {
          delete tenantData[key];
        }
      });

      await createTenant.mutateAsync(tenantData);

      // Reset form
      setIsCreateDialogOpen(false);
      setFormData({
        property_id: selectedPropertyId || '',
        first_name: '',
        last_name: '',
        email: '',
        phone: '',
        status: 'applicant',
      });
      setLandlordRefs([]);
      setEditingRefIndex(null);
      setCurrentRef({
        landlord_name: '',
        landlord_phone: '',
        landlord_email: '',
        property_address: '',
        contact_date: new Date().toISOString().split('T')[0],
        status: 'no_info',
        notes: '',
      });
    } catch (error) {
      console.error('Error creating tenant:', error);
      alert('Failed to create tenant');
    }
  };

  const handleEditTenant = async (tenant: Tenant) => {
    setSelectedTenant(tenant);

    // Explicitly set all form fields to ensure nothing is missing
    setFormData({
      property_id: tenant.property_id || '',
      unit_id: tenant.unit_id || undefined,
      first_name: tenant.first_name || '',
      last_name: tenant.last_name || '',
      email: tenant.email || '',
      phone: tenant.phone || '',
      current_address: tenant.current_address || '',
      current_city: tenant.current_city || '',
      current_state: tenant.current_state || '',
      current_zip: tenant.current_zip || '',
      employer_name: tenant.employer_name || '',
      status: tenant.status || 'applicant', // Ensure status has a default
      notes: tenant.notes || '',
      background_check_status: tenant.background_check_status || 'not_started',
      monthly_income: tenant.monthly_income || undefined,
      date_of_birth: tenant.date_of_birth || '',
      credit_score: tenant.credit_score || undefined,
    });

    // Load landlord references from JSON column
    if (tenant.landlord_references && Array.isArray(tenant.landlord_references)) {
      setLandlordRefs(tenant.landlord_references);
    } else {
      setLandlordRefs([]);
    }

    console.log('📝 [TENANT] Editing tenant with data:', {
      ...tenant,
      formDataStatus: tenant.status || 'applicant',
    });

    setIsEditDialogOpen(true);
  };

  const handleUpdateTenant = async () => {
    if (!selectedTenant) return;

    try {
      // Validate required fields
      if (!formData.property_id || !formData.first_name || !formData.last_name) {
        alert('Please fill in all required fields (Property, First Name, Last Name)');
        return;
      }

      // Build update data in the EXACT order of the Iceberg table schema
      // Order must match: id, property_id, unit_id, first_name, last_name, email, phone,
      // current_address, current_city, current_state, current_zip, employer_name, status,
      // notes, background_check_status, monthly_income, date_of_birth, landlord_references,
      // credit_score, created_at, updated_at
      const updateData: any = {
        // Field order matches Iceberg schema exactly
        property_id: formData.property_id || undefined,
        unit_id: formData.unit_id && formData.unit_id !== '__none__' ? formData.unit_id : undefined,
        first_name: formData.first_name || undefined,
        last_name: formData.last_name || undefined,
        email: formData.email || undefined,
        phone: formData.phone ? stripPhoneNumber(formData.phone) || undefined : undefined,
        current_address: formData.current_address || undefined,
        current_city: formData.current_city || undefined,
        current_state: formData.current_state || undefined,
        current_zip: formData.current_zip || undefined,
        employer_name: formData.employer_name || undefined,
        status: formData.status || 'applicant', // Always include status, default to 'applicant'
        notes: formData.notes || undefined,
        background_check_status: formData.background_check_status || undefined,
        monthly_income: formData.monthly_income ? Number(formData.monthly_income) : undefined,
        date_of_birth: formData.date_of_birth || undefined,
        landlord_references: landlordRefs.length > 0 ? landlordRefs : undefined,
        credit_score: formData.credit_score ? Number(formData.credit_score) : undefined,
      };

      // Remove undefined and null values, but keep empty strings for optional string fields
      // Required fields (property_id, first_name, last_name) should always be included
      // Status should always be included if it exists
      Object.keys(updateData).forEach(key => {
        if (updateData[key] === undefined || updateData[key] === null) {
          // Don't delete status - it should always be included
          if (key !== 'status') {
            delete updateData[key];
          }
        }
      });

      // Ensure status is always included
      if (!updateData.status && formData.status) {
        updateData.status = formData.status;
      }

      console.log('📝 [TENANT] Updating tenant with payload:', updateData);

      await updateTenant.mutateAsync({ id: selectedTenant.id, data: updateData });

      // Reset form
      setIsEditDialogOpen(false);
      setSelectedTenant(null);
      setFormData({
        property_id: selectedPropertyId || '',
        first_name: '',
        last_name: '',
        email: '',
        phone: '',
        status: 'applicant',
      });
      setLandlordRefs([]);
      setEditingRefIndex(null);
      setCurrentRef({
        landlord_name: '',
        landlord_phone: '',
        landlord_email: '',
        property_address: '',
        contact_date: new Date().toISOString().split('T')[0],
        status: 'no_info',
        notes: '',
      });
    } catch (error) {
      console.error('Error updating tenant:', error);
      alert('Failed to update tenant');
    }
  };

  const handleDeleteTenant = async (id: string) => {
    if (confirm('Are you sure you want to delete this tenant profile?')) {
      setDeletingTenantId(id);
      try {
        await deleteTenant.mutateAsync(id);
      } catch (err) {
        console.error('Error deleting tenant:', err);
      } finally {
        setDeletingTenantId(null);
      }
    }
  };

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case 'applicant':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-700 bg-blue-50 rounded-full">
            <Clock className="h-3 w-3" />
            Applicant
          </span>
        );
      case 'approved':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-green-700 bg-green-50 rounded-full">
            <CheckCircle className="h-3 w-3" />
            Approved
          </span>
        );
      case 'current':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-purple-700 bg-purple-50 rounded-full">
            <UserCheck className="h-3 w-3" />
            Current
          </span>
        );
      case 'former':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-gray-700 bg-gray-100 rounded-full">
            <UserX className="h-3 w-3" />
            Former
          </span>
        );
      case 'rejected':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-red-700 bg-red-50 rounded-full">
            <XCircle className="h-3 w-3" />
            Rejected
          </span>
        );
      default:
        return null;
    }
  };

  const getBackgroundCheckBadge = (status?: string) => {
    switch (status) {
      case 'pass':
        return <span className="text-xs text-green-600 font-medium">✓ Passed</span>;
      case 'fail':
        return <span className="text-xs text-red-600 font-medium">✗ Failed</span>;
      case 'pending':
        return <span className="text-xs text-yellow-600 font-medium">⏳ Pending</span>;
      case 'not_started':
        return <span className="text-xs text-gray-500">Not Started</span>;
      default:
        return <span className="text-xs text-gray-400">—</span>;
    }
  };

  // Strip non-numeric characters from phone number for storage
  const stripPhoneNumber = (phone: string): string => {
    if (!phone) return '';
    return phone.replace(/\D/g, '');
  };

  // Format phone number for display: (XXX) XXX-XXXX
  const formatPhoneNumber = (phone?: string) => {
    if (!phone) return '—';
    // Remove all non-numeric characters
    const cleaned = phone.replace(/\D/g, '');
    // Format as (xxx) xxx-xxxx
    if (cleaned.length === 10) {
      return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
    }
    // If not 10 digits, return cleaned version (might be partial entry)
    return cleaned || '—';
  };

  // Format phone number as user types (for input display)
  const formatPhoneInput = (phone: string): string => {
    if (!phone) return '';
    const cleaned = phone.replace(/\D/g, '');
    if (cleaned.length === 0) return '';
    if (cleaned.length <= 3) return `(${cleaned}`;
    if (cleaned.length <= 6) return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3)}`;
    return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6, 10)}`;
  };

  const properties = propertiesData?.items || [];
  // Memoize tenants to avoid creating new array reference on every render
  const tenants = useMemo(() => tenantsData?.tenants || [], [tenantsData?.tenants]);

  // Get units for selected property
  const { data: unitsData } = useUnits(selectedPropertyId || undefined);
  const units = unitsData?.items || [];

  // Get units for the currently selected property in the form
  const formPropertyUnits = useMemo(() => {
    if (!formData.property_id) return [];
    return units.filter(u => u.property_id === formData.property_id);
  }, [units, formData.property_id]);

  // Create a stable key from tenant property IDs for dependency tracking
  const tenantPropertyIdsKey = useMemo(() => {
    if (!tenants.length) return '';
    return tenants
      .map(t => t.property_id)
      .filter(Boolean)
      .sort()
      .join(',');
  }, [tenants]);

  // Auto-expand all properties when property is selected
  useEffect(() => {
    if (selectedPropertyId && tenants.length > 0) {
      const newExpandedProperties = new Set<string>();
      tenants.forEach(tenant => {
        if (tenant.property_id) {
          newExpandedProperties.add(tenant.property_id);
        }
      });
      setExpandedProperties(newExpandedProperties);
    } else if (!selectedPropertyId) {
      setExpandedProperties(new Set());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPropertyId, tenantPropertyIdsKey]);

  // Filter tenants by status
  const filteredTenants = useMemo(() => {
    return tenants.filter(tenant => {
      if (statusFilter === 'all') return true;
      return tenant.status === statusFilter;
    });
  }, [tenants, statusFilter]);

  // Group tenants by property
  const groupedByProperty = useMemo(() => {
    const result: Record<string, Tenant[]> = {};
    filteredTenants.forEach(tenant => {
      const propId = tenant.property_id || 'unassigned';
      if (!result[propId]) result[propId] = [];
      result[propId].push(tenant);
    });

    // Sort tenants within each property by name
    Object.values(result).forEach(propertyTenants => {
      propertyTenants.sort((a, b) => {
        const nameA = `${a.first_name} ${a.last_name}`.toLowerCase();
        const nameB = `${b.first_name} ${b.last_name}`.toLowerCase();
        return nameA.localeCompare(nameB);
      });
    });

    return result;
  }, [filteredTenants]);

  const getPropertyName = (propertyId: string) => {
    const prop = properties.find(p => p.id === propertyId);
    return prop?.display_name || prop?.address_line1 || propertyId;
  };

  const toggleProperty = (propertyId: string) => {
    setExpandedProperties(prev => {
      const newSet = new Set(prev);
      if (newSet.has(propertyId)) {
        newSet.delete(propertyId);
      } else {
        newSet.add(propertyId);
      }
      return newSet;
    });
  };

  const sortedPropertyIds = Object.keys(groupedByProperty).sort((a, b) =>
    getPropertyName(a).localeCompare(getPropertyName(b))
  );

  return (
    <div className="p-3 max-w-6xl mx-auto">
      <div className="mb-3 flex justify-between items-center">
        <div>
          <h1 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
            <UsersIcon className="h-3.5 w-3.5" />
            Tenant Profiles
          </h1>
          <p className="text-xs text-gray-500">Manage prospective and current tenant information</p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)} className="bg-black text-white hover:bg-gray-800 h-7 text-xs px-2">
          <Plus className="h-3 w-3 mr-1" />
          Add Tenant
        </Button>
      </div>

      {/* Property Filter - Required */}
      <div className="mb-2">
        <select
          value={selectedPropertyId}
          onChange={(e) => setSelectedPropertyId(e.target.value)}
          className="px-2 py-1.5 border border-gray-300 rounded text-sm w-full md:w-auto min-w-[200px]"
          required
        >
          <option value="">Select Property</option>
          {properties.map((prop) => (
            <option key={prop.id} value={prop.id}>
              {prop.display_name || prop.address_line1 || prop.id}
            </option>
          ))}
        </select>
      </div>

      {/* Status Filter */}
      {selectedPropertyId && (
        <div className="mb-3">
          <div className="flex items-center gap-2">
            <Label htmlFor="status-filter" className="text-xs font-medium">Status:</Label>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-40 h-7 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="applicant">Applicant</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="current">Current</SelectItem>
                <SelectItem value="former">Former</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
            <div className="ml-auto text-xs text-gray-600">
              {filteredTenants.length} tenant{filteredTenants.length !== 1 ? 's' : ''}
            </div>
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="text-center py-8 text-gray-500 text-sm">Loading tenants...</div>
      )}

      {/* Empty State */}
      {!isLoading && !selectedPropertyId && (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <UsersIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">Please select a property to view tenants</p>
          </CardContent>
        </Card>
      )}

      {!isLoading && selectedPropertyId && filteredTenants.length === 0 && (
        <Card>
          <CardContent className="py-8 text-center text-gray-500">
            <UsersIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">
              {statusFilter === 'all'
                ? 'No tenants found for this property'
                : `No tenants with status "${statusFilter}"`}
            </p>
            <Button onClick={() => setIsCreateDialogOpen(true)} size="sm" className="mt-3">
              <Plus className="h-3 w-3 mr-1" />
              Add Tenant
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Grouped by Property */}
      {selectedPropertyId && sortedPropertyIds.map(propId => {
        const propertyTenants = groupedByProperty[propId];
        const isPropertyExpanded = expandedProperties.has(propId);

        return (
          <Card key={propId} className="mb-3">
            <CardHeader
              className="py-2 px-3 cursor-pointer hover:bg-gray-50"
              onClick={() => toggleProperty(propId)}
            >
              <div className="flex items-center gap-2">
                {isPropertyExpanded ? (
                  <ChevronDown className="h-4 w-4 text-gray-400" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-gray-400" />
                )}
                <Building2 className="h-4 w-4 text-gray-600" />
                <span className="font-semibold text-sm">{getPropertyName(propId)}</span>
                <span className="text-xs text-gray-500">({propertyTenants.length})</span>
              </div>
            </CardHeader>

            {/* Tenant List */}
            {isPropertyExpanded && (
              <CardContent className="p-0">
                {/* Header Row */}
                <div className="px-3 py-2 bg-gray-50 border-b border-gray-200 flex items-center gap-2 text-xs font-medium text-gray-500">
                  <div className="flex-1 min-w-0">Name</div>
                  {propertyTenants.some(t => t.unit_id) && (
                    <div className="w-20 shrink-0">Unit</div>
                  )}
                  <div className="w-16 text-right shrink-0">Income</div>
                  <div className="w-12 text-right shrink-0">Credit</div>
                  <div className="w-16 text-center shrink-0">Refs</div>
                  <div className="w-20 shrink-0">Background</div>
                  <div className="w-24 shrink-0">Status</div>
                  <div className="flex gap-1 shrink-0 w-14">Actions</div>
                </div>
                <div className="divide-y">
                  {propertyTenants.map(tenant => (
                    <div
                      key={tenant.id}
                      className="px-3 py-2 flex items-center gap-2 hover:bg-gray-50 cursor-pointer"
                      onClick={() => handleEditTenant(tenant)}
                    >
                      {/* Name */}
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900">
                          {tenant.first_name} {tenant.last_name}
                        </div>
                        <div className="text-xs text-gray-500">
                          {tenant.email || formatPhoneNumber(tenant.phone) || '—'}
                        </div>
                      </div>

                      {/* Unit */}
                      {tenant.unit_id && (
                        <span className="text-xs text-gray-600 w-20 shrink-0">
                          {units.find(u => u.id === tenant.unit_id)?.unit_number || '—'}
                        </span>
                      )}

                      {/* Income */}
                      <span className="text-xs font-semibold text-gray-900 w-16 text-right shrink-0">
                        {tenant.monthly_income ? `$${(tenant.monthly_income / 1000).toFixed(1)}k` : '—'}
                      </span>

                      {/* Credit */}
                      <span className="text-xs font-semibold text-gray-900 w-12 text-right shrink-0">
                        {tenant.credit_score || '—'}
                      </span>

                      {/* Landlord Refs */}
                      <span className="text-xs text-gray-600 w-16 text-center shrink-0">
                        {tenant.landlord_references?.filter((ref: any) => ref.status === 'pass').length || 0} passed
                      </span>

                      {/* Background Check */}
                      <div className="w-20 shrink-0">
                        {getBackgroundCheckBadge(tenant.background_check_status)}
                      </div>

                      {/* Status */}
                      <div className="w-24 shrink-0">
                        {getStatusBadge(tenant.status)}
                      </div>

                      {/* Actions */}
                      <div className="flex gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleEditTenant(tenant)}
                          className="h-6 w-6 p-0"
                        >
                          <Pencil className="h-3 w-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteTenant(tenant.id)}
                          className="h-6 w-6 p-0 text-red-500 hover:text-red-700"
                          disabled={deletingTenantId === tenant.id}
                        >
                          {deletingTenantId === tenant.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Trash2 className="h-3 w-3" />
                          )}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            )}
          </Card>
        );
      })}

      {/* Create/Edit Dialog */}
      <Dialog open={isCreateDialogOpen || isEditDialogOpen} onOpenChange={(open) => {
        setIsCreateDialogOpen(false);
        setIsEditDialogOpen(false);
        if (!open) {
          setSelectedTenant(null);
          setFormData({
            property_id: selectedPropertyId || '',
            first_name: '',
            last_name: '',
            email: '',
            phone: '',
            status: 'applicant',
          });
          setLandlordRefs([]);
          setEditingRefIndex(null);
          setCurrentRef({
            landlord_name: '',
            landlord_phone: '',
            landlord_email: '',
            property_address: '',
            contact_date: new Date().toISOString().split('T')[0],
            status: 'no_info',
            notes: '',
          });
        }
      }}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {isEditDialogOpen ? 'Edit Tenant Profile' : 'Add New Tenant'}
            </DialogTitle>
            <DialogDescription>
              Enter tenant information below. You can update this later as the leasing process progresses.
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-2 gap-4">
            {/* Property Selection - Top of Form */}
            <div>
              <Label htmlFor="property_id">Property *</Label>
              <Select
                value={formData.property_id || ''}
                onValueChange={(value) => setFormData({ ...formData, property_id: value, unit_id: undefined })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select Property" />
                </SelectTrigger>
                <SelectContent>
                  {properties.map((prop) => (
                    <SelectItem key={prop.id} value={prop.id}>
                      {prop.display_name || prop.address_line1 || prop.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Unit Selection - Only show if property has units (multi-family) */}
            {formData.property_id && formPropertyUnits.length > 0 && (
              <div>
                <Label htmlFor="unit_id">Unit (if multi-family)</Label>
                <Select
                  value={formData.unit_id || '__none__'}
                  onValueChange={(value) => setFormData({ ...formData, unit_id: value === '__none__' ? undefined : value })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select Unit (optional)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">None</SelectItem>
                    {formPropertyUnits.map((unit) => (
                      <SelectItem key={unit.id} value={unit.id}>
                        Unit {unit.unit_number}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {!formData.property_id && <div></div>}

            <div>
              <Label htmlFor="first_name">First Name *</Label>
              <Input
                id="first_name"
                value={formData.first_name || ''}
                onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                placeholder="John"
              />
            </div>
            <div>
              <Label htmlFor="last_name">Last Name *</Label>
              <Input
                id="last_name"
                value={formData.last_name || ''}
                onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                placeholder="Doe"
              />
            </div>
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={formData.email || ''}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="john.doe@example.com"
              />
            </div>
            <div>
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                type="tel"
                value={formData.phone ? formatPhoneInput(formData.phone) : ''}
                onChange={(e) => {
                  // Strip non-numeric characters and store only digits
                  const cleaned = stripPhoneNumber(e.target.value);
                  // Limit to 10 digits
                  const limited = cleaned.slice(0, 10);
                  setFormData({ ...formData, phone: limited });
                }}
                placeholder="(402) 555-1234"
                maxLength={14} // (XXX) XXX-XXXX = 14 chars
              />
            </div>
            <div className="col-span-2">
              <Label htmlFor="current_address">Current Address</Label>
              <Input
                id="current_address"
                value={formData.current_address || ''}
                onChange={(e) => setFormData({ ...formData, current_address: e.target.value })}
                placeholder="123 Main St"
              />
            </div>
            <div>
              <Label htmlFor="current_city">City</Label>
              <Input
                id="current_city"
                value={formData.current_city || ''}
                onChange={(e) => setFormData({ ...formData, current_city: e.target.value })}
                placeholder="Omaha"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label htmlFor="current_state">State</Label>
                <Input
                  id="current_state"
                  value={formData.current_state || ''}
                  onChange={(e) => setFormData({ ...formData, current_state: e.target.value })}
                  placeholder="NE"
                  maxLength={2}
                />
              </div>
              <div>
                <Label htmlFor="current_zip">ZIP</Label>
                <Input
                  id="current_zip"
                  value={formData.current_zip || ''}
                  onChange={(e) => setFormData({ ...formData, current_zip: e.target.value })}
                  placeholder="68102"
                />
              </div>
            </div>
            <div>
              <Label htmlFor="employer_name">Employer</Label>
              <Input
                id="employer_name"
                value={formData.employer_name || ''}
                onChange={(e) => setFormData({ ...formData, employer_name: e.target.value })}
                placeholder="Company Name"
              />
            </div>
            <div>
              <Label htmlFor="monthly_income">Monthly Income</Label>
              <Input
                id="monthly_income"
                type="number"
                value={formData.monthly_income || ''}
                onChange={(e) => setFormData({ ...formData, monthly_income: parseFloat(e.target.value) || undefined })}
                placeholder="5000"
              />
              {/* Affordability Calculation */}
              {formData.monthly_income && formData.property_id && (() => {
                const property = properties.find(p => p.id === formData.property_id);
                if (!property) return null;

                const ratio = property.monthly_rent_to_income_ratio || 2.75;
                const rent = property.current_monthly_rent || 0;
                const affordability = formData.monthly_income / ratio;
                const isAffordable = affordability >= rent;

                return (
                  <div className={`text-xs mt-1 ${isAffordable ? 'text-blue-600 font-medium' : 'text-red-600 font-medium'}`}>
                    Income / {ratio} = ${affordability.toFixed(2)} | Rent = ${rent.toFixed(2)}
                    {!isAffordable && <span className="ml-1">⚠️ Not affordable</span>}
                  </div>
                );
              })()}
            </div>

            <div>
              <Label htmlFor="status">Status</Label>
              <Select
                value={formData.status || 'applicant'}
                onValueChange={(value) => setFormData({ ...formData, status: value as any })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="applicant">Applicant</SelectItem>
                  <SelectItem value="approved">Approved</SelectItem>
                  <SelectItem value="current">Current</SelectItem>
                  <SelectItem value="former">Former</SelectItem>
                  <SelectItem value="rejected">Rejected</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div></div>

            {/* Background Check & Screening Section */}
            <div className="col-span-2 pt-4 border-t border-gray-200">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Background Check & Screening</h3>
            </div>

            <div>
              <Label htmlFor="date_of_birth">Date of Birth</Label>
              <Input
                id="date_of_birth"
                type="date"
                value={formData.date_of_birth || ''}
                onChange={(e) => setFormData({ ...formData, date_of_birth: e.target.value || undefined })}
              />
            </div>

            <div>
              <Label htmlFor="credit_score">Credit Score</Label>
              <Input
                id="credit_score"
                type="number"
                value={formData.credit_score || ''}
                onChange={(e) => setFormData({ ...formData, credit_score: parseInt(e.target.value) || undefined })}
                placeholder="720"
                min="300"
                max="850"
              />
            </div>

            <div>
              <Label htmlFor="background_check_status">Background Check Status</Label>
              <Select
                value={formData.background_check_status || 'not_started'}
                onValueChange={(value) => setFormData({ ...formData, background_check_status: value as any })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="not_started">Not Started</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="pass">Pass</SelectItem>
                  <SelectItem value="fail">Fail</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="col-span-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                value={formData.notes || ''}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                placeholder="Internal notes about this tenant..."
                rows={3}
              />
            </div>

            {/* Landlord Reference Checks Section */}
            <div className="col-span-2 pt-4 border-t border-gray-200">
              <h3 className="text-sm font-semibold text-gray-900 mb-1">Landlord Reference Checks</h3>
              <p className="text-xs text-gray-500 mb-1">Add landlord references to verify rental history.</p>
              <p className="text-xs text-amber-600 font-medium mb-3">
                ⚠️ Click "Add Reference" to add to list, then click "Update Tenant" at bottom to save all changes.
              </p>
            </div>

            {/* Reference Table */}
            {landlordRefs.length > 0 && (
              <div className="col-span-2 mb-4">
                <div className="border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Landlord</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Phone</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Status</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Date</th>
                        <th className="px-3 py-2"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {landlordRefs.map((ref, idx) => (
                        <tr key={idx} className="border-t">
                          <td className="px-3 py-2">{ref.landlord_name}</td>
                          <td className="px-3 py-2">{ref.landlord_phone ? formatPhoneNumber(ref.landlord_phone) : '-'}</td>
                          <td className="px-3 py-2">
                            <span className={`px-2 py-0.5 text-xs rounded-full ${
                              ref.status === 'pass' ? 'bg-green-100 text-green-800' :
                              ref.status === 'fail' ? 'bg-red-100 text-red-800' :
                              'bg-gray-100 text-gray-800'
                            }`}>
                              {ref.status === 'pass' ? '✓ Pass' : ref.status === 'fail' ? '✗ Fail' : 'No Info'}
                            </span>
                          </td>
                          <td className="px-3 py-2">{ref.contact_date ? new Date(ref.contact_date).toLocaleDateString() : '-'}</td>
                          <td className="px-3 py-2">
                            <div className="flex gap-2">
                              <button
                                onClick={() => {
                                  setCurrentRef({
                                    landlord_name: ref.landlord_name || '',
                                    landlord_phone: ref.landlord_phone || '',
                                    landlord_email: ref.landlord_email || '',
                                    property_address: ref.property_address || '',
                                    contact_date: ref.contact_date || new Date().toISOString().split('T')[0],
                                    status: ref.status || 'no_info',
                                    notes: ref.notes || '',
                                  });
                                  // Set editing index - don't remove from list
                                  setEditingRefIndex(idx);
                                }}
                                className="text-blue-600 hover:text-blue-800 text-xs"
                              >
                                Edit
                              </button>
                              <button
                                onClick={() => {
                                  // Remove from list
                                  setLandlordRefs(landlordRefs.filter((_, i) => i !== idx));
                                }}
                                className="text-red-600 hover:text-red-800 text-xs"
                              >
                                Delete
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Add Reference Form */}
            <div className="col-span-2 bg-gray-50 rounded-lg p-4 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="ref_landlord_name" className="text-xs">Landlord Name</Label>
                  <Input
                    id="ref_landlord_name"
                    value={currentRef.landlord_name}
                    onChange={(e) => setCurrentRef({ ...currentRef, landlord_name: e.target.value })}
                    placeholder="John Smith"
                    className="h-8 text-sm"
                  />
                </div>
                <div>
                  <Label htmlFor="ref_landlord_phone" className="text-xs">Phone</Label>
                  <Input
                    id="ref_landlord_phone"
                    value={currentRef.landlord_phone ? formatPhoneInput(currentRef.landlord_phone) : ''}
                    onChange={(e) => {
                      // Strip non-numeric characters and store only digits
                      const cleaned = stripPhoneNumber(e.target.value);
                      // Limit to 10 digits
                      const limited = cleaned.slice(0, 10);
                      setCurrentRef({ ...currentRef, landlord_phone: limited });
                    }}
                    placeholder="(402) 555-1234"
                    className="h-8 text-sm"
                    maxLength={14} // (XXX) XXX-XXXX = 14 chars
                  />
                </div>
                <div>
                  <Label htmlFor="ref_landlord_email" className="text-xs">Email</Label>
                  <Input
                    id="ref_landlord_email"
                    type="email"
                    value={currentRef.landlord_email}
                    onChange={(e) => setCurrentRef({ ...currentRef, landlord_email: e.target.value })}
                    placeholder="landlord@example.com"
                    className="h-8 text-sm"
                  />
                </div>
                <div>
                  <Label htmlFor="ref_property_address" className="text-xs">Property Address</Label>
                  <Input
                    id="ref_property_address"
                    value={currentRef.property_address}
                    onChange={(e) => setCurrentRef({ ...currentRef, property_address: e.target.value })}
                    placeholder="123 Main St"
                    className="h-8 text-sm"
                  />
                </div>
                <div>
                  <Label htmlFor="ref_contact_date" className="text-xs">Contact Date</Label>
                  <Input
                    id="ref_contact_date"
                    type="date"
                    value={currentRef.contact_date}
                    onChange={(e) => setCurrentRef({ ...currentRef, contact_date: e.target.value })}
                    className="h-8 text-sm"
                  />
                </div>
                <div>
                  <Label htmlFor="ref_status" className="text-xs">Status</Label>
                  <Select
                    value={currentRef.status}
                    onValueChange={(value) => setCurrentRef({ ...currentRef, status: value as any })}
                  >
                    <SelectTrigger className="h-8 text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="pass">✓ Pass</SelectItem>
                      <SelectItem value="fail">✗ Fail</SelectItem>
                      <SelectItem value="no_info">No Info</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end">
                  <Button
                    type="button"
                    size="sm"
                    className="h-8 w-full"
                    onClick={() => {
                      if (currentRef.landlord_name) {
                        if (editingRefIndex !== null) {
                          // Update existing reference
                          const updatedRefs = [...landlordRefs];
                          updatedRefs[editingRefIndex] = currentRef;
                          setLandlordRefs(updatedRefs);
                          setEditingRefIndex(null);
                        } else {
                          // Add new reference
                          setLandlordRefs([...landlordRefs, currentRef]);
                        }
                        // Reset form
                        setCurrentRef({
                          landlord_name: '',
                          landlord_phone: '',
                          landlord_email: '',
                          property_address: '',
                          contact_date: new Date().toISOString().split('T')[0],
                          status: 'no_info',
                          notes: '',
                        });
                      }
                    }}
                    disabled={!currentRef.landlord_name}
                  >
                    {editingRefIndex !== null ? (
                      <>
                        <Pencil className="h-3 w-3 mr-1" />
                        Update
                      </>
                    ) : (
                      <>
                        <Plus className="h-3 w-3 mr-1" />
                        Add to List
                      </>
                    )}
                  </Button>
                </div>
                <div className="col-span-2">
                  <Label htmlFor="ref_notes" className="text-xs">Notes (optional)</Label>
                  <Textarea
                    id="ref_notes"
                    value={currentRef.notes}
                    onChange={(e) => setCurrentRef({ ...currentRef, notes: e.target.value })}
                    placeholder="Notes from conversation..."
                    rows={2}
                    className="text-sm"
                  />
                </div>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setIsCreateDialogOpen(false);
                setIsEditDialogOpen(false);
                setSelectedTenant(null);
                setFormData({
                  property_id: selectedPropertyId || '',
                  first_name: '',
                  last_name: '',
                  email: '',
                  phone: '',
                  status: 'applicant',
                });
                setLandlordRefs([]);
                setEditingRefIndex(null);
                setCurrentRef({
                  landlord_name: '',
                  landlord_phone: '',
                  landlord_email: '',
                  property_address: '',
                  contact_date: new Date().toISOString().split('T')[0],
                  status: 'no_info',
                  notes: '',
                });
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={isEditDialogOpen ? handleUpdateTenant : handleCreateTenant}
              disabled={!formData.property_id || !formData.first_name || !formData.last_name}
            >
              {isEditDialogOpen ? 'Save Changes' : 'Create Tenant'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

