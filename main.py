import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import db, create_document, get_documents
from schemas import Complaint, Notification
from bson import ObjectId

app = FastAPI(title="Internet Complaint Register API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Utility helpers
# -----------------------------

def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

# -----------------------------
# Health & test
# -----------------------------

@app.get("/")
def read_root():
    return {"message": "Internet Complaint Register API running"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, 'name', None) or "❌ Unknown"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# -----------------------------
# Pydantic DTOs for requests
# -----------------------------

class ComplaintCreate(Complaint):
    pass

class ComplaintUpdate(BaseModel):
    subject: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = Field(None, description="low, normal, high, urgent")
    status: Optional[str] = Field(None, description="pending, process, complete")
    assigned_team: Optional[str] = None
    note: Optional[str] = Field(None, description="A single update note to append to timeline")

class AssignTeamRequest(BaseModel):
    team: str

class MarkReadRequest(BaseModel):
    is_read: bool = True

# -----------------------------
# Complaints Endpoints
# -----------------------------

@app.post("/api/complaints", status_code=201)
def create_complaint(payload: ComplaintCreate):
    comp_id = create_document("complaint", payload)
    # create a notification for 'admin'
    notif = Notification(
        user_id="admin",
        title="New complaint submitted",
        message=f"{payload.customer_name} reported: {payload.subject}",
        type="info",
        related_complaint_id=comp_id
    )
    create_document("notification", notif)
    return {"id": comp_id}

@app.get("/api/complaints")
def list_complaints(status: Optional[str] = None, priority: Optional[str] = None):
    filt = {}
    if status:
        filt["status"] = status
    if priority:
        filt["priority"] = priority
    items = get_documents("complaint", filt)
    # Convert ObjectIds to strings
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

@app.get("/api/complaints/{complaint_id}")
def get_complaint(complaint_id: str):
    docs = get_documents("complaint", {"_id": oid(complaint_id)})
    if not docs:
        raise HTTPException(status_code=404, detail="Complaint not found")
    doc = docs[0]
    doc["id"] = str(doc.pop("_id"))
    return doc

@app.patch("/api/complaints/{complaint_id}")
def update_complaint(complaint_id: str, payload: ComplaintUpdate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    update_fields = {k: v for k, v in payload.model_dump().items() if v is not None and k != "note"}
    update_fields["updated_at"] = datetime.now(timezone.utc)
    if payload.note:
        note_entry = {
            "text": payload.note,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        update_op = {"$set": update_fields, "$push": {"notes": note_entry}}
    else:
        update_op = {"$set": update_fields}

    result = db["complaint"].update_one({"_id": oid(complaint_id)}, update_op)
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Complaint not found")

    # Notification on status change
    if "status" in update_fields:
        notif = Notification(
            user_id="admin",
            title="Complaint status updated",
            message=f"Complaint {complaint_id} status: {update_fields['status']}",
            type="success" if update_fields["status"] == "complete" else "info",
            related_complaint_id=complaint_id
        )
        create_document("notification", notif)

    return {"updated": True}

@app.post("/api/complaints/{complaint_id}/assign")
def assign_team(complaint_id: str, req: AssignTeamRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    result = db["complaint"].update_one(
        {"_id": oid(complaint_id)},
        {"$set": {"assigned_team": req.team, "status": "process", "updated_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Complaint not found")

    notif = Notification(
        user_id=req.team,
        title="New assignment",
        message=f"You have been assigned complaint {complaint_id}",
        type="warning",
        related_complaint_id=complaint_id
    )
    create_document("notification", notif)
    return {"assigned": True}

# -----------------------------
# Notifications Endpoints
# -----------------------------

@app.get("/api/notifications")
def list_notifications(user_id: Optional[str] = None, unread_only: bool = False):
    filt = {}
    if user_id:
        filt["user_id"] = user_id
    if unread_only:
        filt["is_read"] = False
    items = get_documents("notification", filt)
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items

@app.patch("/api/notifications/{notification_id}")
def mark_notification(notification_id: str, req: MarkReadRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    result = db["notification"].update_one(
        {"_id": oid(notification_id)},
        {"$set": {"is_read": req.is_read, "updated_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"updated": True}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
