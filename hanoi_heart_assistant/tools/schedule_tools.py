"""Read-only schedule lookup tools backed by the Module 4 SQLite database with Firestore fallback."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DB = Path(__file__).resolve().parents[1] / "data" / "schedule.db"


def search_published_schedule_firestore(
    work_date: str | None = None,
    room_name: str | None = None,
    shift: str | None = None,
) -> list[dict[str, Any]]:
    """Query published doctor schedules directly from Cloud Firestore."""
    try:
        from hanoi_heart_assistant.tools.firebase_vector_tools import _firestore_client
        fs = _firestore_client()
        query = fs.collection("published_schedules").where("state", "==", "working")
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
                "value": d.get("doctor_name")
            })
        # Sort by date, area, room, shift
        matches.sort(key=lambda x: (
            x.get("work_date", ""), 
            x.get("area_name", ""), 
            x.get("room_name", ""), 
            x.get("shift", "")
        ))
        return matches
    except Exception as e:
        print(f"Error querying published_schedules from Firestore: {e}")
        return []


def search_published_schedule(
    work_date: str | None = None,
    room_name: str | None = None,
    shift: str | None = None,
) -> dict[str, Any]:
    """Find published doctor shifts by date, room, and morning/afternoon shift (SQLite with Firestore fallback)."""
    if shift is not None and shift not in {"morning", "afternoon"}:
        return {"status": "error", "message": "Ca chỉ có thể là morning hoặc afternoon."}

    if not DB.exists():
        matches = search_published_schedule_firestore(work_date, room_name, shift)
        return {"status": "success", "matches": matches, "count": len(matches), "source": "firestore"}

    query = """
        SELECT i.id AS import_id, a.name AS area_name, r.name AS room_name,
               r.work_time, d.work_date, d.label, s.shift, s.state, s.value
        FROM schedule_shifts s
        JOIN schedule_rooms r ON r.id = s.room_id
        JOIN schedule_areas a ON a.id = r.area_id
        JOIN schedule_days d ON d.id = s.day_id
        JOIN schedule_imports i ON i.id = a.import_id
        WHERE i.status = 'published' AND s.state = 'working'
    """
    params: list[str] = []
    if work_date:
        query += " AND d.work_date = ?"
        params.append(work_date)
    if room_name:
        query += " AND r.name LIKE ?"
        params.append(f"%{room_name}%")
    if shift:
        query += " AND s.shift = ?"
        params.append(shift)
    query += " ORDER BY d.work_date, a.sort_order, r.sort_order, s.shift"

    try:
        with sqlite3.connect(DB) as con:
            con.row_factory = sqlite3.Row
            matches = [dict(row) for row in con.execute(query, params)]
        return {"status": "success", "matches": matches, "count": len(matches), "source": "sqlite"}
    except sqlite3.Error:
        # Fallback to Firestore if local query fails due to database locks or schema mismatch
        matches = search_published_schedule_firestore(work_date, room_name, shift)
        return {"status": "success", "matches": matches, "count": len(matches), "source": "firestore"}
