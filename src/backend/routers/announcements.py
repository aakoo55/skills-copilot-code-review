"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from pydantic import BaseModel

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class AnnouncementCreate(BaseModel):
    message: str
    start_date: Optional[date] = None
    end_date: date


class AnnouncementUpdate(BaseModel):
    message: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


@router.get("", response_model=List[Dict[str, Any]])
@router.get("/", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """
    Get all active announcements (within their date range)
    """
    today = datetime.now().date()
    
    # Query for announcements that are currently active
    query = {
        "end_date": {"$gte": today.isoformat()},
        "$or": [
            {"start_date": {"$lte": today.isoformat()}},
            {"start_date": None}
        ]
    }
    
    announcements = []
    for announcement in announcements_collection.find(query).sort("created_at", -1):
        # Convert ObjectId to string for JSON serialization
        announcement["id"] = str(announcement["_id"])
        del announcement["_id"]
        announcements.append(announcement)
    
    return announcements


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str = Query(...)) -> List[Dict[str, Any]]:
    """
    Get all announcements (for management interface) - requires teacher authentication
    """
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")
    
    announcements = []
    for announcement in announcements_collection.find().sort("created_at", -1):
        # Convert ObjectId to string for JSON serialization
        announcement["id"] = str(announcement["_id"])
        del announcement["_id"]
        announcements.append(announcement)
    
    return announcements


@router.post("", response_model=Dict[str, Any])
@router.post("/", response_model=Dict[str, Any])
def create_announcement(
    announcement: AnnouncementCreate,
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    """
    Create a new announcement - requires teacher authentication
    """
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")
    
    # Validate dates
    if announcement.start_date and announcement.start_date > announcement.end_date:
        raise HTTPException(
            status_code=400, detail="Start date cannot be after end date")
    
    # Create announcement document
    announcement_doc = {
        "message": announcement.message,
        "start_date": announcement.start_date.isoformat() if announcement.start_date else None,
        "end_date": announcement.end_date.isoformat(),
        "created_at": datetime.now(),
        "created_by": teacher_username,
        "created_by_name": teacher["display_name"]
    }
    
    # Insert into database
    result = announcements_collection.insert_one(announcement_doc)
    
    # Return the created announcement
    created_announcement = announcements_collection.find_one({"_id": result.inserted_id})
    created_announcement["id"] = str(created_announcement["_id"])
    del created_announcement["_id"]
    
    return created_announcement


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    announcement: AnnouncementUpdate,
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    """
    Update an existing announcement - requires teacher authentication
    """
    from bson import ObjectId
    from bson.errors import InvalidId
    
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")
    
    # Validate announcement ID
    try:
        object_id = ObjectId(announcement_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    # Check if announcement exists
    existing_announcement = announcements_collection.find_one({"_id": object_id})
    if not existing_announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    # Build update document
    update_doc = {"updated_at": datetime.now(), "updated_by": teacher_username}
    
    if announcement.message is not None:
        update_doc["message"] = announcement.message
    
    if announcement.start_date is not None:
        update_doc["start_date"] = announcement.start_date.isoformat()
    
    if announcement.end_date is not None:
        update_doc["end_date"] = announcement.end_date.isoformat()
    
    # Validate dates if both are provided
    start_date = announcement.start_date if announcement.start_date is not None else (
        datetime.fromisoformat(existing_announcement["start_date"]).date() 
        if existing_announcement.get("start_date") else None
    )
    end_date = announcement.end_date if announcement.end_date is not None else (
        datetime.fromisoformat(existing_announcement["end_date"]).date()
    )
    
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400, detail="Start date cannot be after end date")
    
    # Update the announcement
    result = announcements_collection.update_one(
        {"_id": object_id},
        {"$set": update_doc}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=500, detail="Failed to update announcement")
    
    # Return the updated announcement
    updated_announcement = announcements_collection.find_one({"_id": object_id})
    updated_announcement["id"] = str(updated_announcement["_id"])
    del updated_announcement["_id"]
    
    return updated_announcement


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: str = Query(...)
) -> Dict[str, str]:
    """
    Delete an announcement - requires teacher authentication
    """
    from bson import ObjectId
    from bson.errors import InvalidId
    
    # Check teacher authentication
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(
            status_code=401, detail="Authentication required for this action")
    
    # Validate announcement ID
    try:
        object_id = ObjectId(announcement_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    # Delete the announcement
    result = announcements_collection.delete_one({"_id": object_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    return {"message": "Announcement deleted successfully"}