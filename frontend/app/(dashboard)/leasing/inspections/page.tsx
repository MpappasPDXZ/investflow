'use client'

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { 
  ClipboardCheck, 
  Plus, 
  Camera, 
  Trash2, 
  ChevronDown, 
  ChevronUp,
  Home,
  User,
  Calendar,
  FileSignature,
  CheckCircle2
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

export default function InspectionsPage() {
  const { data: properties, isLoading: propertiesLoading } = useProperties()
  const { data: units } = useUnits()
  const { data: tenants } = useTenants()
  
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>('')
  const [selectedUnitId, setSelectedUnitId] = useState<string>('')
  const [selectedTenantId, setSelectedTenantId] = useState<string>('')
  const [inspectionType, setInspectionType] = useState<'move-in' | 'move-out' | ''>('')
  const [inspectionDate, setInspectionDate] = useState<string>(new Date().toISOString().split('T')[0])
  
  const [areas, setAreas] = useState<AreaInspection[]>([])
  const [newAreaName, setNewAreaName] = useState('')
  const [showAddArea, setShowAddArea] = useState(false)
  
  const [inspectionStarted, setInspectionStarted] = useState(false)

  const selectedProperty = properties?.properties?.find(p => p.id === selectedPropertyId)
  const propertyUnits = units?.units?.filter(u => u.property_id === selectedPropertyId) || []
  const isMultiFamily = selectedProperty?.property_type !== 'single_family'

  // Initialize areas when starting inspection
  const startInspection = () => {
    const initialAreas: AreaInspection[] = DEFAULT_AREAS.map((name, idx) => ({
      id: `area-${idx}`,
      name,
      condition: '',
      notes: '',
      photos: [],
      expanded: false
    }))
    setAreas(initialAreas)
    setInspectionStarted(true)
  }

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
    setShowAddArea(false)
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

  const completedCount = areas.filter(a => a.condition !== '').length

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <ClipboardCheck className="h-8 w-8 text-teal-600" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Property Inspection Checklist</h1>
          <p className="text-sm text-gray-500">Document property condition for move-in or move-out</p>
        </div>
      </div>

      {!inspectionStarted ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <FileSignature className="h-5 w-5" />
              New Inspection
            </CardTitle>
            <CardDescription>
              Select the property, tenant, and inspection type to begin
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Property Selection */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Home className="h-4 w-4" />
                  Property
                </Label>
                <Select value={selectedPropertyId} onValueChange={(v) => {
                  setSelectedPropertyId(v)
                  setSelectedUnitId('')
                }}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select property..." />
                  </SelectTrigger>
                  <SelectContent>
                    {properties?.properties?.map(p => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.display_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {isMultiFamily && (
                <div className="space-y-2">
                  <Label>Unit</Label>
                  <Select value={selectedUnitId} onValueChange={setSelectedUnitId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select unit..." />
                    </SelectTrigger>
                    <SelectContent>
                      {propertyUnits.map(u => (
                        <SelectItem key={u.id} value={u.id}>
                          Unit {u.unit_number}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <User className="h-4 w-4" />
                  Tenant
                </Label>
                <Select value={selectedTenantId} onValueChange={setSelectedTenantId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select tenant..." />
                  </SelectTrigger>
                  <SelectContent>
                    {tenants?.tenants?.map(t => (
                      <SelectItem key={t.id} value={t.id}>
                        {t.first_name} {t.last_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Inspection Type</Label>
                <Select value={inspectionType} onValueChange={(v: 'move-in' | 'move-out') => setInspectionType(v)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select type..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="move-in">Move-In Inspection</SelectItem>
                    <SelectItem value="move-out">Move-Out Inspection</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Calendar className="h-4 w-4" />
                  Date
                </Label>
                <Input 
                  type="date" 
                  value={inspectionDate}
                  onChange={(e) => setInspectionDate(e.target.value)}
                />
              </div>
            </div>

            <Separator />

            <div className="flex justify-end">
              <Button 
                onClick={startInspection}
                disabled={!selectedPropertyId || !selectedTenantId || !inspectionType}
                className="bg-teal-600 hover:bg-teal-700"
              >
                <ClipboardCheck className="h-4 w-4 mr-2" />
                Start Inspection
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {/* Header with progress */}
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <Badge variant={inspectionType === 'move-in' ? 'default' : 'secondary'} className="text-sm">
                    {inspectionType === 'move-in' ? 'Move-In' : 'Move-Out'} Inspection
                  </Badge>
                  <span className="text-sm text-gray-600">
                    {selectedProperty?.display_name}
                    {selectedUnitId && propertyUnits.find(u => u.id === selectedUnitId) && 
                      ` - Unit ${propertyUnits.find(u => u.id === selectedUnitId)?.unit_number}`
                    }
                  </span>
                  <span className="text-sm text-gray-400">|</span>
                  <span className="text-sm text-gray-600">{inspectionDate}</span>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-sm">
                    <span className="font-medium text-teal-600">{completedCount}</span>
                    <span className="text-gray-400"> / {areas.length} areas</span>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => setShowAddArea(true)}>
                    <Plus className="h-4 w-4 mr-1" />
                    Add Area
                  </Button>
                  <Button className="bg-teal-600 hover:bg-teal-700" size="sm">
                    <CheckCircle2 className="h-4 w-4 mr-1" />
                    Complete & Sign
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Add custom area */}
          {showAddArea && (
            <Card className="border-teal-200 bg-teal-50">
              <CardContent className="py-4">
                <div className="flex items-center gap-3">
                  <Input 
                    placeholder="Enter area name (e.g., Patio, Storage Room)..."
                    value={newAreaName}
                    onChange={(e) => setNewAreaName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && addCustomArea()}
                    className="flex-1"
                  />
                  <Button onClick={addCustomArea} size="sm">Add</Button>
                  <Button variant="ghost" size="sm" onClick={() => setShowAddArea(false)}>Cancel</Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Areas list */}
          <div className="space-y-2">
            {areas.map((area) => (
              <Card key={area.id} className={area.expanded ? 'ring-2 ring-teal-200' : ''}>
                <CardContent className="py-3">
                  {/* Collapsed view */}
                  <div 
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => toggleArea(area.id)}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-3 h-3 rounded-full ${getConditionColor(area.condition)}`} />
                      <span className="font-medium">{area.name}</span>
                      {area.notes && (
                        <Badge variant="outline" className="text-xs">Has notes</Badge>
                      )}
                      {area.photos.length > 0 && (
                        <Badge variant="outline" className="text-xs">
                          <Camera className="h-3 w-3 mr-1" />
                          {area.photos.length}
                        </Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {area.condition && (
                        <Badge className={`${getConditionColor(area.condition)} text-white capitalize`}>
                          {area.condition.replace('-', ' ')}
                        </Badge>
                      )}
                      {area.expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </div>
                  </div>

                  {/* Expanded view */}
                  {area.expanded && (
                    <div className="mt-4 pt-4 border-t space-y-4">
                      <div className="space-y-2">
                        <Label>Condition</Label>
                        <div className="flex gap-2 flex-wrap">
                          {['excellent', 'good', 'fair', 'poor', 'not-applicable'].map((cond) => (
                            <Button
                              key={cond}
                              variant={area.condition === cond ? 'default' : 'outline'}
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation()
                                updateArea(area.id, { condition: cond as AreaInspection['condition'] })
                              }}
                              className={area.condition === cond ? getConditionColor(cond) : ''}
                            >
                              {cond.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                            </Button>
                          ))}
                        </div>
                      </div>

                      <div className="space-y-2">
                        <Label>Notes</Label>
                        <Textarea 
                          placeholder="Describe any damage, wear, or notable conditions..."
                          value={area.notes}
                          onChange={(e) => updateArea(area.id, { notes: e.target.value })}
                          onClick={(e) => e.stopPropagation()}
                          rows={3}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>Photos</Label>
                        <div className="flex items-center gap-2">
                          <Button variant="outline" size="sm" onClick={(e) => e.stopPropagation()}>
                            <Camera className="h-4 w-4 mr-2" />
                            Add Photo
                          </Button>
                          <span className="text-xs text-gray-500">
                            {area.photos.length} photo(s) attached
                          </span>
                        </div>
                      </div>

                      <div className="flex justify-end">
                        <Button 
                          variant="ghost" 
                          size="sm" 
                          className="text-red-600 hover:text-red-700"
                          onClick={(e) => {
                            e.stopPropagation()
                            removeArea(area.id)
                          }}
                        >
                          <Trash2 className="h-4 w-4 mr-1" />
                          Remove Area
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

