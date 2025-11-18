"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# ---------------------------------------------------------------------
# Example schemas (kept for reference)
# ---------------------------------------------------------------------
class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# ---------------------------------------------------------------------
# Internet Complaint Register App Schemas
# ---------------------------------------------------------------------

class Complaint(BaseModel):
    """
    Internet service complaint submitted by customers, admins, or team members.
    Collection name: "complaint"
    """
    customer_name: str
    customer_contact: str = Field(..., description="Email or phone")
    address: Optional[str] = None
    subject: str
    description: str
    priority: str = Field("normal", description="low, normal, high, urgent")
    status: str = Field("pending", description="pending, process, complete")
    assigned_team: Optional[str] = Field(None, description="Team name handling the complaint")
    notes: List[dict] = Field(default_factory=list, description="Timeline notes/updates")

class Notification(BaseModel):
    """
    Lightweight notification for users about complaint updates.
    Collection name: "notification"
    """
    user_id: str = Field(..., description="Identifier like email/username/team name")
    title: str
    message: str
    type: str = Field("info", description="info, success, warning, error")
    is_read: bool = False
    related_complaint_id: Optional[str] = None

class Team(BaseModel):
    """
    Optional team collection for future extensions.
    Collection name: "team"
    """
    name: str
    description: Optional[str] = None
    is_active: bool = True

class Admin(BaseModel):
    """
    Optional admin collection for future extensions.
    Collection name: "admin"
    """
    name: str
    email: Optional[str] = None
    is_active: bool = True

# Timestamps like created_at/updated_at are auto-added by database helpers
# when using create_document(). For updates, backend endpoints will set
# updated_at accordingly.
