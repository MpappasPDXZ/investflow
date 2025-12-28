"""SQLAlchemy models"""
import uuid
from datetime import date
from sqlalchemy import (
    Column, String, Integer, Numeric, Boolean, Date, Text, 
    ForeignKey, UniqueConstraint, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID, JSONB  # Note: Used for compatibility, data stored in Iceberg
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin
import enum


# Enums
class ExpenseType(str, enum.Enum):
    CAPEX = "capex"
    PANDI = "pandi"
    UTILITIES = "utilities"
    MAINTENANCE = "maintenance"
    INSURANCE = "insurance"
    PROPERTY_MANAGEMENT = "property_management"
    OTHER = "other"


class DocumentType(str, enum.Enum):
    RECEIPT = "receipt"
    LEASE = "lease"
    BACKGROUND_CHECK = "background_check"
    CONTRACT = "contract"
    INVOICE = "invoice"
    OTHER = "other"


class PaymentMethod(str, enum.Enum):
    CHECK = "check"
    CASH = "cash"
    ELECTRONIC = "electronic"
    MONEY_ORDER = "money_order"
    OTHER = "other"


class PropertyStatus(str, enum.Enum):
    OWN = "own"
    EVALUATING = "evaluating"
    REHABBING = "rehabbing"
    LISTED_FOR_RENT = "listed_for_rent"
    LISTED_FOR_SALE = "listed_for_sale"
    SOLD = "sold"
    HIDE = "hide"


class User(Base, TimestampMixin):
    """User model"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    tax_rate = Column(Numeric(5, 2), nullable=True)  # Tax rate for breakeven pro forma (e.g., 0.22 for 22%)
    mortgage_interest_rate = Column(Numeric(5, 4), nullable=True)  # 30-year mortgage rate (e.g., 0.0700 for 7%)
    loc_interest_rate = Column(Numeric(5, 4), nullable=True)  # Line of Credit interest rate (e.g., 0.0700 for 7%)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    properties = relationship("Property", back_populates="user", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="user", cascade="all, delete-orphan")


class Property(Base, TimestampMixin):
    """Property model"""
    __tablename__ = "properties"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    purchase_price = Column(Numeric(12, 2), nullable=False)
    down_payment = Column(Numeric(12, 2), nullable=True)
    cash_invested = Column(Numeric(12, 2), nullable=True)  # Total cash out of pocket (manual entry)
    current_market_value = Column(Numeric(12, 2), nullable=True)
    property_status = Column(SQLEnum(PropertyStatus), default=PropertyStatus.EVALUATING, nullable=False)
    vacancy_rate = Column(Numeric(5, 4), default=0.07, nullable=False)  # Default 7% vacancy rate
    monthly_rent_to_income_ratio = Column(Numeric(4, 2), default=2.75, nullable=False)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    property_type = Column(String(50), nullable=True)  # 'single_family', 'multi_family', 'condo', 'townhouse'
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Numeric(3, 1), nullable=True)
    square_feet = Column(Integer, nullable=True)
    year_built = Column(Integer, nullable=True)
    current_monthly_rent = Column(Numeric(10, 2), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="properties")
    property_plans = relationship("PropertyPlan", back_populates="property", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="property", cascade="all, delete-orphan")
    clients = relationship("Client", back_populates="property", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="property", cascade="all, delete-orphan")


class PropertyPlan(Base, TimestampMixin):
    """Property plan model for annual tax planning"""
    __tablename__ = "property_plan"  # Matches Iceberg table name
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    annual_tax = Column(Numeric(10, 2), nullable=False)
    annual_property_taxes = Column(Numeric(10, 2), nullable=False)
    plan_year = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relationships
    property = relationship("Property", back_populates="property_plans")
    
    # Unique constraint: one plan per property per year
    __table_args__ = (
        UniqueConstraint('property_id', 'plan_year', name='uq_property_plan_year'),
    )


class Expense(Base, TimestampMixin):
    """Expense model"""
    __tablename__ = "expenses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(String(500), nullable=False)
    date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(10, 2), nullable=False)
    vendor = Column(String(255), nullable=True)
    expense_type = Column(SQLEnum(ExpenseType), nullable=False, index=True)
    document_storage_id = Column(UUID(as_uuid=True), ForeignKey("document_storage.id", ondelete="SET NULL"), nullable=True)
    is_planned = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    property = relationship("Property", back_populates="expenses")
    document = relationship("DocumentStorage", foreign_keys=[document_storage_id])
    
    # Indexes
    __table_args__ = (
        Index('idx_expenses_property_date', 'property_id', 'date'),
        Index('idx_expenses_type', 'expense_type'),
    )


class DocumentStorage(Base, TimestampMixin):
    """Document storage model"""
    __tablename__ = "document_storage"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    blob_location = Column(String(500), nullable=False)  # URL or path to blob storage
    file_name = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=True)  # MIME type
    file_size = Column(Integer, nullable=True)  # Size in bytes
    document_type = Column(SQLEnum(DocumentType), nullable=True)
    document_metadata = Column(JSONB, nullable=True)  # Additional metadata (OCR text, tags, etc.)
    uploaded_by_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(Date, nullable=True)


class Client(Base, TimestampMixin):
    """Client/Tenant model"""
    __tablename__ = "clients"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(20), nullable=True)
    phone_secondary = Column(String(20), nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    emergency_contact_name = Column(String(200), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)
    annual_income = Column(Numeric(12, 2), nullable=True)
    lease_start_date = Column(Date, nullable=True)
    lease_end_date = Column(Date, nullable=True)
    monthly_rent_amount = Column(Numeric(10, 2), nullable=True)
    security_deposit = Column(Numeric(10, 2), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    property = relationship("Property", back_populates="clients")
    rents = relationship("Rent", back_populates="client", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_clients_property', 'property_id'),
    )


class Rent(Base, TimestampMixin):
    """Rent collection model"""
    __tablename__ = "rents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id = Column(UUID(as_uuid=True), nullable=True, index=True)  # Optional unit reference
    amount = Column(Numeric(10, 2), nullable=False)
    rent_period_start = Column(Date, nullable=False)
    rent_period_end = Column(Date, nullable=False)
    payment_date = Column(Date, nullable=False, index=True)
    payment_method = Column(SQLEnum(PaymentMethod), nullable=True)
    transaction_reference = Column(String(255), nullable=True)  # Check number, transaction ID, etc.
    is_late = Column(Boolean, default=False, nullable=False)
    late_fee = Column(Numeric(10, 2), default=0, nullable=True)
    notes = Column(Text, nullable=True)
    created_by_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    client = relationship("Client", back_populates="rents")
    
    # Indexes
    __table_args__ = (
        Index('idx_rents_property_date', 'property_id', 'payment_date'),
        Index('idx_rents_client_date', 'client_id', 'payment_date'),
        Index('idx_rents_unit_date', 'unit_id', 'payment_date'),
    )


class Scenario(Base, TimestampMixin):
    """Rent scenario analysis model"""
    __tablename__ = "scenarios"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_name = Column(String(100), nullable=True)  # "Conservative", "Optimistic", etc.
    monthly_rent = Column(Numeric(10, 2), nullable=False)
    vacancy_rate = Column(Numeric(5, 2), default=7.00, nullable=False)  # Percentage (e.g., 7.00 for 7%)
    annual_expenses = Column(Numeric(10, 2), default=44558.00, nullable=False)
    tax_savings = Column(Numeric(10, 2), default=7029.00, nullable=False)
    annual_appreciation = Column(Numeric(10, 2), default=17520.00, nullable=False)
    purchase_price = Column(Numeric(12, 2), nullable=False)
    down_payment = Column(Numeric(12, 2), nullable=False)
    # Calculated fields (stored for historical reference)
    annual_rent = Column(Numeric(10, 2), nullable=True)  # (monthly_rent * 12) * (1 - vacancy_rate / 100)
    cash_on_cash_roi = Column(Numeric(5, 2), nullable=True)  # ((annual_rent - annual_expenses) / down_payment) * 100
    total_roi = Column(Numeric(5, 2), nullable=True)  # ((annual_rent - annual_expenses + tax_savings + annual_appreciation) / purchase_price) * 100
    net_cash_flow = Column(Numeric(10, 2), nullable=True)  # annual_rent - annual_expenses
    
    # Relationships
    property = relationship("Property", back_populates="scenarios")
    user = relationship("User", back_populates="scenarios")
    
    # Indexes
    __table_args__ = (
        Index('idx_scenarios_property', 'property_id'),
        Index('idx_scenarios_user', 'user_id'),
    )


class Walkthrough(Base, TimestampMixin):
    """Property walkthrough inspection model"""
    __tablename__ = "walkthroughs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id = Column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"), nullable=True)
    
    walkthrough_type = Column(String(50), nullable=False, default="move_in")  # move_in, move_out, periodic, maintenance
    walkthrough_date = Column(Date, nullable=False, default=date.today)
    status = Column(String(50), nullable=False, default="draft")  # draft, pending_signature, completed
    
    inspector_name = Column(String(200), nullable=True)
    tenant_name = Column(String(200), nullable=True)
    tenant_signed = Column(Boolean, default=False, nullable=False)
    tenant_signature_date = Column(Date, nullable=True)
    landlord_signed = Column(Boolean, default=False, nullable=False)
    landlord_signature_date = Column(Date, nullable=True)
    
    notes = Column(Text, nullable=True)
    
    generated_pdf_blob_name = Column(String(500), nullable=True)  # ADLS blob name
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    user = relationship("User")
    property = relationship("Property")
    areas = relationship("WalkthroughArea", back_populates="walkthrough", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_walkthroughs_property', 'property_id'),
        Index('idx_walkthroughs_user', 'user_id'),
    )


class WalkthroughArea(Base, TimestampMixin):
    """Individual area within a walkthrough inspection"""
    __tablename__ = "walkthrough_areas"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    walkthrough_id = Column(UUID(as_uuid=True), ForeignKey("walkthroughs.id", ondelete="CASCADE"), nullable=False, index=True)
    
    floor = Column(String(100), nullable=False)  # "Basement", "Floor 1", "Floor 2"
    area_name = Column(String(100), nullable=False)  # "Living Room", "Kitchen", "Bathroom"
    area_order = Column(Integer, nullable=False, default=1)
    inspection_status = Column(String(50), nullable=False, default="no_issues")  # no_issues, issue_noted_as_is, issue_landlord_to_fix
    notes = Column(Text, nullable=True)  # General notes (available for all statuses)
    landlord_fix_notes = Column(Text, nullable=True)  # Required notes when landlord will fix (only for issue_landlord_to_fix)
    
    # Issues stored as JSON array
    issues = Column(Text, nullable=True)  # JSON: [{"description": "...", "severity": "minor", "estimated_cost": 50.00}]
    
    # Photos stored as JSON array
    photos = Column(Text, nullable=True)  # JSON: [{"blob_name": "...", "notes": "...", "order": 1}]
    
    # Relationships
    walkthrough = relationship("Walkthrough", back_populates="areas")
    
    __table_args__ = (
        Index('idx_walkthrough_areas_walkthrough', 'walkthrough_id'),
    )

