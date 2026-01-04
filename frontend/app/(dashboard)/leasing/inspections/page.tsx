'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useProperties } from '@/lib/hooks/use-properties';
import { useWalkthroughsList, useWalkthroughs, type WalkthroughListItem } from '@/lib/hooks/use-walkthroughs';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { 
  ClipboardCheck, 
  Plus, 
  FileText, 
  Edit, 
  Trash2, 
  ChevronDown,
  ChevronRight,
  User,
  Calendar,
  Download
} from 'lucide-react';
import { format } from 'date-fns';
import Link from 'next/link';

interface GroupedByTenant {
  [tenantKey: string]: WalkthroughListItem[];
}

export default function InspectionsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>('');
  const [expandedTenants, setExpandedTenants] = useState<Set<string>>(new Set());
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [currentWalkthroughId, setCurrentWalkthroughId] = useState<string | null>(null);
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  
  const { data: propertiesData } = useProperties();
  const { data: walkthroughsData, isLoading, refetch } = useWalkthroughsList(
    selectedPropertyId ? { property_id: selectedPropertyId } : {}
  );
  
  // Refetch when refresh parameter is present
  useEffect(() => {
    if (searchParams.get('refresh') === 'true') {
      refetch();
      // Remove the refresh parameter from URL
      router.replace('/leasing/inspections', { scroll: false });
    }
  }, [searchParams, refetch, router]);
  
  const { generatePDF, deleteWalkthrough } = useWalkthroughs();
  
  const properties = propertiesData?.items || [];
  const walkthroughs = walkthroughsData?.items || [];
  const hasInitializedProperty = useRef(false);

  // Format status for display
  const getStatusDisplay = (status: string) => {
    if (status === 'draft') return 'draft';
    if (status === 'pending_signature') return 'pending signature';
    if (status === 'completed') return 'completed';
    return status;
  };

  // Get status badge color
  const getStatusColor = (status: string) => {
    if (status === 'draft') return 'bg-gray-100 text-gray-700';
    if (status === 'completed') return 'bg-green-100 text-green-700';
    if (status === 'pending_signature') return 'bg-blue-100 text-blue-700';
    return 'bg-gray-100 text-gray-700';
  };

  // Auto-select first property if available and none selected
  useEffect(() => {
    if (!hasInitializedProperty.current && !selectedPropertyId && properties.length > 0) {
      setSelectedPropertyId(properties[0].id);
      hasInitializedProperty.current = true;
    }
  }, [properties.length, selectedPropertyId]);

  // Group walkthroughs by tenant (using tenant_name as key)
  const groupedByTenant = useMemo(() => {
    const result: GroupedByTenant = {};
    
    walkthroughs.forEach(walkthrough => {
      // Use tenant_name from walkthrough
      const tenantKey = walkthrough.tenant_name || 'No Tenant';
      
      if (!result[tenantKey]) {
        result[tenantKey] = [];
      }
      result[tenantKey].push(walkthrough);
    });
    
    // Sort walkthroughs within each tenant group by created_at (newest first)
    Object.values(result).forEach(tenantWalkthroughs => {
      tenantWalkthroughs.sort((a, b) => {
        const timeA = new Date(a.created_at).getTime();
        const timeB = new Date(b.created_at).getTime();
        return timeB - timeA; // Newest first
      });
    });
    
    // Also sort tenant groups by their newest walkthrough (newest tenant group first)
    const sortedEntries = Object.entries(result).sort(([, walkthroughsA], [, walkthroughsB]) => {
      if (walkthroughsA.length === 0 && walkthroughsB.length === 0) return 0;
      if (walkthroughsA.length === 0) return 1;
      if (walkthroughsB.length === 0) return -1;
      const newestA = new Date(walkthroughsA[0].created_at).getTime();
      const newestB = new Date(walkthroughsB[0].created_at).getTime();
      return newestB - newestA; // Newest first
    });
    
    return Object.fromEntries(sortedEntries) as GroupedByTenant;
  }, [walkthroughs]);

  // Get property name
  const getPropertyName = (propId: string) => {
    const prop = properties.find(p => p.id === propId);
    return prop?.display_name || prop?.address_line1 || 'Unknown Property';
  };

  // Toggle tenant expansion
  const toggleTenant = (tenantKey: string) => {
    setExpandedTenants(prev => {
      const newSet = new Set(prev);
      if (newSet.has(tenantKey)) {
        newSet.delete(tenantKey);
      } else {
        newSet.add(tenantKey);
      }
      return newSet;
    });
  };

  // Handle delete
  const handleDelete = async (walkthroughId: string, e?: React.MouseEvent) => {
    // Stop event propagation to prevent row click
    if (e) {
      e.stopPropagation();
    }
    
    if (!confirm('⚠️ WARNING: Are you sure you want to delete this inspection?\n\nThis action cannot be undone and will permanently remove all inspection data.')) {
      return;
    }
    
    setDeletingId(walkthroughId);
    try {
      await deleteWalkthrough(walkthroughId);
      await refetch();
    } catch (error) {
      console.error('Error deleting inspection:', error);
      alert('Failed to delete inspection');
    } finally {
      setDeletingId(null);
    }
  };

  // Handle generate PDF
  const handleGeneratePDF = async (walkthroughId: string) => {
    setGeneratingId(walkthroughId);
    try {
      const result = await generatePDF(walkthroughId, false);
      setPdfUrl(result.pdf_url);
      setCurrentWalkthroughId(walkthroughId);
      setShowPdfViewer(true);
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('Failed to generate PDF');
    } finally {
      setGeneratingId(null);
    }
  };

  // Tenant keys are already sorted by newest walkthrough first from the useMemo
  const sortedTenantKeys = Object.keys(groupedByTenant);

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Left Panel - Inspections List */}
      <div className={`flex-1 overflow-y-auto p-3 ${showPdfViewer ? 'border-r border-gray-300' : ''}`}>
      {/* Header */}
      <div className="flex justify-between items-center mb-3">
        <div>
          <h1 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
            <ClipboardCheck className="h-3.5 w-3.5" />
            Inspections
          </h1>
          <p className="text-xs text-gray-500">Manage property inspections</p>
        </div>
        <div className="flex gap-1.5">
          <Link href="/leasing/inspections/create">
            <Button size="sm" className="bg-black text-white hover:bg-gray-800 h-7 text-xs px-2">
              <Plus className="h-3 w-3 mr-1" />
              Add Inspection
            </Button>
          </Link>
        </div>
      </div>

      {/* Property Filter - Required */}
      <div className="mb-3">
        <select
          value={selectedPropertyId}
          onChange={(e) => setSelectedPropertyId(e.target.value)}
          className="px-2 py-1.5 border border-gray-300 rounded text-sm w-full md:w-auto min-w-[200px]"
          required
        >
          <option value="">Select Property</option>
          {properties.map((prop) => (
            <option key={prop.id} value={prop.id}>
              {prop.display_name || prop.address_line1 || prop.id}
            </option>
          ))}
        </select>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="text-center py-8 text-sm text-gray-500">
          Loading inspections...
        </div>
      )}

      {/* Empty State */}
      {!isLoading && selectedPropertyId && walkthroughs.length === 0 && (
        <Card>
          <CardContent className="py-8 text-center">
            <ClipboardCheck className="h-12 w-12 text-gray-400 mx-auto mb-2" />
            <p className="text-sm text-gray-500">No inspections found for this property</p>
            <Link href="/leasing/inspections/create">
              <Button size="sm" className="mt-4">
                <Plus className="h-3 w-3 mr-1" />
                Create First Inspection
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Inspections List - Grouped by Tenant */}
      {!isLoading && selectedPropertyId && walkthroughs.length > 0 && (
        <div className="space-y-2">
          {sortedTenantKeys.map(tenantKey => {
            const tenantWalkthroughs = groupedByTenant[tenantKey];
            const isExpanded = expandedTenants.has(tenantKey);
            
            return (
              <Card key={tenantKey}>
                <CardHeader 
                  className="py-2 px-3 cursor-pointer hover:bg-gray-50"
                  onClick={() => toggleTenant(tenantKey)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {isExpanded ? (
                        <ChevronDown className="h-4 w-4 text-gray-500" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-gray-500" />
                      )}
                      <User className="h-4 w-4 text-gray-500" />
                      <CardTitle className="text-sm font-semibold">
                        {tenantKey}
                      </CardTitle>
                      <span className="text-xs text-gray-500">
                        ({tenantWalkthroughs.length} {tenantWalkthroughs.length === 1 ? 'inspection' : 'inspections'})
                      </span>
                    </div>
                  </div>
                </CardHeader>
                
                {isExpanded && (
                  <CardContent className="pt-0 px-0 pb-3">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-gray-50">
                          <TableHead className="text-xs font-semibold py-2 px-3">unit</TableHead>
                          <TableHead className="text-xs font-semibold py-2 px-3">type</TableHead>
                          <TableHead className="text-xs font-semibold py-2 px-3">date</TableHead>
                          <TableHead className="text-xs font-semibold py-2 px-3">areas</TableHead>
                          <TableHead className="text-xs font-semibold py-2 px-3">status</TableHead>
                          <TableHead className="text-xs font-semibold py-2 px-3 w-[100px]">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {tenantWalkthroughs.map(walkthrough => (
                          <TableRow
                            key={walkthrough.id}
                            className="cursor-pointer hover:bg-gray-50"
                            onClick={() => router.push(`/leasing/inspections/${walkthrough.id}/edit`)}
                          >
                            <TableCell className="text-xs py-2 px-3">
                              {walkthrough.unit_number || '-'}
                            </TableCell>
                            <TableCell className="text-xs py-2 px-3">
                              {walkthrough.walkthrough_type === 'move_in' ? 'Move-In' : 
                               walkthrough.walkthrough_type === 'move_out' ? 'Move-Out' :
                               walkthrough.walkthrough_type === 'periodic' ? 'Periodic' :
                               walkthrough.walkthrough_type === 'maintenance' ? 'Maintenance' : 
                               walkthrough.walkthrough_type}
                            </TableCell>
                            <TableCell className="text-xs py-2 px-3">
                              {walkthrough.walkthrough_date 
                                ? format(new Date(walkthrough.walkthrough_date), 'MMM d, yyyy')
                                : '-'}
                            </TableCell>
                            <TableCell className="text-xs py-2 px-3">
                              {walkthrough.areas_count || 0} area{(walkthrough.areas_count || 0) !== 1 ? 's' : ''}
                            </TableCell>
                            <TableCell className="text-xs py-2 px-3">
                              <span className={`px-1.5 py-0.5 rounded ${getStatusColor(walkthrough.status || 'draft')}`}>
                                {getStatusDisplay(walkthrough.status || 'draft')}
                              </span>
                            </TableCell>
                            <TableCell className="text-xs py-2 px-3" onClick={(e) => e.stopPropagation()}>
                              <div className="flex gap-1">
                                {walkthrough.pdf_url ? (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-6 text-xs px-1.5"
                                    onClick={() => {
                                      setPdfUrl(walkthrough.pdf_url!);
                                      setCurrentWalkthroughId(walkthrough.id);
                                      setShowPdfViewer(true);
                                    }}
                                    title="View Inspection"
                                  >
                                    <FileText className="h-3 w-3" />
                                  </Button>
                                ) : (
                                  <Button
                                    size="sm"
                                    variant="default"
                                    className="h-6 text-xs px-2 bg-black text-white hover:bg-gray-800"
                                    onClick={() => handleGeneratePDF(walkthrough.id)}
                                    disabled={generatingId === walkthrough.id}
                                  >
                                    {generatingId === walkthrough.id ? (
                                      <>
                                        <FileText className="h-3 w-3 animate-spin mr-1" />
                                        Generating (loading photos)...
                                      </>
                                    ) : (
                                      <>
                                        <FileText className="h-3 w-3 mr-1" />
                                        Generate Inspection
                                      </>
                                    )}
                                  </Button>
                                )}
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-6 text-xs px-1.5 text-red-600 hover:text-red-700 hover:bg-red-50"
                                  onClick={(e) => handleDelete(walkthrough.id, e)}
                                  disabled={deletingId === walkthrough.id}
                                >
                                  {deletingId === walkthrough.id ? (
                                    <FileText className="h-3 w-3 animate-spin" />
                                  ) : (
                                    <Trash2 className="h-3 w-3" />
                                  )}
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </CardContent>
                )}
              </Card>
            );
          })}
        </div>
      )}

      </div>

      {/* Right Panel - PDF Viewer */}
      {showPdfViewer && pdfUrl && (
        <div className="w-1/2 border-l border-gray-300 flex flex-col bg-white">
          <div className="flex items-center justify-between p-3 border-b">
            <h2 className="text-sm font-semibold">Inspection Document</h2>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs px-3"
                onClick={() => {
                  // Use window.open to open in new tab (like leases)
                  window.open(pdfUrl, '_blank');
                }}
              >
                <Download className="h-3 w-3 mr-1" />
                Download Inspection
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setShowPdfViewer(false);
                  setPdfUrl(null);
                  setCurrentWalkthroughId(null);
                }}
                className="h-7 text-xs px-2"
              >
                Close
              </Button>
            </div>
          </div>
          <div className="flex-1 overflow-hidden">
            <iframe
              src={pdfUrl}
              className="w-full h-full"
              title="Inspection PDF"
            />
          </div>
        </div>
      )}
    </div>
  );
}
