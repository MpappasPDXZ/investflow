'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { LayoutGrid, Plus, Pencil, Trash2, Check, X, ChevronRight, ChevronDown, Printer } from 'lucide-react';
import { apiClient } from '@/lib/api-client';
import { Property } from '@/lib/types';

interface Comparable {
  id: string;
  property_id: string;
  unit_id?: string;
  address: string;
  city?: string;
  state?: string;
  zip_code?: string;
  property_type?: string;
  is_furnished?: boolean;
  bedrooms: number;
  bathrooms: number;
  square_feet: number;
  asking_price: number;
  has_fence?: boolean;
  has_solid_flooring?: boolean;
  has_quartz_granite?: boolean;
  has_ss_appliances?: boolean;
  has_shaker_cabinets?: boolean;
  has_washer_dryer?: boolean;
  garage_spaces?: number;
  date_listed: string;
  date_rented?: string;
  contacts?: number;
  is_rented?: boolean;
  last_rented_price?: number;
  last_rented_year?: number;
  is_subject_property: boolean;
  is_active: boolean;
  notes?: string;
  // Calculated fields
  days_on_zillow?: number;
  price_per_sf?: number;
  contact_rate?: number;
  actual_price_per_sf?: number;
}

interface Props {
  propertyId: string;
  unitId?: string;
}

const PROPERTY_TYPES = ['House', 'Duplex', 'Townhouse', 'Condo', 'Apartment'];

const emptyForm = {
  address: '',
  city: '',
  state: 'NE',
  zip_code: '',
  property_type: 'House',
  is_furnished: false,
  bedrooms: 3,
  bathrooms: 1,
  square_feet: 1000,
  asking_price: 1500,
  has_fence: false,
  has_solid_flooring: false,
  has_quartz_granite: false,
  has_ss_appliances: false,
  has_shaker_cabinets: false,
  has_washer_dryer: false,
  garage_spaces: 0,
  date_listed: new Date().toISOString().split('T')[0],
  date_rented: (() => {
    const date = new Date();
    date.setDate(date.getDate() + 30);
    return date.toISOString().split('T')[0];
  })(),
  contacts: 0,
  is_rented: false,
  last_rented_price: '',
  last_rented_year: '',
  is_subject_property: false,
  notes: '',
};

export default function ComparablesTab({ propertyId, unitId }: Props) {
  const [comparables, setComparables] = useState<Comparable[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [showFormAmenities, setShowFormAmenities] = useState(false);
  const [showTableAmenities, setShowTableAmenities] = useState(true);
  const [viewMode, setViewMode] = useState<'normal' | 'print'>('normal');
  const [property, setProperty] = useState<Property | null>(null);

  // Fetch property data to get default city/state/zip
  useEffect(() => {
    const fetchProperty = async () => {
      try {
        const response = await apiClient.get<Property>(`/properties/${propertyId}`);
        setProperty(response);
      } catch (err) {
        console.error('Error fetching property:', err);
      }
    };
    fetchProperty();
  }, [propertyId]);

  // Update form defaults when showing add form
  useEffect(() => {
    if (showAddForm && property && !editingId) {
      setForm(prev => ({
        ...prev,
        city: property.city || prev.city || '',
        state: property.state || prev.state || 'NE',
        zip_code: property.zip_code || prev.zip_code || '',
      }));
    }
  }, [showAddForm, property, editingId]);

  useEffect(() => {
    fetchComparables();
  }, [propertyId, unitId]);

  const fetchComparables = async () => {
    try {
      setLoading(true);
      const url = unitId 
        ? `/comparables?property_id=${propertyId}&unit_id=${unitId}`
        : `/comparables?property_id=${propertyId}`;
      const response = await apiClient.get<{ items: Comparable[] }>(url);
      setComparables(response.items || []);
    } catch (err) {
      console.error('Error fetching comparables:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    try {
      const payload = {
        property_id: propertyId,
        unit_id: unitId || undefined,
        address: form.address,
        city: form.city || undefined,
        state: form.state || undefined,
        zip_code: form.zip_code || undefined,
        property_type: form.property_type || undefined,
        is_furnished: form.is_furnished || undefined,
        bedrooms: form.bedrooms,
        bathrooms: form.bathrooms,
        square_feet: form.square_feet,
        asking_price: form.asking_price,
        has_fence: form.has_fence || undefined,
        has_solid_flooring: form.has_solid_flooring || undefined,
        has_quartz_granite: form.has_quartz_granite || undefined,
        has_ss_appliances: form.has_ss_appliances || undefined,
        has_shaker_cabinets: form.has_shaker_cabinets || undefined,
        has_washer_dryer: form.has_washer_dryer || undefined,
        garage_spaces: form.garage_spaces || undefined,
        date_listed: form.date_listed,
        date_rented: form.date_rented || undefined,
        contacts: form.is_rented ? undefined : (form.contacts || undefined),  // Contacts null if rented (not listed)
        is_rented: form.is_rented || undefined,
        last_rented_price: form.last_rented_price ? parseFloat(form.last_rented_price) : undefined,
        last_rented_year: form.last_rented_year ? parseInt(form.last_rented_year) : undefined,
        is_subject_property: form.is_subject_property,
        notes: form.notes || undefined,
      };
      await apiClient.post('/comparables', payload);
      resetForm();
      fetchComparables();
    } catch (err) {
      console.error('Error creating comparable:', err);
      alert(`Failed to create comparable: ${(err as Error).message}`);
    }
  };

  const handleUpdate = async (id: string) => {
    try {
      const payload = {
        address: form.address,
        city: form.city || undefined,
        state: form.state || undefined,
        zip_code: form.zip_code || undefined,
        property_type: form.property_type || undefined,
        is_furnished: form.is_furnished,
        bedrooms: form.bedrooms,
        bathrooms: form.bathrooms,
        square_feet: form.square_feet,
        asking_price: form.asking_price,
        has_fence: form.has_fence,
        has_solid_flooring: form.has_solid_flooring,
        has_quartz_granite: form.has_quartz_granite,
        has_ss_appliances: form.has_ss_appliances,
        has_shaker_cabinets: form.has_shaker_cabinets,
        has_washer_dryer: form.has_washer_dryer,
        garage_spaces: form.garage_spaces,
        date_listed: form.date_listed,
        contacts: form.is_rented ? undefined : form.contacts,  // Contacts null if rented (not listed)
        is_rented: form.is_rented,
        last_rented_price: form.last_rented_price ? parseFloat(form.last_rented_price) : undefined,
        last_rented_year: form.last_rented_year ? parseInt(form.last_rented_year) : undefined,
        is_subject_property: form.is_subject_property,
        notes: form.notes || undefined,
      };
      await apiClient.put(`/comparables/${id}`, payload);
      resetForm();
      fetchComparables();
    } catch (err) {
      console.error('Error updating comparable:', err);
      alert(`Failed to update comparable: ${(err as Error).message}`);
    }
  };

  const handleDelete = async (id: string, address: string) => {
    if (!confirm(`Delete comparable "${address}"?`)) return;
    try {
      await apiClient.delete(`/comparables/${id}`);
      fetchComparables();
    } catch (err) {
      console.error('Error deleting comparable:', err);
      alert(`Failed to delete comparable: ${(err as Error).message}`);
    }
  };

  const startEdit = (comp: Comparable) => {
    setEditingId(comp.id);
    setForm({
      address: comp.address,
      city: comp.city || '',
      state: comp.state || 'NE',
      zip_code: comp.zip_code || '',
      property_type: comp.property_type || 'House',
      is_furnished: comp.is_furnished || false,
      bedrooms: comp.bedrooms,
      bathrooms: comp.bathrooms,
      square_feet: comp.square_feet,
      asking_price: comp.asking_price,
      has_fence: comp.has_fence || false,
      has_solid_flooring: comp.has_solid_flooring || false,
      has_quartz_granite: comp.has_quartz_granite || false,
      has_ss_appliances: comp.has_ss_appliances || false,
      has_shaker_cabinets: comp.has_shaker_cabinets || false,
      has_washer_dryer: comp.has_washer_dryer || false,
      garage_spaces: comp.garage_spaces || 0,
      date_listed: comp.date_listed.split('T')[0],
      date_rented: comp.date_rented ? comp.date_rented.split('T')[0] : undefined,
      contacts: comp.contacts || 0,
      is_rented: comp.is_rented || false,
      last_rented_price: comp.last_rented_price?.toString() || '',
      last_rented_year: comp.last_rented_year?.toString() || '',
      is_subject_property: comp.is_subject_property,
      notes: comp.notes || '',
    });
    setShowAddForm(false);
  };

  const resetForm = () => {
    // Reset form with property defaults for city/state/zip
    setForm({
      ...emptyForm,
      city: property?.city || '',
      state: property?.state || 'NE',
      zip_code: property?.zip_code || '',
    });
    setEditingId(null);
    setShowAddForm(false);
  };

  // Build full address for tooltip
  const getFullAddress = (comp: Comparable) => {
    const parts = [comp.address];
    if (comp.city) parts.push(comp.city);
    if (comp.state) parts.push(comp.state);
    if (comp.zip_code) parts.push(comp.zip_code);
    return parts.join(', ');
  };

  // Open Google search for address + zillow
  const searchZillow = (comp: Comparable) => {
    const fullAddress = getFullAddress(comp);
    const query = encodeURIComponent(`${fullAddress} zillow`);
    window.open(`https://www.google.com/search?q=${query}`, '_blank');
  };

  // CR color coding based on value - using blue theme
  const getCRStyle = (cr: number | undefined) => {
    if (!cr) return '';
    if (cr >= 1.0) return 'bg-blue-200 text-blue-900 font-bold'; // Very high
    if (cr >= 0.5) return 'bg-blue-100 text-blue-800 font-semibold'; // High
    if (cr >= 0.2) return 'bg-blue-50 text-blue-700'; // Medium
    return ''; // Low - no special styling
  };

  // Amenity cell - light blue checkmark for yes, dash for no/null (no red)
  const AmenityCell = ({ value }: { value: boolean | undefined | null }) => {
    if (value === true) {
      return <span className="text-blue-500 font-medium">✓</span>;
    }
    return <span className="text-gray-300">-</span>;
  };

  // Format decimal display (for BA and GAR)
  const formatDecimal = (value: number | undefined) => {
    if (value === undefined || value === null) return '-';
    if (Number.isInteger(value)) return value.toString();
    return value.toFixed(1);
  };

  // Property type abbreviation
  const getTypeAbbrev = (type: string | undefined) => {
    if (!type) return '-';
    const abbrevs: Record<string, string> = {
      'House': 'H',
      'Duplex': 'D',
      'Townhouse': 'TH',
      'Condo': 'C',
      'Apartment': 'A',
    };
    return abbrevs[type] || type.charAt(0);
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="p-4">
          <div className="text-gray-500 text-sm">Loading comparables...</div>
        </CardContent>
      </Card>
    );
  }

  // PRINT VIEW - Most compact printable format
  if (viewMode === 'print') {
    return (
      <>
        <style>{`
          @media print {
            @page {
              size: landscape;
              margin: 0.5cm;
            }
            body {
              print-color-adjust: exact;
              -webkit-print-color-adjust: exact;
            }
            .print-table {
              font-size: 8pt !important;
            }
            .print-table th,
            .print-table td {
              padding: 2px !important;
            }
          }
        `}</style>
        <div className="p-2 bg-white print:p-0">
          <div className="flex justify-between items-center mb-2 print:hidden">
            <h2 className="text-sm font-bold">Rental Comparables - Print View</h2>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => window.print()} className="h-7 text-xs">
                <Printer className="h-3 w-3 mr-1" />
                Print
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setViewMode('normal')} className="h-7 text-xs">
                Back
              </Button>
            </div>
          </div>
          <table className="print-table w-full text-[9px] border-collapse border border-gray-800 print:text-[8pt]">
            <thead>
              <tr className="bg-gray-200 print:bg-gray-300">
                <th className="border border-gray-800 p-1 text-left font-bold">Address</th>
                <th className="border border-gray-800 p-1 w-8 font-bold">T</th>
                <th className="border border-gray-800 p-1 w-8 font-bold">B</th>
                <th className="border border-gray-800 p-1 w-8 font-bold">BA</th>
                <th className="border border-gray-800 p-1 w-16 font-bold">$</th>
                <th className="border border-gray-800 p-1 w-14 font-bold">SF</th>
                <th className="border border-gray-800 p-1 w-8 font-bold">G</th>
                <th className="border border-gray-800 p-1 w-10 font-bold">DOZ</th>
                <th className="border border-gray-800 p-1 w-10 font-bold">INQ</th>
                <th className="border border-gray-800 p-1 w-12 font-bold">$/SF</th>
                <th className="border border-gray-800 p-1 w-12 font-bold">ACT</th>
                <th className="border border-gray-800 p-1 w-10 font-bold">CR</th>
                <th className="border border-gray-800 p-1 w-8 font-bold">R</th>
              </tr>
            </thead>
            <tbody>
              {comparables.map((comp) => (
                <tr 
                  key={comp.id} 
                  className={comp.is_subject_property ? 'bg-blue-100 print:bg-blue-200 font-bold' : ''}
                >
                  <td className="border border-gray-800 p-1">
                    {comp.is_subject_property && '★ '}
                    {comp.address}
                  </td>
                  <td className="border border-gray-800 p-1 text-center">{getTypeAbbrev(comp.property_type)}</td>
                  <td className="border border-gray-800 p-1 text-center">{comp.bedrooms}</td>
                  <td className="border border-gray-800 p-1 text-center">{formatDecimal(comp.bathrooms)}</td>
                  <td className="border border-gray-800 p-1 text-right">{comp.asking_price.toLocaleString()}</td>
                  <td className="border border-gray-800 p-1 text-right">{comp.square_feet.toLocaleString()}</td>
                  <td className="border border-gray-800 p-1 text-center">{formatDecimal(comp.garage_spaces)}</td>
                  <td className="border border-gray-800 p-1 text-right">{comp.days_on_zillow || '-'}</td>
                  <td className="border border-gray-800 p-1 text-right">{comp.contacts ?? '-'}</td>
                  <td className="border border-gray-800 p-1 text-right font-semibold">
                    {comp.price_per_sf ? comp.price_per_sf.toFixed(2) : '-'}
                  </td>
                  <td className="border border-gray-800 p-1 text-right font-semibold">
                    {comp.actual_price_per_sf ? comp.actual_price_per_sf.toFixed(2) : '-'}
                  </td>
                  <td className="border border-gray-800 p-1 text-right">
                    {comp.is_rented || !comp.contact_rate ? '-' : comp.contact_rate.toFixed(2)}
                  </td>
                  <td className="border border-gray-800 p-1 text-center">
                    {comp.is_rented === true ? '✓' : comp.is_rented === false ? '✗' : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-2 text-[10px] text-gray-600 print:text-[7pt] print:text-black print:mt-1">
            <strong>Legend:</strong> T=Type (H=House, D=Duplex, TH=Townhouse) | B=Beds | BA=Baths | G=Garage | DOZ=Days on Zillow | INQ=Inquiries | $/SF=Price per SF | ACT=Actual $/SF (last rented) | CR=Contact Rate | R=Rented (✓=Yes, ✗=No)
          </div>
        </div>
      </>
    );
  }

  // NORMAL VIEW
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-bold flex items-center gap-2">
            <LayoutGrid className="h-4 w-4" />
            Rental Comparables
          </CardTitle>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setViewMode('print')}
              className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
              title="Compact printable view"
            >
              <Printer className="h-3 w-3" />
            </button>
            <button
              onClick={() => setShowTableAmenities(!showTableAmenities)}
              className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
              title={showTableAmenities ? 'Hide amenities columns' : 'Show amenities columns'}
            >
              {showTableAmenities ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Amenities
            </button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => { 
                setShowAddForm(!showAddForm); 
                setEditingId(null); 
                setForm({
                  ...emptyForm,
                  city: property?.city || '',
                  state: property?.state || 'NE',
                  zip_code: property?.zip_code || '',
                });
              }}
              className="h-7 text-xs"
            >
              <Plus className="h-3 w-3 mr-1" />
              Add Comp
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        {/* Add/Edit Form */}
        {(showAddForm || editingId) && (
          <div className="bg-gray-50 border rounded-lg p-3 mb-4">
            <div className="grid grid-cols-5 gap-2 mb-2">
              <div className="col-span-2">
                <Label className="text-xs">Address *</Label>
                <Input
                  value={form.address}
                  onChange={(e) => setForm({ ...form, address: e.target.value })}
                  className="h-7 text-xs"
                  placeholder="123 Main St"
                />
              </div>
              <div>
                <Label className="text-xs">City</Label>
                <Input
                  value={form.city}
                  onChange={(e) => setForm({ ...form, city: e.target.value })}
                  className="h-7 text-xs"
                  placeholder="Omaha"
                />
              </div>
              <div>
                <Label className="text-xs">State</Label>
                <Input
                  value={form.state}
                  onChange={(e) => setForm({ ...form, state: e.target.value })}
                  className="h-7 text-xs"
                  placeholder="NE"
                />
              </div>
              <div>
                <Label className="text-xs">Zip</Label>
                <Input
                  value={form.zip_code}
                  onChange={(e) => setForm({ ...form, zip_code: e.target.value })}
                  className="h-7 text-xs"
                  placeholder="68132"
                />
              </div>
            </div>
            
            <div className="grid grid-cols-7 gap-2 mb-2">
              <div>
                <Label className="text-xs">Type</Label>
                <select
                  value={form.property_type}
                  onChange={(e) => setForm({ ...form, property_type: e.target.value })}
                  className="h-7 text-xs w-full border rounded px-1"
                >
                  {PROPERTY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <Label className="text-xs">BD</Label>
                <Input
                  type="number"
                  value={form.bedrooms}
                  onChange={(e) => setForm({ ...form, bedrooms: parseInt(e.target.value) || 0 })}
                  className="h-7 text-xs"
                />
              </div>
              <div>
                <Label className="text-xs">BA</Label>
                <Input
                  type="number"
                  step="0.5"
                  value={form.bathrooms}
                  onChange={(e) => setForm({ ...form, bathrooms: parseFloat(e.target.value) || 0 })}
                  className="h-7 text-xs"
                />
              </div>
              <div>
                <Label className="text-xs">SF</Label>
                <Input
                  type="number"
                  value={form.square_feet}
                  onChange={(e) => setForm({ ...form, square_feet: parseInt(e.target.value) || 0 })}
                  className="h-7 text-xs"
                />
              </div>
              <div>
                <Label className="text-xs">Price $</Label>
                <Input
                  type="number"
                  value={form.asking_price}
                  onChange={(e) => setForm({ ...form, asking_price: parseFloat(e.target.value) || 0 })}
                  className="h-7 text-xs"
                />
              </div>
              <div>
                <Label className="text-xs">Listed</Label>
                <Input
                  type="date"
                  value={form.date_listed}
                  onChange={(e) => {
                    const newDateListed = e.target.value;
                    // Auto-update date_rented to be 30 days after date_listed if not manually set
                    if (newDateListed && !form.date_rented) {
                      const date = new Date(newDateListed);
                      date.setDate(date.getDate() + 30);
                      setForm({ ...form, date_listed: newDateListed, date_rented: date.toISOString().split('T')[0] });
                    } else {
                      setForm({ ...form, date_listed: newDateListed });
                    }
                  }}
                  className="h-7 text-xs w-full"
                />
              </div>
              <div>
                <Label className="text-xs">Date Rented</Label>
                <Input
                  type="date"
                  value={form.date_rented || ''}
                  onChange={(e) => setForm({ ...form, date_rented: e.target.value })}
                  className="h-7 text-xs w-full"
                  title="Date the property was rented (used for accurate DOZ calculation)"
                />
              </div>
              <div>
                <Label className="text-xs">Inquiries</Label>
                <Input
                  type="number"
                  value={form.contacts}
                  onChange={(e) => setForm({ ...form, contacts: parseInt(e.target.value) || 0 })}
                  className="h-7 text-xs"
                  disabled={form.is_rented}
                  placeholder={form.is_rented ? "N/A (not listed)" : ""}
                  title={form.is_rented ? "Inquiries not visible for rented properties (no longer listed)" : ""}
                />
              </div>
            </div>

            <div className="grid grid-cols-7 gap-2 mb-2">
              <div>
                <Label className="text-xs">Garage</Label>
                <Input
                  type="number"
                  step="0.5"
                  value={form.garage_spaces}
                  onChange={(e) => setForm({ ...form, garage_spaces: parseFloat(e.target.value) || 0 })}
                  className="h-7 text-xs"
                />
              </div>
              <div>
                <Label className="text-xs">Actual $</Label>
                <Input
                  type="number"
                  value={form.last_rented_price}
                  onChange={(e) => setForm({ ...form, last_rented_price: e.target.value })}
                  className="h-7 text-xs"
                  placeholder="Rent"
                />
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-1 text-xs h-7">
                  <Checkbox
                    checked={form.is_rented}
                    onCheckedChange={(checked) => {
                      const isRented = !!checked;
                      setForm({ 
                        ...form, 
                        is_rented: isRented,
                        contacts: isRented ? undefined : form.contacts  // Clear contacts if rented (not listed)
                      });
                    }}
                  />
                  Rented
                </label>
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-1 text-xs h-7">
                  <Checkbox
                    checked={form.is_furnished}
                    onCheckedChange={(checked) => setForm({ ...form, is_furnished: !!checked })}
                  />
                  Furnished
                </label>
              </div>
              <div className="col-span-2 flex items-end">
                <label className="flex items-center gap-1 text-xs h-7">
                  <Checkbox
                    checked={form.is_subject_property}
                    onCheckedChange={(checked) => setForm({ ...form, is_subject_property: !!checked })}
                  />
                  Subject Property
                </label>
              </div>
            </div>

            {/* Amenities Toggle */}
            <button
              onClick={() => setShowFormAmenities(!showFormAmenities)}
              className="text-xs text-blue-600 hover:underline mb-2 flex items-center gap-1"
            >
              {showFormAmenities ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Amenities
            </button>
            
            {showFormAmenities && (
              <div className="grid grid-cols-6 gap-2 mb-2">
                <label className="flex items-center gap-1 text-xs">
                  <Checkbox checked={form.has_fence} onCheckedChange={(c) => setForm({ ...form, has_fence: !!c })} />
                  Fence
                </label>
                <label className="flex items-center gap-1 text-xs">
                  <Checkbox checked={form.has_solid_flooring} onCheckedChange={(c) => setForm({ ...form, has_solid_flooring: !!c })} />
                  LVP/HW
                </label>
                <label className="flex items-center gap-1 text-xs">
                  <Checkbox checked={form.has_quartz_granite} onCheckedChange={(c) => setForm({ ...form, has_quartz_granite: !!c })} />
                  Quartz
                </label>
                <label className="flex items-center gap-1 text-xs">
                  <Checkbox checked={form.has_ss_appliances} onCheckedChange={(c) => setForm({ ...form, has_ss_appliances: !!c })} />
                  SS App
                </label>
                <label className="flex items-center gap-1 text-xs">
                  <Checkbox checked={form.has_shaker_cabinets} onCheckedChange={(c) => setForm({ ...form, has_shaker_cabinets: !!c })} />
                  Shaker
                </label>
                <label className="flex items-center gap-1 text-xs">
                  <Checkbox checked={form.has_washer_dryer} onCheckedChange={(c) => setForm({ ...form, has_washer_dryer: !!c })} />
                  W/D
                </label>
              </div>
            )}

            <div className="flex gap-2 mt-2">
              {editingId ? (
                <>
                  <Button size="sm" onClick={() => handleUpdate(editingId)} className="h-7 text-xs">
                    <Check className="h-3 w-3 mr-1" />
                    Save
                  </Button>
                  <Button size="sm" variant="outline" onClick={resetForm} className="h-7 text-xs">
                    <X className="h-3 w-3 mr-1" />
                    Cancel
                  </Button>
                </>
              ) : (
                <>
                  <Button size="sm" onClick={handleCreate} className="h-7 text-xs">
                    <Check className="h-3 w-3 mr-1" />
                    Add
                  </Button>
                  <Button size="sm" variant="outline" onClick={resetForm} className="h-7 text-xs">
                    <X className="h-3 w-3 mr-1" />
                    Cancel
                  </Button>
                </>
              )}
            </div>
          </div>
        )}

        {/* Compact Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="border-b-2 border-gray-300 bg-gray-100">
                <th className="text-left p-1.5 font-semibold">Address</th>
                <th className="text-center p-1.5 font-semibold w-8" title="Property Type (H=House, D=Duplex, TH=Townhouse)">T</th>
                <th className="text-center p-1.5 font-semibold w-8" title="Bedrooms">BD</th>
                <th className="text-center p-1.5 font-semibold w-8" title="Bathrooms">BA</th>
                <th className="text-right p-1.5 font-semibold" title="Monthly Rent / Asking Price">Price</th>
                <th className="text-right p-1.5 font-semibold" title="Square Feet">SF</th>
                {showTableAmenities && (
                  <>
                    <th className="text-center p-1.5 font-semibold w-8" title="Fence">FNC</th>
                    <th className="text-center p-1.5 font-semibold w-8" title="LVP/Hardwood Flooring">FLR</th>
                    <th className="text-center p-1.5 font-semibold w-8" title="Quartz/Granite Counters">CTR</th>
                    <th className="text-center p-1.5 font-semibold w-8" title="Stainless Steel Appliances">APP</th>
                    <th className="text-center p-1.5 font-semibold w-8" title="Shaker Cabinets">CAB</th>
                    <th className="text-center p-1.5 font-semibold w-8" title="Washer/Dryer">WD</th>
                  </>
                )}
                <th className="text-center p-1.5 font-semibold w-8" title="Garage Spaces">GAR</th>
                <th className="text-right p-1.5 font-semibold" title="Days on Zillow (calculated from list date)">DOZ</th>
                <th className="text-right p-1.5 font-semibold" title="Inquiries / Contacts">INQ</th>
                <th className="text-center p-1.5 font-semibold" title="Price per Square Foot">$/SF</th>
                <th className="text-center p-1.5 font-semibold" title="Actual Price per SF (last rented price ÷ SF)">ACT $/SF</th>
                <th className="text-center p-1.5 font-semibold" title="Contact Rate (Contacts ÷ Days on Zillow)">CR</th>
                <th className="text-center p-1.5 font-semibold w-8" title="Rented Status">R</th>
                <th className="text-center p-1.5 font-semibold" title="Rented">R</th>
                <th className="w-16"></th>
              </tr>
            </thead>
            <tbody>
              {comparables.length === 0 ? (
                <tr>
                  <td colSpan={showTableAmenities ? 19 : 13} className="text-center p-4 text-gray-500">
                    No comparables yet. Add your property and market comps!
                  </td>
                </tr>
              ) : (
                comparables.map((comp) => (
                  <tr
                    key={comp.id}
                    className={`border-b border-gray-200 hover:bg-gray-50 ${
                      comp.is_subject_property ? 'bg-blue-50 border-l-4 border-l-blue-500' : ''
                    }`}
                  >
                    <td className="p-1.5">
                      <div 
                        className="flex items-center gap-1"
                        title={`${getFullAddress(comp)} - Click to search Zillow`}
                      >
                        {comp.is_subject_property && <span className="text-blue-600">★</span>}
                        <button
                          onClick={() => searchZillow(comp)}
                          className="truncate max-w-[140px] text-left hover:text-blue-600 hover:underline cursor-pointer"
                        >
                          {comp.address}
                        </button>
                      </div>
                    </td>
                    <td className="text-center p-1.5 text-gray-500" title={comp.property_type}>
                      {getTypeAbbrev(comp.property_type)}
                    </td>
                    <td className="text-center p-1.5">{comp.bedrooms}</td>
                    <td className="text-center p-1.5">{formatDecimal(comp.bathrooms)}</td>
                    <td className="text-right p-1.5 font-medium">${comp.asking_price.toLocaleString()}</td>
                    <td className="text-right p-1.5">{comp.square_feet.toLocaleString()}</td>
                    {showTableAmenities && (
                      <>
                        <td className="text-center p-1.5"><AmenityCell value={comp.has_fence} /></td>
                        <td className="text-center p-1.5"><AmenityCell value={comp.has_solid_flooring} /></td>
                        <td className="text-center p-1.5"><AmenityCell value={comp.has_quartz_granite} /></td>
                        <td className="text-center p-1.5"><AmenityCell value={comp.has_ss_appliances} /></td>
                        <td className="text-center p-1.5"><AmenityCell value={comp.has_shaker_cabinets} /></td>
                        <td className="text-center p-1.5"><AmenityCell value={comp.has_washer_dryer} /></td>
                      </>
                    )}
                    <td className="text-center p-1.5">{formatDecimal(comp.garage_spaces)}</td>
                    <td className="text-right p-1.5">{comp.days_on_zillow || '-'}</td>
                    <td className="text-right p-1.5">{comp.contacts ?? '-'}</td>
                    <td className="text-center p-1.5">
                      {comp.price_per_sf ? (
                        <span className="inline-flex items-center justify-center px-1.5 py-0.5 rounded-full border border-purple-400 text-purple-700 font-medium">
                          ${comp.price_per_sf.toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="text-center p-1.5">
                      {comp.actual_price_per_sf ? (
                        <span className="inline-flex items-center justify-center px-1.5 py-0.5 rounded-full border border-blue-400 text-blue-700 font-medium">
                          ${comp.actual_price_per_sf.toFixed(2)}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className={`text-center p-1.5 ${getCRStyle(comp.is_rented ? undefined : comp.contact_rate)}`}>
                      {comp.is_rented || !comp.contact_rate ? (
                        <span className="text-gray-400">-</span>
                      ) : (
                        <span className="font-medium">{comp.contact_rate.toFixed(2)}</span>
                      )}
                    </td>
                    <td className="text-center p-1.5">
                      {comp.is_rented === true ? (
                        <span className="text-green-600">✓</span>
                      ) : comp.is_rented === false ? (
                        <span className="text-red-400">✗</span>
                      ) : (
                        <span className="text-gray-300">-</span>
                      )}
                    </td>
                    <td className="p-1.5">
                      <div className="flex gap-1 justify-end">
                        <button
                          onClick={() => startEdit(comp)}
                          className="p-1 hover:bg-gray-200 rounded"
                          title="Edit"
                        >
                          <Pencil className="h-3 w-3 text-gray-500" />
                        </button>
                        <button
                          onClick={() => handleDelete(comp.id, comp.address)}
                          className="p-1 hover:bg-gray-200 rounded"
                          title="Delete"
                        >
                          <Trash2 className="h-3 w-3 text-gray-400" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Legend */}
        <div className="mt-2 text-xs text-gray-500 flex flex-wrap gap-4">
          <span>★ = Your Property</span>
          <span>T: H=House, D=Duplex, TH=Town</span>
          <span><span className="text-blue-500">✓</span> = Has Feature</span>
          <span><strong>CR</strong>: <span className="bg-blue-200 px-1 rounded">≥1</span> <span className="bg-blue-100 px-1 rounded">≥.5</span> <span className="bg-blue-50 px-1 rounded">≥.2</span></span>
        </div>

        {/* Column Explanations */}
        <div className="mt-4 border-t pt-3">
          <h4 className="text-sm font-semibold text-gray-700 mb-2">Column Explanations</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2 text-xs text-gray-600">
            <div><strong>T:</strong> Property Type (H=House, D=Duplex, TH=Townhouse)</div>
            <div><strong>BD:</strong> Number of Bedrooms</div>
            <div><strong>BA:</strong> Number of Bathrooms</div>
            <div><strong>Price:</strong> Monthly rent / asking price</div>
            <div><strong>SF:</strong> Square feet</div>
            <div><strong>FNC:</strong> Has Fence</div>
            <div><strong>FLR:</strong> Has LVP/Hardwood Flooring</div>
            <div><strong>CTR:</strong> Has Quartz/Granite Counters</div>
            <div><strong>APP:</strong> Has Stainless Steel Appliances</div>
            <div><strong>CAB:</strong> Has Shaker Cabinets</div>
            <div><strong>WD:</strong> Has Washer/Dryer included</div>
            <div><strong>GAR:</strong> Number of Garage Spaces</div>
            <div><strong>DOZ:</strong> Days on Zillow (calculated from list date)</div>
            <div><strong>INQ:</strong> Number of Inquiries/Contacts on Zillow</div>
            <div><strong>$/SF:</strong> Price per square foot (Price ÷ SF)</div>
            <div><strong>ACT $/SF:</strong> Actual price per SF (last rented price ÷ SF)</div>
            <div><strong>CR:</strong> Contact Rate (Inquiries ÷ Days on Zillow) - higher = more interest</div>
            <div><strong>R:</strong> Rented Status (✓ = rented, ✗ = not rented)</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

