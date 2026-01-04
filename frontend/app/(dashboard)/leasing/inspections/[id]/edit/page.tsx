'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useQueryClient } from '@tanstack/react-query';
import { useWalkthrough, useWalkthroughs } from '@/lib/hooks/use-walkthroughs';
import { apiClient } from '@/lib/api-client';
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
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { 
  ClipboardCheck, 
  Camera, 
  Save,
  ArrowLeft,
  X,
  Loader2,
  FileText,
  Trash2
} from 'lucide-react';
import Link from 'next/link';
import type { WalkthroughArea, Walkthrough } from '@/lib/hooks/use-walkthroughs';

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

export default function InspectionEditPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const id = params.id as string;
  const { data: walkthrough, isLoading } = useWalkthrough(id);
  const { updateWalkthrough, uploadAreaPhoto, deleteAreaPhoto, generatePDF } = useWalkthroughs();
  
  const { data: propertiesData } = useProperties();
  const { data: unitsData } = useUnits(walkthrough?.property_id || '');
  const { data: tenantsData } = useTenants(
    walkthrough?.property_id ? { property_id: walkthrough.property_id } : undefined
  );
  
  const properties = propertiesData?.items || [];
  const units = unitsData?.items || [];
  const availableTenants = tenantsData?.tenants || [];
  
  const [saving, setSaving] = useState(false);
  const [generatingPDF, setGeneratingPDF] = useState(false);
  const [uploadingPhotos, setUploadingPhotos] = useState<{ [areaIndex: number]: boolean }>({});
  const [selectedPhoto, setSelectedPhoto] = useState<{ areaIndex: number; photoIndex: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    property_id: '',
    unit_id: '',
    tenant_name: '',
    walkthrough_type: 'move_in' as 'move_in' | 'move_out' | 'periodic' | 'maintenance',
    walkthrough_date: new Date().toISOString().split('T')[0],
    inspector_name: '',
    notes: '',
  });
  
  // Areas state - managed as array like pets/tenants
  const [areas, setAreas] = useState<AreaInspection[]>([]);
  const [newAreaName, setNewAreaName] = useState('');

  // Handle refresh parameter (from create page redirect)
  useEffect(() => {
    if (searchParams.get('refresh') === 'true') {
      queryClient.invalidateQueries({ queryKey: ['walkthrough', id] });
      router.replace(`/leasing/inspections/${id}/edit`, { scroll: false });
    }
  }, [searchParams, queryClient, router, id]);

  // Initialize form from walkthrough data
  useEffect(() => {
    if (walkthrough) {
      setFormData({
        property_id: walkthrough.property_id,
        unit_id: walkthrough.unit_id || '',
        tenant_name: walkthrough.tenant_name || '',
        walkthrough_type: walkthrough.walkthrough_type || 'move_in',
        walkthrough_date: walkthrough.walkthrough_date ? new Date(walkthrough.walkthrough_date).toISOString().split('T')[0] : new Date().toISOString().split('T')[0],
        inspector_name: walkthrough.inspector_name || 'Sarah Pappas, Manager S&M Axios Heartland Holdings LLC',
        notes: walkthrough.notes || '',
      });
      
      // Parse areas from areas_json (like pets/tenants)
      try {
        if (walkthrough.areas && Array.isArray(walkthrough.areas)) {
          const parsedAreas: AreaInspection[] = walkthrough.areas.map((area: WalkthroughArea) => ({
            id: area.id,
            floor: area.floor || 'Floor 1',
            area_name: area.area_name,
            inspection_status: area.inspection_status || '',
            notes: area.notes || '',
            photos: area.photos || [],
          }));
          setAreas(parsedAreas);
        }
      } catch (e) {
        console.error('Error parsing areas:', e);
        setAreas([]);
      }
    }
  }, [walkthrough]);

  // Initialize areas if empty and type/property selected
  useEffect(() => {
    if (formData.walkthrough_type && formData.property_id && areas.length === 0 && !walkthrough) {
      const initialAreas: AreaInspection[] = DEFAULT_AREAS.map((name) => ({
        floor: 'Floor 1',
        area_name: name,
        inspection_status: '',
        notes: '',
        photos: [],
      }));
      setAreas(initialAreas);
    }
  }, [formData.walkthrough_type, formData.property_id, walkthrough]);

  const selectedProperty = properties.find(p => p.id === formData.property_id);
  const propertyUnits = units.filter(u => u.property_id === formData.property_id);
  const isMultiFamily = selectedProperty?.property_type !== 'single_family';

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
      
      const updatedWalkthrough = await updateWalkthrough(id, walkthroughData);
      
      // Reload walkthrough to get updated area IDs (needed for photo uploads)
      await queryClient.invalidateQueries({ queryKey: ['walkthrough', id] });
      await queryClient.invalidateQueries({ queryKey: ['walkthroughs'] });
      
      // Update areas with IDs from the response
      if (updatedWalkthrough && updatedWalkthrough.areas) {
        const parsedAreas: AreaInspection[] = updatedWalkthrough.areas.map((area: WalkthroughArea) => ({
          id: area.id,
          floor: area.floor || 'Floor 1',
          area_name: area.area_name,
          inspection_status: area.inspection_status || '',
          notes: area.notes || '',
          landlord_fix_notes: area.landlord_fix_notes || '',
          photos: area.photos || [],
        }));
        setAreas(parsedAreas);
      }
      
      alert('Inspection saved successfully! You can now add photos to each area.');
    } catch (error: any) {
      console.error('Error saving inspection:', error);
      setError(error.message || 'Failed to save inspection');
      alert(error.message || 'Failed to save inspection');
    } finally {
      setSaving(false);
    }
  };

  const handleAddPhoto = async (areaIndex: number) => {
    const area = areas[areaIndex];
    
    // If area doesn't have an ID, save the inspection first
    if (!area.id) {
      try {
        // Save inspection first to get area IDs
        await handleSave();
        // Wait a moment for the save to complete
        await new Promise(resolve => setTimeout(resolve, 500));
        // Reload walkthrough to get updated areas with IDs
        await queryClient.invalidateQueries({ queryKey: ['walkthrough', id] });
        // Re-fetch to get updated areas with IDs
        const updatedWalkthrough = await apiClient.get<Walkthrough>(`/walkthroughs/${id}`);
        
        if (updatedWalkthrough?.areas) {
          const parsedAreas: AreaInspection[] = updatedWalkthrough.areas.map((area: WalkthroughArea) => ({
            id: area.id,
            floor: area.floor || 'Floor 1',
            area_name: area.area_name,
            inspection_status: area.inspection_status || '',
            notes: area.notes || '',
            photos: area.photos || [],
          }));
          setAreas(parsedAreas);
          
          // Find the area by name/index to get the new ID
          const updatedArea = parsedAreas[areaIndex];
          if (!updatedArea?.id) {
            alert('Please save the inspection first. The area needs to be saved before adding photos.');
            return;
          }
        } else {
          alert('Please save the inspection first. The area needs to be saved before adding photos.');
          return;
        }
      } catch (error: any) {
        console.error('Error saving inspection:', error);
        alert('Failed to save inspection. Please try again.');
        return;
      }
    }
    
    const currentArea = areas[areaIndex];
    if (!currentArea.id) {
      alert('Please save the inspection first before adding photos');
      return;
    }
    
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.multiple = true;
    input.onchange = async (e) => {
      const files = (e.target as HTMLInputElement).files;
      if (!files || files.length === 0) return;
      
      // Validate file sizes
      const invalidFiles = Array.from(files).filter(f => f.size > 10 * 1024 * 1024);
      if (invalidFiles.length > 0) {
        alert(`Some files are too large (max 10MB): ${invalidFiles.map(f => f.name).join(', ')}`);
        return;
      }
      
      try {
        // Set uploading state
        setUploadingPhotos(prev => ({ ...prev, [areaIndex]: true }));
        
        // First, save the inspection with current notes to ensure all text changes are saved
        // This can take ~17s, so we notify the user
        await handleSave();
        
        // Then upload all photos
        const uploadPromises = Array.from(files).map(async (file, fileIndex) => {
          const photoOrder = (currentArea.photos?.length || 0) + fileIndex + 1;
          return await uploadAreaPhoto(id, currentArea.id!, file, undefined, photoOrder);
        });
        
        const uploadedPhotos = await Promise.all(uploadPromises);
        
        // Update local state with uploaded photos
        updateArea(areaIndex, {
          photos: [...(currentArea.photos || []), ...uploadedPhotos.map(photo => ({
            photo_blob_name: photo.photo_blob_name,
            photo_url: photo.photo_url,
            notes: photo.notes,
            order: photo.order,
            document_id: photo.document_id
          }))]
        });
        
        // Reload walkthrough to get updated data
        await queryClient.invalidateQueries({ queryKey: ['walkthrough', id] });
      } catch (error: any) {
        console.error('Error uploading photos:', error);
        alert(error.message || 'Failed to upload photos');
      } finally {
        // Clear uploading state
        setUploadingPhotos(prev => {
          const newState = { ...prev };
          delete newState[areaIndex];
          return newState;
        });
      }
    };
    input.click();
  };

  const handleDeletePhoto = async (areaIndex: number, photoIndex: number) => {
    const area = areas[areaIndex];
    const photo = area.photos?.[photoIndex];
    
    if (!area.id || !photo?.document_id) {
      alert('Cannot delete photo: missing area ID or document ID');
      return;
    }
    
    if (!confirm('Are you sure you want to delete this photo?')) {
      return;
    }
    
    try {
      await deleteAreaPhoto(id, area.id, photo.document_id);
      
      // Update local state
      const updatedPhotos = [...(area.photos || [])];
      updatedPhotos.splice(photoIndex, 1);
      updateArea(areaIndex, { photos: updatedPhotos });
      
      // Clear selection
      setSelectedPhoto(null);
      
      // Reload walkthrough to get updated data
      await queryClient.invalidateQueries({ queryKey: ['walkthrough', id] });
    } catch (error: any) {
      console.error('Error deleting photo:', error);
      alert(error.message || 'Failed to delete photo');
    }
  };

  const handleGeneratePDF = async () => {
    setGeneratingPDF(true);
    try {
      // "Generating..." message includes photo loading
      const result = await generatePDF(id, false);
      if (result.pdf_url) {
        window.open(result.pdf_url, '_blank');
      }
      alert('PDF generated successfully!');
    } catch (error: any) {
      console.error('Error generating PDF:', error);
      alert(error.message || 'Failed to generate PDF');
    } finally {
      setGeneratingPDF(false);
    }
  };

  const completedCount = areas.filter(a => a.inspection_status !== '').length;

  if (isLoading) {
    return <div className="p-6">Loading...</div>;
  }

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
            Edit Inspection
          </h1>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            className="h-7 text-xs px-3"
            onClick={handleGeneratePDF}
            disabled={generatingPDF || saving || Object.keys(uploadingPhotos).length > 0}
            title={
              saving 
                ? "Please wait for save to complete" 
                : Object.keys(uploadingPhotos).length > 0 
                  ? "Please wait for photos to finish uploading" 
                  : undefined
            }
          >
            {generatingPDF ? (
              <>
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                Generating (loading photos)...
              </>
            ) : (
              <>
                <FileText className="h-3 w-3 mr-1" />
                Generate Inspection
              </>
            )}
          </Button>
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
                <SelectTrigger className="h-8 text-xs">
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
                  <SelectTrigger className="h-8 text-xs">
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
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder={!formData.property_id ? "Select property first" : availableTenants.length === 0 ? "No tenants found" : "Select tenant..."} />
              </SelectTrigger>
              <SelectContent>
                {availableTenants.map(t => (
                  <SelectItem key={t.id} value={`${t.first_name} ${t.last_name}`}>
                    {t.first_name} {t.last_name}
                  </SelectItem>
                ))}
                {/* Include existing tenant_name if it doesn't match any tenant in the list */}
                {formData.tenant_name && !availableTenants.some(t => `${t.first_name} ${t.last_name}` === formData.tenant_name) && (
                  <SelectItem value={formData.tenant_name}>
                    {formData.tenant_name}
                  </SelectItem>
                )}
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


              {/* Photos Section - Always show camera icon */}
              <div className="space-y-1.5 pt-1.5 border-t">
                <div className="flex items-center justify-between">
                  <Label className="text-xs">Photos ({area.photos?.length || 0})</Label>
                  <div className="flex items-center gap-2">
                    {selectedPhoto && selectedPhoto.areaIndex === index && area.id && (
                      <Button 
                        variant="destructive" 
                        size="sm" 
                        className="h-7 text-xs" 
                        onClick={() => handleDeletePhoto(index, selectedPhoto.photoIndex)}
                      >
                        <Trash2 className="h-3 w-3 mr-1" />
                        Delete Photo
                      </Button>
                    )}
                    {area.id ? (
                      <Button 
                        variant="outline" 
                        size="sm" 
                        className="h-7 text-xs" 
                        onClick={() => {
                          setSelectedPhoto(null);
                          handleAddPhoto(index);
                        }}
                        disabled={uploadingPhotos[index]}
                      >
                        {uploadingPhotos[index] ? (
                          <>
                            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                            Uploading...
                          </>
                        ) : (
                          <>
                            <Camera className="h-3 w-3 mr-1" />
                            Add Photo
                          </>
                        )}
                      </Button>
                    ) : (
                      <div className="relative group">
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="h-7 text-xs" 
                          disabled
                        >
                          <Camera className="h-3 w-3 mr-1" />
                          Add Photo
                        </Button>
                        <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 group-hover:opacity-100 pointer-events-none whitespace-nowrap z-10">
                          Save Area First
                        </div>
                      </div>
                    )}
                  </div>
                </div>
                {area.photos && area.photos.length > 0 && (
                  <div className="grid grid-cols-4 gap-1.5">
                    {area.photos.map((photo, photoIndex) => (
                      <div 
                        key={photoIndex} 
                        className={`relative group cursor-pointer ${
                          selectedPhoto?.areaIndex === index && selectedPhoto?.photoIndex === photoIndex
                            ? 'ring-2 ring-blue-500 ring-offset-1'
                            : ''
                        }`}
                        onClick={() => {
                          if (area.id) {
                            setSelectedPhoto({ areaIndex: index, photoIndex });
                          }
                        }}
                      >
                        {photo.photo_url && (
                          <img 
                            src={photo.photo_url} 
                            alt={`Photo ${photoIndex + 1}`}
                            className="w-full h-16 object-cover rounded border"
                          />
                        )}
                        {selectedPhoto?.areaIndex === index && selectedPhoto?.photoIndex === photoIndex && (
                          <div className="absolute inset-0 bg-blue-500/20 flex items-center justify-center">
                            <div className="bg-white rounded-full p-1">
                              <Trash2 className="h-4 w-4 text-red-600" />
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
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

