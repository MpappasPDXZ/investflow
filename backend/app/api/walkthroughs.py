"""API routes for walkthrough inspection management"""
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form
from typing import List, Optional
from uuid import UUID
import uuid
import pandas as pd
import json
from datetime import datetime, date

from app.core.dependencies import get_current_user
from app.schemas.walkthrough import (
    WalkthroughCreate, WalkthroughUpdate, WalkthroughResponse, WalkthroughListResponse, WalkthroughListItem,
    WalkthroughAreaCreate, WalkthroughAreaResponse, WalkthroughAreaPhoto, PhotoUploadRequest,
    WalkthroughAreaIssue
)
from app.core.iceberg import read_table, append_data, table_exists, load_table, read_table_filtered, upsert_data
from app.core.logging import get_logger
from app.services.adls_service import adls_service
from app.services.walkthrough_generator_service import WalkthroughGeneratorService
from app.services.document_service import document_service
from pyiceberg.expressions import EqualTo, In

NAMESPACE = ("investflow",)
WALKTHROUGHS_TABLE = "walkthroughs"
WALKTHROUGH_AREAS_TABLE = "walkthrough_areas"
PROPERTIES_TABLE = "properties"

router = APIRouter(prefix="/walkthroughs", tags=["walkthroughs"])
logger = get_logger(__name__)


def _verify_property_ownership(property_id: str, user_id: str):
    """Verify that the user owns the property"""
    try:
        if not table_exists(NAMESPACE, PROPERTIES_TABLE):
            raise HTTPException(status_code=404, detail="Property not found")
        
        # OPTIMIZATION: Use filtered read instead of reading entire table
        properties_df = read_table_filtered(
            NAMESPACE,
            PROPERTIES_TABLE,
            EqualTo("id", property_id)
        )
        
        if len(properties_df) == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        
        property_data = properties_df.iloc[0]
        if property_data["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this property")
        
        return property_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying property ownership: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error verifying property ownership")


@router.post("", response_model=WalkthroughResponse, status_code=201)
async def create_walkthrough(
    walkthrough_data: WalkthroughCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new walkthrough inspection"""
    try:
        logger.info(f"📥 [WALKTHROUGH] Received create request with {len(walkthrough_data.areas)} areas")
        logger.info(f"📥 [WALKTHROUGH] Payload: {walkthrough_data.model_dump_json(indent=2)}")
        user_id = current_user["sub"]
        walkthrough_id = str(uuid.uuid4())
        now = pd.Timestamp.now()
        
        # Verify property ownership and get property data
        property_data = _verify_property_ownership(str(walkthrough_data.property_id), user_id)
        
        # Get property display_name
        property_display_name = property_data.get("display_name") or property_data.get("address", "")
        if property_data.get("city") or property_data.get("state"):
            if not property_display_name:
                property_display_name = property_data.get("address", "")
            if property_data.get("city"):
                property_display_name += f", {property_data.get('city', '')}"
            if property_data.get("state"):
                property_display_name += f", {property_data.get('state', '')}"
        
        # Get unit_number if unit_id is provided
        unit_number = None
        if walkthrough_data.unit_id:
            try:
                if table_exists(NAMESPACE, "units"):
                    units_df = read_table_filtered(
                        NAMESPACE,
                        "units",
                        EqualTo("id", str(walkthrough_data.unit_id))
                    )
                    if len(units_df) > 0:
                        unit_number = units_df.iloc[0].get("unit_number", "")
            except Exception as e:
                logger.warning(f"Could not get unit number: {e}")
        
        # Convert to dict
        walkthrough_dict = walkthrough_data.model_dump(exclude={"areas"})
        walkthrough_dict["id"] = walkthrough_id
        walkthrough_dict["user_id"] = user_id
        walkthrough_dict["status"] = "draft"
        walkthrough_dict["created_at"] = now
        walkthrough_dict["updated_at"] = now
        walkthrough_dict["is_active"] = True
        walkthrough_dict["generated_pdf_blob_name"] = None
        
        # Convert UUIDs and dates
        walkthrough_dict["property_id"] = str(walkthrough_data.property_id)
        walkthrough_dict["unit_id"] = str(walkthrough_data.unit_id) if walkthrough_data.unit_id else None
        walkthrough_dict["property_display_name"] = property_display_name
        walkthrough_dict["unit_number"] = unit_number
        walkthrough_dict["walkthrough_date"] = pd.Timestamp(walkthrough_data.walkthrough_date)
        
        # Ensure tenant_name and inspector_name are explicitly included (they should be from model_dump, but be explicit)
        walkthrough_dict["tenant_name"] = walkthrough_data.tenant_name
        # Default inspector to Sarah Pappas if not provided
        walkthrough_dict["inspector_name"] = walkthrough_data.inspector_name or "Sarah Pappas, Member S&M Axios Heartland Holdings LLC"
        
        # Convert signature dates if present
        if walkthrough_data.tenant_signature_date:
            walkthrough_dict["tenant_signature_date"] = pd.Timestamp(walkthrough_data.tenant_signature_date)
        else:
            walkthrough_dict["tenant_signature_date"] = None
            
        if walkthrough_data.landlord_signature_date:
            walkthrough_dict["landlord_signature_date"] = pd.Timestamp(walkthrough_data.landlord_signature_date)
        else:
            walkthrough_dict["landlord_signature_date"] = None
        
        # OPTIMIZATION: Store areas as JSON in walkthrough table (much faster than separate table)
        areas_json_data = []
        area_responses = []
        for idx, area_data in enumerate(walkthrough_data.areas):
            area_id = str(uuid.uuid4())
            
            area_json = {
                "id": area_id,
                "floor": area_data.floor,
                "area_name": area_data.area_name,
                "area_order": idx + 1,
                "inspection_status": area_data.inspection_status,
                "notes": area_data.notes,
                "landlord_fix_notes": area_data.landlord_fix_notes,
                "issues": [issue.model_dump() for issue in area_data.issues] if area_data.issues else [],
                "photos": []  # Photos will be added via upload endpoint
            }
            areas_json_data.append(area_json)
            
            # Build area response
            area_responses.append(WalkthroughAreaResponse(
                id=UUID(area_id),
                walkthrough_id=UUID(walkthrough_id),
                floor=area_data.floor,
                area_name=area_data.area_name,
                area_order=idx + 1,
                inspection_status=area_data.inspection_status,
                notes=area_data.notes,
                landlord_fix_notes=area_data.landlord_fix_notes,
                issues=area_data.issues,
                photos=[],
                created_at=now.to_pydatetime(),
                updated_at=now.to_pydatetime()
            ))
        
        # Store areas as JSON in walkthrough table
        walkthrough_dict["areas_json"] = json.dumps(areas_json_data) if areas_json_data else None
        
        # OPTIMIZATION: Use upsert_data for walkthrough (like leases) - much faster
        walkthrough_df = pd.DataFrame([walkthrough_dict])
        if table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)
            schema_columns = [field.name for field in table.schema().fields]
            walkthrough_df = walkthrough_df.reindex(columns=schema_columns, fill_value=None)
        
        upsert_data(NAMESPACE, WALKTHROUGHS_TABLE, walkthrough_df, join_cols=["id"])
        
        # Build response
        pdf_url = None
        if walkthrough_dict.get("generated_pdf_blob_name"):
            pdf_url = adls_service.get_blob_download_url(walkthrough_dict["generated_pdf_blob_name"])
        
        return WalkthroughResponse(
            id=UUID(walkthrough_id),
            user_id=user_id,
            property_id=walkthrough_data.property_id,
            unit_id=walkthrough_data.unit_id,
            property_display_name=property_display_name,
            unit_number=unit_number,
            walkthrough_type=walkthrough_data.walkthrough_type,
            walkthrough_date=walkthrough_data.walkthrough_date,
            inspector_name=walkthrough_data.inspector_name,
            tenant_name=walkthrough_data.tenant_name,
            tenant_signed=walkthrough_data.tenant_signed,
            tenant_signature_date=walkthrough_data.tenant_signature_date,
            landlord_signed=walkthrough_data.landlord_signed,
            landlord_signature_date=walkthrough_data.landlord_signature_date,
            notes=walkthrough_data.notes,
            status="draft",
            generated_pdf_blob_name=None,
            pdf_url=pdf_url,
            areas=area_responses,
            created_at=now.to_pydatetime(),
            updated_at=now.to_pydatetime()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating walkthrough: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating walkthrough: {str(e)}")


@router.get("", response_model=WalkthroughListResponse)
async def list_walkthroughs(
    property_id: Optional[UUID] = Query(None, description="Filter by property"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    """List all walkthroughs for the current user - SIMPLIFIED: only walkthroughs table, no areas"""
    try:
        user_id = current_user["sub"]
        
        if not table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            return WalkthroughListResponse(items=[], total=0)
        
        # Read walkthroughs - ONLY from walkthroughs table
        walkthroughs_df = read_table_filtered(
            NAMESPACE,
            WALKTHROUGHS_TABLE,
            EqualTo("user_id", user_id)
        )
        
        if len(walkthroughs_df) == 0:
            return WalkthroughListResponse(items=[], total=0)
        
        # Filter active walkthroughs if is_active column exists
        if "is_active" in walkthroughs_df.columns:
            walkthroughs_df = walkthroughs_df[walkthroughs_df["is_active"] == True]
        
        # Get latest version per walkthrough
        walkthroughs_df = walkthroughs_df.sort_values("updated_at", ascending=False)
        walkthroughs_df = walkthroughs_df.drop_duplicates(subset=["id"], keep="first")
        
        # Apply filters
        if property_id:
            walkthroughs_df = walkthroughs_df[walkthroughs_df["property_id"] == str(property_id)]
        if status:
            walkthroughs_df = walkthroughs_df[walkthroughs_df["status"] == status]
        
        # Build simplified responses - NO AREAS, just count from areas_json
        items = []
        for _, walkthrough in walkthroughs_df.iterrows():
            # Count areas from areas_json (fast - just parse JSON length)
            areas_count = 0
            areas_json_str = walkthrough.get("areas_json")
            if areas_json_str:
                try:
                    areas_data = json.loads(areas_json_str)
                    areas_count = len(areas_data) if isinstance(areas_data, list) else 0
                except:
                    pass
            
            # Generate PDF URL if available
            pdf_url = None
            if walkthrough.get("generated_pdf_blob_name"):
                pdf_url = adls_service.get_blob_download_url(walkthrough["generated_pdf_blob_name"])
            
            items.append(WalkthroughListItem(
                id=UUID(walkthrough["id"]),
                user_id=walkthrough["user_id"],
                property_id=UUID(walkthrough["property_id"]),
                unit_id=UUID(walkthrough["unit_id"]) if walkthrough.get("unit_id") else None,
                property_display_name=walkthrough.get("property_display_name"),
                unit_number=walkthrough.get("unit_number"),
                walkthrough_type=walkthrough["walkthrough_type"],
                walkthrough_date=pd.Timestamp(walkthrough["walkthrough_date"]).date(),
                inspector_name=walkthrough.get("inspector_name"),
                tenant_name=walkthrough.get("tenant_name"),
                status=walkthrough.get("status", "draft"),
                generated_pdf_blob_name=walkthrough.get("generated_pdf_blob_name"),
                pdf_url=pdf_url,
                areas_count=areas_count,
                created_at=pd.Timestamp(walkthrough["created_at"]).to_pydatetime(),
                updated_at=pd.Timestamp(walkthrough["updated_at"]).to_pydatetime()
            ))
        
        return WalkthroughListResponse(items=items, total=len(items))
        
    except Exception as e:
        logger.error(f"Error listing walkthroughs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error listing walkthroughs: {str(e)}")


@router.post("/{walkthrough_id}/areas/{area_id}/photos", response_model=WalkthroughAreaPhoto)
async def upload_area_photo(
    walkthrough_id: UUID,
    area_id: UUID,
    file: UploadFile = File(...),
    notes: Optional[str] = Form(None),
    order: int = Form(1),
    current_user: dict = Depends(get_current_user)
):
    """Upload a photo for a walkthrough area"""
    try:
        user_id = current_user["sub"]
        
        # Verify walkthrough exists and user owns it
        if not table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        walkthroughs_df = read_table_filtered(
            NAMESPACE,
            WALKTHROUGHS_TABLE,
            EqualTo("id", str(walkthrough_id))
        )
        
        if len(walkthroughs_df) == 0:
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        walkthrough = walkthroughs_df.iloc[0]
        if walkthrough["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Upload photo using DocumentService (stores in vault table)
        file_content = await file.read()
        from uuid import UUID as UUIDType
        document = document_service.upload_document(
            user_id=UUIDType(user_id),
            file_content=file_content,
            filename=file.filename or "photo.jpg",
            content_type=file.content_type or "image/jpeg",
            document_type="walkthrough_photo",
            property_id=UUIDType(walkthrough["property_id"]),
            unit_id=UUIDType(walkthrough["unit_id"]) if walkthrough.get("unit_id") else None
        )
        
        # OPTIMIZATION: Update areas_json in walkthrough table instead of separate table
        areas_json_str = walkthrough.get("areas_json")
        areas_data = []
        
        if areas_json_str:
            # New format: areas stored as JSON in walkthrough table
            try:
                areas_data = json.loads(areas_json_str)
                logger.info(f"📷 [PHOTO] Loaded {len(areas_data)} areas from areas_json for walkthrough {walkthrough_id}")
            except Exception as e:
                logger.error(f"📷 [PHOTO] Failed to parse areas_json: {e}")
                pass
        
        # Find the area by area_id
        area_found = False
        target_area = None
        
        logger.info(f"📷 [PHOTO] Looking for area_id: {area_id} in {len(areas_data)} areas")
        for area_data in areas_data:
            area_data_id = area_data.get("id")
            logger.info(f"📷 [PHOTO] Checking area: id={area_data_id}, name={area_data.get('area_name')}")
            # Try to match by ID (compare as strings)
            if str(area_data_id) == str(area_id):
                target_area = area_data
                area_found = True
                logger.info(f"📷 [PHOTO] Found area by ID: {area_id}")
                break
        
        if not area_found:
            logger.warning(f"📷 [PHOTO] Area {area_id} not found in areas_json. Available area IDs: {[a.get('id') for a in areas_data]}")
        
        if area_found and target_area:
            # Get existing photos
            existing_photos = target_area.get("photos", [])
            
            # Add new photo - store document_id instead of blob_name
            new_photo = {
                "document_id": str(document["id"]),  # Store document ID from vault
                "photo_blob_name": document["blob_name"],  # Keep for backward compatibility
                "notes": notes,
                "order": order
            }
            existing_photos.append(new_photo)
            target_area["photos"] = existing_photos
        
        if not area_found:
            # Fallback: try separate table (legacy format)
            if table_exists(NAMESPACE, WALKTHROUGH_AREAS_TABLE):
                areas_df = read_table_filtered(
                    NAMESPACE,
                    WALKTHROUGH_AREAS_TABLE,
                    EqualTo("id", str(area_id))
                )
                
                if len(areas_df) == 0:
                    raise HTTPException(status_code=404, detail="Area not found")
                
                area = areas_df.iloc[0]
                if area["walkthrough_id"] != str(walkthrough_id):
                    raise HTTPException(status_code=400, detail="Area does not belong to this walkthrough")
                
                # Get existing photos
                existing_photos = []
                if area.get("photos"):
                    try:
                        existing_photos = json.loads(area["photos"])
                    except:
                        pass
                
                # Add new photo
                new_photo = {
                    "document_id": str(document["id"]),
                    "photo_blob_name": document["blob_name"],
                    "notes": notes,
                    "order": order
                }
                existing_photos.append(new_photo)
                
                # Update area in separate table (legacy)
                area_dict = area.to_dict()
                area_dict["photos"] = json.dumps(existing_photos)
                area_dict["updated_at"] = pd.Timestamp.now()
                
                table = load_table(NAMESPACE, WALKTHROUGH_AREAS_TABLE)
                schema_columns = [field.name for field in table.schema().fields]
                
                if "condition" in schema_columns:
                    inspection_status = area_dict.get("inspection_status", "no_issues")
                    if inspection_status == "no_issues":
                        area_dict["condition"] = "good"
                    elif inspection_status == "issue_noted_as_is":
                        area_dict["condition"] = "fair"
                    elif inspection_status == "issue_landlord_to_fix":
                        area_dict["condition"] = "poor"
                    else:
                        area_dict["condition"] = "good"
                
                table.delete(EqualTo("id", str(area_id)))
                area_df = pd.DataFrame([area_dict])
                area_df = area_df.reindex(columns=schema_columns, fill_value=None)
                append_data(NAMESPACE, WALKTHROUGH_AREAS_TABLE, area_df)
            else:
                raise HTTPException(status_code=404, detail="Area not found")
        else:
            # Update walkthrough with updated areas_json
            walkthrough_dict = walkthrough.to_dict()
            walkthrough_dict["areas_json"] = json.dumps(areas_data)
            walkthrough_dict["updated_at"] = pd.Timestamp.now()
            
            walkthroughs_table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)
            schema_columns = [field.name for field in walkthroughs_table.schema().fields]
            walkthrough_df = pd.DataFrame([walkthrough_dict])
            walkthrough_df = walkthrough_df.reindex(columns=schema_columns, fill_value=None)
            
            upsert_data(NAMESPACE, WALKTHROUGHS_TABLE, walkthrough_df, join_cols=["id"])
        
        # Generate photo URL using document service
        photo_url = document_service.get_document_download_url(UUIDType(document["id"]), UUIDType(user_id))
        
        return WalkthroughAreaPhoto(
            photo_blob_name=document["blob_name"],
            photo_url=photo_url,
            notes=notes,
            order=order,
            document_id=document["id"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading photo: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error uploading photo: {str(e)}")


@router.post("/{walkthrough_id}/generate-pdf")
async def generate_walkthrough_pdf(
    walkthrough_id: UUID,
    regenerate: bool = Query(False, description="Regenerate PDF even if it exists"),
    current_user: dict = Depends(get_current_user)
):
    """Generate PDF for walkthrough inspection"""
    try:
        user_id = current_user["sub"]
        
        # Get walkthrough
        if not table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        walkthroughs_df = read_table_filtered(
            NAMESPACE,
            WALKTHROUGHS_TABLE,
            EqualTo("id", str(walkthrough_id))
        )
        
        if len(walkthroughs_df) == 0:
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        walkthrough = walkthroughs_df.iloc[0]
        
        # Verify ownership
        if walkthrough["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Check if PDF already exists (unless regenerate is True)
        if not regenerate and walkthrough.get("generated_pdf_blob_name"):
            pdf_blob = walkthrough["generated_pdf_blob_name"]
            if adls_service.blob_exists(pdf_blob):
                pdf_url = adls_service.get_blob_download_url(pdf_blob)
                return {
                    "walkthrough_id": walkthrough_id,
                    "pdf_url": pdf_url,
                    "pdf_blob_name": pdf_blob,
                    "generated_at": datetime.now().isoformat(),
                    "status": walkthrough["status"]
                }
        
        # Get property data
        if not table_exists(NAMESPACE, PROPERTIES_TABLE):
            raise HTTPException(status_code=404, detail="Property not found")
        
        properties_df = read_table_filtered(
            NAMESPACE,
            PROPERTIES_TABLE,
            EqualTo("id", str(walkthrough["property_id"]))
        )
        
        if len(properties_df) == 0:
            raise HTTPException(status_code=404, detail="Property not found")
        
        property_data = properties_df.iloc[0].to_dict()
        
        # Get user/landlord name for inspector default
        landlord_name = None
        if table_exists(NAMESPACE, "users"):
            try:
                users_df = read_table_filtered(
                    NAMESPACE,
                    "users",
                    EqualTo("id", user_id)
                )
                if len(users_df) > 0:
                    user_data = users_df.iloc[0]
                    # Build name from first_name and last_name
                    first_name = user_data.get("first_name", "")
                    last_name = user_data.get("last_name", "")
                    if first_name or last_name:
                        landlord_name = f"{first_name} {last_name}".strip()
                    else:
                        # Fallback to email username
                        landlord_name = user_data.get("email", "").split("@")[0] if user_data.get("email") else None
            except Exception as e:
                logger.warning(f"Could not get user name: {e}")
        
        # Get areas from areas_json (preferred) or separate table (legacy)
        areas_list = []
        areas_json_str = walkthrough.get("areas_json")
        
        if areas_json_str:
            # New format: areas stored as JSON in walkthrough table
            try:
                areas_list = json.loads(areas_json_str)
            except Exception as e:
                logger.warning(f"Failed to parse areas_json, falling back to separate table: {e}")
                areas_json_str = None
        
        # Fallback to separate table if areas_json doesn't exist
        if not areas_json_str:
            if table_exists(NAMESPACE, WALKTHROUGH_AREAS_TABLE):
                areas_df = read_table_filtered(
                    NAMESPACE,
                    WALKTHROUGH_AREAS_TABLE,
                    EqualTo("walkthrough_id", str(walkthrough_id))
                )
                
                if len(areas_df) > 0:
                    areas_df = areas_df.sort_values("area_order")
                    for _, area in areas_df.iterrows():
                        area_dict = area.to_dict()
                        # Deserialize issues and photos
                        if area_dict.get("issues"):
                            try:
                                area_dict["issues"] = json.loads(area_dict["issues"])
                            except:
                                area_dict["issues"] = []
                        else:
                            area_dict["issues"] = []
                        
                        if area_dict.get("photos"):
                            try:
                                area_dict["photos"] = json.loads(area_dict["photos"])
                            except:
                                area_dict["photos"] = []
                        else:
                            area_dict["photos"] = []
                        
                        areas_list.append(area_dict)
        
        # Generate PDF
        generator = WalkthroughGeneratorService()
        walkthrough_dict = walkthrough.to_dict()
        
        pdf_bytes, pdf_blob_name, latex_blob_name = generator.generate_walkthrough_pdf(
            walkthrough_data=walkthrough_dict,
            areas=areas_list,
            property_data=property_data,
            user_id=user_id
        )
        
        # Update walkthrough record with PDF location using upsert
        update_dict = walkthrough.to_dict()
        update_dict["generated_pdf_blob_name"] = pdf_blob_name
        update_dict["status"] = "pending_signature" if walkthrough["status"] == "draft" else walkthrough["status"]
        update_dict["updated_at"] = pd.Timestamp.now()
        
        update_df = pd.DataFrame([update_dict])
        if table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)
            schema_columns = [field.name for field in table.schema().fields]
            update_df = update_df.reindex(columns=schema_columns, fill_value=None)
        
        upsert_data(NAMESPACE, WALKTHROUGHS_TABLE, update_df, join_cols=["id"])
        
        # Get download URL
        pdf_url = adls_service.get_blob_download_url(pdf_blob_name)
        
        return {
            "walkthrough_id": walkthrough_id,
            "pdf_url": pdf_url,
            "pdf_blob_name": pdf_blob_name,
            "latex_blob_name": latex_blob_name,
            "generated_at": datetime.now().isoformat(),
            "status": update_dict["status"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


@router.get("/{walkthrough_id}/download-pdf")
async def download_walkthrough_pdf(
    walkthrough_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Download walkthrough PDF"""
    try:
        user_id = current_user["sub"]
        
        # Get walkthrough
        if not table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        walkthroughs_df = read_table_filtered(
            NAMESPACE,
            WALKTHROUGHS_TABLE,
            EqualTo("id", str(walkthrough_id))
        )
        
        if len(walkthroughs_df) == 0:
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        walkthrough = walkthroughs_df.iloc[0]
        
        # Verify ownership
        if walkthrough["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Get PDF blob name
        pdf_blob_name = walkthrough.get("generated_pdf_blob_name")
        if not pdf_blob_name:
            raise HTTPException(status_code=404, detail="PDF not generated for this walkthrough")
        
        # Get download URL
        pdf_url = adls_service.get_blob_download_url(pdf_blob_name)
        
        return {"pdf_url": pdf_url}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PDF download URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting PDF download URL: {str(e)}")


@router.get("/{walkthrough_id}/pdf/proxy")
async def proxy_walkthrough_pdf_download(
    walkthrough_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Proxy download for walkthrough PDF (forces actual download instead of opening in browser - IE compatible)"""
    try:
        from fastapi.responses import StreamingResponse
        import io
        
        user_id = current_user["sub"]
        
        # Get walkthrough
        if not table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        walkthroughs_df = read_table_filtered(
            NAMESPACE,
            WALKTHROUGHS_TABLE,
            EqualTo("id", str(walkthrough_id))
        )
        
        if len(walkthroughs_df) == 0:
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        walkthrough = walkthroughs_df.iloc[0]
        
        # Verify ownership
        if walkthrough["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Get PDF blob name
        pdf_blob_name = walkthrough.get("generated_pdf_blob_name")
        if not pdf_blob_name:
            raise HTTPException(status_code=404, detail="PDF not generated for this walkthrough")
        
        if not adls_service.blob_exists(pdf_blob_name):
            raise HTTPException(status_code=404, detail="PDF file not found")
        
        # Download blob content
        blob_content, content_type, filename = adls_service.download_blob(pdf_blob_name)
        
        # Use property name and date for filename if available
        property_name = walkthrough.get("property_display_name", "Property")
        inspection_date = walkthrough.get("inspection_date")
        if inspection_date:
            try:
                from datetime import datetime
                if isinstance(inspection_date, str):
                    date_obj = datetime.fromisoformat(inspection_date.replace('Z', '+00:00'))
                else:
                    date_obj = inspection_date
                date_str = date_obj.strftime("%Y-%m-%d")
                download_filename = f"Inspection_{property_name}_{date_str}.pdf"
            except:
                download_filename = f"Inspection_{property_name}.pdf"
        else:
            download_filename = f"Inspection_{property_name}.pdf"
        
        # Sanitize filename
        download_filename = "".join(c for c in download_filename if c.isalnum() or c in (' ', '-', '_', '.')).strip()
        
        # Return as streaming response with Content-Disposition header to force download
        return StreamingResponse(
            io.BytesIO(blob_content),
            media_type=content_type or "application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{download_filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error proxying walkthrough PDF download: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error downloading walkthrough PDF: {str(e)}")




@router.put("/{walkthrough_id}", response_model=WalkthroughResponse)
async def update_walkthrough(
    walkthrough_id: UUID,
    walkthrough_data: WalkthroughCreate,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing walkthrough"""
    import time
    start_time = time.time()
    try:
        logger.info(f"📥 [WALKTHROUGH] Received update request for {walkthrough_id} with {len(walkthrough_data.areas)} areas")
        user_id = current_user["sub"]
        
        step_start = time.time()
        # Verify property ownership and get property data
        property_data = _verify_property_ownership(str(walkthrough_data.property_id), user_id)
        logger.info(f"⏱️  [WALKTHROUGH] Property ownership check: {time.time() - step_start:.3f}s")
        
        # Get property display_name
        property_display_name = property_data.get("display_name") or property_data.get("address", "")
        if property_data.get("city") or property_data.get("state"):
            if not property_display_name:
                property_display_name = property_data.get("address", "")
            if property_data.get("city"):
                property_display_name += f", {property_data.get('city', '')}"
            if property_data.get("state"):
                property_display_name += f", {property_data.get('state', '')}"
        
        # Get unit_number if unit_id is provided
        unit_number = None
        if walkthrough_data.unit_id:
            try:
                if table_exists(NAMESPACE, "units"):
                    units_df = read_table_filtered(
                        NAMESPACE,
                        "units",
                        EqualTo("id", str(walkthrough_data.unit_id))
                    )
                    if len(units_df) > 0:
                        unit_number = units_df.iloc[0].get("unit_number", "")
            except Exception as e:
                logger.warning(f"Could not get unit number: {e}")
        
        step_start = time.time()
        # Check if walkthrough exists - cache table load
        if not table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        walkthroughs_table = load_table(NAMESPACE, WALKTHROUGHS_TABLE)  # Cache this
        walkthroughs_df = read_table_filtered(
            NAMESPACE,
            WALKTHROUGHS_TABLE,
            EqualTo("id", str(walkthrough_id))
        )
        logger.info(f"⏱️  [WALKTHROUGH] Read existing walkthrough: {time.time() - step_start:.3f}s")
        
        if len(walkthroughs_df) == 0:
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        existing_walkthrough = walkthroughs_df.iloc[0]
        
        # Verify ownership
        if existing_walkthrough["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        now = pd.Timestamp.now()
        
        step_start = time.time()
        # Update walkthrough fields
        walkthrough_dict = walkthrough_data.model_dump(exclude={"areas"})
        walkthrough_dict["id"] = str(walkthrough_id)
        walkthrough_dict["user_id"] = user_id
        walkthrough_dict["updated_at"] = now
        
        # Keep existing fields that shouldn't change
        walkthrough_dict["created_at"] = pd.Timestamp(existing_walkthrough["created_at"])
        walkthrough_dict["status"] = existing_walkthrough.get("status", "draft")
        walkthrough_dict["is_active"] = existing_walkthrough.get("is_active", True)
        walkthrough_dict["generated_pdf_blob_name"] = existing_walkthrough.get("generated_pdf_blob_name")
        
        # Convert UUIDs and dates
        walkthrough_dict["property_id"] = str(walkthrough_data.property_id)
        walkthrough_dict["unit_id"] = str(walkthrough_data.unit_id) if walkthrough_data.unit_id else None
        walkthrough_dict["property_display_name"] = property_display_name
        walkthrough_dict["unit_number"] = unit_number
        walkthrough_dict["walkthrough_date"] = pd.Timestamp(walkthrough_data.walkthrough_date)
        
        # Ensure tenant_name and inspector_name are explicitly included
        walkthrough_dict["tenant_name"] = walkthrough_data.tenant_name
        # Default inspector to Sarah Pappas if not provided
        walkthrough_dict["inspector_name"] = walkthrough_data.inspector_name or "Sarah Pappas, Member S&M Axios Heartland Holdings LLC"
        
        # Convert signature dates if present
        if walkthrough_data.tenant_signature_date:
            walkthrough_dict["tenant_signature_date"] = pd.Timestamp(walkthrough_data.tenant_signature_date)
        else:
            walkthrough_dict["tenant_signature_date"] = None
            
        if walkthrough_data.landlord_signature_date:
            walkthrough_dict["landlord_signature_date"] = pd.Timestamp(walkthrough_data.landlord_signature_date)
        else:
            walkthrough_dict["landlord_signature_date"] = None
        logger.info(f"⏱️  [WALKTHROUGH] Prepared walkthrough dict: {time.time() - step_start:.3f}s")
        
        step_start = time.time()
        # OPTIMIZATION: Store areas as JSON in walkthrough table (much faster than separate table upserts)
        # Preserve existing photos from areas_json or separate table
        existing_areas_map = {}
        
        # Try to get existing areas from areas_json first
        existing_areas_json_str = existing_walkthrough.get("areas_json")
        if existing_areas_json_str:
            try:
                existing_areas_list = json.loads(existing_areas_json_str)
                for area in existing_areas_list:
                    key = f"{area['floor']}|{area['area_name']}"
                    existing_areas_map[key] = area
            except:
                pass
        
        # Fallback to separate table if areas_json doesn't exist
        if not existing_areas_map and table_exists(NAMESPACE, WALKTHROUGH_AREAS_TABLE):
            try:
                existing_areas_df = read_table_filtered(
                    NAMESPACE,
                    WALKTHROUGH_AREAS_TABLE,
                    EqualTo("walkthrough_id", str(walkthrough_id))
                )
                for _, area in existing_areas_df.iterrows():
                    key = f"{area['floor']}|{area['area_name']}"
                    # Convert to JSON format
                    photos = []
                    if area.get("photos"):
                        try:
                            photos = json.loads(area["photos"])
                        except:
                            pass
                    existing_areas_map[key] = {
                        "id": area["id"],
                        "floor": area["floor"],
                        "area_name": area["area_name"],
                        "photos": photos
                    }
            except:
                pass
        
        # Convert areas to JSON string, preserving existing photos
        areas_json_data = []
        for idx, area_data in enumerate(walkthrough_data.areas):
            key = f"{area_data.floor}|{area_data.area_name}"
            existing_area = existing_areas_map.get(key)
            
            # Preserve photos from existing area if it exists
            photos = existing_area.get("photos", []) if existing_area else []
            
            area_json = {
                "id": existing_area["id"] if existing_area else str(uuid.uuid4()),
                "floor": area_data.floor,
                "area_name": area_data.area_name,
                "area_order": idx + 1,
                "inspection_status": area_data.inspection_status,
                "notes": area_data.notes,
                "landlord_fix_notes": area_data.landlord_fix_notes,
                "issues": [issue.model_dump() for issue in area_data.issues] if area_data.issues else [],
                "photos": photos  # Preserve existing photos
            }
            areas_json_data.append(area_json)
        
        walkthrough_dict["areas_json"] = json.dumps(areas_json_data) if areas_json_data else None
        logger.info(f"⏱️  [WALKTHROUGH] Prepared areas JSON ({len(areas_json_data)} areas): {time.time() - step_start:.3f}s")
        
        step_start = time.time()
        # Update walkthrough using upsert - now includes areas_json
        walkthrough_df = pd.DataFrame([walkthrough_dict])
        schema_columns = [field.name for field in walkthroughs_table.schema().fields]
        walkthrough_df = walkthrough_df.reindex(columns=schema_columns, fill_value=None)
        logger.info(f"⏱️  [WALKTHROUGH] Prepared walkthrough DataFrame: {time.time() - step_start:.3f}s")
        
        step_start = time.time()
        from app.core.iceberg import upsert_data
        upsert_data(NAMESPACE, WALKTHROUGHS_TABLE, walkthrough_df, join_cols=["id"])
        logger.info(f"⏱️  [WALKTHROUGH] Upserted walkthrough (with areas_json): {time.time() - step_start:.3f}s")
        
        # Build area responses from JSON data
        area_responses = []
        for area_json in areas_json_data:
            area_responses.append(WalkthroughAreaResponse(
                id=UUID(area_json["id"]),
                walkthrough_id=walkthrough_id,
                floor=area_json["floor"],
                area_name=area_json["area_name"],
                area_order=area_json["area_order"],
                inspection_status=area_json["inspection_status"],
                notes=area_json.get("notes"),
                landlord_fix_notes=area_json.get("landlord_fix_notes"),
                issues=[WalkthroughAreaIssue(**issue) for issue in area_json.get("issues", [])] if area_json.get("issues") else [],
                photos=area_json.get("photos", []),
                created_at=now.to_pydatetime(),
                updated_at=now.to_pydatetime()
            ))
        
        step_start = time.time()
        # Build response
        pdf_url = None
        if walkthrough_dict.get("generated_pdf_blob_name"):
            pdf_url = adls_service.get_blob_download_url(walkthrough_dict["generated_pdf_blob_name"])
        logger.info(f"⏱️  [WALKTHROUGH] Built response: {time.time() - step_start:.3f}s")
        
        total_time = time.time() - start_time
        logger.info(f"✅ [WALKTHROUGH] Update completed in {total_time:.3f}s total")
        
        return WalkthroughResponse(
            id=walkthrough_id,
            user_id=user_id,
            property_id=walkthrough_data.property_id,
            unit_id=walkthrough_data.unit_id if walkthrough_data.unit_id else None,
            property_display_name=property_display_name,
            unit_number=unit_number,
            walkthrough_type=walkthrough_data.walkthrough_type,
            walkthrough_date=walkthrough_dict["walkthrough_date"].to_pydatetime(),
            inspector_name=walkthrough_data.inspector_name,
            tenant_name=walkthrough_data.tenant_name,
            notes=walkthrough_data.notes,
            status=walkthrough_dict["status"],
            tenant_signature=None,
            tenant_signature_date=walkthrough_dict["tenant_signature_date"].to_pydatetime() if walkthrough_dict.get("tenant_signature_date") and pd.notna(walkthrough_dict["tenant_signature_date"]) else None,
            landlord_signature=None,
            landlord_signature_date=walkthrough_dict["landlord_signature_date"].to_pydatetime() if walkthrough_dict.get("landlord_signature_date") and pd.notna(walkthrough_dict["landlord_signature_date"]) else None,
            areas=area_responses,
            pdf_url=pdf_url,
            created_at=walkthrough_dict["created_at"].to_pydatetime(),
            updated_at=walkthrough_dict["updated_at"].to_pydatetime()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        total_time = time.time() - start_time if 'start_time' in locals() else 0
        logger.error(f"Error updating walkthrough (took {total_time:.3f}s): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating walkthrough: {str(e)}")


@router.delete("/{walkthrough_id}", status_code=204)
async def delete_walkthrough(
    walkthrough_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Delete a walkthrough inspection"""
    try:
        user_id = current_user["sub"]
        
        # Get walkthrough to verify it exists and check permissions
        if not table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        walkthroughs_df = read_table_filtered(
            NAMESPACE,
            WALKTHROUGHS_TABLE,
            EqualTo("id", str(walkthrough_id))
        )
        
        if len(walkthroughs_df) == 0:
            logger.warning(f"Delete attempt: Walkthrough {walkthrough_id} not found")
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        # Get the latest version to check permissions
        walkthroughs_df = walkthroughs_df.sort_values("updated_at", ascending=False)
        walkthrough = walkthroughs_df.iloc[0]
        
        # Check if already deleted
        is_active = walkthrough.get("is_active", True)
        if not is_active:
            logger.warning(f"Delete attempt: Walkthrough {walkthrough_id} already deleted")
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        # Verify ownership
        if walkthrough["user_id"] != user_id:
            logger.warning(f"Delete attempt: Walkthrough {walkthrough_id} unauthorized for user {user_id}")
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # HARD DELETE: Remove all rows for this walkthrough ID from Iceberg
        from app.core.iceberg import get_catalog
        
        catalog = get_catalog()
        
        # Delete walkthrough areas first
        if table_exists(NAMESPACE, WALKTHROUGH_AREAS_TABLE):
            areas_table = catalog.load_table((*NAMESPACE, WALKTHROUGH_AREAS_TABLE))
            areas_table.delete(EqualTo("walkthrough_id", str(walkthrough_id)))
            logger.info(f"Deleted all areas for walkthrough {walkthrough_id}")
        
        # Delete walkthrough
        walkthroughs_table = catalog.load_table((*NAMESPACE, WALKTHROUGHS_TABLE))
        walkthroughs_table.delete(EqualTo("id", str(walkthrough_id)))
        logger.info(f"Hard deleted all rows for walkthrough {walkthrough_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting walkthrough: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting walkthrough: {str(e)}")


@router.get("/{walkthrough_id}", response_model=WalkthroughResponse)
async def get_walkthrough(
    walkthrough_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific walkthrough by ID"""
    try:
        user_id = current_user["sub"]
        
        if not table_exists(NAMESPACE, WALKTHROUGHS_TABLE):
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        walkthroughs_df = read_table_filtered(
            NAMESPACE,
            WALKTHROUGHS_TABLE,
            EqualTo("id", str(walkthrough_id))
        )
        
        if len(walkthroughs_df) == 0:
            raise HTTPException(status_code=404, detail="Walkthrough not found")
        
        walkthrough = walkthroughs_df.iloc[0]
        
        # Verify ownership
        if walkthrough["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Get areas - prefer areas_json (new format) over separate table (legacy)
        area_responses = []
        areas_json_str = walkthrough.get("areas_json")
        
        if areas_json_str:
            # New format: areas stored as JSON in walkthrough table
            try:
                areas_data = json.loads(areas_json_str)
                for area_data in areas_data:
                    # Handle photos (may still reference separate table or documents)
                    photos = []
                    if area_data.get("photos"):
                        for photo_data in area_data["photos"]:
                            photo_url = None
                            blob_name = photo_data.get("photo_blob_name", "")
                            
                            if photo_data.get("document_id"):
                                from uuid import UUID as UUIDType
                                try:
                                    photo_url = document_service.get_document_download_url(
                                        UUIDType(photo_data["document_id"]),
                                        UUIDType(walkthrough["user_id"])
                                    )
                                    if not blob_name:
                                        doc = document_service.get_document(
                                            UUIDType(photo_data["document_id"]),
                                            UUIDType(walkthrough["user_id"])
                                        )
                                        if doc:
                                            blob_name = doc.get("blob_name", "")
                                except:
                                    pass
                            
                            if not photo_url and blob_name:
                                photo_url = adls_service.get_blob_download_url(blob_name)
                            
                            photos.append(WalkthroughAreaPhoto(
                                photo_blob_name=blob_name,
                                photo_url=photo_url,
                                notes=photo_data.get("notes"),
                                order=photo_data.get("order", 1),
                                document_id=photo_data.get("document_id")
                            ))
                    
                    area_responses.append(WalkthroughAreaResponse(
                        id=UUID(area_data["id"]),
                        walkthrough_id=walkthrough_id,
                        floor=area_data["floor"],
                        area_name=area_data["area_name"],
                        area_order=area_data.get("area_order", 0),
                        inspection_status=area_data.get("inspection_status", "no_issues"),
                        notes=area_data.get("notes"),
                        landlord_fix_notes=area_data.get("landlord_fix_notes"),
                        issues=[WalkthroughAreaIssue(**issue) for issue in area_data.get("issues", [])],
                        photos=photos,
                        created_at=pd.Timestamp(walkthrough["created_at"]).to_pydatetime(),
                        updated_at=pd.Timestamp(walkthrough["updated_at"]).to_pydatetime()
                    ))
            except Exception as e:
                logger.warning(f"Failed to parse areas_json, falling back to separate table: {e}")
                areas_json_str = None  # Fall through to legacy format
        
        # Legacy format: read from separate areas table
        if not areas_json_str:
            areas_df = pd.DataFrame()
            if table_exists(NAMESPACE, WALKTHROUGH_AREAS_TABLE):
                areas_df = read_table_filtered(
                    NAMESPACE,
                    WALKTHROUGH_AREAS_TABLE,
                    EqualTo("walkthrough_id", str(walkthrough_id))
                )
            
            if len(areas_df) > 0:
                areas_df = areas_df.sort_values("area_order")
                for _, area in areas_df.iterrows():
                    # Deserialize issues and photos
                    issues = []
                if area.get("issues"):
                    try:
                        issues_data = json.loads(area["issues"])
                        from app.schemas.walkthrough import WalkthroughAreaIssue
                        issues = [WalkthroughAreaIssue(**issue) for issue in issues_data]
                    except:
                        pass
                
                photos = []
                if area.get("photos"):
                    try:
                        photos_data = json.loads(area["photos"])
                        # Generate URLs for photos using DocumentService (vault) when available
                        for photo_data in photos_data:
                            photo_url = None
                            blob_name = photo_data.get("photo_blob_name", "")
                            
                            # Prefer document_id (vault) over blob_name for new photos
                            if photo_data.get("document_id"):
                                from uuid import UUID as UUIDType
                                try:
                                    photo_url = document_service.get_document_download_url(
                                        UUIDType(photo_data["document_id"]),
                                        UUIDType(walkthrough["user_id"])
                                    )
                                    # Get blob_name from document if not already present
                                    if not blob_name:
                                        doc = document_service.get_document(
                                            UUIDType(photo_data["document_id"]),
                                            UUIDType(walkthrough["user_id"])
                                        )
                                        if doc:
                                            blob_name = doc.get("blob_name", "")
                                except:
                                    pass
                            
                            # Fallback to direct ADLS URL for backward compatibility
                            if not photo_url and blob_name:
                                photo_url = adls_service.get_blob_download_url(blob_name)
                            
                            photos.append(WalkthroughAreaPhoto(
                                photo_blob_name=blob_name,
                                photo_url=photo_url,
                                notes=photo_data.get("notes"),
                                order=photo_data.get("order", 1),
                                document_id=photo_data.get("document_id")
                            ))
                    except:
                        pass
                
                area_responses.append(WalkthroughAreaResponse(
                    id=UUID(area["id"]),
                    walkthrough_id=UUID(area["walkthrough_id"]),
                    floor=area.get("floor", "Floor 1"),
                    area_name=area["area_name"],
                    area_order=int(area.get("area_order", 0)),
                    inspection_status=area.get("inspection_status", "no_issues"),
                    notes=area.get("notes"),
                    landlord_fix_notes=area.get("landlord_fix_notes"),
                    issues=issues,
                    photos=photos,
                    created_at=pd.Timestamp(area["created_at"]).to_pydatetime(),
                    updated_at=pd.Timestamp(area["updated_at"]).to_pydatetime()
                ))
        
        pdf_url = None
        if walkthrough.get("generated_pdf_blob_name"):
            pdf_url = adls_service.get_blob_download_url(walkthrough["generated_pdf_blob_name"])
        
        return WalkthroughResponse(
            id=UUID(walkthrough["id"]),
            user_id=walkthrough["user_id"],
            property_id=UUID(walkthrough["property_id"]),
            unit_id=UUID(walkthrough["unit_id"]) if walkthrough.get("unit_id") else None,
            property_display_name=walkthrough.get("property_display_name"),
            unit_number=walkthrough.get("unit_number"),
            walkthrough_type=walkthrough["walkthrough_type"],
            walkthrough_date=pd.Timestamp(walkthrough["walkthrough_date"]).date(),
            inspector_name=walkthrough.get("inspector_name"),
            tenant_name=walkthrough.get("tenant_name"),
            tenant_signed=bool(walkthrough.get("tenant_signed", False)),
            tenant_signature_date=pd.Timestamp(walkthrough["tenant_signature_date"]).date() if walkthrough.get("tenant_signature_date") else None,
            landlord_signed=bool(walkthrough.get("landlord_signed", False)),
            landlord_signature_date=pd.Timestamp(walkthrough["landlord_signature_date"]).date() if walkthrough.get("landlord_signature_date") else None,
            notes=walkthrough.get("notes"),
            status=walkthrough["status"],
            generated_pdf_blob_name=walkthrough.get("generated_pdf_blob_name"),
            pdf_url=pdf_url,
            areas=area_responses,
            created_at=pd.Timestamp(walkthrough["created_at"]).to_pydatetime(),
            updated_at=pd.Timestamp(walkthrough["updated_at"]).to_pydatetime()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting walkthrough: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting walkthrough: {str(e)}")

