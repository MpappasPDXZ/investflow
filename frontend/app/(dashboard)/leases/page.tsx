'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useProperties } from '@/lib/hooks/use-properties';
import { useLeasesList, useLeases, type Lease } from '@/lib/hooks/use-leases';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { 
  Plus, 
  FileText, 
  Edit, 
  Trash2, 
  FileCheck,
  ChevronDown,
  ChevronRight,
  Building2,
  User,
  Calendar,
  DollarSign,
  Download
} from 'lucide-react';
import { format } from 'date-fns';
import Link from 'next/link';

interface GroupedByTenant {
  [tenantKey: string]: Lease[];
}

export default function LeasesPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>('');
  const [expandedTenants, setExpandedTenants] = useState<Set<string>>(new Set());
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [currentLeaseId, setCurrentLeaseId] = useState<string | null>(null);
  const [holdingFeePdfUrls, setHoldingFeePdfUrls] = useState<Record<string, string>>({});
  const [showPdfViewer, setShowPdfViewer] = useState(false);
  
  const { data: propertiesData } = useProperties();
  const { data: leasesData, isLoading, refetch } = useLeasesList(
    selectedPropertyId ? { property_id: selectedPropertyId } : {}
  );
  
  // Refetch when refresh parameter is present
  useEffect(() => {
    if (searchParams.get('refresh') === 'true') {
      refetch();
      // Remove the refresh parameter from URL
      router.replace('/leases', { scroll: false });
    }
  }, [searchParams, refetch, router]);
  const { generatePDF, deleteLease } = useLeases();
  
  const properties = propertiesData?.items || [];
  const leases = leasesData?.leases || [];
  const hasInitializedProperty = useRef(false);

  // Extract unit number from property display_name (format: "Property Name - Unit 123")
  const getUnitNumber = (lease: Lease) => {
    // The property.display_name includes unit number when applicable
    // Format: "Property Name - Unit 123" or just "Property Name"
    if (lease.property?.display_name) {
      const match = lease.property.display_name.match(/ - Unit (.+)$/);
      return match ? match[1] : null;
    }
    return null;
  };

  // Format status for display
  const getStatusDisplay = (status: string) => {
    if (status === 'draft') return 'drafting';
    if (status === 'active' || status === 'pending_signature') return 'signed';
    return status;
  };

  // Get status badge color
  const getStatusColor = (status: string) => {
    if (status === 'draft') return 'bg-gray-100 text-gray-700';
    if (status === 'active' || status === 'pending_signature') return 'bg-green-100 text-green-700';
    return 'bg-red-100 text-red-700';
  };

  // Auto-select first property if available and none selected
  useEffect(() => {
    if (!hasInitializedProperty.current && !selectedPropertyId && properties.length > 0) {
      setSelectedPropertyId(properties[0].id);
      hasInitializedProperty.current = true;
    }
  }, [properties.length, selectedPropertyId]);

  // Group leases by tenant (using tenant names as key)
  const groupedByTenant = useMemo(() => {
    const result: GroupedByTenant = {};
    
    leases.forEach(lease => {
      // Create a tenant key from all tenant names
      const tenantNames = (lease.tenants || [])
        .map(t => `${t.first_name} ${t.last_name}`)
        .filter(Boolean)
        .join(', ');
      
      const tenantKey = tenantNames || 'No Tenants';
      
      if (!result[tenantKey]) {
        result[tenantKey] = [];
      }
      result[tenantKey].push(lease);
    });
    
    // Sort leases within each tenant group by created_at (newest first)
    Object.values(result).forEach(tenantLeases => {
      tenantLeases.sort((a, b) => {
        const timeA = new Date(a.created_at).getTime();
        const timeB = new Date(b.created_at).getTime();
        return timeB - timeA; // Newest first
      });
    });
    
    // Also sort tenant groups by their newest lease (newest tenant group first)
    const sortedEntries = Object.entries(result).sort(([, leasesA], [, leasesB]) => {
      if (leasesA.length === 0 && leasesB.length === 0) return 0;
      if (leasesA.length === 0) return 1;
      if (leasesB.length === 0) return -1;
      const newestA = new Date(leasesA[0].created_at).getTime();
      const newestB = new Date(leasesB[0].created_at).getTime();
      return newestB - newestA; // Newest first
    });
    
    return Object.fromEntries(sortedEntries) as GroupedByTenant;
  }, [leases]);

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
  const handleDelete = async (leaseId: string, e?: React.MouseEvent) => {
    // Stop event propagation to prevent row click
    if (e) {
      e.stopPropagation();
    }
    
    if (!confirm('⚠️ WARNING: Are you sure you want to delete this lease?\n\nThis action cannot be undone and will permanently remove all lease data.')) {
      return;
    }
    
    setDeletingId(leaseId);
    try {
      await deleteLease(leaseId);
      await refetch();
    } catch (error) {
      console.error('Error deleting lease:', error);
      alert('Failed to delete lease');
    } finally {
      setDeletingId(null);
    }
  };

  // Handle generate PDF
  const handleGeneratePDF = async (leaseId: string) => {
    setGeneratingId(leaseId);
    try {
      const result = await generatePDF(leaseId, false);
      setPdfUrl(result.pdf_url);
      setCurrentLeaseId(leaseId);
      if (result.holding_fee_pdf_url) {
        setHoldingFeePdfUrls(prev => ({ ...prev, [leaseId]: result.holding_fee_pdf_url! }));
      }
      setShowPdfViewer(true);
    } catch (error) {
      console.error('Error generating PDF:', error);
      alert('Failed to generate PDF');
    } finally {
      setGeneratingId(null);
    }
  };

  // Tenant keys are already sorted by newest lease first from the useMemo
  const sortedTenantKeys = Object.keys(groupedByTenant);

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden">
      {/* Left Panel - Leases List */}
      <div className={`flex-1 overflow-y-auto p-3 ${showPdfViewer ? 'border-r border-gray-300' : ''}`}>
      {/* Header */}
      <div className="flex justify-between items-center mb-3">
        <div>
          <h1 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
            <FileText className="h-3.5 w-3.5" />
            Leases
          </h1>
          <p className="text-xs text-gray-500">Manage lease agreements</p>
        </div>
        <div className="flex gap-1.5">
          <Link href="/leases/create">
            <Button size="sm" className="bg-black text-white hover:bg-gray-800 h-7 text-xs px-2">
              <Plus className="h-3 w-3 mr-1" />
              Add Lease
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
          Loading leases...
        </div>
      )}

      {/* Empty State */}
      {!isLoading && selectedPropertyId && leases.length === 0 && (
        <Card>
          <CardContent className="py-8 text-center">
            <FileText className="h-12 w-12 text-gray-400 mx-auto mb-2" />
            <p className="text-sm text-gray-500">No leases found for this property</p>
            <Link href="/leases/create">
              <Button size="sm" className="mt-4">
                <Plus className="h-3 w-3 mr-1" />
                Create First Lease
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {/* Leases List - Grouped by Tenant */}
      {!isLoading && selectedPropertyId && leases.length > 0 && (
        <div className="space-y-2">
          {sortedTenantKeys.map(tenantKey => {
            const tenantLeases = groupedByTenant[tenantKey];
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
                        ({tenantLeases.length} {tenantLeases.length === 1 ? 'lease' : 'leases'})
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
                          <TableHead className="text-xs font-semibold py-2 px-3">created</TableHead>
                          <TableHead className="text-xs font-semibold py-2 px-3">lease_start</TableHead>
                          <TableHead className="text-xs font-semibold py-2 px-3">lease_end</TableHead>
                          <TableHead className="text-xs font-semibold py-2 px-3">monthly_rent</TableHead>
                          <TableHead className="text-xs font-semibold py-2 px-3">status</TableHead>
                          <TableHead className="text-xs font-semibold py-2 px-3 w-[100px]">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {tenantLeases.map(lease => (
                          <TableRow
                            key={lease.id}
                            className="cursor-pointer hover:bg-gray-50"
                            onClick={() => router.push(`/leases/${lease.id}/edit`)}
                          >
                            <TableCell className="text-xs py-2 px-3">
                              {getUnitNumber(lease) || '-'}
                            </TableCell>
                            <TableCell className="text-xs py-2 px-3">
                              {lease.created_at ? format(new Date(lease.created_at), 'MMM d, yyyy h:mm a') : '-'}
                            </TableCell>
                            <TableCell className="text-xs py-2 px-3">
                              {lease.lease_start 
                                ? format(new Date(lease.lease_start as string), 'MMM d, yyyy')
                                : '-'}
                            </TableCell>
                            <TableCell className="text-xs py-2 px-3">
                              {lease.lease_end 
                                ? format(new Date(lease.lease_end as string), 'MMM d, yyyy')
                                : '-'}
                            </TableCell>
                            <TableCell className="text-xs py-2 px-3">
                              ${Number(lease.monthly_rent || 0).toLocaleString()}
                            </TableCell>
                            <TableCell className="text-xs py-2 px-3">
                              <span className={`px-1.5 py-0.5 rounded ${getStatusColor(lease.status || 'draft')}`}>
                                {getStatusDisplay(lease.status || 'draft')}
                              </span>
                            </TableCell>
                            <TableCell className="text-xs py-2 px-3" onClick={(e) => e.stopPropagation()}>
                              <div className="flex gap-1">
                                {lease.pdf_url ? (
                                  <>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="h-6 text-xs px-1.5"
                                      onClick={() => {
                                        setPdfUrl(lease.pdf_url!);
                                        setCurrentLeaseId(lease.id);
                                        setShowPdfViewer(true);
                                      }}
                                      title="View Lease"
                                    >
                                      <FileCheck className="h-3 w-3" />
                                    </Button>
                                    {(() => {
                                      // Check if holding fee addendum exists
                                      // Show button if: 1) we have URL in state from generation, 2) lease has include_holding_fee_addendum flag
                                      const holdingFeeUrl = holdingFeePdfUrls[lease.id] || (lease as any).holding_fee_pdf_url;
                                      const hasHoldingFee = holdingFeeUrl || (lease as any).include_holding_fee_addendum;
                                      
                                      if (!hasHoldingFee) return null;
                                      
                                      return (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="h-6 text-xs px-1.5"
                                          onClick={() => {
                                            if (holdingFeeUrl) {
                                              // Use direct URL if available
                                              window.open(holdingFeeUrl, '_blank');
                                            } else {
                                              // Fallback: use proxy endpoint (constructs URL from lease PDF blob name)
                                              // The proxy endpoint will construct the holding fee PDF blob name from the lease PDF
                                              window.open(`${API_URL}/api/v1/leases/${lease.id}/pdf/proxy?document_type=holding_fee`, '_blank');
                                            }
                                          }}
                                          title="Download Holding Fee Addendum"
                                        >
                                          <Download className="h-3 w-3" />
                                        </Button>
                                      );
                                    })()}
                                  </>
                                ) : (
                                  <Button
                                    size="sm"
                                    variant="default"
                                    className="h-6 text-xs px-2 bg-black text-white hover:bg-gray-800"
                                    onClick={() => handleGeneratePDF(lease.id)}
                                    disabled={generatingId === lease.id}
                                  >
                                    {generatingId === lease.id ? (
                                      <>
                                        <FileText className="h-3 w-3 animate-spin mr-1" />
                                        Generating...
                                      </>
                                    ) : (
                                      <>
                                        <FileText className="h-3 w-3 mr-1" />
                                        Generate Lease
                                      </>
                                    )}
                                  </Button>
                                )}
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-6 text-xs px-1.5 text-red-600 hover:text-red-700 hover:bg-red-50"
                                  onClick={(e) => handleDelete(lease.id, e)}
                                  disabled={deletingId === lease.id}
                                >
                                  {deletingId === lease.id ? (
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
            <h2 className="text-sm font-semibold">Lease Document</h2>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                className="h-7 text-xs px-3"
                onClick={() => {
                  window.open(pdfUrl, '_blank');
                }}
              >
                <Download className="h-3 w-3 mr-1" />
                Download Lease
              </Button>
              {(() => {
                // Check if holding fee addendum exists for current lease
                if (!currentLeaseId) return null;
                
                const holdingFeeUrl = holdingFeePdfUrls[currentLeaseId];
                const currentLease = leases.find(l => l.id === currentLeaseId);
                const hasHoldingFee = holdingFeeUrl || (currentLease as any)?.include_holding_fee_addendum;
                
                if (!hasHoldingFee) return null;
                
                return (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs px-3"
                    onClick={() => {
                      if (holdingFeeUrl) {
                        window.open(holdingFeeUrl, '_blank');
                      } else {
                        // Fallback: use proxy endpoint
                        window.open(`${API_URL}/api/v1/leases/${currentLeaseId}/pdf/proxy?document_type=holding_fee`, '_blank');
                      }
                    }}
                  >
                    <Download className="h-3 w-3 mr-1" />
                    Download Holding Fee Agreement
                  </Button>
                );
              })()}
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setShowPdfViewer(false);
                  setPdfUrl(null);
                  setCurrentLeaseId(null);
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
              title="Lease PDF"
            />
          </div>
        </div>
      )}
    </div>
  );
}
