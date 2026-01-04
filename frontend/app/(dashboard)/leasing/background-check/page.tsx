'use client';

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Upload, FileText, Trash2, Download, Eye } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { useTenants } from '@/lib/hooks/use-tenants';
import { useProperties } from '@/lib/hooks/use-properties';
import { useDocuments, useDeleteDocument, type Document } from '@/lib/hooks/use-documents';
import { apiClient } from '@/lib/api-client';
import { ReceiptViewer } from '@/components/ReceiptViewer';

const DOCUMENT_TYPES = [
  { value: 'credit_report', label: 'Credit Report' },
  { value: 'identity_report', label: 'Identity Report' },
  { value: 'criminal_check', label: 'Criminal Report' },
  { value: 'eviction_report', label: 'Evictions Report' },
  { value: 'income_insights', label: 'Income Insights' },
  { value: 'income_verification', label: 'Income Verification' },
  { value: 'employment_verification', label: 'Employment Verification' },
  { value: 'reference_check', label: 'Reference Check' },
  { value: 'screening_other', label: 'Other Screening Document' },
];

export default function BackgroundCheckPage() {
  const queryClient = useQueryClient();
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>('');
  const [selectedTenantId, setSelectedTenantId] = useState<string>('');
  const [selectedDocType, setSelectedDocType] = useState<string>('credit_report');
  const [displayName, setDisplayName] = useState<string>('');
  const [uploading, setUploading] = useState(false);
  const [fileToUpload, setFileToUpload] = useState<File | null>(null);
  
  const { data: propertiesData } = useProperties();
  const properties = propertiesData?.items || [];
  const { data: tenantsData } = useTenants({ 
    property_id: selectedPropertyId || undefined,
    enabled: !!selectedPropertyId 
  });
  
  // Fetch all documents for the tenant, then filter for background check types
  // This is necessary because existing documents may have sub-types (credit_report, 
  // criminal_check, etc.) instead of the main "background_check" type
  const { data: documentsData, isLoading: docsLoading } = useDocuments({
    property_id: selectedPropertyId || '',
    tenant_id: selectedTenantId || undefined,
    // Don't filter by document_type here - fetch all and filter on frontend
  });
  
  // Filter to only show background check related documents
  // Only documents with document_type = 'background_check' should be shown
  // Documents with document_type = 'other' need to be updated in the database to 'background_check'
  const backgroundCheckTypes = [
    'background_check',
    'credit_report',
    'identity_report',
    'criminal_check',
    'eviction_report',
    'eviction_history',
    'income_insights',
    'income_verification',
    'employment_verification',
    'reference_check',
    'screening_other',
    'screening', // Legacy type
  ];
  
  const allDocuments = documentsData?.items || [];
  
  const documents = allDocuments.filter((doc: Document) => {
    return backgroundCheckTypes.includes(doc.document_type);
  });
  
  const deleteMutation = useDeleteDocument();
  
  const handleUpload = async () => {
    if (!fileToUpload || !selectedTenantId || !selectedPropertyId) return;
    setUploading(true);
    try {
      const uploadFormData = new FormData();
      uploadFormData.append('file', fileToUpload);
      // All documents uploaded from background check page should have document_type = "background_check"
      uploadFormData.append('document_type', 'background_check');
      uploadFormData.append('property_id', selectedPropertyId);
      uploadFormData.append('tenant_id', selectedTenantId);
      
      // Use the selected doc type (credit_report, criminal_check, etc.) as the display_name if no custom name provided
      const finalDisplayName = displayName.trim() || 
        `${DOCUMENT_TYPES.find(t => t.value === selectedDocType)?.label || selectedDocType} - ${fileToUpload.name}`;
      uploadFormData.append('display_name', finalDisplayName);
      
      await apiClient.upload('/documents/upload', uploadFormData);
      
      setFileToUpload(null);
      setDisplayName('');
      const fileInput = document.getElementById('file-upload') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
      
      // Refresh documents list
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    } catch (error) {
      console.error('Upload error:', error);
      alert('Failed to upload document');
    } finally {
      setUploading(false);
    }
  };
  
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };
  
  const getDocTypeLabel = (type: string, displayName?: string) => {
    // If it's a sub-type, return the label
    const subType = DOCUMENT_TYPES.find(t => t.value === type);
    if (subType) {
      return subType.label;
    }
    
    // If it's "background_check", try to extract sub-type from display_name
    if (type === 'background_check' && displayName) {
      // Display name format is typically "Credit Report - filename.pdf"
      // Try to match against known sub-type labels
      for (const docType of DOCUMENT_TYPES) {
        if (displayName.toLowerCase().includes(docType.label.toLowerCase())) {
          return docType.label;
        }
      }
      return 'Background Check';
    }
    
    // Handle legacy "screening" type
    if (type === 'screening') {
      return 'Screening Document';
    }
    
    // Fallback to the type itself
    return type;
  };
  
  const selectedTenant = tenantsData?.tenants.find(t => t.id === selectedTenantId);
  
  return (
    <div className="p-8">
      <div className="mb-6">
        <div className="text-xs text-gray-500 mb-1">Viewing:</div>
        <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Background Check Documents
        </h1>
        <p className="text-sm text-gray-600 mt-1">
          Upload and manage tenant screening documents
        </p>
      </div>
      
      {/* Property & Tenant Selection + Upload Section */}
      <div className="flex flex-col md:flex-row gap-6 mb-6">
        {/* Property & Tenant Card */}
        <Card className="flex-1">
          <CardHeader>
            <CardTitle className="text-sm font-bold">Property & Tenant</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="property-select" className="text-xs">Property *</Label>
              <select
                id="property-select"
                value={selectedPropertyId}
                onChange={(e) => {
                  setSelectedPropertyId(e.target.value);
                  setSelectedTenantId(''); // Reset tenant when property changes
                }}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm mt-1"
              >
                <option value="">Select a property...</option>
                {properties?.map((property) => (
                  <option key={property.id} value={property.id}>
                    {property.display_name || property.address_line1}
                  </option>
                ))}
              </select>
            </div>
            
            {selectedPropertyId && (
              <div>
                <Label htmlFor="tenant-select" className="text-xs">Tenant</Label>
                <Select 
                  value={selectedTenantId} 
                  onValueChange={setSelectedTenantId}
                  disabled={!selectedPropertyId}
                >
                  <SelectTrigger id="tenant-select">
                    <SelectValue placeholder="Choose a tenant..." />
                  </SelectTrigger>
                  <SelectContent>
                    {tenantsData?.tenants?.map((tenant) => (
                      <SelectItem key={tenant.id} value={tenant.id}>
                        {tenant.first_name} {tenant.last_name}
                        {tenant.email && ` (${tenant.email})`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
          </CardContent>
        </Card>
        
        {/* Upload Section */}
        {selectedTenantId && (
          <Card className="flex-1">
            <CardHeader>
              <CardTitle className="text-sm font-bold">Upload Document</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label htmlFor="doc-type" className="text-xs">Document Type</Label>
                <Select value={selectedDocType} onValueChange={setSelectedDocType}>
                  <SelectTrigger id="doc-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DOCUMENT_TYPES.map((type) => (
                      <SelectItem key={type.value} value={type.value}>
                        {type.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div>
                <Label htmlFor="display-name" className="text-xs">Display Name (optional)</Label>
                <Input
                  id="display-name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="e.g., Credit Report - 12/20/2025"
                />
              </div>
              
              <div>
                <Label htmlFor="file-upload" className="text-xs">Choose File</Label>
                <Input
                  id="file-upload"
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png,.gif,.webp"
                  onChange={(e) => setFileToUpload(e.target.files?.[0] || null)}
                  className="cursor-pointer"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Accepted formats: PDF, JPG, PNG, GIF, WEBP (Max 10MB)
                </p>
              </div>
              
              <Button
                onClick={handleUpload}
                disabled={!fileToUpload || uploading}
                className="w-full h-8 text-xs"
              >
                <Upload className="h-3 w-3 mr-2" />
                {uploading ? 'Uploading...' : 'Upload Document'}
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
      
      {/* Documents List */}
      {selectedTenantId && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-bold">
                Background Check Documents ({documents?.length || 0})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {docsLoading ? (
                <div className="text-center py-8 text-gray-500">Loading documents...</div>
              ) : documents && documents.length > 0 ? (
                <div className="space-y-2">
                  {documents.map((doc) => (
                    <div
                      key={doc.id}
                      className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50"
                    >
                      <div className="flex items-center gap-3 flex-1">
                        <FileText className="h-8 w-8 text-blue-600" />
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-sm text-gray-900 truncate">
                            {doc.display_name || doc.file_name}
                          </div>
                          <div className="text-xs text-gray-500">
                            {getDocTypeLabel(doc.document_type, doc.display_name)} • {formatFileSize(doc.file_size || 0)} • {new Date(doc.created_at).toLocaleDateString()}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <ReceiptViewer
                          documentId={doc.id}
                          fileName={doc.display_name || doc.file_name}
                          fileType={doc.file_type}
                          trigger={
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0"
                              title="View"
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          }
                        />
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            if (confirm('Are you sure you want to delete this document?')) {
                              deleteMutation.mutate(doc.id);
                            }
                          }}
                          className="h-8 w-8 p-0 text-red-600 hover:bg-red-50"
                          title="Delete"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500 text-sm">
                  No background check documents found.
                </div>
              )}
            </CardContent>
          </Card>
      )}
      
      {/* Show documents list even when no tenant is selected, but property is selected */}
      {selectedPropertyId && !selectedTenantId && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-bold">
              Background Check Documents ({documents?.length || 0})
            </CardTitle>
          </CardHeader>
          <CardContent>
            {docsLoading ? (
              <div className="text-center py-8 text-gray-500">Loading documents...</div>
            ) : documents && documents.length > 0 ? (
              <div className="space-y-2">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between p-4 border rounded-lg hover:bg-gray-50"
                  >
                    <div className="flex items-center gap-3 flex-1">
                      <FileText className="h-8 w-8 text-blue-600" />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm text-gray-900 truncate">
                          {doc.display_name || doc.file_name}
                        </div>
                        <div className="text-xs text-gray-500">
                          {getDocTypeLabel(doc.document_type, doc.display_name)} • {formatFileSize(doc.file_size || 0)} • {new Date(doc.created_at).toLocaleDateString()}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <ReceiptViewer
                        documentId={doc.id}
                        fileName={doc.display_name || doc.file_name}
                        fileType={doc.file_type}
                        trigger={
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0"
                            title="View"
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        }
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (confirm('Are you sure you want to delete this document?')) {
                            deleteMutation.mutate(doc.id);
                          }
                        }}
                        className="h-8 w-8 p-0 text-red-600 hover:bg-red-50"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500 text-sm">
                No background check documents found for this property. Select a tenant to upload documents.
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

