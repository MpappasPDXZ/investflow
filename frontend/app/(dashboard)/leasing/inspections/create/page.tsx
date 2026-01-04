'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { useWalkthroughs } from '@/lib/hooks/use-walkthroughs';
import { useProperties } from '@/lib/hooks/use-properties';
import { useUnits } from '@/lib/hooks/use-units';
import { useTenants } from '@/lib/hooks/use-tenants';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  ClipboardCheck,
  Camera,
  Save,
  ArrowLeft,
  X,
  Loader2
} from 'lucide-react';
import Link from 'next/link';

// Default areas for residential property inspection
const DEFAULT_AREAS = [
  'Living Room',
  'Kitchen',
  'Dining Room',
  'Master Bedroom',
  'Bedroom 2',
  'Bedroom 3',
  'Bathroom 1',
  'Bathroom 2',
  'Hallway',
  'Closets',
  'Garage',
  'Exterior - Front',
  'Exterior - Back',
  'Basement',
  'Laundry Room',
  'HVAC/Mechanical',
  'Windows & Doors',
  'Flooring',
  'Walls & Ceilings',
  'Appliances'
];

interface AreaInspection {
  id?: string;
  floor: string;
  area_name: string;
  inspection_status: 'no_issues' | 'issue_noted_as_is' | 'issue_landlord_to_fix' | '';
  notes: string;
  photos: Array<{ photo_blob_name?: string; photo_url?: string; notes?: string; order: number; document_id?: string }>;
}

export default function InspectionCreatePage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { createWalkthrough } = useWalkthroughs();

  const { data: propertiesData } = useProperties();
  const properties = propertiesData?.items || [];

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    property_id: '',
    unit_id: '',
    tenant_name: '',
    walkthrough_type: 'move_in' as 'move_in' | 'move_out' | 'periodic' | 'maintenance',
    walkthrough_date: new Date().toISOString().split('T')[0],
    inspector_name: 'Sarah Pappas, Manager S&M Axios Heartland Holdings LLC',
    notes: '',
  });

  // Areas state - managed as array like pets/tenants
  const [areas, setAreas] = useState<AreaInspection[]>([]);
  const [newAreaName, setNewAreaName] = useState('');

  // Load units when property is selected
  const { data: unitsData } = useUnits(formData.property_id || undefined);
  const units = unitsData?.items || [];

  // Load tenants when property is selected
  const { data: tenantsData } = useTenants(
    formData.property_id ? { property_id: formData.property_id } : undefined
  );
  const availableTenants = tenantsData?.tenants || [];

  const selectedProperty = properties.find(p => p.id === formData.property_id);
  const propertyUnits = units.filter(u => u.property_id === formData.property_id);
  const isMultiFamily = selectedProperty?.property_type !== 'single_family';

  // Initialize areas when type and property are selected
  useEffect(() => {
    if (formData.walkthrough_type && formData.property_id && areas.length === 0) {
      const initialAreas: AreaInspection[] = DEFAULT_AREAS.map((name) => ({
        floor: 'Floor 1',
        area_name: name,
        inspection_status: '',
        notes: '',
        photos: [],
      }));
      setAreas(initialAreas);
    }
  }, [formData.walkthrough_type, formData.property_id]);

  const addCustomArea = () => {
    if (!newAreaName.trim()) return;
    const newArea: AreaInspection = {
      floor: 'Floor 1',
      area_name: newAreaName.trim(),
      inspection_status: '',
      notes: '',
      photos: [],
    };
    setAreas([...areas, newArea]);
    setNewAreaName('');
  };

  const removeArea = (index: number) => {
    setAreas(areas.filter((_, i) => i !== index));
  };

  const updateArea = (index: number, updates: Partial<AreaInspection>) => {
    setAreas(areas.map((a, i) => i === index ? { ...a, ...updates } : a));
  };

  const handleSave = async () => {
    if (!formData.property_id) {
      alert('Please select a property');
      return;
    }

    if (!formData.tenant_name) {
      alert('Please select a tenant');
      return;
    }

    if (areas.length === 0) {
      alert('Please add at least one inspection area');
      return;
    }

    // Filter to only areas with inspection status
    const areasWithStatus = areas.filter(a => a.inspection_status);

    if (areasWithStatus.length === 0) {
      alert('Please set inspection status for at least one area before saving');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const walkthroughData = {
        property_id: formData.property_id,
        unit_id: formData.unit_id || undefined,
        walkthrough_type: formData.walkthrough_type,
        walkthrough_date: formData.walkthrough_date,
        inspector_name: formData.inspector_name || undefined,
        tenant_name: formData.tenant_name,
        notes: formData.notes || undefined,
        areas: areasWithStatus.map(a => ({
          floor: a.floor || 'Floor 1',
          area_name: a.area_name,
          inspection_status: a.inspection_status as 'no_issues' | 'issue_noted_as_is' | 'issue_landlord_to_fix',
          notes: a.notes || undefined,
          issues: [],
        })),
      };

      const newWalkthrough = await createWalkthrough(walkthroughData);

      // Redirect to edit page to add photos
      router.push(`/leasing/inspections/${newWalkthrough.id}/edit?refresh=true`);
    } catch (error: any) {
      console.error('Error creating inspection:', error);
      setError(error.message || 'Failed to create inspection');
      alert(error.message || 'Failed to create inspection');
    } finally {
      setSaving(false);
    }
  };

  const completedCount = areas.filter(a => a.inspection_status !== '').length;

  return (
    <div className="p-6 h-[calc(100vh-4rem)] overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <Link href="/leasing/inspections">
            <Button variant="outline" size="sm" className="h-7 text-xs">
              <ArrowLeft className="h-3 w-3 mr-1" />
              Back
            </Button>
          </Link>
          <h1 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
            <ClipboardCheck className="h-3.5 w-3.5" />
            Create Inspection
          </h1>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-800">
          {error}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Inspection Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Property Selection */}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-xs">Property *</Label>
              <Select
                value={formData.property_id}
                onValueChange={(v) => setFormData({...formData, property_id: v, unit_id: ''})}
              >
                <SelectTrigger className="h-7 text-xs">
                  <SelectValue placeholder="Select property..." />
                </SelectTrigger>
                <SelectContent>
                  {properties.map(p => (
                    <SelectItem key={p.id} value={p.id}>{p.display_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {isMultiFamily && (
              <div className="space-y-1">
                <Label className="text-xs">Unit</Label>
                <Select
                  value={formData.unit_id}
                  onValueChange={(v) => setFormData({...formData, unit_id: v})}
                >
                  <SelectTrigger className="h-7 text-xs">
                    <SelectValue placeholder="Select unit..." />
                  </SelectTrigger>
                  <SelectContent>
                    {propertyUnits.map(u => (
                      <SelectItem key={u.id} value={u.id}>Unit {u.unit_number}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>

          {/* Tenant Selection */}
          <div className="space-y-1">
            <Label className="text-xs">Tenant *</Label>
            <Select
              value={formData.tenant_name}
              onValueChange={(v) => setFormData({...formData, tenant_name: v})}
              disabled={!formData.property_id || availableTenants.length === 0}
            >
              <SelectTrigger className="h-7 text-xs">
                <SelectValue placeholder={!formData.property_id ? "Select property first" : availableTenants.length === 0 ? "No tenants found" : "Select tenant..."} />
              </SelectTrigger>
              <SelectContent>
                {availableTenants.map(t => (
                  <SelectItem key={t.id} value={`${t.first_name} ${t.last_name}`}>
                    {t.first_name} {t.last_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!formData.property_id && (
              <p className="text-xs text-gray-500 mt-1">Please select a property first</p>
            )}
          </div>

          {/* Inspection Header Info */}
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-xs">Inspection Type *</Label>
              <Select
                value={formData.walkthrough_type}
                onValueChange={(v: any) => setFormData({...formData, walkthrough_type: v})}
              >
                <SelectTrigger className="h-7 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="move_in">Move-In</SelectItem>
                  <SelectItem value="move_out">Move-Out</SelectItem>
                  <SelectItem value="periodic">Periodic</SelectItem>
                  <SelectItem value="maintenance">Maintenance</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label className="text-xs">Inspection Date *</Label>
              <Input
                type="date"
                value={formData.walkthrough_date}
                onChange={(e) => setFormData({...formData, walkthrough_date: e.target.value})}
                className="h-7 text-xs"
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label className="text-xs">Inspector Name</Label>
            <Input
              type="text"
              value={formData.inspector_name}
              onChange={(e) => setFormData({...formData, inspector_name: e.target.value})}
              placeholder="Sarah Pappas, Manager S&M Axios Heartland Holdings LLC"
              className="h-7 text-xs"
            />
          </div>

          <div className="space-y-1">
            <Label className="text-xs">General Notes</Label>
            <Textarea
              value={formData.notes}
              onChange={(e) => setFormData({...formData, notes: e.target.value})}
              placeholder="Additional notes about the inspection..."
              className="text-xs min-h-[60px]"
            />
          </div>
        </CardContent>
      </Card>

      {/* Areas Section */}
      <Card className="mt-4">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">
              Inspection Areas ({completedCount}/{areas.length} completed)
            </CardTitle>
            <div className="flex items-center gap-2">
              <Input
                placeholder="Add custom area..."
                value={newAreaName}
                onChange={(e) => setNewAreaName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addCustomArea()}
                className="h-7 text-xs w-40"
              />
              <Button size="sm" className="h-7 text-xs" onClick={addCustomArea}>
                Add
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {areas.map((area, index) => (
            <div key={index} className="border-2 border-gray-400 rounded-lg p-2.5 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 flex-1 flex-wrap">
                  <div className="flex items-center gap-1.5">
                    <Label className="text-xs whitespace-nowrap">Floor:</Label>
                    <Select
                      value={area.floor}
                      onValueChange={(v) => updateArea(index, { floor: v })}
                    >
                      <SelectTrigger className="h-7 text-xs w-28">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Basement">Basement</SelectItem>
                        <SelectItem value="Floor 1">Floor 1</SelectItem>
                        <SelectItem value="Floor 2">Floor 2</SelectItem>
                        <SelectItem value="Floor 3">Floor 3</SelectItem>
                        <SelectItem value="Attic">Attic</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Label className="text-xs whitespace-nowrap">Area Name:</Label>
                    <Input
                      value={area.area_name}
                      onChange={(e) => updateArea(index, { area_name: e.target.value })}
                      placeholder="Area name"
                      className="h-7 text-xs w-40"
                    />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Label className="text-xs whitespace-nowrap">Status:</Label>
                    <div className="flex gap-1">
                      {[
                        { value: 'no_issues', label: 'No Issues Noted', borderColor: 'border-blue-600', textColor: 'text-blue-600' },
                        { value: 'issue_noted_as_is', label: 'Issue Noted (As-Is)', borderColor: 'border-yellow-500', textColor: 'text-yellow-600' },
                        { value: 'issue_landlord_to_fix', label: 'Landlord to Fix', borderColor: 'border-orange-500', textColor: 'text-orange-600' }
                      ].map((option) => (
                        <Button
                          key={option.value}
                          variant="outline"
                          size="sm"
                          onClick={() => updateArea(index, {
                            inspection_status: option.value as AreaInspection['inspection_status']
                          })}
                          className={`h-7 text-xs px-2 ${
                            area.inspection_status === option.value
                              ? `${option.borderColor} ${option.textColor} border-2 font-medium`
                              : 'border-gray-300'
                          }`}
                        >
                          {option.label}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 p-0 text-red-600 hover:text-red-700 flex-shrink-0"
                  onClick={() => removeArea(index)}
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>

              <Textarea
                placeholder="Describe any damage, wear, or notable conditions..."
                value={area.notes}
                onChange={(e) => updateArea(index, { notes: e.target.value })}
                rows={2}
                className="text-xs min-h-[60px]"
              />


              {/* Note: Photos can only be added after saving */}
              {!area.id && (
                <div className="text-xs text-gray-500 italic pt-1.5 border-t">
                  Save inspection first to add photos
                </div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="mt-4 flex justify-end gap-2">
        <Link href="/leasing/inspections">
          <Button variant="outline" size="sm" className="h-7 text-xs">
            Cancel
          </Button>
        </Link>
        <Button
          size="sm"
          className="bg-black text-white hover:bg-gray-800 h-7 text-xs"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? (
            <>
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="h-3 w-3 mr-1" />
              Save Inspection
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

