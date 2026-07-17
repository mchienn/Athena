"""Excel schedule-review component for the Hanoi Heart Hospital assistant.

Use ``app`` to run this module by itself during development, or use
``mount_schedule(host_app)`` to attach it beneath an existing FastAPI service.
The published shift records are read by ``tools.schedule_tools``.
"""

from __future__ import annotations

import re
import os
import shutil
import sqlite3
import uuid
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, File, HTTPException, UploadFile, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from hanoi_heart_assistant.tools.firebase_vector_tools import _firestore_client

PACKAGE_ROOT = Path(__file__).resolve().parent
DATA = PACKAGE_ROOT / "data"
UPLOADS = DATA / "schedule_uploads"
DB = DATA / "schedule.db"
STATIC = PACKAGE_ROOT / "static" / "schedule"
DATA.mkdir(exist_ok=True)
UPLOADS.mkdir(exist_ok=True)

EMPTY, CLOSED, WORKING = "empty", "closed", "working"
MORNING, AFTERNOON = "morning", "afternoon"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
router = APIRouter()


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 5000")
    return con


def init_db() -> None:
    with db() as con:
        con.execute("PRAGMA journal_mode = WAL")
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS schedule_imports (
              id INTEGER PRIMARY KEY, original_name TEXT NOT NULL, file_path TEXT NOT NULL,
              sheet_name TEXT NOT NULL, title TEXT, week_start TEXT, week_end TEXT,
              facility INTEGER DEFAULT 1,
              status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'published')),
              created_at TEXT NOT NULL, approved_at TEXT
            );
            CREATE TABLE IF NOT EXISTS schedule_areas (
              id INTEGER PRIMARY KEY,
              import_id INTEGER NOT NULL REFERENCES schedule_imports(id) ON DELETE CASCADE,
              name TEXT NOT NULL, sort_order INTEGER NOT NULL,
              UNIQUE(import_id, sort_order)
            );
            CREATE TABLE IF NOT EXISTS schedule_rooms (
              id INTEGER PRIMARY KEY,
              area_id INTEGER NOT NULL REFERENCES schedule_areas(id) ON DELETE CASCADE,
              name TEXT NOT NULL, work_time TEXT, sort_order INTEGER NOT NULL,
              UNIQUE(area_id, sort_order)
            );
            CREATE TABLE IF NOT EXISTS schedule_days (
              id INTEGER PRIMARY KEY,
              import_id INTEGER NOT NULL REFERENCES schedule_imports(id) ON DELETE CASCADE,
              work_date TEXT, label TEXT NOT NULL, sort_order INTEGER NOT NULL,
              UNIQUE(import_id, sort_order)
            );
            CREATE TABLE IF NOT EXISTS schedule_shifts (
              id INTEGER PRIMARY KEY,
              room_id INTEGER NOT NULL REFERENCES schedule_rooms(id) ON DELETE CASCADE,
              day_id INTEGER NOT NULL REFERENCES schedule_days(id) ON DELETE CASCADE,
              shift TEXT NOT NULL CHECK(shift IN ('morning', 'afternoon')),
              state TEXT NOT NULL CHECK(state IN ('working', 'closed', 'empty')),
              value TEXT,
              booked_count INTEGER DEFAULT 0 CHECK(booked_count >= 0),
              updated_at TEXT NOT NULL,
              UNIQUE(room_id, day_id, shift),
              CHECK((state = 'working' AND value IS NOT NULL AND trim(value) <> '')
                 OR (state IN ('closed', 'empty') AND value IS NULL))
            );
            CREATE INDEX IF NOT EXISTS idx_schedule_shift_day
              ON schedule_shifts(day_id, shift, state);
            CREATE INDEX IF NOT EXISTS idx_schedule_shift_room
              ON schedule_shifts(room_id, day_id);
            """
        )
        try:
            cursor = con.execute("PRAGMA table_info(schedule_imports)")
            cols = [row["name"] for row in cursor.fetchall()]
            if "facility" not in cols:
                con.execute("ALTER TABLE schedule_imports ADD COLUMN facility INTEGER DEFAULT 1")
                
            cursor2 = con.execute("PRAGMA table_info(schedule_shifts)")
            cols2 = [row["name"] for row in cursor2.fetchall()]
            if "booked_count" not in cols2:
                con.execute("ALTER TABLE schedule_shifts ADD COLUMN booked_count INTEGER DEFAULT 0")
        except Exception:
            pass


def column_number(reference: str) -> int:
    number = 0
    for character in re.match(r"[A-Z]+", reference).group(0):
        number = number * 26 + ord(character) - 64
    return number


def cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    value = cell.find("m:v", NS)
    text = value.text if value is not None and value.text else ""
    if cell.attrib.get("t") == "s" and text.isdigit() and int(text) < len(shared_strings):
        return shared_strings[int(text)].strip()
    if cell.attrib.get("t") == "inlineStr":
        return "".join(item.text or "" for item in cell.findall(".//m:t", NS)).strip()
    return text.strip()


def parse_xlsx(path: Path) -> tuple[str, list[list[str]]]:
    """Extract the first worksheet, including values inherited from merged cells."""
    try:
        with zipfile.ZipFile(path) as archive:
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            sheet = workbook.find("m:sheets/m:sheet", NS)
            if sheet is None:
                raise HTTPException(422, "File Excel không có sheet dữ liệu.")
            sheet_name = sheet.attrib.get("name", "Sheet1")
            shared_strings: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                shared_xml = ET.fromstring(archive.read("xl/sharedStrings.xml"))
                shared_strings = [
                    "".join(item.text or "" for item in entry.findall(".//m:t", NS))
                    for entry in shared_xml.findall("m:si", NS)
                ]
            sheet_xml = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise HTTPException(422, "File không phải Excel .xlsx hợp lệ.") from exc

    values: dict[tuple[int, int], str] = {}
    max_row = max_column = 0
    for row in sheet_xml.findall(".//m:sheetData/m:row", NS):
        row_number = int(row.attrib["r"])
        for cell in row.findall("m:c", NS):
            column = column_number(cell.attrib["r"])
            values[row_number, column] = cell_text(cell, shared_strings)
            max_row, max_column = max(max_row, row_number), max(max_column, column)

    merged_values: dict[tuple[int, int], str] = {}
    merged_cells = sheet_xml.find("m:mergeCells", NS)
    if merged_cells is not None:
        for merge in merged_cells.findall("m:mergeCell", NS):
            start, end = merge.attrib["ref"].split(":")
            start_column, start_row = column_number(start), int(re.search(r"\d+", start).group())
            end_column, end_row = column_number(end), int(re.search(r"\d+", end).group())
            merged_value = values.get((start_row, start_column), "")
            for row_number in range(start_row, end_row + 1):
                for column in range(start_column, end_column + 1):
                    merged_values[row_number, column] = merged_value

    return sheet_name, [
        [values.get((row, column)) or merged_values.get((row, column), "")
         for column in range(1, max_column + 1)]
        for row in range(1, max_row + 1)
    ]


def clean(value: str) -> str:
    return re.sub(r"[ \t]+", " ", value.replace("\r", "")).strip()


def is_schedule_time(value: str) -> bool:
    return bool(re.fullmatch(r"\s*\d{1,2}[.:]\d{2}\s*[-–]\s*\d{1,2}[.:]\d{2}\s*", value))


def parse_dates(title: str, labels: list[str]) -> list[str | None]:
    range_match = re.search(
        r"từ ngày\s*(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(20\d{2})", title, re.I
    )
    start = date(*map(int, reversed(range_match.groups()))) if range_match else None
    year_match = re.search(r"(?:\.|/)\s*(20\d{2})\b", title)
    year = int(year_match.group(1)) if year_match else (start.year if start else None)
    output: list[str | None] = []
    for label in labels:
        match = re.search(r"\((\d{1,2})\s*/\s*(\d{1,2})(?:\s*/\s*(\d{4}))?\)", label)
        if match and (match.group(3) or year):
            day, month, explicit_year = match.groups()
            output.append(date(int(explicit_year or year), int(month), int(day)).isoformat())
        elif start:
            output.append((start + timedelta(days=len(output))).isoformat())
        else:
            output.append(None)
    return output


def parse_dates_with_override(title: str, labels: list[str], week_start_str: str | None = None) -> list[str | None]:
    if week_start_str:
        try:
            start_date = date.fromisoformat(week_start_str)
            return [(start_date + timedelta(days=i)).isoformat() for i in range(len(labels))]
        except ValueError:
            pass
    return parse_dates(title, labels)



def shift_value(value: str) -> tuple[str, str | None]:
    value = clean(value)
    if not value:
        return EMPTY, None
    if value.casefold() == "nghỉ":
        return CLOSED, None
    return WORKING, value


def parse_cell(value: str) -> dict[str, tuple[str, str | None]]:
    """Map a source cell to exact morning and afternoon states."""
    value = clean(value)
    markers = list(re.finditer(r"(?im)^\s*(sáng|chiều)\b\s*:?[ \t]*(?:\n)?", value))
    if not markers:
        parsed = shift_value(value)
        return {MORNING: parsed, AFTERNOON: parsed}
    result = {MORNING: (EMPTY, None), AFTERNOON: (EMPTY, None)}
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(value)
        shift = MORNING if marker.group(1).casefold() == "sáng" else AFTERNOON
        result[shift] = shift_value(value[marker.end() : end])
    return result


def find_header(matrix: list[list[str]]) -> tuple[int, int, int, list[int]]:
    for index, row in enumerate(matrix):
        day_columns = [
            column
            for column, value in enumerate(row)
            if clean(value).casefold().startswith("thứ") or "chủ nhật" in clean(value).casefold()
        ]
        room_column = next(
            (
                column
                for column, value in enumerate(row)
                if clean(value).casefold().startswith("phòng")
            ),
            None,
        )
        time_column = next(
            (column for column, value in enumerate(row) if "thời gian" in clean(value).casefold()),
            None,
        )
        if len(day_columns) == 7 and room_column is not None and time_column is not None:
            return index, room_column, time_column, day_columns
    raise HTTPException(422, "Không tìm thấy hàng tiêu đề Phòng/Thời gian/Thứ 2–Chủ nhật.")


def import_excel(path: Path, original_name: str, week_start_str: str | None = None) -> int:
    sheet_name, matrix = parse_xlsx(path)
    header_index, room_column, time_column, day_columns = find_header(matrix)
    labels = [clean(matrix[header_index][column]) for column in day_columns]
    title = "\n".join(clean(row[0]) for row in matrix[:header_index] if row and clean(row[0]))
    dates = parse_dates_with_override(title, labels, week_start_str)
    now = datetime.utcnow().isoformat()
    area_column = room_column - 1 if room_column else None
    initial_area = (
        "Phòng khám đa khoa"
        if area_column is None and "đa khoa" in title.casefold()
        else None
    )

    title_upper = title.upper()
    name_upper = original_name.upper()
    facility = 1
    if "CƠ SỞ 2" in title_upper or "CS2" in title_upper or "FAC_2" in name_upper or "FAC2" in name_upper:
        facility = 2

    with db() as con:
        import_id = con.execute(
            """INSERT INTO schedule_imports(
                   original_name,file_path,sheet_name,title,week_start,week_end,facility,created_at
               )
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                original_name,
                str(path),
                sheet_name,
                title,
                next((item for item in dates if item), None),
                next((item for item in reversed(dates) if item), None),
                facility,
                now,
            ),
        ).lastrowid
        day_ids = [
            con.execute(
                "INSERT INTO schedule_days(import_id,work_date,label,sort_order) VALUES(?,?,?,?)",
                (import_id, work_date, label, order),
            ).lastrowid
            for order, (label, work_date) in enumerate(zip(labels, dates, strict=True), 1)
        ]
        area_id: int | None = None
        current_area = initial_area
        area_order = room_order = 0
        for source_row in matrix[header_index + 1 :]:
            row = source_row + [""] * max(0, max(day_columns) + 1 - len(source_row))
            room_name, work_time = clean(row[room_column]), clean(row[time_column])
            if not room_name or not is_schedule_time(work_time):
                continue
            # The general-clinic sheet calls rooms "RHM", "TMH", etc.; the
            # voluntary-clinic sheets use the literal "Phòng khám".
            if room_column != 0 and "phòng" not in room_name.casefold():
                continue
            area_text = clean(row[area_column]) if area_column is not None else ""
            if area_text and area_text != current_area:
                current_area, area_id = area_text, None
            if area_id is None:
                area_order += 1
                area_id = con.execute(
                    "INSERT INTO schedule_areas(import_id,name,sort_order) VALUES(?,?,?)",
                    (import_id, current_area or "Khu khám chưa phân loại", area_order),
                ).lastrowid
                room_order = 0
            room_order += 1
            room_id = con.execute(
                "INSERT INTO schedule_rooms(area_id,name,work_time,sort_order) VALUES(?,?,?,?)",
                (area_id, room_name, work_time, room_order),
            ).lastrowid
            for day_id, column in zip(day_ids, day_columns, strict=True):
                for shift, (state, value) in parse_cell(row[column]).items():
                    con.execute(
                        """INSERT INTO schedule_shifts(room_id,day_id,shift,state,value,updated_at)
                           VALUES(?,?,?,?,?,?)""",
                        (room_id, day_id, shift, state, value, now),
                    )
        room_count = con.execute(
            """SELECT COUNT(*) FROM schedule_rooms
               WHERE area_id IN (SELECT id FROM schedule_areas WHERE import_id=?)""",
            (import_id,),
        ).fetchone()[0]
        if not room_count:
            raise HTTPException(422, "Không có dòng phòng khám hợp lệ trong file Excel.")
    return import_id


@router.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@router.get("/api/sources")
def list_sources() -> list[dict[str, Any]]:
    with db() as con:
        return [dict(row) for row in con.execute("SELECT * FROM schedule_imports ORDER BY id DESC")]


@router.post("/api/sources")
async def upload_source(
    file: UploadFile = File(...),
    week_start: str = Form(None)
) -> dict[str, Any]:  # noqa: B008
    if not file.filename or Path(file.filename).suffix.casefold() != ".xlsx":
        raise HTTPException(415, "Chỉ nhận file Excel định dạng .xlsx.")
    target = UPLOADS / f"{uuid.uuid4().hex}.xlsx"
    with target.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    try:
        return {"id": import_excel(target, file.filename, week_start), "status": "draft"}
    except Exception:
        target.unlink(missing_ok=True)
        raise


@router.get("/api/sources/{source_id}")
def get_source(source_id: int) -> dict[str, Any]:
    with db() as con:
        source = con.execute("SELECT * FROM schedule_imports WHERE id=?", (source_id,)).fetchone()
        if not source:
            raise HTTPException(404, "Không tìm thấy lịch.")
        days = [dict(row) for row in con.execute(
            "SELECT * FROM schedule_days WHERE import_id=? ORDER BY sort_order", (source_id,)
        )]
        areas = [dict(row) for row in con.execute(
            "SELECT * FROM schedule_areas WHERE import_id=? ORDER BY sort_order", (source_id,)
        )]
        for area in areas:
            area["rooms"] = [dict(row) for row in con.execute(
                "SELECT * FROM schedule_rooms WHERE area_id=? ORDER BY sort_order", (area["id"],)
            )]
            for room in area["rooms"]:
                shifts = con.execute(
                    "SELECT * FROM schedule_shifts WHERE room_id=?", (room["id"],)
                ).fetchall()
                room["shifts"] = {
                    f"{shift['day_id']}:{shift['shift']}": dict(shift) for shift in shifts
                }
    return {"source": dict(source), "days": days, "areas": areas}


def sync_import_to_firestore(source_id: int) -> None:
    query = """
        SELECT s.id AS shift_id, a.name AS area_name, r.name AS room_name, r.work_time,
               d.work_date, d.label AS day_label, s.shift, s.state, s.value AS doctor_name, s.booked_count,
               i.facility, i.week_start, i.week_end
        FROM schedule_shifts s
        JOIN schedule_rooms r ON r.id = s.room_id
        JOIN schedule_areas a ON a.id = r.area_id
        JOIN schedule_days d ON d.id = s.day_id
        JOIN schedule_imports i ON i.id = a.import_id
        WHERE i.id = ?
    """
    with db() as con:
        shifts = [dict(row) for row in con.execute(query, (source_id,))]
        
    fs_client = _firestore_client()
    batch = fs_client.batch()
    for s in shifts:
        clean_room = re.sub(r'[^a-zA-Z0-9]', '_', s['room_name'])
        doc_id = f"fac{s['facility']}_{s['work_date']}_{clean_room}_{s['shift']}"
        doc_ref = fs_client.collection("published_schedules").document(doc_id)
        
        batch.set(doc_ref, {
            "shift_id": s["shift_id"],
            "import_id": source_id,
            "area_name": s["area_name"],
            "room_name": s["room_name"],
            "work_time": s["work_time"],
            "work_date": s["work_date"],
            "day_label": s["day_label"],
            "shift": s["shift"],
            "state": s["state"],
            "doctor_name": s["doctor_name"],
            "booked_count": s["booked_count"] or 0,
            "facility": s["facility"],
            "week_start": s["week_start"],
            "week_end": s["week_end"],
            "updated_at": datetime.utcnow().isoformat()
        })
    batch.commit()


def update_firestore_shift(shift_id: int, state: str, value: str | None) -> None:
    query = """
        SELECT s.id AS shift_id, a.name AS area_name, r.name AS room_name, r.work_time,
               d.work_date, d.label AS day_label, s.shift, s.state, s.value AS doctor_name, s.booked_count,
               i.facility, i.week_start, i.week_end, i.status AS import_status
        FROM schedule_shifts s
        JOIN schedule_rooms r ON r.id = s.room_id
        JOIN schedule_areas a ON a.id = r.area_id
        JOIN schedule_days d ON d.id = s.day_id
        JOIN schedule_imports i ON i.id = a.import_id
        WHERE s.id = ?
    """
    with db() as con:
        row = con.execute(query, (shift_id,)).fetchone()
        
    if not row or row["import_status"] != "published":
        return
        
    fs_client = _firestore_client()
    clean_room = re.sub(r'[^a-zA-Z0-9]', '_', row['room_name'])
    doc_id = f"fac{row['facility']}_{row['work_date']}_{clean_room}_{row['shift']}"
    
    fs_client.collection("published_schedules").document(doc_id).update({
        "state": state,
        "doctor_name": value,
        "updated_at": datetime.utcnow().isoformat()
    })


def sync_booked_counts_from_firestore() -> None:
    try:
        fs_client = _firestore_client()
        docs = fs_client.collection("appointments").where("status", "==", "upcoming").stream()
        
        counts = {}
        for doc in docs:
            data = doc.to_dict()
            date_str = data.get("date")
            doc_id = data.get("doctorId")
            time_str = data.get("time")
            if not date_str or not doc_id or not time_str:
                continue
                
            try:
                hour = int(time_str.split(":")[0])
                shift = "morning" if hour < 12 else "afternoon"
            except (ValueError, IndexError):
                continue
                
            key = (date_str, doc_id, shift)
            counts[key] = counts.get(key, 0) + 1
            
        with db() as con:
            con.execute("UPDATE schedule_shifts SET booked_count = 0")
            for (date_str, doc_id, shift), count in counts.items():
                con.execute("""
                    UPDATE schedule_shifts 
                    SET booked_count = ?
                    WHERE id IN (
                        SELECT s.id 
                        FROM schedule_shifts s
                        JOIN schedule_days d ON d.id = s.day_id
                        WHERE d.work_date = ? AND s.value = ? AND s.shift = ?
                    )
                """, (count, date_str, doc_id, shift))
    except Exception as e:
        print(f"Error syncing booked counts from Firestore: {e}")


class ShiftUpdate(BaseModel):
    state: str = Field(pattern="^(working|closed|empty)$")
    value: str | None = None


@router.patch("/api/shifts/{shift_id}")
def update_shift(shift_id: int, update: ShiftUpdate) -> dict[str, str]:
    value = clean(update.value or "") if update.state == WORKING else None
    if update.state == WORKING and not value:
        raise HTTPException(422, "Ca làm việc cần có tên bác sĩ hoặc nội dung trực.")
    with db() as con:
        if not con.execute("SELECT 1 FROM schedule_shifts WHERE id=?", (shift_id,)).fetchone():
            raise HTTPException(404, "Không tìm thấy ca trực.")
        con.execute(
            "UPDATE schedule_shifts SET state=?,value=?,updated_at=? WHERE id=?",
            (update.state, value, datetime.utcnow().isoformat(), shift_id),
        )
    try:
        update_firestore_shift(shift_id, update.state, value)
    except Exception as e:
        print(f"Lỗi đồng bộ lên Firestore: {e}")
    return {"status": "saved"}


@router.post("/api/sources/{source_id}/approve")
def approve_source(source_id: int) -> dict[str, str]:
    with db() as con:
        if not con.execute("SELECT 1 FROM schedule_imports WHERE id=?", (source_id,)).fetchone():
            raise HTTPException(404, "Không tìm thấy lịch.")
        con.execute(
            "UPDATE schedule_imports SET status='published',approved_at=? WHERE id=?",
            (datetime.utcnow().isoformat(), source_id),
        )
    try:
        sync_import_to_firestore(source_id)
    except Exception as e:
        print(f"Lỗi đồng bộ lịch lên Firestore: {e}")
    return {"status": "published"}


@router.get("/api/schedule")
def published_schedule(work_date: str | None = None) -> list[dict[str, Any]]:
    query = """SELECT i.id AS import_id,a.name AS area_name,r.name AS room_name,r.work_time,
                      d.work_date,d.label,s.shift,s.state,s.value
               FROM schedule_shifts s JOIN schedule_rooms r ON r.id=s.room_id
               JOIN schedule_areas a ON a.id=r.area_id JOIN schedule_days d ON d.id=s.day_id
               JOIN schedule_imports i ON i.id=a.import_id WHERE i.status='published'"""
    params: list[str] = []
    if work_date:
        query += " AND d.work_date=?"
        params.append(work_date)
    query += " ORDER BY d.work_date,a.sort_order,r.sort_order,s.shift"
    with db() as con:
        return [dict(row) for row in con.execute(query, params)]


@router.get("/api/schedule/view")
def get_schedule_view(week_start: str, facility: int) -> dict[str, Any]:
    query = """SELECT i.id AS import_id, a.name AS area_name, r.name AS room_name, r.work_time,
                      d.work_date, d.label, s.shift, s.state, s.value
               FROM schedule_shifts s JOIN schedule_rooms r ON r.id=s.room_id
               JOIN schedule_areas a ON a.id=r.area_id JOIN schedule_days d ON d.id=s.day_id
               JOIN schedule_imports i ON i.id=a.import_id 
               WHERE i.status='published' AND i.week_start=? AND i.facility=?"""
    
    days_query = """SELECT DISTINCT d.work_date, d.label, d.sort_order
                    FROM schedule_days d
                    JOIN schedule_imports i ON i.id = d.import_id
                    WHERE i.status='published' AND i.week_start=? AND i.facility=?
                    ORDER BY d.sort_order"""
                    
    with db() as con:
        shifts = [dict(row) for row in con.execute(query, (week_start, facility))]
        days = [dict(row) for row in con.execute(days_query, (week_start, facility))]
        
    return {"status": "success", "shifts": shifts, "days": days}


class BookingRequest(BaseModel):
    facilityId: str
    specialtyId: str
    doctorId: str
    date: str
    time: str
    patientName: str
    patientPhone: str
    patientEmail: str | None = None
    patientDob: str | None = None
    patientGender: str | None = None
    symptoms: str | None = None


def get_max_bookings() -> int:
    try:
        return int(os.getenv("MAX_BOOKINGS_PER_SHIFT", "6"))
    except ValueError:
        return 6


@router.post("/appointments")
@router.post("/api/appointments")
async def create_appointment(request: BookingRequest) -> dict[str, Any]:
    try:
        hour = int(request.time.split(":")[0])
        shift = "morning" if hour < 12 else "afternoon"
    except (ValueError, IndexError):
        raise HTTPException(422, "Khung giờ khám không hợp lệ (định dạng HH:MM).")

    query = """SELECT s.id, s.booked_count, s.value, r.name AS room_name, i.facility
               FROM schedule_shifts s JOIN schedule_rooms r ON r.id=s.room_id
               JOIN schedule_areas a ON a.id=r.area_id JOIN schedule_days d ON d.id=s.day_id
               JOIN schedule_imports i ON i.id=a.import_id 
               WHERE i.status='published' AND d.work_date=? AND s.shift=? AND s.value=?"""
    
    with db() as con:
        row = con.execute(query, (request.date, shift, request.doctorId)).fetchone()
        
    if not row:
        raise HTTPException(422, f"Bác sĩ {request.doctorId} không có ca trực đã publish vào ngày {request.date} ({'Sáng' if shift == 'morning' else 'Chiều'}).")
        
    shift_id = row["id"]
    current_booked = row["booked_count"] or 0
    max_bookings = get_max_bookings()
    
    if current_booked >= max_bookings:
        raise HTTPException(409, f"Ca trực của bác sĩ đã đầy (tối đa {max_bookings} người đăng ký).")
        
    try:
        fs_client = _firestore_client()
        code = f"BVT-{uuid.uuid4().hex[:8].upper()}"
        app_id = str(uuid.uuid4())
        appointment_data = {
            "id": app_id,
            "code": code,
            "doctorId": request.doctorId,
            "doctorName": request.doctorId,
            "specialtyId": request.specialtyId,
            "specialty": request.specialtyId,
            "facilityId": request.facilityId,
            "facilityName": "Bệnh viện Tim Hà Nội — " + ("Cơ sở 2" if "2" in request.facilityId else "Cơ sở 1"),
            "date": request.date,
            "time": request.time,
            "status": "upcoming",
            "patientName": request.patientName,
            "patientPhone": request.patientPhone,
            "patientEmail": request.patientEmail,
            "patientDob": request.patientDob,
            "patientGender": request.patientGender,
            "symptoms": request.symptoms,
            "shift_id": shift_id,
            "created_at": datetime.utcnow().isoformat()
        }
        fs_client.collection("appointments").document(app_id).set(appointment_data)
    except Exception as e:
        raise HTTPException(500, f"Không thể lưu lịch hẹn lên Firebase: {str(e)}")
        
    with db() as con:
        con.execute("UPDATE schedule_shifts SET booked_count = booked_count + 1 WHERE id=?", (shift_id,))
        
    return appointment_data


@router.get("/appointments")
@router.get("/api/appointments")
async def list_appointments(phone: str | None = None) -> list[dict[str, Any]]:
    try:
        fs_client = _firestore_client()
        query = fs_client.collection("appointments")
        if phone:
            query = query.where("patientPhone", "==", phone)
        docs = query.stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            results.append(data)
        results.sort(key=lambda x: (x.get("date", ""), x.get("time", "")))
        return results
    except Exception as e:
        raise HTTPException(500, f"Lỗi truy vấn lịch đặt từ Firebase: {str(e)}")


@router.get("/api/schedule/bookings-summary")
def get_bookings_summary(week_start: str, facility: int) -> list[dict[str, Any]]:
    sync_booked_counts_from_firestore()
    query = """SELECT s.id AS shift_id, a.name AS area_name, r.name AS room_name, r.work_time,
                      d.work_date, d.label AS day_label, s.shift, s.value AS doctor_name, s.booked_count
               FROM schedule_shifts s JOIN schedule_rooms r ON r.id=s.room_id
               JOIN schedule_areas a ON a.id=r.area_id JOIN schedule_days d ON d.id=s.day_id
               JOIN schedule_imports i ON i.id=a.import_id 
               WHERE i.status='published' AND i.week_start=? AND i.facility=? AND s.state='working'
               ORDER BY d.work_date, a.sort_order, r.sort_order, s.shift"""
    with db() as con:
        return [dict(row) for row in con.execute(query, (week_start, facility))]


@router.get("/api/appointments/by-shift/{shift_id}")
async def get_appointments_by_shift(shift_id: int) -> list[dict[str, Any]]:
    try:
        fs_client = _firestore_client()
        docs = fs_client.collection("appointments").where("shift_id", "==", shift_id).stream()
        results = []
        for doc in docs:
            results.append(doc.to_dict())
        results.sort(key=lambda x: x.get("time", ""))
        return results
    except Exception as e:
        raise HTTPException(500, f"Lỗi truy vấn lịch hẹn theo ca từ Firebase: {str(e)}")



def create_schedule_app() -> FastAPI:
    """Create an independently runnable schedule-review app."""
    application = FastAPI(title="Hanoi Heart Hospital schedule review")
    application.mount("/static", StaticFiles(directory=STATIC), name="schedule-static")
    application.include_router(router)

    @application.on_event("startup")
    def initialise_schedule_database() -> None:
        init_db()
        sync_booked_counts_from_firestore()

    return application


def mount_schedule(host_app: FastAPI, path: str = "/schedule") -> None:
    """Attach the full schedule UI/API as a component of a host FastAPI app."""
    host_app.mount(path, create_schedule_app())


app = create_schedule_app()

__all__ = ["app", "create_schedule_app", "import_excel", "init_db", "mount_schedule"]
