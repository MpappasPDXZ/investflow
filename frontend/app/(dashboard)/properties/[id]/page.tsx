'use client';

import { useParams, useRouter } from 'next/navigation';
import { useProperty } from '@/lib/hooks/use-properties';
import { useFinancialPerformance } from '@/lib/hooks/use-financial-performance';
import { useExpenses } from '@/lib/hooks/use-expenses';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Building2, Plus, Edit2, Trash2, X, Check, FileText, DollarSign, Home, Eye, TrendingUp, Hammer, ListChecks, Tag, Archive, ShoppingCart, Calendar, LayoutGrid } from 'lucide-react';
import { useEffect, useState } from 'react';
import { apiClient } from '@/lib/api-client';
import ScheduledFinancialsTab from '@/components/ScheduledFinancialsTab';
import RentManagementTab from '@/components/RentManagementTab';
import RentAnalysisTab from '@/components/RentAnalysisTab';
import SetRentAnalysisTab from '@/components/SetRentAnalysisTab';
import FinancialPerformanceTab from '@/components/FinancialPerformanceTab';
import ComparablesTab from '@/components/ComparablesTab';

interface Unit {
  id: string;
  property_id: string;
  unit_number: string;
  bedrooms: number | null;
  bathrooms: number | null;
  square_feet: number | null;
  current_monthly_rent: number | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export default function PropertyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const { data: property, isLoading, refetch } = useProperty(id);
  const [units, setUnits] = useState<Unit[]>([]);
  const [loadingUnits, setLoadingUnits] = useState(false);
  const [showAddUnit, setShowAddUnit] = useState(false);
  const [editingUnit, setEditingUnit] = useState<string | null>(null);
  const [deletingUnit, setDeletingUnit] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'details' | 'performance' | 'financials' | 'down-payment' | 'rent' | 'comps'>('details');
  const [editingProperty, setEditingProperty] = useState(false);

  // Fetch financial performance for YTD P/L display
  const { data: financialPerformance } = useFinancialPerformance(id);
  const { data: expensesData } = useExpenses(id);

  // Calculate total rehab expenses
  const totalRehabExpenses = expensesData?.items
    ?.filter((exp: any) => exp.expense_type === 'rehab')
    ?.reduce((sum: number, exp: any) => sum + Number(exp.amount), 0) || 0;

  // Form state for adding/editing units
  const [unitForm, setUnitForm] = useState({
    unit_number: '',
    bedrooms: '',
    bathrooms: '',
    square_feet: '',
    current_monthly_rent: '',
  });

  // Form state for editing property
  const [propertyForm, setPropertyForm] = useState({
    display_name: '',
    purchase_price: '',
    purchase_date: '',
    down_payment: '',
    cash_invested: '',
    current_market_value: '',
    property_status: '',
    vacancy_rate: '',
    address_line1: '',
    address_line2: '',
    city: '',
    state: '',
    zip_code: '',
    property_type: '',
    year_built: '',
    bedrooms: '',
    bathrooms: '',
    square_feet: '',
    current_monthly_rent: '',
    notes: '',
  });

  // Check if property is multi-unit
  const isMultiUnit = property?.property_type === 'multi_family' || property?.property_type === 'duplex';

  // Fetch units if multi-unit property
  useEffect(() => {
    if (property?.id && isMultiUnit) {
      fetchUnits();
    }
  }, [property?.id, isMultiUnit]);

  const fetchUnits = async () => {
    try {
      setLoadingUnits(true);
      const response = await apiClient.get<{ items: Unit[]; total: number }>(`/units?property_id=${property?.id}`);
      setUnits(response.items);
      console.log('✅ [UNITS] Fetched units:', response);
    } catch (err) {
      console.error('❌ [UNITS] Error fetching units:', err);
    } finally {
      setLoadingUnits(false);
    }
  };

  const handleAddUnit = async () => {
    try {
      const payload = {
        property_id: id,
        unit_number: unitForm.unit_number,
        bedrooms: unitForm.bedrooms ? parseInt(unitForm.bedrooms) : null,
        bathrooms: unitForm.bathrooms ? parseFloat(unitForm.bathrooms) : null,
        square_feet: unitForm.square_feet ? parseInt(unitForm.square_feet) : null,
        current_monthly_rent: unitForm.current_monthly_rent ? parseFloat(unitForm.current_monthly_rent) : null,
      };

      await apiClient.post('/units', payload);
      console.log('✅ [UNIT] Created unit');
      
      // Reset form and hide
      setUnitForm({ unit_number: '', bedrooms: '', bathrooms: '', square_feet: '', current_monthly_rent: '' });
      setShowAddUnit(false);
      
      // Refresh units list
      fetchUnits();
    } catch (err) {
      console.error('❌ [UNIT] Error creating unit:', err);
      alert(`Failed to create unit: ${(err as Error).message}`);
    }
  };

  const handleEditUnit = async (unitId: string) => {
    try {
      const payload = {
        unit_number: unitForm.unit_number,
        bedrooms: unitForm.bedrooms ? parseInt(unitForm.bedrooms) : null,
        bathrooms: unitForm.bathrooms ? parseFloat(unitForm.bathrooms) : null,
        square_feet: unitForm.square_feet ? parseInt(unitForm.square_feet) : null,
        current_monthly_rent: unitForm.current_monthly_rent ? parseFloat(unitForm.current_monthly_rent) : null,
      };

      await apiClient.put(`/units/${unitId}`, payload);
      console.log('✅ [UNIT] Updated unit');
      
      // Reset form and editing state
      setUnitForm({ unit_number: '', bedrooms: '', bathrooms: '', square_feet: '', current_monthly_rent: '' });
      setEditingUnit(null);
      
      // Refresh units list
      fetchUnits();
    } catch (err) {
      console.error('❌ [UNIT] Error updating unit:', err);
      alert(`Failed to update unit: ${(err as Error).message}`);
    }
  };

  const handleDeleteUnit = async (unitId: string, unitNumber: string) => {
    if (!confirm(`Are you sure you want to delete ${unitNumber}?`)) {
      return;
    }

    setDeletingUnit(unitId);
    try {
      await apiClient.delete(`/units/${unitId}`);
      console.log('✅ [UNIT] Deleted unit');
      fetchUnits();
    } catch (err) {
      console.error('❌ [UNIT] Error deleting unit:', err);
      alert(`Failed to delete unit: ${(err as Error).message}`);
    } finally {
      setDeletingUnit(null);
    }
  };

  const startEditUnit = (unit: Unit) => {
    setEditingUnit(unit.id);
    setUnitForm({
      unit_number: unit.unit_number,
      bedrooms: unit.bedrooms?.toString() || '',
      bathrooms: unit.bathrooms?.toString() || '',
      square_feet: unit.square_feet?.toString() || '',
      current_monthly_rent: unit.current_monthly_rent?.toString() || '',
    });
    setShowAddUnit(false);
  };

  const cancelEdit = () => {
    setEditingUnit(null);
    setShowAddUnit(false);
    setUnitForm({ unit_number: '', bedrooms: '', bathrooms: '', square_feet: '', current_monthly_rent: '' });
  };

  const startEditProperty = () => {
    if (!property) return;
    setEditingProperty(true);
    setPropertyForm({
      display_name: property.display_name || '',
      purchase_price: property.purchase_price?.toString() || '',
      purchase_date: property.purchase_date?.split('T')[0] || '2024-10-23',
      down_payment: property.down_payment?.toString() || '',
      cash_invested: property.cash_invested?.toString() || '',
      current_market_value: property.current_market_value?.toString() || '',
      property_status: property.property_status || 'evaluating',
      vacancy_rate: property.vacancy_rate?.toString() || '0.07',
      address_line1: property.address_line1 || '',
      address_line2: property.address_line2 || '',
      city: property.city || '',
      state: property.state || '',
      zip_code: property.zip_code || '',
      property_type: property.property_type || '',
      year_built: property.year_built?.toString() || '',
      bedrooms: property.bedrooms?.toString() || '',
      bathrooms: property.bathrooms?.toString() || '',
      square_feet: property.square_feet?.toString() || '',
      current_monthly_rent: property.current_monthly_rent?.toString() || '',
      notes: property.notes || '',
    });
  };

  const handleSaveProperty = async () => {
    try {
      const payload: any = {
        display_name: propertyForm.display_name || undefined,
        purchase_price: propertyForm.purchase_price ? parseFloat(propertyForm.purchase_price) : undefined,
        purchase_date: propertyForm.purchase_date || undefined,
        down_payment: propertyForm.down_payment ? parseFloat(propertyForm.down_payment) : undefined,
        cash_invested: propertyForm.cash_invested ? parseFloat(propertyForm.cash_invested) : undefined,
        current_market_value: propertyForm.current_market_value ? parseFloat(propertyForm.current_market_value) : undefined,
        property_status: propertyForm.property_status || undefined,
        vacancy_rate: propertyForm.vacancy_rate ? parseFloat(propertyForm.vacancy_rate) : undefined,
        address_line1: propertyForm.address_line1 || undefined,
        address_line2: propertyForm.address_line2 || undefined,
        city: propertyForm.city || undefined,
        state: propertyForm.state || undefined,
        zip_code: propertyForm.zip_code || undefined,
        property_type: propertyForm.property_type || undefined,
        year_built: propertyForm.year_built ? parseInt(propertyForm.year_built) : undefined,
        notes: propertyForm.notes || undefined,
      };

      // For single-unit properties, include unit details
      if (!isMultiUnit) {
        payload.bedrooms = propertyForm.bedrooms ? parseInt(propertyForm.bedrooms) : undefined;
        payload.bathrooms = propertyForm.bathrooms ? parseFloat(propertyForm.bathrooms) : undefined;
        payload.square_feet = propertyForm.square_feet ? parseInt(propertyForm.square_feet) : undefined;
        payload.current_monthly_rent = propertyForm.current_monthly_rent ? parseFloat(propertyForm.current_monthly_rent) : undefined;
      } else {
        // For multi-unit properties, include total square feet if provided
        payload.square_feet = propertyForm.square_feet ? parseInt(propertyForm.square_feet) : undefined;
      }

      // Remove undefined values
      Object.keys(payload).forEach(key => {
        if (payload[key] === undefined || payload[key] === '') {
          delete payload[key];
        }
      });

      console.log('📝 [PROPERTY] Updating property with payload:', JSON.stringify(payload, null, 2));
      await apiClient.put(`/properties/${id}`, payload);
      console.log('✅ [PROPERTY] Updated property');
      
      setEditingProperty(false);
      refetch();
    } catch (err) {
      console.error('❌ [PROPERTY] Error updating property:', err);
      alert(`Failed to update property: ${(err as Error).message}`);
    }
  };

  const cancelEditProperty = () => {
    setEditingProperty(false);
  };

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="text-gray-500">Loading property...</div>
      </div>
    );
  }

  if (!property) {
    return (
      <div className="p-8">
        <div className="text-red-600">Property not found</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-6 flex justify-between items-start">
        <div>
          <div className="text-xs text-gray-500 mb-1">Viewing:</div>
          <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <Building2 className="h-5 w-5" />
            {property.display_name || 'Unnamed Property'}
          </h1>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => router.push('/properties')}
            size="sm"
            className="h-8 text-xs"
          >
            Back to Properties
          </Button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="mb-6 border-b border-gray-200">
        <nav className="flex gap-4">
          <button
            onClick={() => setActiveTab('details')}
            className={`pb-3 px-4 text-sm transition-colors relative ${
              activeTab === 'details'
                ? 'text-black border-b-2 border-black font-bold'
                : 'text-gray-600 hover:text-gray-900 font-normal'
            }`}
          >
            <FileText className="h-4 w-4 inline mr-2" />
            Details & Units
          </button>
          <button
            onClick={() => setActiveTab('performance')}
            className={`pb-3 px-4 text-sm transition-colors relative ${
              activeTab === 'performance'
                ? 'text-black border-b-2 border-black font-bold'
                : 'text-gray-600 hover:text-gray-900 font-normal'
            }`}
          >
            <DollarSign className="h-4 w-4 inline mr-2" />
            Financial Performance
          </button>
          <button
            onClick={() => setActiveTab('financials')}
            className={`pb-3 px-4 text-sm transition-colors relative ${
              activeTab === 'financials'
                ? 'text-black border-b-2 border-black font-bold'
                : 'text-gray-600 hover:text-gray-900 font-normal'
            }`}
          >
            <Calendar className="h-4 w-4 inline mr-2" />
            Scheduled Financials
          </button>
          <button
            onClick={() => setActiveTab('down-payment')}
            className={`pb-3 px-4 text-sm transition-colors relative ${
              activeTab === 'down-payment'
                ? 'text-black border-b-2 border-black font-bold'
                : 'text-gray-600 hover:text-gray-900 font-normal'
            }`}
          >
            <TrendingUp className="h-4 w-4 inline mr-2" />
            Set Down Payment
          </button>
          <button
            onClick={() => setActiveTab('rent')}
            className={`pb-3 px-4 text-sm transition-colors relative ${
              activeTab === 'rent'
                ? 'text-black border-b-2 border-black font-bold'
                : 'text-gray-600 hover:text-gray-900 font-normal'
            }`}
          >
            <Home className="h-4 w-4 inline mr-2" />
            Set Rent
          </button>
          <button
            onClick={() => setActiveTab('comps')}
            className={`pb-3 px-4 text-sm transition-colors relative ${
              activeTab === 'comps'
                ? 'text-black border-b-2 border-black font-bold'
                : 'text-gray-600 hover:text-gray-900 font-normal'
            }`}
          >
            <LayoutGrid className="h-4 w-4 inline mr-2" />
            Comps
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'details' && (
        <>
          {editingProperty && (
            <Card className="mb-6 bg-blue-50 border-blue-200">
              <CardHeader>
                <CardTitle className="text-sm font-bold">Edit Property</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="edit_display_name">Display Name</Label>
                    <Input
                      id="edit_display_name"
                      value={propertyForm.display_name}
                      onChange={(e) => setPropertyForm({ ...propertyForm, display_name: e.target.value })}
                      className="text-sm"
                    />
                  </div>
                  <div>
                    <Label htmlFor="edit_purchase_price">Purchase Price *</Label>
                    <Input
                      id="edit_purchase_price"
                      type="number"
                      step="0.01"
                      value={propertyForm.purchase_price}
                      onChange={(e) => setPropertyForm({ ...propertyForm, purchase_price: e.target.value })}
                      required
                      className="text-sm"
                    />
                  </div>
                  <div>
                    <Label htmlFor="edit_purchase_date">Purchase Date</Label>
                    <Input
                      id="edit_purchase_date"
                      type="date"
                      value={propertyForm.purchase_date}
                      onChange={(e) => setPropertyForm({ ...propertyForm, purchase_date: e.target.value })}
                      className="text-sm"
                    />
                    <p className="text-xs text-gray-500 mt-1">For depreciation calculations</p>
                  </div>
                  <div>
                    <Label htmlFor="edit_down_payment">Down Payment</Label>
                    <Input
                      id="edit_down_payment"
                      type="number"
                      step="0.01"
                      value={propertyForm.down_payment}
                      onChange={(e) => setPropertyForm({ ...propertyForm, down_payment: e.target.value })}
                      className="text-sm"
                    />
                  </div>
                  <div>
                    <Label htmlFor="edit_cash_invested">Cash Invested (for CoC)</Label>
                    <Input
                      id="edit_cash_invested"
                      type="number"
                      step="0.01"
                      value={propertyForm.cash_invested}
                      onChange={(e) => setPropertyForm({ ...propertyForm, cash_invested: e.target.value })}
                      className="text-sm"
                      placeholder="e.g., 75000"
                    />
                    <p className="text-xs text-gray-500 mt-1">Manual entry: down payment + cash rehab costs</p>
                    <div className="mt-2 p-2 bg-gray-50 rounded text-xs space-y-1">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Down Payment:</span>
                        <span className="font-semibold text-gray-900">
                          ${propertyForm.down_payment ? Math.round(parseFloat(propertyForm.down_payment) / 1000).toLocaleString() + 'k' : '$0'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Rehab Expenses:</span>
                        <span className="font-semibold text-gray-900">
                          ${totalRehabExpenses ? Math.round(totalRehabExpenses / 1000).toLocaleString() + 'k' : '$0'}
                        </span>
                      </div>
                      <div className="flex justify-between pt-1 border-t border-gray-200">
                        <span className="text-gray-700 font-medium">Suggested Total:</span>
                        <span className="font-bold text-blue-600">
                          ${Math.round(((parseFloat(propertyForm.down_payment) || 0) + totalRehabExpenses) / 1000).toLocaleString()}k
                        </span>
                      </div>
                    </div>
                  </div>
                  <div>
                    <Label htmlFor="edit_current_market_value">Current Market Value</Label>
                    <Input
                      id="edit_current_market_value"
                      type="number"
                      step="0.01"
                      value={propertyForm.current_market_value}
                      onChange={(e) => setPropertyForm({ ...propertyForm, current_market_value: e.target.value })}
                      className="text-sm"
                    />
                  </div>
                  <div>
                    <Label htmlFor="edit_property_status">Property Status</Label>
                    <Select
                      value={propertyForm.property_status}
                      onValueChange={(value) => setPropertyForm({ ...propertyForm, property_status: value })}
                    >
                      <SelectTrigger className="text-sm">
                        <SelectValue placeholder="Select status" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="evaluating">Evaluating</SelectItem>
                        <SelectItem value="own">Own</SelectItem>
                        <SelectItem value="rehabbing">Rehabbing</SelectItem>
                        <SelectItem value="listed_for_rent">Listed for Rent</SelectItem>
                        <SelectItem value="listed_for_sale">Listed for Sale</SelectItem>
                        <SelectItem value="sold">Sold</SelectItem>
                        <SelectItem value="hide">Hide</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label htmlFor="edit_vacancy_rate">Vacancy Rate</Label>
                    <Input
                      id="edit_vacancy_rate"
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      value={propertyForm.vacancy_rate}
                      onChange={(e) => setPropertyForm({ ...propertyForm, vacancy_rate: e.target.value })}
                      className="text-sm"
                      placeholder="0.07"
                    />
                    <p className="text-xs text-gray-500 mt-1">Enter as decimal (e.g., 0.07 = 7%)</p>
                  </div>
                  {isMultiUnit && (
                    <div>
                      <Label htmlFor="edit_total_square_feet">Total Building Square Feet</Label>
                      <Input
                        id="edit_total_square_feet"
                        type="number"
                        min="0"
                        value={propertyForm.square_feet}
                        onChange={(e) => setPropertyForm({ ...propertyForm, square_feet: e.target.value })}
                        className="text-sm"
                        placeholder="Total SF for vacancy calculations"
                      />
                    </div>
                  )}
                  <div>
                    <Label htmlFor="edit_address_line1">Address</Label>
                    <Input
                      id="edit_address_line1"
                      value={propertyForm.address_line1}
                      onChange={(e) => setPropertyForm({ ...propertyForm, address_line1: e.target.value })}
                      className="text-sm"
                    />
                  </div>
                  <div>
                    <Label htmlFor="edit_address_line2">Address Line 2</Label>
                    <Input
                      id="edit_address_line2"
                      value={propertyForm.address_line2}
                      onChange={(e) => setPropertyForm({ ...propertyForm, address_line2: e.target.value })}
                      className="text-sm"
                      placeholder="Apt, Suite, Unit, etc."
                    />
                  </div>
                  <div>
                    <Label htmlFor="edit_city">City</Label>
                    <Input
                      id="edit_city"
                      value={propertyForm.city}
                      onChange={(e) => setPropertyForm({ ...propertyForm, city: e.target.value })}
                      className="text-sm"
                    />
                  </div>
                  <div>
                    <Label htmlFor="edit_state">State</Label>
                    <Input
                      id="edit_state"
                      value={propertyForm.state}
                      onChange={(e) => setPropertyForm({ ...propertyForm, state: e.target.value })}
                      className="text-sm"
                    />
                  </div>
                  <div>
                    <Label htmlFor="edit_zip_code">Zip Code</Label>
                    <Input
                      id="edit_zip_code"
                      value={propertyForm.zip_code}
                      onChange={(e) => setPropertyForm({ ...propertyForm, zip_code: e.target.value })}
                      className="text-sm"
                    />
                  </div>
                  <div>
                    <Label htmlFor="edit_year_built">Year Built</Label>
                    <Input
                      id="edit_year_built"
                      type="number"
                      min="1800"
                      max="2100"
                      value={propertyForm.year_built}
                      onChange={(e) => setPropertyForm({ ...propertyForm, year_built: e.target.value })}
                      className="text-sm"
                      placeholder="e.g., 1985"
                    />
                  </div>
                  <div>
                    <Label htmlFor="edit_property_type">Property Type</Label>
                    <Select
                      value={propertyForm.property_type}
                      onValueChange={(value) => setPropertyForm({ ...propertyForm, property_type: value })}
                    >
                      <SelectTrigger className="text-sm">
                        <SelectValue placeholder="Select property type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="single_family">Single Family</SelectItem>
                        <SelectItem value="multi_family">Multi Family</SelectItem>
                        <SelectItem value="condo">Condo</SelectItem>
                        <SelectItem value="apartment">Apartment</SelectItem>
                        <SelectItem value="townhome">Townhome</SelectItem>
                        <SelectItem value="duplex">Duplex</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  
                  {!isMultiUnit && (
                    <>
                      <div>
                        <Label htmlFor="edit_bedrooms">Bedrooms</Label>
                        <Input
                          id="edit_bedrooms"
                          type="number"
                          min="0"
                          value={propertyForm.bedrooms}
                          onChange={(e) => setPropertyForm({ ...propertyForm, bedrooms: e.target.value })}
                          className="text-sm"
                        />
                      </div>
                      <div>
                        <Label htmlFor="edit_bathrooms">Bathrooms</Label>
                        <Input
                          id="edit_bathrooms"
                          type="number"
                          min="0"
                          step="0.5"
                          value={propertyForm.bathrooms}
                          onChange={(e) => setPropertyForm({ ...propertyForm, bathrooms: e.target.value })}
                          className="text-sm"
                        />
                      </div>
                      <div>
                        <Label htmlFor="edit_square_feet">Square Feet</Label>
                        <Input
                          id="edit_square_feet"
                          type="number"
                          min="0"
                          value={propertyForm.square_feet}
                          onChange={(e) => setPropertyForm({ ...propertyForm, square_feet: e.target.value })}
                          className="text-sm"
                        />
                      </div>
                      <div>
                        <Label htmlFor="edit_current_monthly_rent">Monthly Rent</Label>
                        <Input
                          id="edit_current_monthly_rent"
                          type="number"
                          step="0.01"
                          value={propertyForm.current_monthly_rent}
                          onChange={(e) => setPropertyForm({ ...propertyForm, current_monthly_rent: e.target.value })}
                          className="text-sm"
                        />
                      </div>
                    </>
                  )}
                </div>
                
                {/* Notes field - always shown */}
                <div className="mt-4 pt-4 border-t">
                  <Label htmlFor="edit_notes">Notes</Label>
                  <textarea
                    id="edit_notes"
                    value={propertyForm.notes}
                    onChange={(e) => setPropertyForm({ ...propertyForm, notes: e.target.value })}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm mt-1"
                    placeholder="Additional details about the property..."
                  />
                </div>
                
                <div className="flex gap-2 mt-4">
                  <Button
                    type="button"
                    onClick={handleSaveProperty}
                    className="bg-black text-white hover:bg-gray-800 h-8 text-xs"
                  >
                    <Check className="h-3 w-3 mr-1" />
                    Save Changes
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={cancelEditProperty}
                    className="h-8 text-xs"
                  >
                    <X className="h-3 w-3 mr-1" />
                    Cancel
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            {/* Property Information Card */}
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <CardTitle className="text-sm font-bold">Property Information</CardTitle>
                  <Button
                    variant="outline"
                    onClick={startEditProperty}
                    className="h-8 text-xs"
                  >
                    <Edit2 className="h-3 w-3 mr-1.5" />
                    Edit Property
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="grid grid-cols-2 gap-x-8 gap-y-4">
                <div>
                  <div className="text-sm text-gray-600">Address</div>
                  <div className="text-sm text-gray-900">
                    {property.address_line1 || 'N/A'}
                    {property.city && `, ${property.city}, ${property.state}`}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Property Type</div>
                  <div className="text-sm text-gray-900 capitalize">
                    {property.property_type?.replace('_', ' ') || 'N/A'}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Purchase Price</div>
                  <div className="text-sm text-gray-900">
                    ${Math.round(property.purchase_price / 1000).toLocaleString()}k
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Cash Invested (for CoC)</div>
                  <div className="text-sm text-gray-900 font-semibold">
                    {property.cash_invested 
                      ? `$${Math.round(property.cash_invested / 1000).toLocaleString()}k`
                      : 'Not Set'}
                  </div>
                </div>
                {totalRehabExpenses > 0 && (
                  <div>
                    <div className="text-sm text-gray-600">Rehab Expenses</div>
                    <div className="text-sm text-gray-900">
                      ${Math.round(totalRehabExpenses / 1000).toLocaleString()}k
                    </div>
                  </div>
                )}
                {property.cash_invested !== null && property.cash_invested !== undefined && (
                  <div>
                    <div className="text-sm text-gray-600">Cash Invested (for CoC)</div>
                    <div className="text-sm text-gray-900 font-semibold">
                      ${Math.round(property.cash_invested / 1000).toLocaleString()}k
                    </div>
                  </div>
                )}
                {property.current_market_value !== null && property.current_market_value !== undefined && (
                  <div>
                    <div className="text-sm text-gray-600">Current Market Value</div>
                    <div className="text-sm text-gray-900">
                      ${Math.round(property.current_market_value / 1000).toLocaleString()}k
                    </div>
                  </div>
                )}
                {property.vacancy_rate !== undefined && property.vacancy_rate !== null && (
                  <div>
                    <div className="text-sm text-gray-600">Vacancy Rate</div>
                    <div className="text-sm text-gray-900">
                      {(property.vacancy_rate * 100).toFixed(1)}%
                    </div>
                  </div>
                )}
                <div>
                  <div className="text-sm text-gray-600">Property Status</div>
                  <div className="text-sm text-gray-900 capitalize flex items-center gap-2">
                    {property.property_status === 'own' && <Home className="h-4 w-4 text-green-600" />}
                    {property.property_status === 'evaluating' && <Eye className="h-4 w-4 text-blue-600" />}
                    {property.property_status === 'rehabbing' && <Hammer className="h-4 w-4 text-orange-600" />}
                    {property.property_status === 'listed_for_rent' && <ListChecks className="h-4 w-4 text-purple-600" />}
                    {property.property_status === 'listed_for_sale' && <Tag className="h-4 w-4 text-yellow-600" />}
                    {property.property_status === 'sold' && <ShoppingCart className="h-4 w-4 text-gray-600" />}
                    {property.property_status === 'hide' && <Archive className="h-4 w-4 text-gray-400" />}
                    {property.property_status?.replace(/_/g, ' ') || 'N/A'}
                  </div>
                </div>
                {!isMultiUnit && (
                  <div>
                    <div className="text-sm text-gray-600">Monthly Rent</div>
                    <div className="text-sm text-gray-900">
                      ${property.current_monthly_rent?.toLocaleString() || 'N/A'}
                    </div>
                  </div>
                )}
                
                {/* Financial Metrics */}
                {financialPerformance && (
                  <div className="col-span-2 pt-4 border-t mt-2 space-y-2">
                    <div className="flex justify-between items-center">
                      <div className="text-sm text-gray-600">Total Revenue</div>
                      <div className="text-sm font-medium text-gray-900">
                        {new Intl.NumberFormat('en-US', {
                          style: 'currency',
                          currency: 'USD',
                          minimumFractionDigits: 0,
                          maximumFractionDigits: 0,
                        }).format(financialPerformance.ytd_total_revenue || 0)}
                      </div>
                    </div>
                    <div className="flex justify-between items-center">
                      <div className="text-sm text-gray-600">IRS Revenue</div>
                      <div className="text-sm font-medium text-blue-900">
                        {new Intl.NumberFormat('en-US', {
                          style: 'currency',
                          currency: 'USD',
                          minimumFractionDigits: 0,
                          maximumFractionDigits: 0,
                        }).format(financialPerformance.ytd_rent)}
                      </div>
                    </div>
                    <div className="flex justify-between items-center">
                      <div className="text-sm text-gray-600">YTD Cost</div>
                      <div className="text-sm font-medium text-red-600">
                        {new Intl.NumberFormat('en-US', {
                          style: 'currency',
                          currency: 'USD',
                          minimumFractionDigits: 0,
                          maximumFractionDigits: 0,
                        }).format(financialPerformance.ytd_expenses)}
                      </div>
                    </div>
                    <div className="flex justify-between items-center pt-2 border-t">
                      <div className="text-sm font-semibold text-gray-700">YTD IRS Profit / (Loss)</div>
                      <div className={`text-lg font-bold ${
                        financialPerformance.ytd_profit_loss >= 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {new Intl.NumberFormat('en-US', {
                          style: 'currency',
                          currency: 'USD',
                          minimumFractionDigits: 0,
                          maximumFractionDigits: 0,
                        }).format(financialPerformance.ytd_profit_loss)}
                      </div>
                    </div>
                    <div className="flex justify-between items-center">
                      <div className="text-sm text-gray-600">Cash Position</div>
                      <div className={`text-sm font-medium ${
                        ((financialPerformance.ytd_total_revenue || 0) - financialPerformance.ytd_expenses) >= 0 
                          ? 'text-blue-600' 
                          : 'text-red-600'
                      }`}>
                        {new Intl.NumberFormat('en-US', {
                          style: 'currency',
                          currency: 'USD',
                          minimumFractionDigits: 0,
                          maximumFractionDigits: 0,
                        }).format((financialPerformance.ytd_total_revenue || 0) - financialPerformance.ytd_expenses)}
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Details Card (for single-unit properties) */}
            {!isMultiUnit && (
              <Card>
                <CardHeader>
                  <CardTitle>Details</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {property.bedrooms !== null && property.bedrooms !== undefined && (
                    <div>
                      <div className="text-sm text-gray-600">Bedrooms</div>
                      <div className="font-medium">{property.bedrooms}</div>
                    </div>
                  )}
                  {property.bathrooms !== null && property.bathrooms !== undefined && (
                    <div>
                      <div className="text-sm text-gray-600">Bathrooms</div>
                      <div className="font-medium">{property.bathrooms}</div>
                    </div>
                  )}
                  {property.square_feet !== null && property.square_feet !== undefined && (
                    <div>
                      <div className="text-sm text-gray-600">Square Feet</div>
                      <div className="font-medium">{property.square_feet.toLocaleString()}</div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Units Section (for multi-unit properties) */}
          {isMultiUnit && (
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <CardTitle className="text-sm font-bold">Units ({units.length})</CardTitle>
                  {!showAddUnit && !editingUnit && (
                    <Button
                      onClick={() => setShowAddUnit(true)}
                      variant="outline"
                      className="h-8 text-xs"
                    >
                      <Plus className="h-3 w-3 mr-1.5" />
                      Add Unit
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                {loadingUnits ? (
                  <div className="text-gray-500 py-4">Loading units...</div>
                ) : (
                  <div className="space-y-4">
                    {/* Add Unit Form */}
                    {showAddUnit && (
                      <Card className="bg-blue-50 border-blue-200">
                        <CardHeader className="pb-3">
                          <CardTitle className="text-lg">Add New Unit</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="grid grid-cols-2 gap-3">
                            <div className="col-span-2">
                              <Label htmlFor="new_unit_number">Unit Number *</Label>
                              <Input
                                id="new_unit_number"
                                value={unitForm.unit_number}
                                onChange={(e) => setUnitForm({ ...unitForm, unit_number: e.target.value })}
                                placeholder="e.g., Unit 1, 1A, Apt 201"
                                className="text-sm"
                              />
                            </div>
                            <div>
                              <Label htmlFor="new_bedrooms">Bedrooms</Label>
                              <Input
                                id="new_bedrooms"
                                type="number"
                                min="0"
                                value={unitForm.bedrooms}
                                onChange={(e) => setUnitForm({ ...unitForm, bedrooms: e.target.value })}
                                className="text-sm"
                              />
                            </div>
                            <div>
                              <Label htmlFor="new_bathrooms">Bathrooms</Label>
                              <Input
                                id="new_bathrooms"
                                type="number"
                                min="0"
                                step="0.5"
                                value={unitForm.bathrooms}
                                onChange={(e) => setUnitForm({ ...unitForm, bathrooms: e.target.value })}
                                className="text-sm"
                              />
                            </div>
                            <div>
                              <Label htmlFor="new_sqft">Square Feet</Label>
                              <Input
                                id="new_sqft"
                                type="number"
                                min="0"
                                value={unitForm.square_feet}
                                onChange={(e) => setUnitForm({ ...unitForm, square_feet: e.target.value })}
                                className="text-sm"
                              />
                            </div>
                            <div>
                              <Label htmlFor="new_rent">Monthly Rent</Label>
                              <Input
                                id="new_rent"
                                type="number"
                                step="0.01"
                                value={unitForm.current_monthly_rent}
                                onChange={(e) => setUnitForm({ ...unitForm, current_monthly_rent: e.target.value })}
                                className="text-sm"
                              />
                            </div>
                          </div>
                          <div className="flex gap-2 mt-4">
                            <Button
                              type="button"
                              onClick={handleAddUnit}
                              disabled={!unitForm.unit_number}
                              size="sm"
                              className="bg-black text-white hover:bg-gray-800"
                            >
                              <Check className="h-4 w-4 mr-1" />
                              Save Unit
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              onClick={cancelEdit}
                              size="sm"
                            >
                              <X className="h-4 w-4 mr-1" />
                              Cancel
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Units Grid */}
                    {units.length === 0 && !showAddUnit ? (
                      <div className="text-gray-500 py-8 text-center">
                        No units added yet. Click "Add Unit" to get started.
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {units.map((unit) => (
                          <Card key={unit.id} className={editingUnit === unit.id ? "bg-blue-50 border-blue-200" : "bg-gray-50"}>
                            {editingUnit === unit.id ? (
                              /* Edit Mode */
                              <>
                                <CardHeader className="pb-3">
                                  <CardTitle className="text-lg">Edit Unit</CardTitle>
                                </CardHeader>
                                <CardContent>
                                  <div className="space-y-3">
                                    <div>
                                      <Label htmlFor={`edit_unit_number_${unit.id}`}>Unit Number *</Label>
                                      <Input
                                        id={`edit_unit_number_${unit.id}`}
                                        value={unitForm.unit_number}
                                        onChange={(e) => setUnitForm({ ...unitForm, unit_number: e.target.value })}
                                        className="text-sm"
                                      />
                                    </div>
                                    <div className="grid grid-cols-2 gap-2">
                                      <div>
                                        <Label htmlFor={`edit_bedrooms_${unit.id}`}>Beds</Label>
                                        <Input
                                          id={`edit_bedrooms_${unit.id}`}
                                          type="number"
                                          min="0"
                                          value={unitForm.bedrooms}
                                          onChange={(e) => setUnitForm({ ...unitForm, bedrooms: e.target.value })}
                                          className="text-sm"
                                        />
                                      </div>
                                      <div>
                                        <Label htmlFor={`edit_bathrooms_${unit.id}`}>Baths</Label>
                                        <Input
                                          id={`edit_bathrooms_${unit.id}`}
                                          type="number"
                                          min="0"
                                          step="0.5"
                                          value={unitForm.bathrooms}
                                          onChange={(e) => setUnitForm({ ...unitForm, bathrooms: e.target.value })}
                                          className="text-sm"
                                        />
                                      </div>
                                    </div>
                                    <div>
                                      <Label htmlFor={`edit_sqft_${unit.id}`}>Sq Ft</Label>
                                      <Input
                                        id={`edit_sqft_${unit.id}`}
                                        type="number"
                                        min="0"
                                        value={unitForm.square_feet}
                                        onChange={(e) => setUnitForm({ ...unitForm, square_feet: e.target.value })}
                                        className="text-sm"
                                      />
                                    </div>
                                    <div>
                                      <Label htmlFor={`edit_rent_${unit.id}`}>Rent</Label>
                                      <Input
                                        id={`edit_rent_${unit.id}`}
                                        type="number"
                                        step="0.01"
                                        value={unitForm.current_monthly_rent}
                                        onChange={(e) => setUnitForm({ ...unitForm, current_monthly_rent: e.target.value })}
                                        className="text-sm"
                                      />
                                    </div>
                                    <div className="flex gap-2 pt-2">
                                      <Button
                                        type="button"
                                        onClick={() => handleEditUnit(unit.id)}
                                        disabled={!unitForm.unit_number}
                                        size="sm"
                                        className="flex-1 bg-black text-white hover:bg-gray-800"
                                      >
                                        <Check className="h-4 w-4 mr-1" />
                                        Save
                                      </Button>
                                      <Button
                                        type="button"
                                        variant="outline"
                                        onClick={cancelEdit}
                                        size="sm"
                                        className="flex-1"
                                      >
                                        <X className="h-4 w-4 mr-1" />
                                        Cancel
                                      </Button>
                                    </div>
                                  </div>
                                </CardContent>
                              </>
                            ) : (
                              /* View Mode */
                              <>
                                <CardHeader className="pb-3">
                                  <div className="flex justify-between items-start">
                                    <CardTitle className="text-lg">{unit.unit_number}</CardTitle>
                                    <div className="flex gap-1">
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => startEditUnit(unit)}
                                        className="h-7 w-7 p-0"
                                      >
                                        <Edit2 className="h-4 w-4" />
                                      </Button>
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => handleDeleteUnit(unit.id, unit.unit_number)}
                                        disabled={deletingUnit === unit.id}
                                        className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                                      >
                                        <Trash2 className="h-4 w-4" />
                                      </Button>
                                    </div>
                                  </div>
                                </CardHeader>
                                <CardContent className="space-y-2">
                                  {unit.bedrooms !== null && (
                                    <div className="flex justify-between text-sm">
                                      <span className="text-gray-600">Bedrooms:</span>
                                      <span className="text-gray-900">{unit.bedrooms}</span>
                                    </div>
                                  )}
                                  {unit.bathrooms !== null && (
                                    <div className="flex justify-between text-sm">
                                      <span className="text-gray-600">Bathrooms:</span>
                                      <span className="text-gray-900">{unit.bathrooms}</span>
                                    </div>
                                  )}
                                  {unit.square_feet !== null && (
                                    <div className="flex justify-between text-sm">
                                      <span className="text-gray-600">Sq Ft:</span>
                                      <span className="text-gray-900">{unit.square_feet.toLocaleString()}</span>
                                    </div>
                                  )}
                                  {unit.current_monthly_rent !== null && (
                                    <div className="flex justify-between text-sm border-t pt-2">
                                      <span className="text-gray-600">Rent:</span>
                                      <span className="text-gray-900">
                                        ${unit.current_monthly_rent.toLocaleString()}
                                      </span>
                                    </div>
                                  )}
                                </CardContent>
                              </>
                            )}
                          </Card>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}

      {activeTab === 'performance' && (
        <FinancialPerformanceTab 
          propertyId={id}
          units={units}
          isMultiUnit={isMultiUnit}
        />
      )}

      {activeTab === 'financials' && (
        <ScheduledFinancialsTab 
          propertyId={id} 
          purchasePrice={property.purchase_price || 0}
        />
      )}

      {activeTab === 'down-payment' && (
        <RentAnalysisTab 
          propertyId={id}
          property={property || {}}
        />
      )}

      {activeTab === 'rent' && (
        <SetRentAnalysisTab 
          propertyId={id}
          property={property || {}}
        />
      )}

      {activeTab === 'comps' && (
        <ComparablesTab 
          propertyId={id}
        />
      )}
    </div>
  );
}
