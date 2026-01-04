"use client";

import { useState, useEffect, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  FileText,
  Trash2,
  Download,
  Loader2,
  Building2,
  Image,
  FileIcon,
  Eye,
  Pencil,
  Plus,
} from "lucide-react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { ReceiptViewer } from "@/components/ReceiptViewer";
import { useDocuments, useDeleteDocument } from "@/lib/hooks/use-documents";
import { useProperties } from "@/lib/hooks/use-properties";
import { useTenants, useTenant } from "@/lib/hooks/use-tenants";
import { useUnits } from "@/lib/hooks/use-units";
import { useQueryClient } from "@tanstack/react-query";

interface Document {
  id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  document_type: string;
  property_id?: string;
  unit_id?: string;
  tenant_id?: string;
  display_name?: string;
  uploaded_at: string;
  created_at: string;
  blob_location: string;
}

interface Property {
  id: string;
  display_name?: string;
  address_line1?: string;
  city?: string;
  state?: string;
}

const DOCUMENT_TYPES = [
  { value: "receipt", label: "Receipt" },
  { value: "lease", label: "Lease" },
  { value: "background_check", label: "Background Check" },
  { value: "contract", label: "Contract" },
  { value: "invoice", label: "Invoice" },
  { value: "inspection", label: "Inspection" },
  { value: "photo", label: "Property Photo" },
  { value: "other", label: "Other" },
];

// Photo types vs Document types for filtering
const PHOTO_TYPES = ["photo", "inspection"];
// Exclude background_check - those are shown on the background check page only
const DOCUMENT_TYPES_FILTER = ["receipt", "lease", "contract", "invoice", "other"];

export default function DocumentsPage() {
  const searchParams = useSearchParams();
  const typeFilter = searchParams.get("type"); // "document" | "photo" | null (all)
  
  const [selectedPropertyId, setSelectedPropertyId] = useState<string>("");
  const { data: propertiesData } = useProperties();
  const { data: documentsData, isLoading } = useDocuments(
    selectedPropertyId ? { property_id: selectedPropertyId } : { property_id: "" }
  );
  const deleteDocument = useDeleteDocument();
  const queryClient = useQueryClient();

  const properties = propertiesData?.items || [];
  const allDocuments = documentsData?.items || [];
  
  // Filter out receipt documents - those are managed via Expenses page
  const documents = allDocuments.filter((doc: Document) => doc.document_type !== "receipt");

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingDoc, setEditingDoc] = useState<Document | null>(null);
  const [editForm, setEditForm] = useState({
    display_name: "",
    property_id: "",
    unit_id: "",
    tenant_id: "",
    document_type: "",
  });
  const [saving, setSaving] = useState(false);
  
  // Fetch tenants for the property - use editingDoc.property_id if available, otherwise use editForm.property_id
  // This ensures tenants load immediately when dialog opens
  const propertyIdForTenants = editingDoc?.property_id || editForm.property_id;
  const { data: editTenantsData } = useTenants(
    propertyIdForTenants && propertyIdForTenants !== "unassigned" 
      ? { property_id: propertyIdForTenants } 
      : undefined
  );
  const editTenants = editTenantsData?.tenants || [];
  
  // If document has a tenant_id but tenant is not in the list, fetch it individually
  const documentTenantId = editingDoc?.tenant_id;
  const { data: documentTenantData } = useTenant(documentTenantId || "");
  const documentTenant = documentTenantData;
  
  // Combine tenants list with the document's tenant if it's not already in the list
  const allEditTenants = useMemo(() => {
    const tenantMap = new Map(editTenants.map(t => [t.id, t]));
    // If document has a tenant that's not in the property's tenant list, add it
    if (documentTenant && documentTenant.id && !tenantMap.has(documentTenant.id)) {
      tenantMap.set(documentTenant.id, documentTenant);
    }
    return Array.from(tenantMap.values());
  }, [editTenants, documentTenant]);
  
  const { data: editUnitsData } = useUnits(editForm.property_id && editForm.property_id !== "unassigned" ? editForm.property_id : "");
  const allEditUnits = editUnitsData?.items || [];
  
  // Get units for the currently selected property in the edit form (for multi-family properties)
  const editFormPropertyUnits = useMemo(() => {
    if (!editForm.property_id || editForm.property_id === "unassigned") return [];
    return allEditUnits.filter(u => u.property_id === editForm.property_id);
  }, [allEditUnits, editForm.property_id]);

  const handleDelete = async (documentId: string) => {
    if (!confirm("Delete this document?")) return;
    try {
      await deleteDocument.mutateAsync(documentId);
    } catch (err) {
      console.error("Error deleting document:", err);
      alert("Failed to delete document");
    }
  };

  const handleDownload = async (doc: Document) => {
    try {
      // Use proxy endpoint for IE compatibility (forces download via Content-Disposition header)
      const token = localStorage.getItem('auth_token');
      const proxyUrl = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/documents/${doc.id}/proxy`;
      
      // Check if browser supports download attribute
      const supportsDownload = 'download' in document.createElement('a');
      
      // Get direct download URL as fallback
      const response = (await apiClient.get(`/documents/${doc.id}/download`)) as any;
      const downloadUrl = response.download_url || response.data?.download_url;
      
      if (supportsDownload && downloadUrl) {
        // Modern browsers - use direct download
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = doc.display_name || doc.file_name || 'document';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      } else {
        // IE or browsers without download support - use proxy
        const proxyResponse = await fetch(proxyUrl, {
          headers: {
            'Authorization': token ? `Bearer ${token}` : ''
          }
        });
        
        if (!proxyResponse.ok) {
          throw new Error('Download failed');
        }
        
        const blob = await proxyResponse.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        // Don't set a.download - proxy already sets Content-Disposition header
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (err) {
      console.error("Error downloading:", err);
      alert('Failed to download document');
    }
  };

  const openEditDialog = (doc: Document) => {
    setEditingDoc(doc);
    setEditForm({
      display_name: doc.display_name || "",
      property_id: doc.property_id || "unassigned",
      unit_id: doc.unit_id || "",
      tenant_id: doc.tenant_id || "",
      document_type: doc.document_type || "other",
    });
    setEditDialogOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!editingDoc) return;

    setSaving(true);
    try {
      // Build updateData in vault table field order (backend will merge and reorder):
      // id, user_id, property_id, unit_id, blob_location, container_name, blob_name,
      // file_name, file_type, document_type, document_metadata, display_name, tenant_id,
      // is_deleted, file_size, uploaded_at, expires_at, created_at, updated_at
      const updateData: any = {};

      // Handle property assignment (required field)
      // Backend requires property_id even when clear_property is true
      if (editForm.property_id === "unassigned") {
        updateData.clear_property = true;
        // Still need to send a property_id for validation, use the original if available
        // or the first property as fallback
        if (editingDoc.property_id) {
          updateData.property_id = editingDoc.property_id;
        } else if (properties.length > 0) {
          updateData.property_id = properties[0].id;
        } else {
          throw new Error("Cannot unassign property: no property available for validation");
        }
      } else if (editForm.property_id && editForm.property_id !== editingDoc.property_id) {
        updateData.property_id = editForm.property_id;
      } else if (editingDoc.property_id) {
        // Always send property_id (required)
        updateData.property_id = editingDoc.property_id;
      } else if (editForm.property_id) {
        // Use the form property_id if document doesn't have one
        updateData.property_id = editForm.property_id;
      } else {
        // Fallback to first property if nothing else available
        if (properties.length > 0) {
          updateData.property_id = properties[0].id;
        } else {
          throw new Error("Property ID is required");
        }
      }
      
      // Handle unit assignment - only send if changed
      const currentUnitId = editingDoc.unit_id || "";
      if (editForm.unit_id !== currentUnitId) {
        updateData.unit_id = editForm.unit_id || null;
      }
      
      // Handle tenant assignment - only send if changed
      const currentTenantId = editingDoc.tenant_id || "";
      if (editForm.tenant_id !== currentTenantId) {
        updateData.tenant_id = editForm.tenant_id || null;
      }

      // Only include document_type if it has a value
      if (editForm.document_type) {
        updateData.document_type = editForm.document_type;
      }

      // Only include display_name if it has content
      if (editForm.display_name.trim()) {
        updateData.display_name = editForm.display_name.trim();
      }

      console.log("[DOCUMENT] 📤 Updating document:", editingDoc.id);
      console.log("[DOCUMENT] 📤 Update payload:", updateData);
      console.log("[DOCUMENT] 📤 Payload field order:", Object.keys(updateData));
      console.log("[DOCUMENT] 📤 Payload VALUES:");
      Object.entries(updateData).forEach(([key, value]) => {
        console.log(`  ${key}: ${value} (type: ${typeof value})`);
      });

      const response = (await apiClient.patch(
        `/documents/${editingDoc.id}`,
        updateData
      )) as Document;
      
      console.log("[DOCUMENT] ✅ Update response:", response);

      // Optimistically update the local state instead of refetching all documents
      queryClient.setQueryData(['documents', { property_id: selectedPropertyId }], (oldData: any) => {
        if (!oldData) return oldData;
        return {
          ...oldData,
          items: oldData.items.map((doc: Document) => 
            doc.id === editingDoc.id ? { ...doc, ...response } : doc
          )
        };
      });

      setEditDialogOpen(false);
      setEditingDoc(null);
    } catch (err) {
      console.error("Error updating document:", err);
      alert("Failed to update document");
    } finally {
      setSaving(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (!bytes) return "-";
    const k = 1024;
    const sizes = ["B", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + sizes[i];
  };

  const formatDate = (dateString: string) => {
    if (!dateString) return "-";
    return new Date(dateString).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "2-digit",
    });
  };

  const getPropertyName = (propertyId?: string) => {
    if (!propertyId) return "Unassigned";
    const prop = properties.find((p) => p.id === propertyId);
    if (!prop) return "Unknown";
    return prop.display_name || `${prop.address_line1}, ${prop.city}` || "Property";
  };

  const getFileIcon = (fileType: string) => {
    if (fileType?.startsWith("image/")) return <Image className="h-3.5 w-3.5" />;
    if (fileType?.includes("pdf")) return <FileText className="h-3.5 w-3.5" />;
    return <FileIcon className="h-3.5 w-3.5" />;
  };

  const getDocTypeBadge = (docType: string) => {
    const colors: Record<string, string> = {
      receipt: "bg-green-100 text-green-800",
      lease: "bg-blue-100 text-blue-800",
      contract: "bg-purple-100 text-purple-800",
      background_check: "bg-orange-100 text-orange-800",
      invoice: "bg-cyan-100 text-cyan-800",
      other: "bg-gray-100 text-gray-800",
    };
    return colors[docType] || colors.other;
  };

  const getDisplayName = (doc: Document) => {
    return doc.display_name || doc.file_name;
  };

  // Remove the eager photo URL fetching - ReceiptViewer now handles lazy loading

  // Filter documents by type (from URL)
  const filteredDocs = typeFilter === "photo"
    ? documents.filter((d) => PHOTO_TYPES.includes(d.document_type))
    : typeFilter === "document"
    ? documents.filter((d) => 
        DOCUMENT_TYPES_FILTER.includes(d.document_type) && 
        d.document_type !== "background_check" // Explicitly exclude background checks
      )
    : documents; // Show all if no filter

  // Group photos by property (similar to expenses page)
  const photosByProperty = typeFilter === "photo" ? 
    filteredDocs.reduce((acc, doc) => {
      const key = doc.property_id || "unassigned";
      if (!acc[key]) acc[key] = [];
      acc[key].push(doc);
      return acc;
    }, {} as Record<string, Document[]>) 
    : {};

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // Show property selection if no property is selected
  if (!selectedPropertyId) {
    return (
      <div className="p-8">
        <div className="mb-6">
          <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            {typeFilter === "photo" ? (
              <><Image className="h-5 w-5" /> Photos</>
            ) : typeFilter === "document" ? (
              <><FileText className="h-5 w-5" /> Documents</>
            ) : (
              <><FileText className="h-5 w-5" /> Vault</>
            )}
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            Select a property to view documents
          </p>
        </div>
        <Card>
          <CardContent className="p-6">
            <Label htmlFor="property-select" className="text-sm font-medium mb-2 block">
              Select Property
            </Label>
            <select
              id="property-select"
              value={selectedPropertyId}
              onChange={(e) => setSelectedPropertyId(e.target.value)}
              className="px-2 py-1.5 border border-gray-300 rounded text-sm w-full"
              required
            >
              <option value="">Select Property</option>
              {properties.map((prop) => (
                <option key={prop.id} value={prop.id}>
                  {prop.display_name || prop.address_line1 || prop.id}
                </option>
              ))}
            </select>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header - Compact */}
      <div className="mb-6 flex justify-between items-start">
        <div>
          <div className="text-xs text-gray-500 mb-1">Viewing:</div>
          <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            {typeFilter === "photo" ? (
              <><Image className="h-5 w-5" /> Photos</>
            ) : typeFilter === "document" ? (
              <><FileText className="h-5 w-5" /> Documents</>
            ) : (
              <><FileText className="h-5 w-5" /> Vault</>
            )}
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            {filteredDocs.length} {typeFilter === "photo" ? "photos" : typeFilter === "document" ? "documents" : "files"}
          </p>
        </div>
        <div className="flex items-center gap-2">
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
          <Link href={`/documents/add?property_id=${selectedPropertyId}`}>
            <Button className="bg-black text-white hover:bg-gray-800 h-7 text-xs px-2">
              <Plus className="h-3 w-3 mr-1" />
              Add Document
            </Button>
          </Link>
        </div>
      </div>

      {/* Photo Table View - Organized by Property */}
      {typeFilter === "photo" ? (
        Object.entries(photosByProperty).length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center py-8">
              <Image className="h-10 w-10 text-muted-foreground mb-3" />
              <p className="text-muted-foreground text-sm">
                No photos yet. Add photos from the vault.
              </p>
            </CardContent>
          </Card>
        ) : (
          Object.entries(photosByProperty).map(([propertyId, docs]) => (
            <Card key={propertyId} className="overflow-hidden">
            <CardHeader className="py-3 px-4 bg-muted/50">
              <CardTitle className="text-sm font-bold flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                {propertyId === "unassigned"
                  ? "Unassigned Photos"
                  : getPropertyName(propertyId)}
                <Badge variant="secondary" className="ml-auto text-xs">
                  {docs.length}
                </Badge>
              </CardTitle>
            </CardHeader>
              
              {/* Desktop Table View */}
              <div className="hidden md:block">
                <Table>
                  <TableHeader>
                    <TableRow className="text-xs">
                      <TableHead className="w-[35%] text-xs">Name</TableHead>
                      <TableHead className="w-[15%] text-xs">Type</TableHead>
                      <TableHead className="w-[12%] text-xs">Date</TableHead>
                      <TableHead className="w-[38%] text-right text-xs">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {docs.map((doc) => (
                      <TableRow key={doc.id} className="text-xs">
                        <TableCell className="py-2">
                          <div className="flex items-center gap-2">
                            <Image className="h-3.5 w-3.5 text-muted-foreground" />
                            <div className="flex flex-col">
                              <span
                                className="truncate max-w-[220px] font-medium text-xs"
                                title={getDisplayName(doc)}
                              >
                                {getDisplayName(doc)}
                              </span>
                              {doc.display_name && (
                                <span
                                  className="text-[10px] text-muted-foreground truncate max-w-[220px]"
                                  title={doc.file_name}
                                >
                                  {doc.file_name}
                                </span>
                              )}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell className="py-2">
                          <Badge
                            variant="outline"
                            className={`text-[10px] ${getDocTypeBadge(doc.document_type)}`}
                          >
                            {doc.document_type}
                          </Badge>
                        </TableCell>
                        <TableCell className="py-2 text-muted-foreground text-xs">
                          {formatDate(doc.created_at || doc.uploaded_at)}
                        </TableCell>
                        <TableCell className="py-2 text-right">
                          <div className="flex justify-end gap-1">
                            <ReceiptViewer
                              documentId={doc.id}
                              fileName={getDisplayName(doc)}
                              fileType={doc.file_type}
                              trigger={
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 w-7 p-0"
                                  title="View photo"
                                >
                                  <Eye className="h-3.5 w-3.5" />
                                </Button>
                              }
                            />
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0"
                              onClick={() => openEditDialog(doc)}
                              title="Edit"
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0"
                              onClick={() => handleDownload(doc)}
                              title="Download"
                            >
                              <Download className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                              onClick={() => handleDelete(doc.id)}
                              title="Delete"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              
              {/* Mobile Card View */}
              <div className="md:hidden divide-y">
                {docs.map((doc) => (
                  <div key={doc.id} className="p-4 space-y-3">
                    <div className="flex items-start gap-3">
                      <div className="p-2 bg-muted rounded-lg">
                        <Image className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate" title={getDisplayName(doc)}>
                          {getDisplayName(doc)}
                        </p>
                        {doc.display_name && (
                          <p className="text-xs text-muted-foreground truncate" title={doc.file_name}>
                            {doc.file_name}
                          </p>
                        )}
                        <div className="flex items-center gap-2 mt-1">
                          <Badge
                            variant="outline"
                            className={`text-xs ${getDocTypeBadge(doc.document_type)}`}
                          >
                            {doc.document_type}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            {formatDate(doc.created_at || doc.uploaded_at)}
                          </span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex justify-end gap-2">
                      <ReceiptViewer
                        documentId={doc.id}
                        fileName={getDisplayName(doc)}
                        fileType={doc.file_type}
                        trigger={
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-10 px-3"
                          >
                            <Eye className="h-4 w-4 mr-1.5" />
                            View
                          </Button>
                        }
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-10 px-3"
                        onClick={() => openEditDialog(doc)}
                      >
                        <Pencil className="h-4 w-4 mr-1.5" />
                        Edit
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-10 px-3"
                        onClick={() => handleDownload(doc)}
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-10 px-3 text-destructive hover:text-destructive border-destructive/30"
                        onClick={() => handleDelete(doc.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          ))
        )
      ) : documents.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center py-8">
            <FileText className="h-10 w-10 text-muted-foreground mb-3" />
            <p className="text-muted-foreground text-sm">
              No documents yet. Upload receipts when adding expenses.
            </p>
          </CardContent>
        </Card>
      ) : (
        /* Documents for selected property */
        <Card className="overflow-hidden">
          <CardHeader className="py-3 px-4 bg-muted/50">
            <CardTitle className="text-sm font-bold flex items-center gap-2">
              <Building2 className="h-4 w-4" />
              {getPropertyName(selectedPropertyId)}
              <Badge variant="secondary" className="ml-auto text-xs">
                {filteredDocs.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          
          {/* Desktop Table View */}
          <div className="hidden md:block">
            <Table>
              <TableHeader>
                <TableRow className="text-xs">
                  <TableHead className="w-[35%] text-xs">Name</TableHead>
                  <TableHead className="w-[12%] text-xs">Type</TableHead>
                  <TableHead className="w-[10%] text-xs">Size</TableHead>
                  <TableHead className="w-[12%] text-xs">Date</TableHead>
                  <TableHead className="w-[31%] text-right text-xs">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredDocs.map((doc: Document) => (
                    <TableRow key={doc.id} className="text-xs">
                      <TableCell className="py-2">
                        <div className="flex items-center gap-2">
                          {getFileIcon(doc.file_type)}
                          <div className="flex flex-col">
                            <span
                              className="truncate max-w-[220px] font-medium text-xs"
                              title={getDisplayName(doc)}
                            >
                              {getDisplayName(doc)}
                            </span>
                            {doc.display_name && (
                              <span
                                className="text-[10px] text-muted-foreground truncate max-w-[220px]"
                                title={doc.file_name}
                              >
                                {doc.file_name}
                              </span>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="py-2">
                        <Badge
                          variant="outline"
                          className={`text-[10px] ${getDocTypeBadge(doc.document_type)}`}
                        >
                          {doc.document_type}
                        </Badge>
                      </TableCell>
                      <TableCell className="py-2 text-muted-foreground text-xs">
                        {formatFileSize(doc.file_size)}
                      </TableCell>
                      <TableCell className="py-2 text-muted-foreground text-xs">
                        {formatDate(doc.created_at || doc.uploaded_at)}
                      </TableCell>
                      <TableCell className="py-2 text-right">
                        <div className="flex justify-end gap-1">
                          <ReceiptViewer
                            documentId={doc.id}
                            fileName={getDisplayName(doc)}
                            fileType={doc.file_type}
                            trigger={
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-7 w-7 p-0"
                                title="View document"
                              >
                                <Eye className="h-3.5 w-3.5" />
                              </Button>
                            }
                          />
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0"
                            onClick={() => openEditDialog(doc)}
                            title="Edit document"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0"
                            onClick={() => handleDownload(doc)}
                            title="Download"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                            onClick={() => handleDelete(doc.id)}
                            title="Delete"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            
            {/* Mobile Card View */}
            <div className="md:hidden divide-y">
              {filteredDocs.map((doc: Document) => (
                <div key={doc.id} className="p-4 space-y-3">
                  {/* Document Info */}
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-muted rounded-lg">
                      {getFileIcon(doc.file_type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate" title={getDisplayName(doc)}>
                        {getDisplayName(doc)}
                      </p>
                      {doc.display_name && (
                        <p className="text-xs text-muted-foreground truncate" title={doc.file_name}>
                          {doc.file_name}
                        </p>
                      )}
                      <div className="flex items-center gap-2 mt-1">
                        <Badge
                          variant="outline"
                          className={`text-xs ${getDocTypeBadge(doc.document_type)}`}
                        >
                          {doc.document_type}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {formatFileSize(doc.file_size)}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {formatDate(doc.created_at || doc.uploaded_at)}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  {/* Action Buttons - Mobile Friendly */}
                  <div className="flex justify-end gap-2">
                    <ReceiptViewer
                      documentId={doc.id}
                      fileName={getDisplayName(doc)}
                      fileType={doc.file_type}
                      trigger={
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-10 px-3"
                        >
                          <Eye className="h-4 w-4 mr-1.5" />
                          View
                        </Button>
                      }
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-10 px-3"
                      onClick={() => openEditDialog(doc)}
                    >
                      <Pencil className="h-4 w-4 mr-1.5" />
                      Edit
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-10 px-3"
                      onClick={() => handleDownload(doc)}
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-10 px-3 text-destructive hover:text-destructive border-destructive/30"
                      onClick={() => handleDelete(doc.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </Card>
      )}

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-[500px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Document</DialogTitle>
            <DialogDescription>
              Update document metadata including property, tenant, type, and display name.
            </DialogDescription>
          </DialogHeader>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
            <p className="text-sm text-blue-800">
              <strong>Note:</strong> You can only edit metadata (property, tenant, type, name). To change the file itself, delete this document and upload a new one.
            </p>
          </div>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="property">Property *</Label>
              <Select
                value={editForm.property_id}
                onValueChange={(val) =>
                  setEditForm({ ...editForm, property_id: val, unit_id: "", tenant_id: "" })
                }
              >
                <SelectTrigger id="property">
                  <SelectValue placeholder="Select property" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="unassigned">Unassigned</SelectItem>
                  {properties.map((prop) => (
                    <SelectItem key={prop.id} value={prop.id}>
                      {prop.display_name || prop.address_line1 || "Property"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            {/* Unit Selection - Only show if property has units (multi-family) */}
            {editForm.property_id && editForm.property_id !== "unassigned" && editFormPropertyUnits.length > 0 && (
              <div className="space-y-2">
                <Label htmlFor="unit_id">Unit (optional)</Label>
                <Select
                  value={editForm.unit_id || "__none__"}
                  onValueChange={(val) =>
                    setEditForm({ ...editForm, unit_id: val === "__none__" ? "" : val })
                  }
                >
                  <SelectTrigger id="unit_id">
                    <SelectValue placeholder="Select unit" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">None</SelectItem>
                    {editFormPropertyUnits.map((unit) => (
                      <SelectItem key={unit.id} value={unit.id}>
                        {unit.unit_number}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            
            <div className="space-y-2">
              <Label htmlFor="tenant_id">Tenant (optional)</Label>
              <Select
                value={editForm.tenant_id || "__none__"}
                onValueChange={(val) =>
                  setEditForm({ ...editForm, tenant_id: val === "__none__" ? "" : val })
                }
                disabled={!editForm.property_id || editForm.property_id === "unassigned"}
              >
                <SelectTrigger id="tenant_id">
                  <SelectValue placeholder="Select tenant" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">None</SelectItem>
                  {allEditTenants.map((tenant) => (
                    <SelectItem key={tenant.id} value={tenant.id}>
                      {tenant.first_name} {tenant.last_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="document_type">Document Type</Label>
              <Select
                value={editForm.document_type}
                onValueChange={(val) =>
                  setEditForm({ ...editForm, document_type: val })
                }
              >
                <SelectTrigger id="document_type">
                  <SelectValue placeholder="Select type" />
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
            
            <div className="space-y-2">
              <Label htmlFor="display_name">Display Name</Label>
              <Input
                id="display_name"
                value={editForm.display_name}
                onChange={(e) =>
                  setEditForm({ ...editForm, display_name: e.target.value })
                }
                placeholder={editingDoc?.file_name || "Enter a name"}
              />
              <p className="text-xs text-muted-foreground">
                Original: {editingDoc?.file_name}
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditDialogOpen(false)}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button onClick={handleSaveEdit} disabled={saving}>
              {saving ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Changes"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
