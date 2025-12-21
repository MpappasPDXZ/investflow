'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, Plus, Phone, Mail, MapPin, Pencil, Trash2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useTenant } from '@/lib/hooks/use-tenants';
import { useLandlordReferences, useCreateLandlordReference, useUpdateLandlordReference, useDeleteLandlordReference } from '@/lib/hooks/use-landlord-references';

export default function TenantLandlordReferencesPage() {
  const params = useParams();
  const router = useRouter();
  const tenantId = params.id as string;
  
  const { data: tenant, isLoading: tenantLoading } = useTenant(tenantId);
  const { data: referencesData, isLoading: referencesLoading } = useLandlordReferences({ tenant_id: tenantId });
  const createReference = useCreateLandlordReference();
  const updateReference = useUpdateLandlordReference();
  const deleteReference = useDeleteLandlordReference();
  
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [editingReference, setEditingReference] = useState<any>(null);
  const [formData, setFormData] = useState<{
    landlord_name: string;
    landlord_phone: string;
    landlord_email: string;
    property_address: string;
    contact_date: string;
    status: 'pass' | 'fail' | 'no_info';
    notes: string;
  }>({
    landlord_name: '',
    landlord_phone: '',
    landlord_email: '',
    property_address: '',
    contact_date: new Date().toISOString().split('T')[0],
    status: 'no_info',
    notes: '',
  });
  
  const handleCreateReference = async () => {
    try {
      await createReference.mutateAsync({
        tenant_id: tenantId,
        ...formData,
      });
      setIsCreateDialogOpen(false);
      setFormData({
        landlord_name: '',
        landlord_phone: '',
        landlord_email: '',
        property_address: '',
        contact_date: new Date().toISOString().split('T')[0],
        status: 'no_info',
        notes: '',
      });
    } catch (error) {
      console.error('Error creating landlord reference:', error);
      alert('Failed to create reference');
    }
  };
  
  const handleEditReference = (ref: any) => {
    setEditingReference(ref);
    setFormData({
      landlord_name: ref.landlord_name,
      landlord_phone: ref.landlord_phone || '',
      landlord_email: ref.landlord_email || '',
      property_address: ref.property_address || '',
      contact_date: ref.contact_date,
      status: ref.status,
      notes: ref.notes || '',
    });
    setIsEditDialogOpen(true);
  };
  
  const handleUpdateReference = async () => {
    if (!editingReference) return;
    
    try {
      await updateReference.mutateAsync({
        id: editingReference.id,
        ...formData,
      });
      setIsEditDialogOpen(false);
      setEditingReference(null);
      setFormData({
        landlord_name: '',
        landlord_phone: '',
        landlord_email: '',
        property_address: '',
        contact_date: new Date().toISOString().split('T')[0],
        status: 'no_info',
        notes: '',
      });
    } catch (error) {
      console.error('Error updating landlord reference:', error);
      alert('Failed to update reference');
    }
  };
  
  const handleDeleteReference = async (refId: string) => {
    if (!confirm('Are you sure you want to delete this landlord reference?')) return;
    
    try {
      await deleteReference.mutateAsync(refId);
    } catch (error) {
      console.error('Error deleting landlord reference:', error);
      alert('Failed to delete reference');
    }
  };
  
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pass':
        return <span className="px-2 py-1 text-xs font-semibold rounded-full bg-green-100 text-green-800">✓ Passed</span>;
      case 'fail':
        return <span className="px-2 py-1 text-xs font-semibold rounded-full bg-red-100 text-red-800">✗ Failed</span>;
      case 'no_info':
        return <span className="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800">No Info</span>;
      default:
        return <span className="px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 text-gray-800">{status}</span>;
    }
  };
  
  if (tenantLoading || referencesLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }
  
  if (!tenant) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-500">Tenant not found</p>
      </div>
    );
  }
  
  const references = referencesData?.references || [];
  const passedCount = referencesData?.passed_count || 0;
  
  return (
    <div className="max-w-5xl mx-auto p-6">
      {/* Header */}
      <div className="mb-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push('/leasing/tenants')}
          className="mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Tenants
        </Button>
        
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Landlord References
            </h1>
            <p className="text-gray-600 mt-1">
              {tenant.first_name} {tenant.last_name}
            </p>
          </div>
          <Button onClick={() => setIsCreateDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Reference Check
          </Button>
        </div>
      </div>
      
      {/* Summary */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-600">{references.length}</div>
              <div className="text-sm text-gray-600">Total Calls</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-green-600">{passedCount}</div>
              <div className="text-sm text-gray-600">Passed</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-red-600">
                {references.filter(r => r.status === 'fail').length}
              </div>
              <div className="text-sm text-gray-600">Failed</div>
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* References List */}
      {references.length === 0 ? (
        <Card>
          <CardContent className="pt-6 text-center text-gray-500">
            <p>No landlord references recorded yet.</p>
            <p className="text-sm mt-2">Click "Add Reference Check" to log a call.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {references.map((ref) => (
            <Card key={ref.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{ref.landlord_name}</CardTitle>
                  <div className="flex items-center gap-2">
                    {getStatusBadge(ref.status)}
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleEditReference(ref)}
                      className="h-8 w-8 p-0"
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteReference(ref.id)}
                      className="h-8 w-8 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  {ref.landlord_phone && (
                    <div className="flex items-center gap-2">
                      <Phone className="h-4 w-4 text-gray-400" />
                      <span>{ref.landlord_phone}</span>
                    </div>
                  )}
                  {ref.landlord_email && (
                    <div className="flex items-center gap-2">
                      <Mail className="h-4 w-4 text-gray-400" />
                      <span>{ref.landlord_email}</span>
                    </div>
                  )}
                  {ref.property_address && (
                    <div className="flex items-center gap-2 col-span-2">
                      <MapPin className="h-4 w-4 text-gray-400" />
                      <span>{ref.property_address}</span>
                    </div>
                  )}
                  <div className="col-span-2">
                    <span className="text-gray-500">Contact Date:</span>{' '}
                    <span className="font-medium">
                      {new Date(ref.contact_date).toLocaleDateString()}
                    </span>
                  </div>
                  {ref.notes && (
                    <div className="col-span-2 mt-2 p-3 bg-gray-50 rounded-lg">
                      <div className="text-xs text-gray-500 mb-1">Notes:</div>
                      <div className="text-sm whitespace-pre-wrap">{ref.notes}</div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      
      {/* Create Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Log Landlord Reference Check</DialogTitle>
            <DialogDescription>
              Record the details of your conversation with a previous landlord.
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <Label htmlFor="landlord_name">Landlord Name *</Label>
              <Input
                id="landlord_name"
                value={formData.landlord_name}
                onChange={(e) => setFormData({ ...formData, landlord_name: e.target.value })}
                placeholder="John Smith"
              />
            </div>
            
            <div>
              <Label htmlFor="landlord_phone">Phone</Label>
              <Input
                id="landlord_phone"
                type="tel"
                value={formData.landlord_phone}
                onChange={(e) => setFormData({ ...formData, landlord_phone: e.target.value })}
                placeholder="(402) 555-1234"
              />
            </div>
            
            <div>
              <Label htmlFor="landlord_email">Email</Label>
              <Input
                id="landlord_email"
                type="email"
                value={formData.landlord_email}
                onChange={(e) => setFormData({ ...formData, landlord_email: e.target.value })}
                placeholder="landlord@example.com"
              />
            </div>
            
            <div className="col-span-2">
              <Label htmlFor="property_address">Property Address</Label>
              <Input
                id="property_address"
                value={formData.property_address}
                onChange={(e) => setFormData({ ...formData, property_address: e.target.value })}
                placeholder="123 Main St, Omaha, NE 68102"
              />
            </div>
            
            <div>
              <Label htmlFor="contact_date">Contact Date *</Label>
              <Input
                id="contact_date"
                type="date"
                value={formData.contact_date}
                onChange={(e) => setFormData({ ...formData, contact_date: e.target.value })}
              />
            </div>
            
            <div>
              <Label htmlFor="status">Status *</Label>
              <Select
                value={formData.status}
                onValueChange={(value) => setFormData({ ...formData, status: value as 'pass' | 'fail' | 'no_info' })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pass">✓ Passed</SelectItem>
                  <SelectItem value="fail">✗ Failed</SelectItem>
                  <SelectItem value="no_info">No Info / Wouldn't Give Info</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="col-span-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                placeholder="Notes from the conversation..."
                rows={4}
              />
            </div>
          </div>
          
          <div className="flex justify-end gap-2 mt-4">
            <Button
              variant="outline"
              onClick={() => setIsCreateDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateReference}
              disabled={!formData.landlord_name || !formData.contact_date}
            >
              Save Reference Check
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      
      {/* Edit Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Landlord Reference Check</DialogTitle>
            <DialogDescription>
              Update the details of this landlord reference check.
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <Label htmlFor="edit_landlord_name">Landlord Name *</Label>
              <Input
                id="edit_landlord_name"
                value={formData.landlord_name}
                onChange={(e) => setFormData({ ...formData, landlord_name: e.target.value })}
                placeholder="John Smith"
              />
            </div>
            
            <div>
              <Label htmlFor="edit_landlord_phone">Phone</Label>
              <Input
                id="edit_landlord_phone"
                type="tel"
                value={formData.landlord_phone}
                onChange={(e) => setFormData({ ...formData, landlord_phone: e.target.value })}
                placeholder="(402) 555-1234"
              />
            </div>
            
            <div>
              <Label htmlFor="edit_landlord_email">Email</Label>
              <Input
                id="edit_landlord_email"
                type="email"
                value={formData.landlord_email}
                onChange={(e) => setFormData({ ...formData, landlord_email: e.target.value })}
                placeholder="landlord@example.com"
              />
            </div>
            
            <div className="col-span-2">
              <Label htmlFor="edit_property_address">Property Address</Label>
              <Input
                id="edit_property_address"
                value={formData.property_address}
                onChange={(e) => setFormData({ ...formData, property_address: e.target.value })}
                placeholder="123 Main St, Omaha, NE 68102"
              />
            </div>
            
            <div>
              <Label htmlFor="edit_contact_date">Contact Date *</Label>
              <Input
                id="edit_contact_date"
                type="date"
                value={formData.contact_date}
                onChange={(e) => setFormData({ ...formData, contact_date: e.target.value })}
              />
            </div>
            
            <div>
              <Label htmlFor="edit_status">Status *</Label>
              <Select
                value={formData.status}
                onValueChange={(value) => setFormData({ ...formData, status: value as 'pass' | 'fail' | 'no_info' })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="pass">✓ Passed</SelectItem>
                  <SelectItem value="fail">✗ Failed</SelectItem>
                  <SelectItem value="no_info">No Info / Wouldn't Give Info</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="col-span-2">
              <Label htmlFor="edit_notes">Notes</Label>
              <Textarea
                id="edit_notes"
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                placeholder="Notes from the conversation..."
                rows={4}
              />
            </div>
          </div>
          
          <div className="flex justify-end gap-2 mt-4">
            <Button
              variant="outline"
              onClick={() => {
                setIsEditDialogOpen(false);
                setEditingReference(null);
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpdateReference}
              disabled={!formData.landlord_name || !formData.contact_date}
            >
              Update Reference Check
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

