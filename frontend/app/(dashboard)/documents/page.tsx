"use client";

import { useState, useEffect } from "react";
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
  Upload,
  X,
  AlertCircle,
} from "lucide-react";
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
  { value: "other", label: "Other" },
];

export default function DocumentsPage() {
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

  // View dialog state
  const [viewingDoc, setViewingDoc] = useState<Document | null>(null);

  // Upload dialog state
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadPreview, setUploadPreview] = useState<string | null>(null);
  const [uploadForm, setUploadForm] = useState({
    display_name: "",
    property_id: "unassigned",
    document_type: "other",
  });
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

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

  // Upload handlers
  const handleFileSelect = (file: File) => {
    const allowedTypes = [
      "application/pdf",
      "image/jpeg",
      "image/png",
      "image/gif",
      "image/webp",
    ];
    
    if (!allowedTypes.includes(file.type)) {
      setUploadError("Invalid file type. Please upload PDF, JPEG, PNG, GIF, or WebP.");
      return;
    }
    
    if (file.size > 10 * 1024 * 1024) {
      setUploadError("File too large. Maximum size is 10MB.");
      return;
    }
    
    setUploadError(null);
    setUploadFile(file);
    
    // Create preview for images
    if (file.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (e) => setUploadPreview(e.target?.result as string);
      reader.readAsDataURL(file);
    } else {
      setUploadPreview(null);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const clearUpload = () => {
    setUploadFile(null);
    setUploadPreview(null);
    setUploadError(null);
    setUploadForm({
      display_name: "",
      property_id: "unassigned",
      document_type: "other",
    });
  };

  const handleUpload = async () => {
    if (!uploadFile) return;

    setUploading(true);
    setUploadError(null);

    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      formData.append("document_type", uploadForm.document_type);
      
      if (uploadForm.property_id && uploadForm.property_id !== "unassigned") {
        formData.append("property_id", uploadForm.property_id);
      }

      const response = await apiClient.upload<any>("/documents/upload", formData);
      
      // If we have a display_name, update the document with it
      if (uploadForm.display_name.trim() && response.document?.id) {
        await apiClient.patch(`/documents/${response.document.id}`, {
          display_name: uploadForm.display_name.trim(),
        });
      }

      // Refresh the documents list
      await fetchData();
      
      // Close dialog and reset
      setUploadDialogOpen(false);
      clearUpload();
    } catch (err) {
      console.error("Error uploading document:", err);
      setUploadError((err as Error).message || "Failed to upload document");
    } finally {
      setUploading(false);
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
    if (fileType?.startsWith("image/")) return <Image className="h-4 w-4" />;
    if (fileType?.includes("pdf")) return <FileText className="h-4 w-4" />;
    return <FileIcon className="h-4 w-4" />;
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

  // Filter documents
  const filteredDocs =
    selectedProperty === "all"
      ? documents
      : selectedProperty === "unassigned"
      ? documents.filter((d) => !d.property_id)
      : documents.filter((d) => d.property_id === selectedProperty);

  // Group by property
  const groupedByProperty = filteredDocs.reduce((acc, doc) => {
    const key = doc.property_id || "unassigned";
    if (!acc[key]) acc[key] = [];
    acc[key].push(doc);
    return acc;
  }, {} as Record<string, Document[]>);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Documents</h1>
          <p className="text-sm text-muted-foreground">
            {documents.length} documents across {properties.length} properties
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={selectedProperty} onValueChange={setSelectedProperty}>
            <SelectTrigger className="w-[200px]">
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
          <Button onClick={() => setUploadDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Document
          </Button>
        </div>
      </div>

      {/* Documents grouped by property */}
      {documents.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center py-8">
            <FileText className="h-10 w-10 text-muted-foreground mb-3" />
            <p className="text-muted-foreground text-sm">
              No documents yet. Upload receipts when adding expenses.
            </p>
          </CardContent>
        </Card>
      ) : (
        Object.entries(groupedByProperty).map(([propertyId, docs]) => (
          <Card key={propertyId} className="overflow-hidden">
            <CardHeader className="py-3 px-4 bg-muted/50">
              <CardTitle className="text-sm font-medium flex items-center gap-2">
                <Building2 className="h-4 w-4" />
                {propertyId === "unassigned"
                  ? "Unassigned Documents"
                  : getPropertyName(propertyId)}
                <Badge variant="secondary" className="ml-auto">
                  {docs.length}
                </Badge>
              </CardTitle>
            </CardHeader>
            <Table>
              <TableHeader>
                <TableRow className="text-xs">
                  <TableHead className="w-[35%]">Name</TableHead>
                  <TableHead className="w-[12%]">Type</TableHead>
                  <TableHead className="w-[10%]">Size</TableHead>
                  <TableHead className="w-[12%]">Date</TableHead>
                  <TableHead className="w-[31%] text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {docs.map((doc) => (
                  <TableRow key={doc.id} className="text-sm">
                    <TableCell className="py-2">
                      <div className="flex items-center gap-2">
                        {getFileIcon(doc.file_type)}
                        <div className="flex flex-col">
                          <span
                            className="truncate max-w-[220px] font-medium"
                            title={getDisplayName(doc)}
                          >
                            {getDisplayName(doc)}
                          </span>
                          {doc.display_name && (
                            <span
                              className="text-xs text-muted-foreground truncate max-w-[220px]"
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
                        className={`text-xs ${getDocTypeBadge(doc.document_type)}`}
                      >
                        {doc.document_type}
                      </Badge>
                    </TableCell>
                    <TableCell className="py-2 text-muted-foreground">
                      {formatFileSize(doc.file_size)}
                    </TableCell>
                    <TableCell className="py-2 text-muted-foreground">
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

      {/* Upload Dialog */}
      <Dialog open={uploadDialogOpen} onOpenChange={(open) => {
        setUploadDialogOpen(open);
        if (!open) clearUpload();
      }}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>Upload Document</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {/* Drop Zone */}
            <div
              onDrop={handleDrop}
              onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={(e) => { e.preventDefault(); setIsDragging(false); }}
              onClick={() => document.getElementById("upload-input")?.click()}
              className={`
                relative border-2 border-dashed rounded-lg p-6 transition-all cursor-pointer
                ${isDragging
                  ? "border-blue-500 bg-blue-50"
                  : uploadFile
                  ? "border-green-400 bg-green-50"
                  : "border-gray-300 hover:border-gray-400 bg-gray-50 hover:bg-gray-100"
                }
              `}
            >
              <input
                id="upload-input"
                type="file"
                accept="application/pdf,image/jpeg,image/png,image/gif,image/webp"
                onChange={(e) => {
                  if (e.target.files?.[0]) handleFileSelect(e.target.files[0]);
                }}
                className="hidden"
              />

              {uploadFile ? (
                <div className="flex items-center justify-center gap-4">
                  {uploadPreview ? (
                    <img
                      src={uploadPreview}
                      alt="Preview"
                      className="h-16 w-16 object-cover rounded-lg shadow-sm"
                    />
                  ) : (
                    <div className="h-16 w-16 bg-red-100 rounded-lg flex items-center justify-center">
                      <FileText className="h-8 w-8 text-red-600" />
                    </div>
                  )}
                  <div className="text-left">
                    <p className="font-medium text-gray-900 truncate max-w-[200px]">
                      {uploadFile.name}
                    </p>
                    <p className="text-sm text-gray-500">
                      {(uploadFile.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setUploadFile(null);
                        setUploadPreview(null);
                      }}
                      className="text-sm text-red-600 hover:text-red-800 mt-1 flex items-center gap-1"
                    >
                      <X className="h-3 w-3" />
                      Remove
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-center">
                  <Upload className="h-10 w-10 mx-auto text-gray-400 mb-2" />
                  <p className="text-sm font-medium text-gray-700">
                    Drag and drop or click to browse
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    PDF, JPEG, PNG, GIF, WebP (max 10MB)
                  </p>
                </div>
              )}
            </div>

            {/* Error */}
            {uploadError && (
              <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 p-3 rounded-lg">
                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                {uploadError}
              </div>
            )}

            {/* Display Name */}
            <div className="space-y-2">
              <Label htmlFor="upload_display_name">Display Name (optional)</Label>
              <Input
                id="upload_display_name"
                value={uploadForm.display_name}
                onChange={(e) =>
                  setUploadForm({ ...uploadForm, display_name: e.target.value })
                }
                placeholder="Enter a name for this document"
              />
            </div>

            {/* Property */}
            <div className="space-y-2">
              <Label htmlFor="upload_property">Property</Label>
              <Select
                value={uploadForm.property_id}
                onValueChange={(val) =>
                  setUploadForm({ ...uploadForm, property_id: val })
                }
              >
                <SelectTrigger id="upload_property">
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

            {/* Document Type */}
            <div className="space-y-2">
              <Label htmlFor="upload_document_type">Document Type</Label>
              <Select
                value={uploadForm.document_type}
                onValueChange={(val) =>
                  setUploadForm({ ...uploadForm, document_type: val })
                }
              >
                <SelectTrigger id="upload_document_type">
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  {DOCUMENT_TYPES.filter(t => t.value !== "receipt").map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Note: For receipts, upload via the Expenses page.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setUploadDialogOpen(false);
                clearUpload();
              }}
              disabled={uploading}
            >
              Cancel
            </Button>
            <Button onClick={handleUpload} disabled={!uploadFile || uploading}>
              {uploading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  Upload
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
