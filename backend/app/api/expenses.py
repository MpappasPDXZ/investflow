"""API routes for expense management"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from typing import List, Optional
from uuid import UUID
from datetime import date

from app.core.dependencies import get_current_user
from app.schemas.expense import (
    ExpenseCreate, ExpenseUpdate, ExpenseResponse, ExpenseListResponse, ExpenseSummaryResponse,
    ExpenseCategory
)
from app.services import expense_service, document_service
from app.core.logging import get_logger

router = APIRouter(prefix="/expenses", tags=["expenses"])
logger = get_logger(__name__)


@router.post("", response_model=ExpenseResponse, status_code=201)
async def create_expense_endpoint(
    expense_data: ExpenseCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new expense"""
    try:
        user_id = UUID(current_user["sub"])
        expense_dict = expense_service.create_expense(
            user_id=user_id,
            expense_data=expense_data
        )
        return ExpenseResponse(**expense_dict)
    except Exception as e:
        logger.error(f"Error creating expense: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/with-receipt", response_model=ExpenseResponse, status_code=201)
async def create_expense_with_receipt(
    property_id: UUID = Form(...),
    description: str = Form(...),
    date: str = Form(...),  # ISO date string
    amount: str = Form(...),  # Decimal as string
    vendor: Optional[str] = Form(None),
    expense_type: str = Form(...),
    expense_category: Optional[str] = Form(None),
    unit_id: Optional[str] = Form(None),
    is_planned: bool = Form(False),
    notes: Optional[str] = Form(None),
    document_type: Optional[str] = Form("receipt"),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Create a new expense with receipt upload"""
    try:
        from datetime import datetime
        from decimal import Decimal
        from app.schemas.expense import ExpenseType
        
        user_id = UUID(current_user["sub"])
        
        # Upload document first
        file_content = await file.read()
        document = document_service.upload_document(
            user_id=user_id,
            file_content=file_content,
            filename=file.filename or "receipt",
            content_type=file.content_type or "application/octet-stream",
            document_type=document_type or "receipt",
            property_id=property_id,
            unit_id=UUID(unit_id) if unit_id else None
        )
        
        # Create expense with document_storage_id
        expense_data = ExpenseCreate(
            property_id=property_id,
            unit_id=UUID(unit_id) if unit_id else None,
            description=description,
            date=datetime.fromisoformat(date).date(),
            amount=Decimal(amount),
            vendor=vendor,
            expense_type=ExpenseType(expense_type),
            expense_category=ExpenseCategory(expense_category) if expense_category else None,
            document_storage_id=UUID(document["id"]),
            is_planned=is_planned,
            notes=notes
        )
        
        expense_dict = expense_service.create_expense(user_id=user_id, expense_data=expense_data)
        return ExpenseResponse(**expense_dict)
        
    except Exception as e:
        logger.error(f"Error creating expense with receipt: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=ExpenseListResponse)
async def list_expenses_endpoint(
    property_id: Optional[UUID] = Query(None, description="Filter by property ID"),
    unit_id: Optional[UUID] = Query(None, description="Filter by unit ID"),
    start_date: Optional[date] = Query(None, description="Filter by start date"),
    end_date: Optional[date] = Query(None, description="Filter by end date"),
    expense_type: Optional[str] = Query(None, description="Filter by expense type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(get_current_user)
):
    """List expenses for the current user"""
    try:
        user_id = UUID(current_user["sub"])
        expenses, total = expense_service.list_expenses(
            user_id=user_id,
            property_id=property_id,
            unit_id=unit_id,
            start_date=start_date,
            end_date=end_date,
            expense_type=expense_type,
            skip=skip,
            limit=limit
        )
        
        items = [ExpenseResponse(**exp) for exp in expenses]
        
        return ExpenseListResponse(
            items=items,
            total=total,
            page=(skip // limit) + 1 if limit > 0 else 1,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Error listing expenses: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=ExpenseSummaryResponse)
async def get_expense_summary_endpoint(
    property_id: Optional[UUID] = Query(None, description="Filter by property ID"),
    year: Optional[int] = Query(None, description="Filter by year"),
    current_user: dict = Depends(get_current_user)
):
    """Get expense summary with yearly subtotals"""
    try:
        user_id = UUID(current_user["sub"])
        summary = expense_service.get_expense_summary(
            user_id=user_id,
            property_id=property_id,
            year=year
        )
        return ExpenseSummaryResponse(**summary)
    except Exception as e:
        logger.error(f"Error getting expense summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense_endpoint(
    expense_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get an expense by ID"""
    try:
        user_id = UUID(current_user["sub"])
        expense_dict = expense_service.get_expense(expense_id, user_id)
        
        if not expense_dict:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        return ExpenseResponse(**expense_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting expense: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense_endpoint(
    expense_id: UUID,
    expense_data: ExpenseUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update an expense"""
    try:
        user_id = UUID(current_user["sub"])
        expense_dict = expense_service.update_expense(expense_id, user_id, expense_data)
        
        if not expense_dict:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        return ExpenseResponse(**expense_dict)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating expense: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{expense_id}", status_code=204)
async def delete_expense_endpoint(
    expense_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Delete an expense"""
    try:
        user_id = UUID(current_user["sub"])
        success = expense_service.delete_expense(expense_id, user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting expense: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{expense_id}/receipt")
async def get_expense_receipt(
    expense_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get receipt download URL for an expense"""
    try:
        user_id = UUID(current_user["sub"])
        expense_dict = expense_service.get_expense(expense_id, user_id)
        
        if not expense_dict:
            raise HTTPException(status_code=404, detail="Expense not found")
        
        if not expense_dict.get("document_storage_id"):
            raise HTTPException(status_code=404, detail="No receipt attached to this expense")
        
        download_url = document_service.get_document_download_url(
            UUID(expense_dict["document_storage_id"]), 
            user_id
        )
        
        if not download_url:
            raise HTTPException(status_code=404, detail="Receipt not found")
        
        return {"download_url": download_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting expense receipt: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

