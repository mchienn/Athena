"""Read-only schedule lookup tools backed by Google Cloud Firestore."""

from __future__ import annotations

from typing import Any


def search_published_schedule(
    work_date: str | None = None,
    room_name: str | None = None,
    shift: str | None = None,
) -> dict[str, Any]:
    """Find published doctor shifts by date, room, and morning/afternoon shift (Direct Firestore Query)."""
    if shift is not None and shift not in {"morning", "afternoon"}:
        return {"status": "error", "message": "Ca chỉ có thể là morning hoặc afternoon."}

    try:
        from hanoi_heart_assistant.tools.firebase_vector_tools import _firestore_client
        fs = _firestore_client()
        query = fs.collection("schedule_shifts") \
            .where("import_status", "==", "published") \
            .where("state", "==", "working")
            
        if work_date:
            query = query.where("work_date", "==", work_date)
        if shift:
            query = query.where("shift", "==", shift)
            
        docs = query.stream()
        matches = []
        for doc in docs:
            d = doc.to_dict()
            if room_name and room_name.lower() not in d.get("room_name", "").lower():
                continue
            matches.append({
                "import_id": d.get("import_id"),
                "area_name": d.get("area_name"),
                "room_name": d.get("room_name"),
                "work_time": d.get("work_time"),
                "work_date": d.get("work_date"),
                "label": d.get("day_label"),
                "shift": d.get("shift"),
                "state": d.get("state"),
                "value": d.get("value")
            })
            
        # Sort matches by work_date, area_name, room_name, shift
        matches.sort(key=lambda x: (
            x.get("work_date", ""),
            x.get("area_name", ""),
            x.get("room_name", ""),
            x.get("shift", "")
        ))
        return {"status": "success", "matches": matches, "count": len(matches), "source": "firestore"}
    except Exception as e:
        return {"status": "error", "message": f"Error querying Firestore: {e}"}
