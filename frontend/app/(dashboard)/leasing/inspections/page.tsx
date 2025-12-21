'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { 
  ClipboardCheck, 
  Plus, 
  Camera, 
  Trash2, 
  ChevronDown, 
  ChevronUp,
  Save,
  Maximize2,
  Minimize2,
  Edit,
  FileText,
  ArrowLeft,
  X
} from 'lucide-react'
import { useProperties } from '@/lib/hooks/use-properties'
import { useUnits } from '@/lib/hooks/use-units'
import { useTenants } from '@/lib/hooks/use-tenants'

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
]

interface AreaInspection {
  id: string
  name: string
  condition: 'excellent' | 'good' | 'fair' | 'poor' | 'not-applicable' | ''
  notes: string
  photos: string[]
  expanded: boolean
}

interface Inspection {
  id: string
  property_name: string
  unit_number?: string
  tenant_name: string
  type: 'walkthrough' | 'exit-checklist'
  date: string
  status: 'draft' | 'completed' | 'signed'
  areas_completed: number
  total_areas: number
}

// Mock data for demonstration
const MOCK_INSPECTIONS: Inspection[] = [
  {
    id: '1',
    property_name: '316 S 50th Ave',
    unit_number: '316 1/2',
    tenant_name: 'John Smith',
    type: 'walkthrough',
    date: '2025-01-15',
    status: 'completed',
    areas_completed: 20,
    total_areas: 20
  },
  {
    id: '2', 
    property_name: '1234 Oak Street',
    tenant_name: 'Jane Doe',
    type: 'exit-checklist',
    date: '2025-01-20',
    status: 'draft',
    areas_completed: 8,
    total_areas: 18
  }
]

export default function InspectionsPage() {
  const { data: propertiesData } = useProperties()
  const { data: unitsData } = useUnits()
  const { data: tenantsData } = useTenants()
  
  const properties = propertiesData?.items || []
  const units = unitsData?.units || []
  const tenantProfiles = tenantsData?.tenants || []
  
  // View state - like leases page
  const [isTableExpanded, setIsTableExpanded] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [currentInspectionId, setCurrentInspectionId] = useState<string | null>(null)
  
  // Expand states for 50/50 layout
  const [isFormExpanded, setIsFormExpanded] = useState(false)
  const [isPreviewExpanded, setIsPreviewExpanded] = useState(false)
  
  // Form state
  const [formData, setFormData] = useState({
    property_id: '',
    unit_id: '',
    tenant_id: '',
    type: '' as 'walkthrough' | 'exit-checklist' | '',
    date: new Date().toISOString().split('T')[0],
  })
  
  const [areas, setAreas] = useState<AreaInspection[]>([])
  const [newAreaName, setNewAreaName] = useState('')
  const [saving, setSaving] = useState(false)

  const selectedProperty = properties.find(p => p.id === formData.property_id)
  const propertyUnits = units.filter(u => u.property_id === formData.property_id)
  const isMultiFamily = selectedProperty?.property_type !== 'single_family'

  // Start new inspection
  const handleNewInspection = () => {
    setFormData({
      property_id: '',
      unit_id: '',
      tenant_id: '',
      type: '',
      date: new Date().toISOString().split('T')[0],
    })
    setAreas([])
    setCurrentInspectionId(null)
    setIsEditing(true)
    setIsTableExpanded(false)
  }

  // Edit existing inspection
  const handleEditInspection = (id: string) => {
    // TODO: Load from API
    const inspection = MOCK_INSPECTIONS.find(i => i.id === id)
    if (inspection) {
      setCurrentInspectionId(id)
      // Initialize with default areas for demo
      const initialAreas: AreaInspection[] = DEFAULT_AREAS.map((name, idx) => ({
        id: `area-${idx}`,
        name,
        condition: idx < inspection.areas_completed ? 'good' : '',
        notes: '',
        photos: [],
        expanded: false
      }))
      setAreas(initialAreas)
      setIsEditing(true)
      setIsTableExpanded(false)
    }
  }

  // Initialize areas when starting new inspection
  const initializeAreas = () => {
    if (formData.type && formData.property_id && areas.length === 0) {
      const initialAreas: AreaInspection[] = DEFAULT_AREAS.map((name, idx) => ({
        id: `area-${idx}`,
        name,
        condition: '',
        notes: '',
        photos: [],
        expanded: false
      }))
      setAreas(initialAreas)
    }
  }

  useEffect(() => {
    initializeAreas()
  }, [formData.type, formData.property_id])

  const addCustomArea = () => {
    if (!newAreaName.trim()) return
    const newArea: AreaInspection = {
      id: `area-custom-${Date.now()}`,
      name: newAreaName.trim(),
      condition: '',
      notes: '',
      photos: [],
      expanded: true
    }
    setAreas([...areas, newArea])
    setNewAreaName('')
  }

  const removeArea = (id: string) => {
    setAreas(areas.filter(a => a.id !== id))
  }

  const toggleArea = (id: string) => {
    setAreas(areas.map(a => a.id === id ? { ...a, expanded: !a.expanded } : a))
  }

  const updateArea = (id: string, updates: Partial<AreaInspection>) => {
    setAreas(areas.map(a => a.id === id ? { ...a, ...updates } : a))
  }

  const getConditionColor = (condition: string) => {
    switch (condition) {
      case 'excellent': return 'bg-green-500'
      case 'good': return 'bg-blue-500'
      case 'fair': return 'bg-yellow-500'
      case 'poor': return 'bg-red-500'
      case 'not-applicable': return 'bg-gray-400'
      default: return 'bg-gray-200'
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed': return <Badge className="bg-green-100 text-green-800">Completed</Badge>
      case 'signed': return <Badge className="bg-blue-100 text-blue-800">Signed</Badge>
      default: return <Badge variant="outline">Draft</Badge>
    }
  }

  const completedCount = areas.filter(a => a.condition !== '').length

  const handleSave = async () => {
    setSaving(true)
    // TODO: Save to backend
    await new Promise(resolve => setTimeout(resolve, 1000))
    setSaving(false)
  }

  const handleBack = () => {
    setIsEditing(false)
    setIsTableExpanded(true)
    setCurrentInspectionId(null)
  }

  return (
    <div className="p-8">
      {/* Header - Properties style */}
      <div className="mb-6 flex justify-between items-start">
        <div>
          <div className="text-xs text-gray-500 mb-1">Viewing:</div>
          <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <ClipboardCheck className="h-5 w-5" />
            Property Inspections
          </h1>
          <p className="text-sm text-gray-600 mt-1">Walkthroughs (move-in) and Exit Checklists (move-out)</p>
        </div>
        {!isEditing && (
          <Button 
            onClick={handleNewInspection}
            className="bg-black text-white hover:bg-gray-800 h-8 text-xs"
          >
            <Plus className="h-3 w-3 mr-1.5" />
            New Inspection
          </Button>
        )}
      </div>

      {/* Collapsible Table - Like Leases */}
      <Card className={`mb-4 ${!isTableExpanded ? 'cursor-pointer' : ''}`}>
        <CardHeader 
          className="py-3 cursor-pointer"
          onClick={() => !isEditing && setIsTableExpanded(!isTableExpanded)}
        >
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              All Inspections
              <Badge variant="outline" className="ml-2">{MOCK_INSPECTIONS.length}</Badge>
            </CardTitle>
            {isTableExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </div>
        </CardHeader>
        {isTableExpanded && (
          <CardContent>
            {MOCK_INSPECTIONS.length === 0 ? (
              <div className="text-center py-8 text-gray-500 text-sm">
                No inspections found. <button onClick={handleNewInspection} className="text-blue-600 hover:underline">Create your first inspection</button>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Property</TableHead>
                    <TableHead className="text-xs">Tenant</TableHead>
                    <TableHead className="text-xs">Type</TableHead>
                    <TableHead className="text-xs">Date</TableHead>
                    <TableHead className="text-xs">Progress</TableHead>
                    <TableHead className="text-xs">Status</TableHead>
                    <TableHead className="text-xs w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {MOCK_INSPECTIONS.map((inspection) => (
                    <TableRow key={inspection.id} className="text-xs">
                      <TableCell className="font-medium">
                        {inspection.property_name}
                        {inspection.unit_number && <span className="text-gray-500 ml-1">Unit {inspection.unit_number}</span>}
                      </TableCell>
                      <TableCell>{inspection.tenant_name}</TableCell>
                      <TableCell>
                        <Badge variant={inspection.type === 'walkthrough' ? 'default' : 'secondary'} className="text-xs">
                          {inspection.type === 'walkthrough' ? 'Walkthrough' : 'Exit Checklist'}
                        </Badge>
                      </TableCell>
                      <TableCell>{inspection.date}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 bg-gray-200 rounded-full">
                            <div 
                              className="h-full bg-teal-500 rounded-full" 
                              style={{ width: `${(inspection.areas_completed / inspection.total_areas) * 100}%` }}
                            />
                          </div>
                          <span className="text-gray-500">{inspection.areas_completed}/{inspection.total_areas}</span>
                        </div>
                      </TableCell>
                      <TableCell>{getStatusBadge(inspection.status)}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            className="h-7 w-7 p-0"
                            onClick={() => handleEditInspection(inspection.id)}
                          >
                            <Edit className="h-3 w-3" />
                          </Button>
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-red-600">
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        )}
      </Card>

      {/* Edit View - 50/50 Split like Leases */}
      {isEditing && (
        <div className="flex gap-4">
          {/* Left: Form */}
          {!isPreviewExpanded && (
            <Card className={`${isFormExpanded ? 'w-full' : 'w-1/2'}`}>
              <CardHeader className="py-3 border-b">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Button variant="ghost" size="sm" onClick={handleBack} className="h-7 w-7 p-0">
                      <ArrowLeft className="h-4 w-4" />
                    </Button>
                    <CardTitle className="text-sm font-bold">
                      {currentInspectionId ? 'Edit Inspection' : 'New Inspection'}
                    </CardTitle>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="h-7"
                      onClick={handleSave}
                      disabled={saving}
                    >
                      <Save className="h-3 w-3 mr-1" />
                      {saving ? 'Saving...' : 'Save'}
                    </Button>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-7 w-7 p-0"
                      onClick={() => setIsFormExpanded(!isFormExpanded)}
                    >
                      {isFormExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-4 max-h-[calc(100vh-280px)] overflow-y-auto">
                <div className="space-y-6">
                  {/* Basic Info */}
                  <div className="space-y-4">
                    <h3 className="text-xs font-bold uppercase text-gray-500">Inspection Details</h3>
                    
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs">Type</Label>
                        <Select 
                          value={formData.type} 
                          onValueChange={(v: 'walkthrough' | 'exit-checklist') => setFormData({...formData, type: v})}
                        >
                          <SelectTrigger className="h-8 text-xs">
                            <SelectValue placeholder="Select type..." />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="walkthrough">Walkthrough (Move-In)</SelectItem>
                            <SelectItem value="exit-checklist">Exit Checklist (Move-Out)</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-1">
                        <Label className="text-xs">Date</Label>
                        <Input 
                          type="date" 
                          value={formData.date}
                          onChange={(e) => setFormData({...formData, date: e.target.value})}
                          className="h-8 text-xs"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <Label className="text-xs">Property</Label>
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

                    <div className="space-y-1">
                      <Label className="text-xs">Tenant</Label>
                      <Select 
                        value={formData.tenant_id} 
                        onValueChange={(v) => setFormData({...formData, tenant_id: v})}
                      >
                        <SelectTrigger className="h-8 text-xs">
                          <SelectValue placeholder="Select tenant..." />
                        </SelectTrigger>
                        <SelectContent>
                          {tenantProfiles.map(t => (
                            <SelectItem key={t.id} value={t.id}>{t.first_name} {t.last_name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <Separator />

                  {/* Areas Section */}
                  {areas.length > 0 && (
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <h3 className="text-xs font-bold uppercase text-gray-500">
                          Inspection Areas ({completedCount}/{areas.length} completed)
                        </h3>
                        <div className="flex items-center gap-2">
                          <Input 
                            placeholder="Add custom area..."
                            value={newAreaName}
                            onChange={(e) => setNewAreaName(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && addCustomArea()}
                            className="h-7 text-xs w-40"
                          />
                          <Button size="sm" className="h-7 text-xs" onClick={addCustomArea}>
                            <Plus className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>

                      <div className="space-y-2">
                        {areas.map((area) => (
                          <div 
                            key={area.id} 
                            className={`border rounded-lg ${area.expanded ? 'ring-2 ring-teal-200' : ''}`}
                          >
                            {/* Collapsed header */}
                            <div 
                              className="flex items-center justify-between p-3 cursor-pointer"
                              onClick={() => toggleArea(area.id)}
                            >
                              <div className="flex items-center gap-3">
                                <div className={`w-2.5 h-2.5 rounded-full ${getConditionColor(area.condition)}`} />
                                <span className="text-sm font-medium">{area.name}</span>
                                {area.notes && <Badge variant="outline" className="text-xs">Notes</Badge>}
                                {area.photos.length > 0 && (
                                  <Badge variant="outline" className="text-xs">
                                    <Camera className="h-3 w-3 mr-1" />{area.photos.length}
                                  </Badge>
                                )}
                              </div>
                              <div className="flex items-center gap-2">
                                {area.condition && (
                                  <Badge className={`${getConditionColor(area.condition)} text-white text-xs capitalize`}>
                                    {area.condition.replace('-', ' ')}
                                  </Badge>
                                )}
                                {area.expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                              </div>
                            </div>

                            {/* Expanded content */}
                            {area.expanded && (
                              <div className="px-3 pb-3 pt-0 border-t space-y-3">
                                <div className="space-y-1 pt-3">
                                  <Label className="text-xs">Condition</Label>
                                  <div className="flex gap-1.5 flex-wrap">
                                    {['excellent', 'good', 'fair', 'poor', 'not-applicable'].map((cond) => (
                                      <Button
                                        key={cond}
                                        variant={area.condition === cond ? 'default' : 'outline'}
                                        size="sm"
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          updateArea(area.id, { condition: cond as AreaInspection['condition'] })
                                        }}
                                        className={`h-7 text-xs ${area.condition === cond ? getConditionColor(cond) : ''}`}
                                      >
                                        {cond.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                                      </Button>
                                    ))}
                                  </div>
                                </div>

                                <div className="space-y-1">
                                  <Label className="text-xs">Notes</Label>
                                  <Textarea 
                                    placeholder="Describe any damage, wear, or notable conditions..."
                                    value={area.notes}
                                    onChange={(e) => updateArea(area.id, { notes: e.target.value })}
                                    onClick={(e) => e.stopPropagation()}
                                    rows={2}
                                    className="text-xs"
                                  />
                                </div>

                                <div className="flex items-center justify-between">
                                  <Button variant="outline" size="sm" className="h-7 text-xs" onClick={(e) => e.stopPropagation()}>
                                    <Camera className="h-3 w-3 mr-1" />
                                    Add Photo
                                  </Button>
                                  <Button 
                                    variant="ghost" 
                                    size="sm" 
                                    className="h-7 text-xs text-red-600 hover:text-red-700"
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      removeArea(area.id)
                                    }}
                                  >
                                    <X className="h-3 w-3 mr-1" />
                                    Remove
                                  </Button>
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Right: Preview */}
          {!isFormExpanded && (
            <Card className={`${isPreviewExpanded ? 'w-full' : 'w-1/2'}`}>
              <CardHeader className="py-3 border-b">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-bold">Inspection Summary</CardTitle>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="h-7 w-7 p-0"
                    onClick={() => setIsPreviewExpanded(!isPreviewExpanded)}
                  >
                    {isPreviewExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="p-4 max-h-[calc(100vh-280px)] overflow-y-auto">
                {areas.length === 0 ? (
                  <div className="text-center py-12 text-gray-500">
                    <FileText className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                    <p className="text-sm">Select inspection type and property to begin</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* Progress */}
                    <div className="p-4 bg-gray-50 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium">Overall Progress</span>
                        <span className="text-sm text-gray-600">{completedCount} of {areas.length} areas</span>
                      </div>
                      <div className="w-full h-2 bg-gray-200 rounded-full">
                        <div 
                          className="h-full bg-teal-500 rounded-full transition-all"
                          style={{ width: `${(completedCount / areas.length) * 100}%` }}
                        />
                      </div>
                    </div>

                    {/* Summary by condition */}
                    <div className="grid grid-cols-5 gap-2">
                      {['excellent', 'good', 'fair', 'poor', 'not-applicable'].map((cond) => {
                        const count = areas.filter(a => a.condition === cond).length
                        return (
                          <div key={cond} className="text-center p-2 rounded-lg border">
                            <div className={`w-3 h-3 rounded-full mx-auto mb-1 ${getConditionColor(cond)}`} />
                            <div className="text-lg font-bold">{count}</div>
                            <div className="text-xs text-gray-500 capitalize">{cond.replace('-', ' ')}</div>
                          </div>
                        )
                      })}
                    </div>

                    <Separator />

                    {/* Areas with notes */}
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase text-gray-500">Areas with Notes</h4>
                      {areas.filter(a => a.notes).length === 0 ? (
                        <p className="text-xs text-gray-400 italic">No notes recorded yet</p>
                      ) : (
                        areas.filter(a => a.notes).map(area => (
                          <div key={area.id} className="p-2 bg-gray-50 rounded text-xs">
                            <div className="font-medium flex items-center gap-2">
                              <div className={`w-2 h-2 rounded-full ${getConditionColor(area.condition)}`} />
                              {area.name}
                            </div>
                            <p className="text-gray-600 mt-1">{area.notes}</p>
                          </div>
                        ))
                      )}
                    </div>

                    <Separator />

                    {/* Signature section */}
                    <div className="space-y-3">
                      <h4 className="text-xs font-bold uppercase text-gray-500">Signatures</h4>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="border rounded-lg p-3 text-center">
                          <div className="text-xs text-gray-500 mb-2">Landlord Signature</div>
                          <div className="h-16 border-b border-dashed border-gray-300 mb-2" />
                          <Button variant="outline" size="sm" className="text-xs h-7">Sign</Button>
                        </div>
                        <div className="border rounded-lg p-3 text-center">
                          <div className="text-xs text-gray-500 mb-2">Tenant Signature</div>
                          <div className="h-16 border-b border-dashed border-gray-300 mb-2" />
                          <Button variant="outline" size="sm" className="text-xs h-7">Sign</Button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
