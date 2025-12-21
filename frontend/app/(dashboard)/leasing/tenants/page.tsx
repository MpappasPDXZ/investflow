'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, Pencil, Trash2, UserCheck, UserX, Users as UsersIcon, CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';
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
import { useCreateLandlordReference, useUpdateLandlordReference, type LandlordReferenceListResponse } from '@/lib/hooks/use-landlord-references';
import { useProperties } from '@/lib/hooks/use-properties';
import { apiClient } from '@/lib/api-client';
import type { Tenant } from '@/lib/types';

export default function TenantsPage() {
  const router = useRouter();
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  
  const { data: tenantsData, isLoading } = useTenants();
  const { data: propertiesData } = useProperties();
  const createTenant = useCreateTenant();
  const updateTenant = useUpdateTenant();
  const deleteTenant = useDeleteTenant();
  const createLandlordReference = useCreateLandlordReference();
  const updateLandlordReference = useUpdateLandlordReference();
  
  const [formData, setFormData] = useState<Partial<Tenant>>({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    status: 'applicant',
  });
  
  // Temp landlord references to add after tenant creation
  const [tempLandlordRefs, setTempLandlordRefs] = useState<Array<{
    id?: string;
    landlord_name: string;
    landlord_phone?: string;
    landlord_email?: string;
    property_address?: string;
    contact_date: string;
    status: 'pass' | 'fail' | 'no_info';
    notes?: string;
  }>>([]);
  
  // Track references to delete
  const [refsToDelete, setRefsToDelete] = useState<string[]>([]);
  
  const [currentRef, setCurrentRef] = useState({
    landlord_name: '',
    landlord_phone: '',
    property_address: '',
    contact_date: new Date().toISOString().split('T')[0],
    status: 'no_info' as 'pass' | 'fail' | 'no_info',
    notes: '',
  });
  
  const handleCreateTenant = async () => {
    try {
      // Create tenant first
      const newTenant = await createTenant.mutateAsync(formData);
      
      // Save landlord references if any
      if (tempLandlordRefs.length > 0 && newTenant.id) {
        for (const ref of tempLandlordRefs) {
          await createLandlordReference.mutateAsync({
            tenant_id: newTenant.id,
            ...ref,
          });
        }
      }
      
      // Reset form
      setIsCreateDialogOpen(false);
      setFormData({
        first_name: '',
        last_name: '',
        email: '',
        phone: '',
        status: 'applicant',
      });
      setTempLandlordRefs([]);
      setCurrentRef({
        landlord_name: '',
        landlord_phone: '',
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
    setFormData(tenant);
    setRefsToDelete([]); // Clear any pending deletions
    
    // Load existing landlord references for this tenant
    try {
      console.log(`📤 Loading landlord references for tenant ${tenant.id}`);
      const refsData = await apiClient.get<LandlordReferenceListResponse>(`/landlord-references?tenant_id=${tenant.id}`);
      console.log('✅ Loaded landlord references:', refsData);
      setTempLandlordRefs(refsData.references || []);
    } catch (error) {
      console.error('❌ Error loading landlord references:', error);
      setTempLandlordRefs([]);
    }
    
    setIsEditDialogOpen(true);
  };
  
  const handleUpdateTenant = async () => {
    if (!selectedTenant) return;
    
    try {
      // Update tenant data
      await updateTenant.mutateAsync({ id: selectedTenant.id, data: formData });
      
      // Delete removed references
      for (const refId of refsToDelete) {
        console.log(`🗑️ Deleting landlord reference ${refId}`);
        await apiClient.delete(`/landlord-references/${refId}`);
      }
      
      // Save/update landlord references
      for (const ref of tempLandlordRefs) {
        if (ref.id) {
          // Update existing reference
          console.log(`✏️ Updating landlord reference ${ref.id}`);
          await updateLandlordReference.mutateAsync({
            id: ref.id,
            tenant_id: selectedTenant.id,
            ...ref,
          });
        } else {
          // Create new reference
          console.log(`➕ Creating new landlord reference`);
          await createLandlordReference.mutateAsync({
            tenant_id: selectedTenant.id,
            ...ref,
          });
        }
      }
      
      // Reset form
      setIsEditDialogOpen(false);
      setSelectedTenant(null);
      setFormData({
        first_name: '',
        last_name: '',
        email: '',
        phone: '',
        status: 'applicant',
      });
      setTempLandlordRefs([]);
      setRefsToDelete([]);
      setCurrentRef({
        landlord_name: '',
        landlord_phone: '',
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
      await deleteTenant.mutateAsync(id);
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
  
  const formatPhoneNumber = (phone?: string) => {
    if (!phone) return '—';
    // Remove all non-numeric characters
    const cleaned = phone.replace(/\D/g, '');
    // Format as (xxx) xxx-xxxx
    if (cleaned.length === 10) {
      return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6)}`;
    }
    return phone; // Return original if not 10 digits
  };
  
  const filteredTenants = tenantsData?.tenants.filter(tenant => {
    if (statusFilter === 'all') return true;
    return tenant.status === statusFilter;
  }) || [];
  
  return (
    <div className="p-8">
      <div className="mb-6 flex justify-between items-start">
        <div>
          <div className="text-xs text-gray-500 mb-1">Viewing:</div>
          <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <UsersIcon className="h-5 w-5" />
            Tenant Profiles
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Manage prospective and current tenant information
          </p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)} className="bg-black text-white hover:bg-gray-800 h-8 text-xs">
          <Plus className="h-3 w-3 mr-1.5" />
          Add Tenant
        </Button>
      </div>
      
      {/* Filters */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="flex items-center gap-4">
            <Label htmlFor="status-filter" className="text-sm font-medium">Filter by Status:</Label>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-48">
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
            <div className="ml-auto text-sm text-gray-600">
              Showing {filteredTenants.length} of {tenantsData?.total || 0} tenants
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* Tenants Table */}
      {isLoading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-2 text-sm text-gray-600">Loading tenants...</p>
        </div>
      ) : filteredTenants.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <UsersIcon className="h-12 w-12 text-gray-400 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">No tenants found</h3>
            <p className="text-sm text-gray-600 mb-4">
              {statusFilter === 'all' 
                ? 'Get started by adding your first tenant profile.'
                : `No tenants with status "${statusFilter}".`}
            </p>
            {statusFilter === 'all' && (
              <Button onClick={() => setIsCreateDialogOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Add Tenant
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Contact</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Income</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Credit</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Landlord Refs</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Background Check</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredTenants.map((tenant) => (
                    <tr 
                      key={tenant.id} 
                      className="hover:bg-gray-50 cursor-pointer"
                      onClick={() => handleEditTenant(tenant)}
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">
                          {tenant.first_name} {tenant.last_name}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900">{tenant.email || '—'}</div>
                        <div className="text-xs text-gray-500">{formatPhoneNumber(tenant.phone)}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-semibold text-gray-900">
                          {tenant.monthly_income ? `$${(tenant.monthly_income / 1000).toFixed(1)}k` : '—'}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-semibold text-gray-900">
                          {tenant.credit_score || '—'}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => router.push(`/leasing/tenants/${tenant.id}/landlord-references`)}
                          className={`text-sm font-medium hover:underline ${(tenant.landlord_references_passed || 0) > 0 ? 'text-green-600' : 'text-gray-400'}`}
                        >
                          {tenant.landlord_references_passed || 0} Passed
                        </button>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getBackgroundCheckBadge(tenant.background_check_status)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getStatusBadge(tenant.status)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleEditTenant(tenant);
                            }}
                            className="h-8 w-8 p-0"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteTenant(tenant.id);
                            }}
                            className="h-8 w-8 p-0"
                          >
                            <Trash2 className="h-4 w-4 text-red-600" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Create/Edit Dialog */}
      <Dialog open={isCreateDialogOpen || isEditDialogOpen} onOpenChange={(open) => {
        setIsCreateDialogOpen(false);
        setIsEditDialogOpen(false);
        if (!open) {
          setSelectedTenant(null);
          setFormData({
            first_name: '',
            last_name: '',
            email: '',
            phone: '',
            status: 'applicant',
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
                value={formData.phone || ''}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                placeholder="(402) 555-1234"
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
            {tempLandlordRefs.length > 0 && (
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
                      {tempLandlordRefs.map((ref, idx) => (
                        <tr key={idx} className="border-t">
                          <td className="px-3 py-2">{ref.landlord_name}</td>
                          <td className="px-3 py-2">{ref.landlord_phone || '-'}</td>
                          <td className="px-3 py-2">
                            <span className={`px-2 py-0.5 text-xs rounded-full ${
                              ref.status === 'pass' ? 'bg-green-100 text-green-800' :
                              ref.status === 'fail' ? 'bg-red-100 text-red-800' :
                              'bg-gray-100 text-gray-800'
                            }`}>
                              {ref.status === 'pass' ? '✓ Pass' : ref.status === 'fail' ? '✗ Fail' : 'No Info'}
                            </span>
                          </td>
                          <td className="px-3 py-2">{new Date(ref.contact_date).toLocaleDateString()}</td>
                          <td className="px-3 py-2">
                            <div className="flex gap-2">
                              <button
                                onClick={() => {
                                  setCurrentRef({
                                    landlord_name: ref.landlord_name,
                                    landlord_phone: ref.landlord_phone || '',
                                    property_address: ref.property_address || '',
                                    contact_date: ref.contact_date,
                                    status: ref.status,
                                    notes: ref.notes || '',
                                  });
                                  // Remove from temp list so it can be re-added when user clicks Add
                                  setTempLandlordRefs(tempLandlordRefs.filter((_, i) => i !== idx));
                                }}
                                className="text-blue-600 hover:text-blue-800 text-xs"
                              >
                                Edit
                              </button>
                              <button
                                onClick={() => {
                                  // If it has an ID, mark it for deletion
                                  if (ref.id) {
                                    setRefsToDelete([...refsToDelete, ref.id]);
                                  }
                                  // Remove from temp list
                                  setTempLandlordRefs(tempLandlordRefs.filter((_, i) => i !== idx));
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
                    value={currentRef.landlord_phone}
                    onChange={(e) => setCurrentRef({ ...currentRef, landlord_phone: e.target.value })}
                    placeholder="(402) 555-1234"
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
                        setTempLandlordRefs([...tempLandlordRefs, currentRef]);
                        setCurrentRef({
                          landlord_name: '',
                          landlord_phone: '',
                          property_address: '',
                          contact_date: new Date().toISOString().split('T')[0],
                          status: 'no_info',
                          notes: '',
                        });
                      }
                    }}
                    disabled={!currentRef.landlord_name}
                  >
                    <Plus className="h-3 w-3 mr-1" />
                    Add to List
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
                  first_name: '',
                  last_name: '',
                  email: '',
                  phone: '',
                  status: 'applicant',
                });
                setTempLandlordRefs([]);
                setRefsToDelete([]);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={isEditDialogOpen ? handleUpdateTenant : handleCreateTenant}
              disabled={!formData.first_name || !formData.last_name}
            >
              {isEditDialogOpen ? 'Save All Changes' : 'Create Tenant'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

