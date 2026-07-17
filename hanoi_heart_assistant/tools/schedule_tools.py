"""Read-only schedule lookup tools backed by the Module 4 SQLite database."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DB = Path(__file__).resolve().parents[1] / "data" / "schedule.db"


def search_published_schedule(
    work_date: str | None = None,
    room_name: str | None = None,
    shift: str | None = None,
) -> dict[str, Any]:
    """Find published doctor shifts by date, room, and morning/afternoon shift."""
    if shift is not None and shift not in {"morning", "afternoon"}:
        return {"status": "error", "message": "Ca chỉ có thể là morning hoặc afternoon."}

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

    if not DB.exists():
        return {"status": "success", "matches": [], "notice": "Chưa có dữ liệu lịch."}
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        matches = [dict(row) for row in con.execute(query, params)]
    return {"status": "success", "matches": matches, "count": len(matches)}
