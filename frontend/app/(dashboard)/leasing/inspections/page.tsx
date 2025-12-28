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
  X,
  Loader2
} from 'lucide-react'
import { useProperties } from '@/lib/hooks/use-properties'
import { useUnits } from '@/lib/hooks/use-units'
import { useTenants } from '@/lib/hooks/use-tenants'
import { useWalkthroughs, useWalkthroughsList, WalkthroughArea } from '@/lib/hooks/use-walkthroughs'

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
  floor?: string
  inspection_status: 'no_issues' | 'issue_noted_as_is' | 'issue_landlord_to_fix' | ''
  notes: string  // General notes (available for all statuses)
  landlord_fix_notes: string  // Required for issue_landlord_to_fix
  photos: Array<{ photo_blob_name?: string; photo_url?: string; notes?: string; order: number; document_id?: string }>
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
  // Only load walkthroughs on initial page load - ONE API CALL
  const { data: walkthroughsData } = useWalkthroughsList()
  const { createWalkthrough, updateWalkthrough, getWalkthrough, generatePDF, uploadAreaPhoto, deleteWalkthrough } = useWalkthroughs()
  
  // Load properties and tenants ONLY when editing (lazy load)
  const [shouldLoadProperties, setShouldLoadProperties] = useState(false)
  const [shouldLoadTenants, setShouldLoadTenants] = useState(false)
  
  // Conditionally fetch properties and tenants - disabled by default
  const propertiesQueryOptions = shouldLoadProperties ? undefined : { enabled: false } as { enabled?: boolean } | undefined
  const tenantsQueryOptions = shouldLoadTenants ? undefined : { enabled: false } as { enabled?: boolean } | undefined
  const { data: propertiesData } = useProperties(propertiesQueryOptions)
  const { data: tenantsData } = useTenants(tenantsQueryOptions)
  
  const properties = propertiesData?.items || []
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
    inspector_name: '',
    notes: '',
  })
  
  const [areas, setAreas] = useState<AreaInspection[]>([])
  const [newAreaName, setNewAreaName] = useState('')
  const [saving, setSaving] = useState(false)
  const [generatingPDF, setGeneratingPDF] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)

  // Load units only when property_id is selected
  const { data: unitsData } = useUnits(formData.property_id || undefined)
  
  const units = unitsData?.items || []
  const walkthroughs = walkthroughsData?.items || []

  const selectedProperty = properties.find(p => p.id === formData.property_id)
  const propertyUnits = units.filter(u => u.property_id === formData.property_id)
  const isMultiFamily = selectedProperty?.property_type !== 'single_family'

  // Start new inspection
  const handleNewInspection = () => {
    // Load properties and tenants when starting to edit
    setShouldLoadProperties(true)
    setShouldLoadTenants(true)
      setFormData({
        property_id: '',
        unit_id: '',
        tenant_id: '',
        type: '',
        date: new Date().toISOString().split('T')[0],
        inspector_name: '',
        notes: '',
      })
    setAreas([])
    setCurrentInspectionId(null)
    setIsEditing(true)
    setIsTableExpanded(false)
  }

  // Edit existing inspection
  const handleEditInspection = async (id: string) => {
    // Load properties and tenants when editing
    setShouldLoadProperties(true)
    setShouldLoadTenants(true)
    try {
      const walkthrough = await getWalkthrough(id)
      setCurrentInspectionId(id)
      
      // Find tenant by matching tenant_name
      let matchedTenantId = ''
      if (walkthrough.tenant_name && tenantProfiles.length > 0) {
        const tenantName = walkthrough.tenant_name.trim()
        const tenantNameParts = tenantName.split(/\s+/)
        const matchedTenant = tenantProfiles.find(t => {
          const tenantFullName = `${t.first_name} ${t.last_name}`.trim().toLowerCase()
          const walkthroughFullName = tenantName.toLowerCase()
          
          // Try exact match first
          if (tenantFullName === walkthroughFullName) {
            return true
          }
          
          // Try matching first and last name separately
          if (tenantNameParts.length >= 2) {
            const firstName = tenantNameParts[0].toLowerCase()
            const lastName = tenantNameParts.slice(1).join(' ').toLowerCase()
            return t.first_name.toLowerCase() === firstName && 
                   t.last_name.toLowerCase() === lastName
          }
          
          return false
        })
        
        if (matchedTenant) {
          matchedTenantId = matchedTenant.id
        }
      }
      
      // Set form data
      setFormData({
        property_id: walkthrough.property_id,
        unit_id: walkthrough.unit_id || '',
        tenant_id: matchedTenantId,
        type: walkthrough.walkthrough_type === 'move_in' ? 'walkthrough' : 'exit-checklist',
        date: walkthrough.walkthrough_date,
        inspector_name: walkthrough.inspector_name || '',
        notes: walkthrough.notes || '',
      })
      
      // Convert areas from API format to local format
      const initialAreas: AreaInspection[] = walkthrough.areas.map((area: WalkthroughArea) => ({
        id: area.id || crypto.randomUUID(),
        name: area.area_name,
        floor: area.floor,
        inspection_status: area.inspection_status || '',
        notes: area.notes || '',
        landlord_fix_notes: area.landlord_fix_notes || '',
        photos: area.photos || [],
        expanded: false
      }))
      
      setAreas(initialAreas)
      setIsEditing(true)
      setIsTableExpanded(false)
    } catch (error) {
      console.error('Error loading walkthrough:', error)
      alert('Failed to load inspection')
    }
  }
  
  // Reload walkthrough data after save to get updated areas with IDs
  const reloadWalkthroughData = async (walkthroughId: string) => {
    try {
      const walkthrough = await getWalkthrough(walkthroughId)
      
      // Create a map of server areas by name+floor for matching
      const serverAreasMap = new Map(
        walkthrough.areas.map((area: WalkthroughArea) => [
          `${area.area_name}|${area.floor}`,
          area
        ])
      )
      
      // Update existing areas with server IDs, preserving areas without status
      const updatedAreas: AreaInspection[] = areas.map((localArea) => {
        const key = `${localArea.name}|${localArea.floor || 'Floor 1'}`
        const serverArea = serverAreasMap.get(key)
        
        if (serverArea) {
          // Area exists on server - use server ID and merge data
          return {
            id: serverArea.id || localArea.id, // Use server ID
            name: serverArea.area_name,
            floor: serverArea.floor,
            inspection_status: serverArea.inspection_status || localArea.inspection_status || '',
            notes: serverArea.notes || localArea.notes || '',
            landlord_fix_notes: serverArea.landlord_fix_notes || localArea.landlord_fix_notes || '',
            photos: serverArea.photos || localArea.photos || [],
            expanded: localArea.expanded || false
          }
        } else {
          // Area not on server yet (no inspection status) - keep local data
          return localArea
        }
      })
      
      // Add any server areas that don't exist locally (shouldn't happen, but just in case)
      walkthrough.areas.forEach((serverArea: WalkthroughArea) => {
        const key = `${serverArea.area_name}|${serverArea.floor}`
        const exists = updatedAreas.some(a => `${a.name}|${a.floor || 'Floor 1'}` === key)
        if (!exists) {
          updatedAreas.push({
            id: serverArea.id || crypto.randomUUID(),
            name: serverArea.area_name,
            floor: serverArea.floor,
            inspection_status: serverArea.inspection_status || '',
            notes: serverArea.notes || '',
            landlord_fix_notes: serverArea.landlord_fix_notes || '',
            photos: serverArea.photos || [],
            expanded: false
          })
        }
      })
      
      setAreas(updatedAreas)
      console.log('✅ Reloaded walkthrough with area IDs:', updatedAreas.map(a => ({ id: a.id, name: a.name, hasStatus: !!a.inspection_status })))
    } catch (error) {
      console.error('Error reloading walkthrough:', error)
    }
  }

  // Initialize areas when starting new inspection
  const initializeAreas = () => {
    if (formData.type && formData.property_id && areas.length === 0) {
      const initialAreas: AreaInspection[] = DEFAULT_AREAS.map((name, idx) => ({
        id: crypto.randomUUID(),
        name,
        floor: 'Floor 1', // Default floor
        inspection_status: '',
        notes: '',
        landlord_fix_notes: '',
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
      id: crypto.randomUUID(),
      name: newAreaName.trim(),
      floor: 'Floor 1', // Default floor
      inspection_status: '',
      notes: '',
      landlord_fix_notes: '',
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'no_issues': return 'bg-green-500'
      case 'issue_noted_as_is': return 'bg-yellow-500'
      case 'issue_landlord_to_fix': return 'bg-orange-500'
      default: return 'bg-gray-200'
    }
  }
  
  const getStatusBadgeStyle = (status: string) => {
    switch (status) {
      case 'no_issues': return 'border border-green-400 text-green-700 bg-transparent'
      case 'issue_noted_as_is': return 'border border-yellow-400 text-yellow-700 bg-transparent'
      case 'issue_landlord_to_fix': return 'border border-orange-400 text-orange-700 bg-transparent'
      default: return 'border border-gray-300 text-gray-500 bg-transparent'
    }
  }
  
  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'no_issues': return 'No Issues Noted'
      case 'issue_noted_as_is': return 'Issue Noted (As-Is)'
      case 'issue_landlord_to_fix': return 'Landlord to Fix'
      default: return 'Not Inspected'
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed': return <Badge className="bg-green-100 text-green-800">Completed</Badge>
      case 'signed': return <Badge className="bg-blue-100 text-blue-800">Signed</Badge>
      default: return <Badge variant="outline">Draft</Badge>
    }
  }

  const completedCount = areas.filter(a => a.inspection_status !== '').length
  
  // Validation: Check if all "landlord to fix" areas have fix notes
  const canSign = () => {
    const landlordToFixAreas = areas.filter(
      a => a.inspection_status === 'issue_landlord_to_fix'
    )
    return landlordToFixAreas.every(
      a => a.landlord_fix_notes && a.landlord_fix_notes.trim().length > 0
    )
  }
  
  const validCount = areas.filter(a => {
    if (a.inspection_status === '') return false
    if (a.inspection_status === 'issue_landlord_to_fix') {
      return a.landlord_fix_notes && a.landlord_fix_notes.trim().length > 0
    }
    return true
  }).length

  const handleSave = async (requireComplete: boolean = false) => {
    // Validation
    if (!formData.property_id) {
      alert('Please select a property')
      return
    }
    
    if (!formData.type) {
      alert('Please select an inspection type')
      return
    }
    
    if (areas.length === 0) {
      alert('Please add at least one inspection area')
      return
    }
    
    // Only require completion if explicitly requested (e.g., for finalizing/signing)
    // Otherwise allow saving drafts with incomplete areas so photos can be uploaded
    if (requireComplete) {
      // Check if all areas have inspection status
      const incompleteAreas = areas.filter(a => !a.inspection_status)
      if (incompleteAreas.length > 0) {
        alert(`Please complete inspection status for all areas. ${incompleteAreas.length} area(s) remaining.`)
        return
      }
      
      // Check if all "landlord to fix" areas have fix notes
      if (!canSign()) {
        alert('All "Landlord to Fix" items must have fix notes before finalizing')
        return
      }
    } else {
      // For draft saves, allow saving even without fix notes - user can add them later
      // No validation needed for draft saves
    }
    
    setSaving(true)
    try {
      const tenant = tenantProfiles.find(t => t.id === formData.tenant_id)
      const tenantName = tenant ? `${tenant.first_name} ${tenant.last_name}` : ''
      
      // Filter to only areas with inspection status (for draft saves, incomplete areas are excluded)
      const areasWithStatus = areas.filter(a => a.inspection_status)
      
      if (areasWithStatus.length === 0) {
        alert('Please set inspection status for at least one area before saving')
        setSaving(false)
        return
      }
      
      const walkthroughData = {
        property_id: formData.property_id,
        unit_id: formData.unit_id || undefined,
        walkthrough_type: (formData.type === 'walkthrough' ? 'move_in' : 'move_out') as 'move_in' | 'move_out' | 'periodic' | 'maintenance',
        walkthrough_date: formData.date,
        inspector_name: formData.inspector_name || undefined, // Will default to "Sarah Pappas, Member S&M Axios Heartland Holdings LLC" on backend if empty
        tenant_name: tenantName,
        notes: formData.notes || undefined,
        areas: areasWithStatus.map(a => ({
          floor: a.floor || 'Floor 1',
          area_name: a.name,
          inspection_status: a.inspection_status as 'no_issues' | 'issue_noted_as_is' | 'issue_landlord_to_fix',
          notes: a.notes || undefined,
          landlord_fix_notes: a.landlord_fix_notes || undefined,
          issues: []
        }))
      }
      
      console.log('💾 [INSPECTION] Saving walkthrough data:', JSON.stringify(walkthroughData, null, 2))
      
      let savedWalkthrough
      if (currentInspectionId) {
        // Update existing
        savedWalkthrough = await updateWalkthrough(currentInspectionId, walkthroughData)
      } else {
        // Create new
        savedWalkthrough = await createWalkthrough(walkthroughData)
      }
      
      // Set the walkthrough ID so photos can be uploaded
      setCurrentInspectionId(savedWalkthrough.id)
      
      // Reload walkthrough to get area IDs from server
      await reloadWalkthroughData(savedWalkthrough.id)
      
      const incompleteCount = areas.filter(a => !a.inspection_status).length
      if (incompleteCount > 0) {
        alert(`Draft saved! ${incompleteCount} area(s) still need inspection status. You can now upload photos for completed areas.`)
      } else {
        alert('Inspection saved successfully! You can now upload photos for each area.')
      }
    } catch (error: any) {
      console.error('Error saving inspection:', error)
      alert(error.message || 'Failed to save inspection. Please try again.')
    } finally {
      setSaving(false)
    }
  }
  
  const handleAddPhoto = async (areaId: string) => {
    if (!currentInspectionId) {
      alert('Please save the inspection first before adding photos')
      return
    }
    
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    input.multiple = true // Allow multiple file selection
    input.onchange = async (e) => {
      const files = (e.target as HTMLInputElement).files
      if (!files || files.length === 0) return
      
      const area = areas.find(a => a.id === areaId)
      if (!area) {
        console.error('Area not found:', areaId, 'Available areas:', areas.map(a => ({ id: a.id, name: a.name })))
        alert('Area not found. Please try saving the inspection again.')
        return
      }
      
      // Validate all files
      const invalidFiles = Array.from(files).filter(f => f.size > 10 * 1024 * 1024)
      if (invalidFiles.length > 0) {
        alert(`Some files are too large (max 10MB): ${invalidFiles.map(f => f.name).join(', ')}`)
        return
      }
      
      try {
        console.log(`📷 Uploading ${files.length} photo(s) to area:`, { areaId, areaName: area.name, walkthroughId: currentInspectionId })
        
        // Upload all photos
        const uploadPromises = Array.from(files).map(async (file, index) => {
          const photoOrder = (area.photos?.length || 0) + index + 1
          return await uploadAreaPhoto(currentInspectionId, areaId, file, undefined, photoOrder)
        })
        
        const uploadedPhotos = await Promise.all(uploadPromises)
        
        // Update local state with all uploaded photos (preserve document_id)
        updateArea(areaId, {
          photos: [...(area.photos || []), ...uploadedPhotos.map(photo => ({
            photo_blob_name: photo.photo_blob_name,
            photo_url: photo.photo_url,
            notes: photo.notes,
            order: photo.order,
            document_id: photo.document_id
          }))]
        })
        
        alert(`Successfully uploaded ${uploadedPhotos.length} photo(s) to ${area.name}!`)
      } catch (error: any) {
        console.error('Error uploading photos:', error)
        alert(error.message || 'Failed to upload photos')
      }
    }
    input.click()
  }

  const handleBack = () => {
    setIsEditing(false)
    setIsTableExpanded(true)
    setCurrentInspectionId(null)
  }

  const handleDeleteInspection = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    
    if (!confirm('Are you sure you want to delete this inspection? This action cannot be undone.')) {
      return
    }
    
    setDeleting(id)
    try {
      await deleteWalkthrough(id)
      // If we're currently editing this inspection, go back to table
      if (currentInspectionId === id) {
        handleBack()
      }
    } catch (error: any) {
      console.error('Error deleting inspection:', error)
      alert(error.message || 'Failed to delete inspection')
    } finally {
      setDeleting(null)
    }
  }

  const handleGeneratePDF = async () => {
    if (!currentInspectionId) {
      alert('Please save the inspection first before generating PDF')
      return
    }
    
    setGeneratingPDF(true)
    try {
      const result = await generatePDF(currentInspectionId, true)
      if (result.pdf_url) {
        window.open(result.pdf_url, '_blank')
      }
      alert('PDF generated successfully!')
    } catch (error: any) {
      console.error('Error generating PDF:', error)
      alert(error.message || 'Failed to generate PDF')
    } finally {
      setGeneratingPDF(false)
    }
  }

  return (
    <div className="p-6 h-[calc(100vh-48px)] flex flex-col">
      {/* ========== COLLAPSIBLE INSPECTIONS TABLE HEADER ========== */}
      {/* When editing, show minimal header bar; when not editing, show full table */}
      {isEditing ? (
        /* Minimal header when editing - just shows Back to Table button */
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold text-gray-700">
              {currentInspectionId ? 'Editing Inspection' : 'New Inspection'}
            </h2>
            {selectedProperty && (
              <Badge variant="secondary" className="text-xs">
                {selectedProperty.display_name}
              </Badge>
            )}
          </div>
          <Button
            onClick={handleBack}
            variant="outline"
            size="sm"
            className="h-8 text-xs px-3"
          >
            <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
            Back to Table
          </Button>
        </div>
      ) : (
        /* Full table when not editing */
        <Card className={`mb-4 transition-all duration-200 ${isTableExpanded ? '' : 'pb-0'}`}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 py-3">
            <div className="flex items-center gap-3">
              <CardTitle className="text-sm font-bold">All Inspections</CardTitle>
              <Badge variant="secondary" className="text-xs">
                {walkthroughs.length} inspection{walkthroughs.length !== 1 ? 's' : ''}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <Button
                onClick={handleNewInspection}
                className="bg-black hover:bg-gray-800 text-white h-8 text-xs px-3"
              >
                <Plus className="h-3 w-3 mr-1.5" />
                New Inspection
              </Button>
              <Button
                onClick={() => setIsTableExpanded(!isTableExpanded)}
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
              >
                {isTableExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
              </Button>
            </div>
          </CardHeader>
          
          {isTableExpanded && (
            <CardContent className="pt-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Property</TableHead>
                    <TableHead className="text-xs">Tenant</TableHead>
                    <TableHead className="text-xs">Type</TableHead>
                    <TableHead className="text-xs">Date</TableHead>
                    <TableHead className="text-xs">Progress</TableHead>
                    <TableHead className="text-xs">Status</TableHead>
                    <TableHead className="text-xs text-right w-24">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {walkthroughs.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-8 text-gray-500 text-sm">
                        No inspections yet. Click "New Inspection" to create one.
                      </TableCell>
                    </TableRow>
                  ) : (
                    walkthroughs.map((inspection) => {
                      // Use simplified data - no property lookup needed
                      const totalAreas = inspection.areas_count || 0
                      return (
                        <TableRow 
                          key={inspection.id} 
                          className={`cursor-pointer hover:bg-gray-50 text-xs ${currentInspectionId === inspection.id ? 'bg-blue-50' : ''}`}
                          onClick={() => handleEditInspection(inspection.id)}
                        >
                          <TableCell className="font-medium">
                            {inspection.property_id}
                            {inspection.unit_id && (
                              <span className="text-gray-500 ml-1">Unit {inspection.unit_id.substring(0, 8)}</span>
                            )}
                          </TableCell>
                          <TableCell>{inspection.tenant_name || 'N/A'}</TableCell>
                          <TableCell>
                            <Badge variant={inspection.walkthrough_type === 'move_in' ? 'default' : 'secondary'} className="text-xs">
                              {inspection.walkthrough_type === 'move_in' ? 'Walkthrough' : 'Exit Checklist'}
                            </Badge>
                          </TableCell>
                          <TableCell>{inspection.walkthrough_date}</TableCell>
                          <TableCell>
                            <span className="text-gray-500">{totalAreas} area{totalAreas !== 1 ? 's' : ''}</span>
                          </TableCell>
                          <TableCell>{getStatusBadge(inspection.status)}</TableCell>
                          <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                            <div className="flex justify-end gap-1">
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                className="h-7 w-7 p-0"
                                onClick={() => handleEditInspection(inspection.id)}
                                title="Edit"
                              >
                                <Edit className="h-3.5 w-3.5" />
                              </Button>
                              {inspection.pdf_url && (
                                <Button 
                                  variant="ghost" 
                                  size="sm" 
                                  className="h-7 w-7 p-0"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    window.open(inspection.pdf_url, '_blank')
                                  }}
                                  title="Download PDF"
                                >
                                  <FileText className="h-3.5 w-3.5" />
                                </Button>
                              )}
                              <Button 
                                variant="ghost" 
                                size="sm" 
                                className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                                onClick={(e) => handleDeleteInspection(inspection.id, e)}
                                disabled={deleting === inspection.id}
                                title="Delete"
                              >
                                {deleting === inspection.id ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <Trash2 className="h-3.5 w-3.5" />
                                )}
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      )
                    })
                  )}
                </TableBody>
              </Table>
            </CardContent>
          )}
        </Card>
      )}

      {/* ========== 50/50 SPLIT: INSPECTION FORM + PREVIEW ========== */}
      {isEditing && (
        <div className={`flex-1 grid gap-4 min-h-0 ${isPreviewExpanded || isFormExpanded ? 'grid-cols-1' : 'grid-cols-2'}`}>
          {/* LEFT: Inspection Form (50%) - Hidden when Preview is expanded */}
          {!isPreviewExpanded && (
            <div className="flex flex-col min-h-0" style={{ width: '100%' }}>
              <Card className="flex-1 flex flex-col min-h-0">
                <CardHeader className="py-2 border-b flex-shrink-0 flex flex-row items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CardTitle className="text-sm font-bold">
                      {currentInspectionId ? 'Edit Inspection' : 'New Inspection'}
                    </CardTitle>
                    {isFormExpanded && (
                      <Badge variant="secondary" className="text-xs">Expanded</Badge>
                    )}
                  </div>
                  <div className="flex gap-1.5 items-center">
                    <Button 
                      variant="outline" 
                      size="sm" 
                      className="h-7 text-xs px-2"
                      onClick={() => handleSave(false)}
                      disabled={saving}
                      title="Save as draft (allows uploading photos before completing all areas)"
                    >
                      {saving ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <>
                          <Save className="h-3 w-3 mr-1" />
                          Save
                        </>
                      )}
                    </Button>
                    {currentInspectionId && (
                      <Button 
                        variant="outline" 
                        size="sm" 
                        className="h-7 text-xs px-2"
                        onClick={handleGeneratePDF}
                        disabled={generatingPDF}
                      >
                        <FileText className="h-3 w-3 mr-1" />
                        {generatingPDF ? 'Generating...' : 'PDF'}
                      </Button>
                    )}
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="h-7 w-7 p-0"
                      onClick={() => setIsFormExpanded(!isFormExpanded)}
                    >
                      {isFormExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
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

                    <div className="grid grid-cols-2 gap-3">
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

                      <div className="space-y-1">
                        <Label className="text-xs">Inspector</Label>
                        <Input 
                          type="text"
                          value={formData.inspector_name}
                          onChange={(e) => setFormData({...formData, inspector_name: e.target.value})}
                          placeholder="Sarah Pappas, Member S&M Axios Heartland Holdings LLC"
                          className="h-8 text-xs"
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <Label className="text-xs">General Notes</Label>
                      <Textarea 
                        value={formData.notes}
                        onChange={(e) => setFormData({...formData, notes: e.target.value})}
                        placeholder="Additional notes about the inspection..."
                        className="text-xs min-h-[80px]"
                      />
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
                            <div className="flex items-center justify-between p-3">
                              <div 
                                className="flex items-center gap-3 flex-1 cursor-pointer"
                                onClick={() => toggleArea(area.id)}
                              >
                                <div className={`w-2.5 h-2.5 rounded-full ${getStatusColor(area.inspection_status)}`} />
                                <span className="text-sm font-medium">{area.name}</span>
                                {area.notes && <Badge variant="outline" className="text-xs">Notes</Badge>}
                                {area.landlord_fix_notes && <Badge variant="outline" className="text-xs bg-orange-50">Fix Notes</Badge>}
                                {area.photos.length > 0 && (
                                  <Badge variant="outline" className="text-xs">
                                    <Camera className="h-3 w-3 mr-1" />{area.photos.length}
                                  </Badge>
                                )}
                              </div>
                              <div className="flex items-center gap-2">
                                {area.inspection_status && (
                                  <Badge className={`${getStatusBadgeStyle(area.inspection_status)} text-xs font-medium`}>
                                    {getStatusLabel(area.inspection_status)}
                                  </Badge>
                                )}
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 w-7 p-0 text-red-600 hover:text-red-700 hover:bg-red-50"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    if (confirm(`Remove "${area.name}" from inspection?`)) {
                                      removeArea(area.id)
                                    }
                                  }}
                                  title="Remove area"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                                {area.expanded ? <ChevronUp className="h-4 w-4 cursor-pointer" onClick={() => toggleArea(area.id)} /> : <ChevronDown className="h-4 w-4 cursor-pointer" onClick={() => toggleArea(area.id)} />}
                              </div>
                            </div>

                            {/* Expanded content */}
                            {area.expanded && (
                              <div className="px-3 pb-3 pt-0 border-t space-y-3">
                                <div className="grid grid-cols-2 gap-3 pt-3">
                                  <div className="space-y-1">
                                    <Label className="text-xs">Floor</Label>
                                    <Select
                                      value={area.floor || ''}
                                      onValueChange={(v) => {
                                        updateArea(area.id, { floor: v })
                                      }}
                                    >
                                      <SelectTrigger 
                                        className="text-xs h-8"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        <SelectValue placeholder="Select floor..." />
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
                                  <div className="space-y-1">
                                    <Label className="text-xs">Area Name</Label>
                                    <Input
                                      value={area.name}
                                      onChange={(e) => {
                                        e.stopPropagation()
                                        updateArea(area.id, { name: e.target.value })
                                      }}
                                      onClick={(e) => e.stopPropagation()}
                                      onFocus={(e) => e.stopPropagation()}
                                      onKeyDown={(e) => e.stopPropagation()}
                                      placeholder="e.g., Living Room, Kitchen"
                                      className="text-xs h-8"
                                    />
                                  </div>
                                </div>

                                <div className="space-y-1">
                                  <Label className="text-xs">Inspection Status <span className="text-red-500">*</span></Label>
                                  <div className="flex flex-col gap-2">
                                    {[
                                      { value: 'no_issues', label: 'Inspected: No Issues Noted', color: 'bg-green-500' },
                                      { value: 'issue_noted_as_is', label: 'Inspected: Issue Noted (leaving as-is)', color: 'bg-yellow-500' },
                                      { value: 'issue_landlord_to_fix', label: 'Inspected: Issue Noted and Landlord to fix', color: 'bg-orange-500' }
                                    ].map((option) => (
                                      <Button
                                        key={option.value}
                                        variant={area.inspection_status === option.value ? 'default' : 'outline'}
                                        size="sm"
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          updateArea(area.id, { 
                                            inspection_status: option.value as AreaInspection['inspection_status'],
                                            // Clear landlord_fix_notes if not selected
                                            landlord_fix_notes: option.value === 'issue_landlord_to_fix' ? area.landlord_fix_notes : '',
                                            // Only collapse if "No Issues Noted" - keep expanded for issues so user can add notes
                                            expanded: option.value === 'no_issues' ? false : true
                                          })
                                        }}
                                        className={`h-8 text-xs justify-start ${area.inspection_status === option.value ? option.color + ' text-white' : ''}`}
                                      >
                                        {option.label}
                                      </Button>
                                    ))}
                                  </div>
                                </div>

                                <div className="space-y-1">
                                  <Label className="text-xs">General Notes (optional)</Label>
                                  <Textarea 
                                    placeholder="Describe any damage, wear, or notable conditions..."
                                    value={area.notes}
                                    onChange={(e) => updateArea(area.id, { notes: e.target.value })}
                                    onClick={(e) => e.stopPropagation()}
                                    rows={2}
                                    className="text-xs"
                                  />
                                </div>

                                {area.inspection_status === 'issue_landlord_to_fix' && (
                                  <div className="space-y-1">
                                    <Label className="text-xs">
                                      Landlord Fix Notes <span className="text-red-500">*</span>
                                      <span className="text-gray-500 ml-1">(Required)</span>
                                    </Label>
                                    <Textarea 
                                      placeholder="Describe what the landlord will fix prior to move-in..."
                                      value={area.landlord_fix_notes}
                                      onChange={(e) => updateArea(area.id, { landlord_fix_notes: e.target.value })}
                                      onClick={(e) => e.stopPropagation()}
                                      rows={3}
                                      className="text-xs border-orange-300 focus:border-orange-500"
                                      required
                                    />
                                    {!area.landlord_fix_notes?.trim() && (
                                      <p className="text-xs text-red-500 mt-1">Fix notes are required for items the landlord will fix</p>
                                    )}
                                  </div>
                                )}

                                <div className="flex items-center justify-between">
                                  {currentInspectionId ? (
                                    <Button 
                                      variant="outline" 
                                      size="sm" 
                                      className="h-7 text-xs" 
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        handleAddPhoto(area.id)
                                      }}
                                      title="Upload photos for this area"
                                    >
                                      <Camera className="h-3 w-3 mr-1" />
                                      Add Photo{area.photos.length > 0 && ` (${area.photos.length})`}
                                    </Button>
                                  ) : (
                                    <p className="text-xs text-gray-500 italic">
                                      Save inspection first to upload photos
                                    </p>
                                  )}
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
                                
                                {/* Show existing photos if any */}
                                {currentInspectionId && area.photos && area.photos.length > 0 && (
                                  <div className="mt-2 pt-2 border-t">
                                    <Label className="text-xs text-gray-600 mb-2 block">Photos ({area.photos.length})</Label>
                                    <div className="grid grid-cols-3 gap-2">
                                      {area.photos.map((photo, idx) => (
                                        <div key={idx} className="relative group">
                                          {photo.photo_url && (
                                            <img 
                                              src={photo.photo_url} 
                                              alt={`Photo ${idx + 1}`}
                                              className="w-full h-20 object-cover rounded border"
                                            />
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
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
            </div>
          )}

          {/* RIGHT: Preview (50%) - Hidden when Form is expanded */}
          {!isFormExpanded && (
            <div className="flex flex-col min-h-0" style={{ width: '100%' }}>
              <Card className="flex-1 flex flex-col min-h-0">
                <CardHeader className="py-2 border-b flex-shrink-0 flex flex-row items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CardTitle className="text-sm font-bold">Inspection Summary</CardTitle>
                    {isPreviewExpanded && (
                      <Badge variant="secondary" className="text-xs">Expanded</Badge>
                    )}
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    className="h-7 w-7 p-0"
                    onClick={() => setIsPreviewExpanded(!isPreviewExpanded)}
                  >
                    {isPreviewExpanded ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                  </Button>
                </CardHeader>
                <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
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

                    {/* Summary by inspection status */}
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { value: 'no_issues', label: 'No Issues' },
                        { value: 'issue_noted_as_is', label: 'Issue (As-Is)' },
                        { value: 'issue_landlord_to_fix', label: 'Landlord to Fix' }
                      ].map((status) => {
                        const count = areas.filter(a => a.inspection_status === status.value).length
                        return (
                          <div key={status.value} className="text-center p-2 rounded-lg border">
                            <div className={`w-3 h-3 rounded-full mx-auto mb-1 ${getStatusColor(status.value)}`} />
                            <div className="text-lg font-bold">{count}</div>
                            <div className="text-xs text-gray-500">{status.label}</div>
                          </div>
                        )
                      })}
                    </div>

                    <Separator />

                    {/* Areas with notes */}
                    <div className="space-y-2">
                      <h4 className="text-xs font-bold uppercase text-gray-500">Areas with Notes</h4>
                      {areas.filter(a => a.notes || a.landlord_fix_notes).length === 0 ? (
                        <p className="text-xs text-gray-400 italic">No notes recorded yet</p>
                      ) : (
                        areas.filter(a => a.notes || a.landlord_fix_notes).map(area => (
                          <div key={area.id} className="p-2 bg-gray-50 rounded text-xs">
                            <div className="font-medium flex items-center gap-2">
                              <div className={`w-2 h-2 rounded-full ${getStatusColor(area.inspection_status)}`} />
                              {area.name}
                            </div>
                            {area.notes && <p className="text-gray-600 mt-1">{area.notes}</p>}
                            {area.landlord_fix_notes && (
                              <p className="text-orange-700 mt-1 font-medium">
                                <span className="font-semibold">Fix Notes:</span> {area.landlord_fix_notes}
                              </p>
                            )}
                          </div>
                        ))
                      )}
                    </div>

                    <Separator />

                    {/* Signature section */}
                    <div className="space-y-3">
                      <h4 className="text-xs font-bold uppercase text-gray-500">Signatures</h4>
                      {!canSign() && (
                        <div className="p-3 bg-orange-50 border border-orange-200 rounded-lg">
                          <p className="text-xs text-orange-800">
                            ⚠️ All "Landlord to Fix" items must have fix notes before signing
                          </p>
                        </div>
                      )}
                      <div className="grid grid-cols-2 gap-3">
                        <div className="border rounded-lg p-3 text-center">
                          <div className="text-xs text-gray-500 mb-2">Landlord Signature</div>
                          <div className="h-16 border-b border-dashed border-gray-300 mb-2" />
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="text-xs h-7"
                            disabled={!canSign()}
                          >
                            Sign
                          </Button>
                        </div>
                        <div className="border rounded-lg p-3 text-center">
                          <div className="text-xs text-gray-500 mb-2">Tenant Signature</div>
                          <div className="h-16 border-b border-dashed border-gray-300 mb-2" />
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="text-xs h-7"
                            disabled={!canSign()}
                          >
                            Sign
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
