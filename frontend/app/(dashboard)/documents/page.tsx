"use client";

import { useState, useEffect } from "react";
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

interface Document {
  id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  document_type: string;
  property_id?: string;
  unit_id?: string;
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
const DOCUMENT_TYPES_FILTER = ["receipt", "lease", "background_check", "contract", "invoice", "other"];

export default function DocumentsPage() {
  const searchParams = useSearchParams();
  const typeFilter = searchParams.get("type"); // "document" | "photo" | null (all)
  
  const [documents, setDocuments] = useState<Document[]>([]);
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedProperty, setSelectedProperty] = useState<string>("all");

  // Edit dialog state
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingDoc, setEditingDoc] = useState<Document | null>(null);
  const [editForm, setEditForm] = useState({
    display_name: "",
    property_id: "",
    document_type: "",
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [docsRes, propsRes] = await Promise.all([
        apiClient.get("/documents"),
        apiClient.get("/properties"),
      ]);

      const docsData = docsRes as any;
      const propsData = propsRes as any;

      // Filter out receipt documents - those are managed via Expenses page
      const allDocs = docsData.items || docsData.data?.items || docsData || [];
      const nonReceiptDocs = allDocs.filter((doc: Document) => doc.document_type !== "receipt");
      setDocuments(nonReceiptDocs);
      setProperties(propsData.items || propsData.data?.items || propsData || []);
    } catch (err) {
      console.error("Error fetching data:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (documentId: string) => {
    if (!confirm("Delete this document?")) return;
    try {
      await apiClient.delete(`/documents/${documentId}`);
      setDocuments(documents.filter((doc) => doc.id !== documentId));
    } catch (err) {
      console.error("Error deleting document:", err);
    }
  };

  const handleDownload = async (doc: Document) => {
    try {
      const response = (await apiClient.get(`/documents/${doc.id}/download`)) as any;
      window.open(response.download_url || response.data?.download_url, "_blank");
    } catch (err) {
      console.error("Error downloading:", err);
    }
  };

  const openEditDialog = (doc: Document) => {
    setEditingDoc(doc);
    setEditForm({
      display_name: doc.display_name || "",
      property_id: doc.property_id || "unassigned",
      document_type: doc.document_type || "other",
    });
    setEditDialogOpen(true);
  };

  const handleSaveEdit = async () => {
    if (!editingDoc) return;

    setSaving(true);
    try {
      const updateData: any = {};

      // Only include document_type if it has a value
      if (editForm.document_type) {
        updateData.document_type = editForm.document_type;
      }

      // Only include display_name if it has content
      if (editForm.display_name.trim()) {
        updateData.display_name = editForm.display_name.trim();
      }

      // Handle property assignment
      if (editForm.property_id === "unassigned") {
        updateData.clear_property = true;
      } else if (editForm.property_id) {
        updateData.property_id = editForm.property_id;
      }

      console.log("Updating document:", editingDoc.id, "with data:", updateData);

      const response = (await apiClient.patch(
        `/documents/${editingDoc.id}`,
        updateData
      )) as Document;
      
      console.log("Update response:", response);

      // Update the document in our local state
      setDocuments(
        documents.map((doc) =>
          doc.id === editingDoc.id
            ? {
                ...doc,
                ...response,
                property_id: editForm.property_id === "unassigned" ? undefined : editForm.property_id,
              }
            : doc
        )
      );

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

  // Filter documents by type (from URL) and property
  const typeFilteredDocs = typeFilter === "photo"
    ? documents.filter((d) => PHOTO_TYPES.includes(d.document_type))
    : typeFilter === "document"
    ? documents.filter((d) => DOCUMENT_TYPES_FILTER.includes(d.document_type))
    : documents; // Show all if no filter
    
  const filteredDocs =
    selectedProperty === "all"
      ? typeFilteredDocs
      : selectedProperty === "unassigned"
      ? typeFilteredDocs.filter((d) => !d.property_id)
      : typeFilteredDocs.filter((d) => d.property_id === selectedProperty);

  // Group by property (for documents view)
  const groupedByProperty = filteredDocs.reduce((acc, doc) => {
    const key = doc.property_id || "unassigned";
    if (!acc[key]) acc[key] = [];
    acc[key].push(doc);
    return acc;
  }, {} as Record<string, Document[]>);

  // Group photos by property (similar to expenses page)
  const photosByProperty = typeFilter === "photo" ? 
    filteredDocs.reduce((acc, doc) => {
      const key = doc.property_id || "unassigned";
      if (!acc[key]) acc[key] = [];
      acc[key].push(doc);
      return acc;
    }, {} as Record<string, Document[]>) 
    : {};

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
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
            {filteredDocs.length} {typeFilter === "photo" ? "photos" : typeFilter === "document" ? "documents" : "files"} across {properties.length} properties
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={selectedProperty} onValueChange={setSelectedProperty}>
            <SelectTrigger className="w-[200px] h-8 text-xs">
              <SelectValue placeholder="Filter by property" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Properties</SelectItem>
              <SelectItem value="unassigned">Unassigned</SelectItem>
              {properties.map((prop) => (
                <SelectItem key={prop.id} value={prop.id}>
                  {prop.display_name || prop.address_line1 || "Property"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Link href="/documents/add">
            <Button className="bg-black text-white hover:bg-gray-800 h-8 text-xs">
              <Plus className="h-3 w-3 mr-1.5" />
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
        /* Documents grouped by property */
        Object.entries(groupedByProperty).map(([propertyId, docs]) => (
          <Card key={propertyId} className="overflow-hidden">
            <CardHeader className="py-3 px-4 bg-muted/50">
              <CardTitle className="text-sm font-bold flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                {propertyId === "unassigned"
                  ? "Unassigned Documents"
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
                    <TableHead className="w-[12%] text-xs">Type</TableHead>
                    <TableHead className="w-[10%] text-xs">Size</TableHead>
                    <TableHead className="w-[12%] text-xs">Date</TableHead>
                    <TableHead className="w-[31%] text-right text-xs">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {docs.map((doc) => (
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
              {docs.map((doc) => (
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
        ))
      )}

      {/* Edit Dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Edit Document</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
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

            <div className="space-y-2">
              <Label htmlFor="property">Property</Label>
              <Select
                value={editForm.property_id}
                onValueChange={(val) =>
                  setEditForm({ ...editForm, property_id: val })
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
