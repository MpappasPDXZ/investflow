'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useProperties } from '@/lib/hooks/use-properties';
import { useLeases, type LeaseCreate, type Tenant, type MoveOutCostItem } from '@/lib/hooks/use-leases';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';
import { FileText, Plus, X, Save, FileCheck, Loader2, ArrowLeft, ExternalLink } from 'lucide-react';

export default function LeaseCreationDashboard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const propertyId = searchParams.get('property_id');
  
  const { data: properties } = useProperties();
  const { createLease, generatePDF } = useLeases();
  
  const [selectedProperty, setSelectedProperty] = useState<any>(null);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [leaseId, setLeaseId] = useState<string | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  
  // Form state
  const [formData, setFormData] = useState({
    property_id: propertyId || '',
    state: 'NE' as 'NE' | 'MO',
    commencement_date: '',
    termination_date: '',
    auto_convert_month_to_month: false,
    monthly_rent: '',
    security_deposit: '',
    payment_method: '',
    tenants: [{ first_name: '', last_name: '', email: '', phone: '' }] as Tenant[],
    max_occupants: 3,
    max_adults: 2,
    max_children: true,
    pets_allowed: true,
    pet_fee_one: '350',
    pet_fee_two: '700',
    max_pets: 2,
    utilities_tenant: 'Gas, Sewer, Water, Electricity',
    utilities_landlord: 'Trash',
    parking_spaces: 2,
    parking_small_vehicles: 2,
    parking_large_trucks: 1,
    front_door_keys: 1,
    back_door_keys: 1,
    key_replacement_fee: '100',
    has_shared_driveway: false,
    shared_driveway_with: '',
    has_garage: false,
    garage_outlets_prohibited: false,
    has_attic: false,
    attic_usage: '',
    has_basement: false,
    appliances_provided: '',
    snow_removal_responsibility: 'tenant',
    lead_paint_disclosure: true,
    lead_paint_year_built: '',
    early_termination_allowed: true,
    early_termination_notice_days: 60,
    early_termination_fee_months: 2,
    moveout_costs: [
      { item: 'Hardwood Floor Cleaning', description: 'Fee if not clean', amount: '100', order: 1 },
      { item: 'Trash Removal Fee', description: 'Fee if trash not removed', amount: '150', order: 2 },
      { item: 'Heavy Cleaning', description: 'Dirty appliances/bathrooms', amount: '400', order: 3 },
      { item: 'Wall Repairs', description: 'Nail holes/minor damage', amount: '150', order: 4 },
    ] as MoveOutCostItem[],
    methamphetamine_disclosure: false,
    owner_name: 'S&M Axios Heartland Holdings, LLC',
    owner_address: 'c/o Sarah Pappas, 1606 S 208th St, Elkhorn, NE 68022',
    moveout_inspection_rights: false,
    notes: '',
  });
  
  // Load property when selected
  useEffect(() => {
    if (formData.property_id && properties?.properties) {
      const prop = properties.properties.find((p: any) => p.id === formData.property_id);
      setSelectedProperty(prop);
      
      if (prop) {
        setFormData(prev => ({
          ...prev,
          state: (prop.state || 'NE') as 'NE' | 'MO',
          lead_paint_year_built: prop.year_built?.toString() || '',
        }));
      }
    }
  }, [formData.property_id, properties]);
  
  // Auto-calculate security deposit
  useEffect(() => {
    if (formData.monthly_rent && !formData.security_deposit) {
      setFormData(prev => ({
        ...prev,
        security_deposit: prev.monthly_rent,
      }));
    }
  }, [formData.monthly_rent]);
  
  const addTenant = () => {
    setFormData(prev => ({
      ...prev,
      tenants: [...prev.tenants, { first_name: '', last_name: '', email: '', phone: '' }],
    }));
  };
  
  const removeTenant = (index: number) => {
    if (formData.tenants.length > 1) {
      setFormData(prev => ({
        ...prev,
        tenants: prev.tenants.filter((_, i) => i !== index),
      }));
    }
  };
  
  const updateTenant = (index: number, field: keyof Tenant, value: string) => {
    setFormData(prev => ({
      ...prev,
      tenants: prev.tenants.map((t, i) => 
        i === index ? { ...t, [field]: value } : t
      ),
    }));
  };
  
  const addMoveoutCost = () => {
    const nextOrder = formData.moveout_costs.length + 1;
    setFormData(prev => ({
      ...prev,
      moveout_costs: [...prev.moveout_costs, 
        { item: '', description: '', amount: '', order: nextOrder }
      ],
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
  
  const handleSaveDraft = async () => {
    setSaving(true);
    try {
      const payload: LeaseCreate = {
        ...formData,
        monthly_rent: parseFloat(formData.monthly_rent),
        security_deposit: parseFloat(formData.security_deposit),
        pet_fee_one: parseFloat(formData.pet_fee_one),
        pet_fee_two: parseFloat(formData.pet_fee_two),
        key_replacement_fee: parseFloat(formData.key_replacement_fee),
        lead_paint_year_built: formData.lead_paint_year_built ? parseInt(formData.lead_paint_year_built) : undefined,
        moveout_costs: formData.moveout_costs.map(c => ({
          ...c,
          amount: parseFloat(c.amount.toString()),
        })),
      };
      
      const response = await createLease(payload);
      setLeaseId(response.id);
      alert('Lease saved as draft');
    } catch (err) {
      console.error('Error saving draft:', err);
      alert('Failed to save draft');
    } finally {
      setSaving(false);
    }
  };
  
  const handleGeneratePDF = async () => {
    let currentLeaseId = leaseId;
    
    if (!currentLeaseId) {
      await handleSaveDraft();
      // Wait for leaseId to be set
      if (!leaseId) return;
      currentLeaseId = leaseId;
    }
    
    setGenerating(true);
    try {
      const response = await generatePDF(currentLeaseId, false);
      setPdfUrl(response.pdf_url);
    } catch (err) {
      console.error('Error generating PDF:', err);
      alert('Failed to generate PDF');
    } finally {
      setGenerating(false);
    }
  };
  
  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-6 flex justify-between items-start">
        <div>
          <div className="text-xs text-gray-500 mb-1">Creating:</div>
          <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Lease Agreement
            {selectedProperty && ` - ${selectedProperty.display_name}`}
          </h1>
        </div>
        <Button
          variant="outline"
          onClick={() => router.push('/leases')}
          size="sm"
          className="h-8 text-xs"
        >
          <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
          Back to Leases
        </Button>
      </div>
      
      {/* Split-screen layout: 75% left (preview) + 25% right (form) */}
      <div className="grid grid-cols-[1fr_25%] gap-6">
        {/* Left: Document Preview (75%) */}
        <div className="space-y-4">
          <Card className="h-[calc(100vh-200px)]">
            <CardHeader className="border-b bg-gray-50 pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-bold">Document Preview</CardTitle>
                {pdfUrl && (
                  <a href={pdfUrl} target="_blank" rel="noopener noreferrer">
                    <Button variant="outline" size="sm" className="h-8 text-xs">
                      <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                      Open in New Tab
                    </Button>
                  </a>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-0 h-[calc(100%-60px)]">
              {pdfUrl ? (
                <iframe
                  src={`${pdfUrl}#view=FitH`}
                  className="w-full h-full"
                  title="Lease Preview"
                />
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-gray-500">
                  <FileText className="h-16 w-16 mb-4 text-gray-300" />
                  <p className="text-sm">Fill out the form and generate PDF to preview</p>
                  <p className="text-xs text-gray-400 mt-2">Document will appear here</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
        
        {/* Right: Parameters (25%) - Compact & Scrollable */}
        <div className="space-y-3 overflow-y-auto h-[calc(100vh-200px)] pr-2">
          {/* Property Selection */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-bold">Property</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Select
                value={formData.property_id}
                onValueChange={(value) => setFormData({ ...formData, property_id: value })}
              >
                <SelectTrigger className="text-sm h-9">
                  <SelectValue placeholder="Select property" />
                </SelectTrigger>
                <SelectContent>
                  {properties?.properties.map((p: any) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.display_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
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
            </CardContent>
          </Card>
          
          {/* Lease Terms */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-bold">Lease Terms</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-xs">Start Date</Label>
                  <Input
                    type="date"
                    value={formData.commencement_date}
                    onChange={(e) => setFormData({ ...formData, commencement_date: e.target.value })}
                    className="text-sm h-9"
                  />
                </div>
                <div>
                  <Label className="text-xs">End Date</Label>
                  <Input
                    type="date"
                    value={formData.termination_date}
                    onChange={(e) => setFormData({ ...formData, termination_date: e.target.value })}
                    className="text-sm h-9"
                  />
                </div>
              </div>
              
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
            </CardContent>
          </Card>
          
          {/* Tenants */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex justify-between items-center">
                <CardTitle className="text-sm font-bold">Tenants</CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={addTenant}
                  className="h-7 text-xs px-2"
                >
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {formData.tenants.map((tenant, index) => (
                <div key={index} className="space-y-2 pb-3 border-b last:border-0">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-600 font-medium">Tenant {index + 1}</span>
                    {formData.tenants.length > 1 && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeTenant(index)}
                        className="h-6 w-6 p-0 text-red-600"
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                  <Input
                    placeholder="First name"
                    value={tenant.first_name}
                    onChange={(e) => updateTenant(index, 'first_name', e.target.value)}
                    className="text-sm h-8"
                  />
                  <Input
                    placeholder="Last name"
                    value={tenant.last_name}
                    onChange={(e) => updateTenant(index, 'last_name', e.target.value)}
                    className="text-sm h-8"
                  />
                  <Input
                    placeholder="Email (optional)"
                    type="email"
                    value={tenant.email || ''}
                    onChange={(e) => updateTenant(index, 'email', e.target.value)}
                    className="text-sm h-8"
                  />
                  <Input
                    placeholder="Phone (optional)"
                    type="tel"
                    value={tenant.phone || ''}
                    onChange={(e) => updateTenant(index, 'phone', e.target.value)}
                    className="text-sm h-8"
                  />
                </div>
              ))}
            </CardContent>
          </Card>
          
          {/* Occupancy & Pets */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-bold">Occupancy & Pets</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-xs">Max Occupants</Label>
                  <Input
                    type="number"
                    value={formData.max_occupants}
                    onChange={(e) => setFormData({ ...formData, max_occupants: parseInt(e.target.value) || 0 })}
                    className="text-sm h-8"
                  />
                </div>
                <div>
                  <Label className="text-xs">Max Adults</Label>
                  <Input
                    type="number"
                    value={formData.max_adults}
                    onChange={(e) => setFormData({ ...formData, max_adults: parseInt(e.target.value) || 0 })}
                    className="text-sm h-8"
                  />
                </div>
              </div>
              
              <Separator className="my-2" />
              
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="pets_allowed"
                  checked={formData.pets_allowed}
                  onCheckedChange={(checked) => setFormData({ ...formData, pets_allowed: checked as boolean })}
                  className="h-4 w-4"
                />
                <Label htmlFor="pets_allowed" className="text-xs font-medium">Pets Allowed</Label>
              </div>
              
              {formData.pets_allowed && (
                <div className="grid grid-cols-2 gap-2 pl-6">
                  <div>
                    <Label className="text-xs">1 Pet Fee</Label>
                    <Input
                      type="number"
                      value={formData.pet_fee_one}
                      onChange={(e) => setFormData({ ...formData, pet_fee_one: e.target.value })}
                      className="text-sm h-8"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">2 Pet Fee</Label>
                    <Input
                      type="number"
                      value={formData.pet_fee_two}
                      onChange={(e) => setFormData({ ...formData, pet_fee_two: e.target.value })}
                      className="text-sm h-8"
                    />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
          
          {/* Property Features */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-bold">Property Features</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <Label className="text-xs">Parking</Label>
                  <Input
                    type="number"
                    value={formData.parking_spaces}
                    onChange={(e) => setFormData({ ...formData, parking_spaces: parseInt(e.target.value) || 0 })}
                    className="text-sm h-8"
                  />
                </div>
                <div>
                  <Label className="text-xs">Keys</Label>
                  <Input
                    type="number"
                    value={formData.front_door_keys}
                    onChange={(e) => setFormData({ ...formData, front_door_keys: parseInt(e.target.value) || 0 })}
                    className="text-sm h-8"
                  />
                </div>
                <div>
                  <Label className="text-xs">Key Fee</Label>
                  <Input
                    type="number"
                    value={formData.key_replacement_fee}
                    onChange={(e) => setFormData({ ...formData, key_replacement_fee: e.target.value })}
                    className="text-sm h-8"
                  />
                </div>
              </div>
              
              <div className="space-y-1.5">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="shared_driveway"
                    checked={formData.has_shared_driveway}
                    onCheckedChange={(checked) => setFormData({ ...formData, has_shared_driveway: checked as boolean })}
                    className="h-4 w-4"
                  />
                  <Label htmlFor="shared_driveway" className="text-xs">Shared Driveway</Label>
                </div>
                
                {formData.has_shared_driveway && (
                  <Input
                    placeholder="Shared with address"
                    value={formData.shared_driveway_with}
                    onChange={(e) => setFormData({ ...formData, shared_driveway_with: e.target.value })}
                    className="text-sm h-8 ml-6"
                  />
                )}
                
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="garage"
                    checked={formData.has_garage}
                    onCheckedChange={(checked) => setFormData({ ...formData, has_garage: checked as boolean })}
                    className="h-4 w-4"
                  />
                  <Label htmlFor="garage" className="text-xs">Garage</Label>
                </div>
                
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="attic"
                    checked={formData.has_attic}
                    onCheckedChange={(checked) => setFormData({ ...formData, has_attic: checked as boolean })}
                    className="h-4 w-4"
                  />
                  <Label htmlFor="attic" className="text-xs">Attic</Label>
                </div>
                
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="basement"
                    checked={formData.has_basement}
                    onCheckedChange={(checked) => setFormData({ ...formData, has_basement: checked as boolean })}
                    className="h-4 w-4"
                  />
                  <Label htmlFor="basement" className="text-xs">Basement</Label>
                </div>
              </div>
            </CardContent>
          </Card>
          
          {/* Move-Out Costs */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex justify-between items-center">
                <CardTitle className="text-sm font-bold">Move-Out Costs</CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={addMoveoutCost}
                  className="h-7 text-xs px-2"
                >
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              {formData.moveout_costs.map((cost, index) => (
                <div key={index} className="space-y-1 pb-2 border-b last:border-0">
                  <div className="flex gap-2 items-center">
                    <Input
                      placeholder="Item"
                      value={cost.item}
                      onChange={(e) => updateMoveoutCost(index, 'item', e.target.value)}
                      className="text-sm h-8 flex-1"
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeMoveoutCost(index)}
                      className="h-6 w-6 p-0 text-red-600"
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                  <Input
                    placeholder="Description"
                    value={cost.description || ''}
                    onChange={(e) => updateMoveoutCost(index, 'description', e.target.value)}
                    className="text-xs h-7"
                  />
                  <Input
                    type="number"
                    placeholder="Amount"
                    value={cost.amount}
                    onChange={(e) => updateMoveoutCost(index, 'amount', e.target.value)}
                    className="text-sm h-8"
                  />
                </div>
              ))}
            </CardContent>
          </Card>
          
          {/* Missouri-Specific */}
          {formData.state === 'MO' && (
            <Card className="bg-amber-50 border-amber-300">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-bold">Missouri Required</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex items-center space-x-2">
                  <Checkbox
                    id="meth_disclosure"
                    checked={formData.methamphetamine_disclosure}
                    onCheckedChange={(checked) => 
                      setFormData({ ...formData, methamphetamine_disclosure: checked as boolean })
                    }
                    className="h-4 w-4"
                  />
                  <Label htmlFor="meth_disclosure" className="text-xs font-medium">
                    Methamphetamine Disclosure
                  </Label>
                </div>
                
                <div>
                  <Label className="text-xs font-medium">Owner Name *</Label>
                  <Input
                    value={formData.owner_name}
                    onChange={(e) => setFormData({ ...formData, owner_name: e.target.value })}
                    className="text-sm h-8"
                  />
                </div>
                
                <div>
                  <Label className="text-xs font-medium">Owner Address *</Label>
                  <textarea
                    value={formData.owner_address}
                    onChange={(e) => setFormData({ ...formData, owner_address: e.target.value })}
                    className="w-full px-2 py-1 border border-gray-300 rounded-md text-sm h-16"
                  />
                </div>
              </CardContent>
            </Card>
          )}
          
          {/* Action Buttons - Sticky at bottom */}
          <Card className="sticky bottom-0 bg-white border-2 border-gray-900 shadow-lg">
            <CardContent className="pt-4">
              <div className="space-y-2">
                <Button
                  onClick={handleSaveDraft}
                  disabled={saving || !formData.property_id || !formData.commencement_date || !formData.termination_date || !formData.monthly_rent}
                  className="w-full bg-gray-600 hover:bg-gray-700 text-white h-9 text-sm font-medium"
                >
                  {saving ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-2" />
                      Save Draft
                    </>
                  )}
                </Button>
                
                <Button
                  onClick={handleGeneratePDF}
                  disabled={generating || !formData.property_id || !formData.commencement_date || !formData.termination_date || !formData.monthly_rent}
                  className="w-full bg-black hover:bg-gray-800 text-white h-9 text-sm font-medium"
                >
                  {generating ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <FileCheck className="h-4 w-4 mr-2" />
                      Generate PDF
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
