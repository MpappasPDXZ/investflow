'use client';

import { useParams, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useLeases } from '@/lib/hooks/use-leases';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { FileSignature, ArrowLeft, Download, FileText, Users, Home, Loader2, AlertCircle, Trash2, RefreshCw, Eye } from 'lucide-react';
import Link from 'next/link';
import { ReceiptViewer } from '@/components/ReceiptViewer';
import { apiClient } from '@/lib/api-client';

export default function LeaseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const { getLease, generatePDF, deleteLease } = useLeases();
  
  const [lease, setLease] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      fetchLease();
    }
  }, [id]);

  const fetchLease = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getLease(id);
      setLease(data);
    } catch (err: any) {
      console.error('Error fetching lease:', err);
      setError(err.message || 'Failed to load lease');
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePDF = async (regenerate = false) => {
    try {
      setGenerating(true);
      const result = await generatePDF(id, regenerate);
      // Refresh lease data to get updated PDF URL
      await fetchLease();
      // Open PDF in ReceiptViewer after generation
      if (result.pdf_url) {
        // The ReceiptViewer will show the PDF
      }
    } catch (err: any) {
      console.error('Error generating PDF:', err);
      alert(err.message || 'Failed to generate PDF');
    } finally {
      setGenerating(false);
    }
  };

  const handleDeletePDF = async () => {
    if (!confirm('Are you sure you want to delete this PDF? The lease data will be retained.')) {
      return;
    }
    
    try {
      setDeleting(true);
      await apiClient.delete(`/leases/${id}/pdf`);
      // Refresh lease data
      await fetchLease();
      alert('PDF deleted successfully');
    } catch (err: any) {
      console.error('Error deleting PDF:', err);
      alert(err.message || 'Failed to delete PDF');
    } finally {
      setDeleting(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this lease? This action cannot be undone.')) {
      return;
    }
    
    try {
      await deleteLease(id);
      router.push('/leases');
    } catch (err: any) {
      console.error('Error deleting lease:', err);
      alert(err.message || 'Failed to delete lease');
    }
  };

  const formatDate = (date: string | null | undefined) => {
    if (!date) return 'N/A';
    return new Date(date).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const formatCurrency = (amount: number | string | null | undefined) => {
    if (amount === null || amount === undefined) return 'N/A';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(Number(amount));
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      draft: 'bg-gray-100 text-gray-800 border-gray-300',
      pending_signature: 'bg-yellow-100 text-yellow-800 border-yellow-300',
      active: 'bg-green-100 text-green-800 border-green-300',
      expired: 'bg-red-100 text-red-800 border-red-300',
      terminated: 'bg-red-100 text-red-800 border-red-300',
    };
    
    return (
      <span className={`px-2 py-1 rounded text-xs font-medium border ${styles[status] || styles.draft}`}>
        {status.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error || !lease) {
    return (
      <div className="p-8">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 text-red-600">
              <AlertCircle className="h-5 w-5" />
              <div>
                <h3 className="font-semibold">Error Loading Lease</h3>
                <p className="text-sm text-gray-600 mt-1">{error || 'Lease not found'}</p>
              </div>
            </div>
            <div className="mt-4">
              <Button onClick={() => router.push('/leases')} variant="outline">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Leases
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Compact Header */}
      <div className="mb-4 flex justify-between items-center">
        <div className="flex items-center gap-3">
          <Link href="/leases">
            <Button variant="ghost" size="sm" className="h-8">
              <ArrowLeft className="h-4 w-4 mr-1" />
              Back
            </Button>
          </Link>
          <div>
            <div className="text-xs text-gray-500">Lease Agreement</div>
            <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
              <FileSignature className="h-5 w-5" />
              {lease.property?.address || 'Lease Details'}
            </h1>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {getStatusBadge(lease.status)}
          {lease.status === 'draft' && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleDelete}
              className="text-red-600 hover:text-red-700 hover:bg-red-50 h-8"
            >
              <Trash2 className="h-3.5 w-3.5 mr-1" />
              Delete Lease
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Compact Info Cards */}
        <div className="lg:col-span-2 space-y-4">
          {/* Property & Lease Terms - Compact */}
          <Card>
            <CardHeader className="py-3 px-4">
              <CardTitle className="text-sm font-bold flex items-center gap-2">
                <Home className="h-4 w-4" />
                Property & Terms
              </CardTitle>
            </CardHeader>
            <CardContent className="px-4 py-3">
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                <div>
                  <span className="text-gray-500">Address:</span>{' '}
                  <span className="font-medium">{lease.property?.address}</span>
                </div>
                <div>
                  <span className="text-gray-500">State:</span>{' '}
                  <span className="font-medium">{lease.state}</span>
                </div>
                <div>
                  <span className="text-gray-500">Start:</span>{' '}
                  <span className="font-medium">{formatDate(lease.lease_start)}</span>
                </div>
                <div>
                  <span className="text-gray-500">End:</span>{' '}
                  <span className="font-medium">{formatDate(lease.lease_end)}</span>
                </div>
                <div>
                  <span className="text-gray-500">Rent:</span>{' '}
                  <span className="font-medium">{formatCurrency(lease.monthly_rent)}</span>
                </div>
                <div>
                  <span className="text-gray-500">Deposit:</span>{' '}
                  <span className="font-medium">{formatCurrency(lease.security_deposit)}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Tenants - Compact */}
          {lease.tenants && lease.tenants.length > 0 && (
            <Card>
              <CardHeader className="py-3 px-4">
                <CardTitle className="text-sm font-bold flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  Tenants ({lease.tenants.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="px-4 py-3">
                <div className="space-y-2">
                  {lease.tenants.map((tenant: any, index: number) => (
                    <div key={tenant.id || index} className="text-sm border-b last:border-0 pb-2 last:pb-0">
                      <div className="font-medium">
                        {tenant.first_name} {tenant.last_name}
                      </div>
                      {(tenant.email || tenant.phone) && (
                        <div className="text-xs text-gray-600">
                          {tenant.email && <span>{tenant.email}</span>}
                          {tenant.email && tenant.phone && <span className="mx-1">•</span>}
                          {tenant.phone && <span>{tenant.phone}</span>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Additional Details - Compact */}
          {(lease.pets_allowed !== undefined || lease.parking_spaces || lease.utilities_tenant) && (
            <Card>
              <CardHeader className="py-3 px-4">
                <CardTitle className="text-sm font-bold">Additional Details</CardTitle>
              </CardHeader>
              <CardContent className="px-4 py-3">
                <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
                  {lease.pets_allowed !== undefined && (
                    <div>
                      <span className="text-gray-500">Pets:</span>{' '}
                      <span className="font-medium">{lease.pets_allowed ? 'Allowed' : 'Not Allowed'}</span>
                      {lease.pets_allowed && lease.pet_fee_one && (
                        <span className="text-xs text-gray-600 ml-1">
                          ({formatCurrency(lease.pet_fee_one)})
                        </span>
                      )}
                    </div>
                  )}
                  {lease.parking_spaces && (
                    <div>
                      <span className="text-gray-500">Parking:</span>{' '}
                      <span className="font-medium">{lease.parking_spaces} spaces</span>
                    </div>
                  )}
                  {lease.utilities_tenant && (
                    <div className="col-span-2">
                      <span className="text-gray-500">Tenant Utilities:</span>{' '}
                      <span className="text-xs">{lease.utilities_tenant}</span>
                    </div>
                  )}
                  {lease.utilities_landlord && (
                    <div className="col-span-2">
                      <span className="text-gray-500">Landlord Utilities:</span>{' '}
                      <span className="text-xs">{lease.utilities_landlord}</span>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar - Actions & PDF */}
        <div className="space-y-4">
          {/* PDF Actions */}
          <Card>
            <CardHeader className="py-3 px-4">
              <CardTitle className="text-sm font-bold">PDF Actions</CardTitle>
            </CardHeader>
            <CardContent className="px-4 py-3 space-y-2">
              {lease.pdf_url ? (
                <>
                  <ReceiptViewer
                    downloadUrl={lease.pdf_url}
                    fileName={`Lease - ${lease.property?.address || 'Property'}`}
                    fileType="application/pdf"
                    trigger={
                      <Button className="w-full h-9 text-sm" variant="default">
                        <Eye className="h-4 w-4 mr-2" />
                        View PDF
                      </Button>
                    }
                  />
                  <Button 
                    className="w-full h-9 text-sm" 
                    variant="outline"
                    onClick={async () => {
                      // Use proxy endpoint for IE compatibility (forces download via Content-Disposition header)
                      const token = localStorage.getItem('auth_token');
                      const proxyUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/leases/${id}/pdf/proxy`;
                      
                      // Check if browser supports download attribute
                      const supportsDownload = 'download' in document.createElement('a');
                      
                      if (supportsDownload && lease.pdf_url) {
                        // Modern browsers - use direct download
                        const a = document.createElement('a');
                        a.href = lease.pdf_url;
                        a.download = `Lease - ${lease.property?.address || 'Property'}.pdf`;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                      } else {
                        // IE or browsers without download support - use proxy
                        try {
                          const response = await fetch(proxyUrl, {
                            headers: {
                              'Authorization': token ? `Bearer ${token}` : ''
                            }
                          });
                          
                          if (!response.ok) {
                            throw new Error('Download failed');
                          }
                          
                          const blob = await response.blob();
                          const url = window.URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          document.body.appendChild(a);
                          a.click();
                          window.URL.revokeObjectURL(url);
                          document.body.removeChild(a);
                        } catch (err) {
                          console.error('Download error:', err);
                          alert('Failed to download PDF');
                        }
                      }
                    }}
                  >
                    <Download className="h-4 w-4 mr-2" />
                    Download PDF
                  </Button>
                  <Button
                    className="w-full h-9 text-sm"
                    variant="outline"
                    onClick={() => handleGeneratePDF(true)}
                    disabled={generating}
                  >
                    {generating ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Regenerating...
                      </>
                    ) : (
                      <>
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Regenerate PDF
                      </>
                    )}
                  </Button>
                  <Button
                    className="w-full h-9 text-sm text-red-600 hover:text-red-700 hover:bg-red-50"
                    variant="outline"
                    onClick={handleDeletePDF}
                    disabled={deleting}
                  >
                    {deleting ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Deleting...
                      </>
                    ) : (
                      <>
                        <Trash2 className="h-4 w-4 mr-2" />
                        Delete PDF
                      </>
                    )}
                  </Button>
                </>
              ) : (
                <Button
                  className="w-full h-9 text-sm"
                  onClick={() => handleGeneratePDF(false)}
                  disabled={generating}
                >
                  {generating ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <FileText className="h-4 w-4 mr-2" />
                      Generate PDF
                    </>
                  )}
                </Button>
              )}
            </CardContent>
          </Card>

          {/* Lease Info */}
          <Card>
            <CardHeader className="py-3 px-4">
              <CardTitle className="text-sm font-bold">Lease Information</CardTitle>
            </CardHeader>
            <CardContent className="px-4 py-3 space-y-2">
              <div className="text-xs">
                <div className="text-gray-500">Lease ID</div>
                <div className="font-mono text-[10px] break-all">{lease.id}</div>
              </div>
              <div className="text-xs">
                <div className="text-gray-500">Created</div>
                <div>{formatDate(lease.created_at)}</div>
              </div>
              <div className="text-xs">
                <div className="text-gray-500">Last Updated</div>
                <div>{formatDate(lease.updated_at)}</div>
              </div>
              {lease.template_used && (
                <div className="text-xs">
                  <div className="text-gray-500">Template</div>
                  <div>{lease.template_used}</div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
