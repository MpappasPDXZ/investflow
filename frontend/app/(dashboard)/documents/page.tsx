'use client';

import { useState, useMemo } from 'react';
import { useDocuments, useDeleteDocument } from '@/lib/hooks/use-documents';
import { useProperties } from '@/lib/hooks/use-properties';
import { DocumentUpload } from '@/components/DocumentUpload';
import { ReceiptViewer } from '@/components/ReceiptViewer';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { 
  FileText, 
  Image, 
  Upload, 
  Trash2, 
  Download,
  Grid3X3,
  List,
  Search,
  Filter,
  FolderOpen,
  File,
  ChevronDown,
  ChevronRight,
  X
} from 'lucide-react';
import { format } from 'date-fns';
import type { Document } from '@/lib/types';

// Note: receipts and invoices are managed in Expenses, not here
type DocumentType = 'all' | 'lease' | 'screening' | 'other';
type ViewMode = 'grid' | 'list';

const documentTypeLabels: Record<string, string> = {
  lease: 'Leases',
  screening: 'Screenings',
  other: 'Other',
};

const documentTypeColors: Record<string, string> = {
  lease: 'bg-blue-100 text-blue-800 border-blue-200',
  screening: 'bg-purple-100 text-purple-800 border-purple-200',
  other: 'bg-gray-100 text-gray-800 border-gray-200',
};

export default function DocumentsPage() {
  const [selectedType, setSelectedType] = useState<DocumentType>('all');
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [selectedDocuments, setSelectedDocuments] = useState<Set<string>>(new Set());

  const { data: properties } = useProperties();
  const { data: documents, isLoading, refetch } = useDocuments({
    property_id: selectedPropertyId || undefined,
    document_type: selectedType === 'all' ? undefined : selectedType,
  });
  const deleteDocument = useDeleteDocument();

  // Filter documents by search query and exclude receipts & invoices (those are in Expenses)
  const filteredDocuments = useMemo(() => {
    if (!documents?.items) return [];
    
    // Always exclude receipts and invoices - they belong in Expenses
    let docs = documents.items.filter(doc => 
      doc.document_type !== 'receipt' && doc.document_type !== 'invoice'
    );
    
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      docs = docs.filter(doc => doc.file_name.toLowerCase().includes(query));
    }
    
    return docs;
  }, [documents, searchQuery]);

  // Group documents by type for stats (excluding receipts and invoices)
  const documentStats = useMemo(() => {
    if (!documents?.items) return {};
    
    const stats: Record<string, number> = {};
    documents.items
      .filter(doc => doc.document_type !== 'receipt' && doc.document_type !== 'invoice')
      .forEach(doc => {
        const type = doc.document_type || 'other';
        stats[type] = (stats[type] || 0) + 1;
      });
    return stats;
  }, [documents]);

  const handleDelete = async (doc: Document) => {
    if (confirm(`Delete "${doc.file_name}"? This cannot be undone.`)) {
      await deleteDocument.mutateAsync(doc.id);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedDocuments.size === 0) return;
    
    if (confirm(`Delete ${selectedDocuments.size} selected documents? This cannot be undone.`)) {
      for (const docId of selectedDocuments) {
        await deleteDocument.mutateAsync(docId);
      }
      setSelectedDocuments(new Set());
    }
  };

  const toggleDocumentSelection = (docId: string) => {
    setSelectedDocuments(prev => {
      const newSet = new Set(prev);
      if (newSet.has(docId)) {
        newSet.delete(docId);
      } else {
        newSet.add(docId);
      }
      return newSet;
    });
  };

  const selectAllDocuments = () => {
    if (selectedDocuments.size === filteredDocuments.length) {
      setSelectedDocuments(new Set());
    } else {
      setSelectedDocuments(new Set(filteredDocuments.map(d => d.id)));
    }
  };

  const isImage = (doc: Document) => 
    doc.file_type?.startsWith('image/') || doc.file_name.match(/\.(jpg|jpeg|png|gif|webp)$/i);
  
  const isPdf = (doc: Document) => 
    doc.file_type === 'application/pdf' || doc.file_name.match(/\.pdf$/i);

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const tabs: { value: DocumentType; label: string }[] = [
    { value: 'all', label: 'All' },
    { value: 'lease', label: 'Leases' },
    { value: 'screening', label: 'Screenings' },
    { value: 'other', label: 'Other' },
  ];

  return (
    <div className="p-4 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-start mb-4">
        <div>
          <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <FolderOpen className="h-4 w-4" />
            Documents
          </h1>
          <p className="text-xs text-gray-600 mt-0.5">
            Manage receipts, leases, and other property documents
          </p>
        </div>
        <Button 
          size="sm"
          onClick={() => setShowUploadModal(true)}
          className="bg-black text-white hover:bg-gray-800"
        >
          <Upload className="h-3.5 w-3.5 mr-1.5" />
          Upload
        </Button>
      </div>

      {/* Document Type Tabs */}
      <div className="flex gap-1.5 mb-4 overflow-x-auto pb-1">
        {tabs.map(tab => {
          const count = tab.value === 'all' 
            ? filteredDocuments.length
            : documentStats[tab.value] || 0;
          
          return (
            <button
              key={tab.value}
              onClick={() => setSelectedType(tab.value)}
              className={`
                px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-all
                ${selectedType === tab.value 
                  ? 'bg-black text-white shadow-sm' 
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }
              `}
            >
              {tab.label}
              <span className={`ml-1.5 px-1 py-0.5 rounded text-xs ${
                selectedType === tab.value ? 'bg-white/20' : 'bg-gray-200'
              }`}>
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Filters & Actions Bar */}
      <Card className="mb-4">
        <CardContent className="py-2.5 px-3">
          <div className="flex flex-wrap items-center gap-3">
            {/* Search */}
            <div className="flex-1 min-w-[180px] max-w-sm relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search..."
                className="w-full pl-8 pr-3 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>

            {/* Property Filter */}
            <select
              value={selectedPropertyId}
              onChange={(e) => setSelectedPropertyId(e.target.value)}
              className="px-2 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-black"
            >
              <option value="">All Properties</option>
              {properties?.items.map((prop) => (
                <option key={prop.id} value={prop.id}>
                  {prop.display_name || prop.address_line1 || prop.id}
                </option>
              ))}
            </select>

            {/* View Mode Toggle */}
            <div className="flex items-center border rounded-md overflow-hidden">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 ${viewMode === 'grid' ? 'bg-gray-100' : 'hover:bg-gray-50'}`}
              >
                <Grid3X3 className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-1.5 ${viewMode === 'list' ? 'bg-gray-100' : 'hover:bg-gray-50'}`}
              >
                <List className="h-3.5 w-3.5" />
              </button>
            </div>

            {/* Bulk Actions */}
            {selectedDocuments.size > 0 && (
              <div className="flex items-center gap-2 ml-auto">
                <span className="text-xs text-gray-600">
                  {selectedDocuments.size} selected
                </span>
                <Button
                  variant="destructive"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={handleBulkDelete}
                >
                  <Trash2 className="h-3.5 w-3.5 mr-1" />
                  Delete
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => setSelectedDocuments(new Set())}
                >
                  Clear
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Documents Content */}
      <Card>
        <CardContent className="p-3">
          {isLoading ? (
            <div className="text-center py-8 text-gray-500 text-sm">
              <div className="animate-pulse">Loading documents...</div>
            </div>
          ) : filteredDocuments.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <FileText className="h-12 w-12 mx-auto text-gray-300 mb-3" />
              <p className="text-sm font-medium text-gray-600 mb-1">No documents found</p>
              <p className="text-xs text-gray-500 mb-3">
                {searchQuery ? 'Try a different search term' : 'Upload your first document to get started'}
              </p>
              <Button size="sm" onClick={() => setShowUploadModal(true)}>
                <Upload className="h-3.5 w-3.5 mr-1.5" />
                Upload
              </Button>
            </div>
          ) : viewMode === 'grid' ? (
            /* Grid View */
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3">
              {filteredDocuments.map(doc => (
                <div
                  key={doc.id}
                  className={`
                    group relative border rounded-md p-2 hover:shadow-md transition-all cursor-pointer
                    ${selectedDocuments.has(doc.id) ? 'ring-2 ring-blue-500 bg-blue-50' : 'hover:border-gray-400'}
                  `}
                >
                  {/* Selection Checkbox */}
                  <div className="absolute top-1.5 left-1.5 z-10">
                    <input
                      type="checkbox"
                      checked={selectedDocuments.has(doc.id)}
                      onChange={() => toggleDocumentSelection(doc.id)}
                      className="h-3.5 w-3.5 rounded border-gray-300"
                      onClick={(e) => e.stopPropagation()}
                    />
                  </div>

                  {/* Document Preview */}
                  <ReceiptViewer
                    documentId={doc.id}
                    fileName={doc.file_name}
                    fileType={doc.file_type}
                    trigger={
                      <div className="aspect-square mb-2 bg-gray-100 rounded flex items-center justify-center overflow-hidden">
                        {isImage(doc) ? (
                          <Image className="h-8 w-8 text-blue-400" />
                        ) : isPdf(doc) ? (
                          <FileText className="h-8 w-8 text-red-400" />
                        ) : (
                          <File className="h-8 w-8 text-gray-400" />
                        )}
                      </div>
                    }
                  />

                  {/* Document Info */}
                  <div>
                    <p className="text-xs font-medium text-gray-900 truncate" title={doc.file_name}>
                      {doc.file_name}
                    </p>
                    <div className="flex items-center justify-between mt-0.5">
                      <span className={`text-[10px] px-1 py-0.5 rounded ${documentTypeColors[doc.document_type] || documentTypeColors.other}`}>
                        {documentTypeLabels[doc.document_type] || 'Other'}
                      </span>
                      <span className="text-[10px] text-gray-500">
                        {formatFileSize(doc.file_size)}
                      </span>
                    </div>
                    <div className="flex items-center justify-between mt-0.5 text-[10px] text-gray-400">
                      <span>{format(new Date(doc.uploaded_at || doc.created_at), 'M/d/yy')}</span>
                      <span>{doc.file_type?.split('/')[1]?.toUpperCase() || 'FILE'}</span>
                    </div>
                  </div>

                  {/* Hover Actions */}
                  <div className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(doc);
                      }}
                      className="p-1 bg-white rounded shadow-sm hover:bg-red-50 hover:text-red-600 transition-colors"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            /* List View */
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="pb-2 pl-2 w-6">
                      <input
                        type="checkbox"
                        checked={selectedDocuments.size === filteredDocuments.length && filteredDocuments.length > 0}
                        onChange={selectAllDocuments}
                        className="h-3.5 w-3.5 rounded border-gray-300"
                      />
                    </th>
                    <th className="pb-2 text-xs font-medium text-gray-600">Name</th>
                    <th className="pb-2 text-xs font-medium text-gray-600">Type</th>
                    <th className="pb-2 text-xs font-medium text-gray-600">Size</th>
                    <th className="pb-2 text-xs font-medium text-gray-600">Uploaded</th>
                    <th className="pb-2 text-xs font-medium text-gray-600 w-[80px]">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDocuments.map(doc => (
                    <tr key={doc.id} className="border-b hover:bg-gray-50">
                      <td className="py-2 pl-2">
                        <input
                          type="checkbox"
                          checked={selectedDocuments.has(doc.id)}
                          onChange={() => toggleDocumentSelection(doc.id)}
                          className="h-3.5 w-3.5 rounded border-gray-300"
                        />
                      </td>
                      <td className="py-2">
                        <div className="flex items-center gap-2">
                          <div className="h-6 w-6 bg-gray-100 rounded flex items-center justify-center flex-shrink-0">
                            {isImage(doc) ? (
                              <Image className="h-3.5 w-3.5 text-blue-400" />
                            ) : isPdf(doc) ? (
                              <FileText className="h-3.5 w-3.5 text-red-400" />
                            ) : (
                              <File className="h-3.5 w-3.5 text-gray-400" />
                            )}
                          </div>
                          <span className="text-xs font-medium text-gray-900 truncate max-w-[200px]">
                            {doc.file_name}
                          </span>
                        </div>
                      </td>
                      <td className="py-2">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${documentTypeColors[doc.document_type] || documentTypeColors.other}`}>
                          {documentTypeLabels[doc.document_type] || 'Other'}
                        </span>
                      </td>
                      <td className="py-2 text-xs text-gray-600">
                        {formatFileSize(doc.file_size)}
                      </td>
                      <td className="py-2 text-xs text-gray-600">
                        {format(new Date(doc.created_at), 'MMM d')}
                      </td>
                      <td className="py-2">
                        <div className="flex items-center gap-1">
                          <ReceiptViewer
                            documentId={doc.id}
                            fileName={doc.file_name}
                            fileType={doc.file_type}
                          />
                          <button
                            onClick={() => handleDelete(doc)}
                            className="text-gray-400 hover:text-red-600 transition-colors p-0.5"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Upload Modal */}
      <Dialog open={showUploadModal} onOpenChange={setShowUploadModal}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm">
              <Upload className="h-4 w-4" />
              Upload Document
            </DialogTitle>
          </DialogHeader>
          <div className="py-2">
            {/* Property Selector */}
            <div className="mb-3">
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Property (optional)
              </label>
              <select
                value={selectedPropertyId}
                onChange={(e) => setSelectedPropertyId(e.target.value)}
                className="w-full px-2 py-1.5 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-black"
              >
                <option value="">No property</option>
                {properties?.items.map((prop) => (
                  <option key={prop.id} value={prop.id}>
                    {prop.display_name || prop.address_line1 || prop.id}
                  </option>
                ))}
              </select>
            </div>

            <DocumentUpload
              propertyId={selectedPropertyId || undefined}
              documentType={selectedType === 'all' ? 'lease' : selectedType}
              hideReceiptOption={true}
              onUploadSuccess={() => {
                setShowUploadModal(false);
                refetch();
              }}
            />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

