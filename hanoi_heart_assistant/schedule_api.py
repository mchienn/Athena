"""Excel schedule-review component for the Hanoi Heart Hospital assistant backed by Google Cloud Firestore."""

from __future__ import annotations

import os
import re
import shutil
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
STATIC = PACKAGE_ROOT / "static" / "schedule"

os.makedirs(UPLOADS, exist_ok=True)

router = APIRouter()

WORKING = "working"


def init_db() -> None:
    """No-op for Firestore schema initialization."""
    pass


def column_number(reference: str) -> int:
    number = 0
    for character in re.match(r"[A-Z]+", reference).group(0):
        number = number * 26 + ord(character) - 64
    return number - 1


def clean(text: str | None) -> str:
    return re.sub(r"[ \t]+", " ", (text or "").replace("\r", "")).strip()


def parse_xlsx(path: Path) -> tuple[str, list[list[str]]]:
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        namespaces = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        sheet = workbook.find(".//ns:sheet", namespaces)
        sheet_name = sheet.attrib.get("name", "Lịch trực") if sheet is not None else "Lịch trực"
        sheet_id = sheet.attrib.get("sheetId", "1") if sheet is not None else "1"

        shared_strings = []
        try:
            shared_strings_xml = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for string_item in shared_strings_xml.findall(".//ns:t", namespaces):
                shared_strings.append(string_item.text or "")
        except KeyError:
            pass

        worksheet = ET.fromstring(archive.read(f"xl/worksheets/sheet{sheet_id}.xml"))
        row_elements = worksheet.findall(".//ns:row", namespaces)
        max_row = max((int(r.attrib["r"]) for r in row_elements), default=0)
        max_col = 0
        for cell in worksheet.findall(".//ns:c", namespaces):
            reference = cell.attrib["r"]
            col_letter = re.match(r"[A-Z]+", reference).group(0)
            max_col = max(max_col, column_number(col_letter) + 1)

        matrix = [["" for _ in range(max_col)] for _ in range(max_row)]
        for cell in worksheet.findall(".//ns:c", namespaces):
            reference = cell.attrib["r"]
            row = int(re.search(r"\d+", reference).group(0)) - 1
            col_letter = re.match(r"[A-Z]+", reference).group(0)
            col = column_number(col_letter)

            cell_type = cell.attrib.get("t", "")
            value_element = cell.find("ns:v", namespaces)
            if value_element is not None:
                value = value_element.text or ""
                if cell_type == "s" and value.isdigit():
                    matrix[row][col] = shared_strings[int(value)]
                else:
                    matrix[row][col] = value
            else:
                inline_string = cell.find(".//ns:t", namespaces)
                if inline_string is not None:
                    matrix[row][col] = inline_string.text or ""

        merges = worksheet.find("ns:mergeCells", namespaces)
        if merges is not None:
            for merge in merges.findall("ns:mergeCell", namespaces):
                ref = merge.attrib["ref"]
                start, end = ref.split(":")
                start_col = column_number(re.match(r"[A-Z]+", start).group(0))
                start_row = int(re.search(r"\d+", start).group(0)) - 1
                end_col = column_number(re.match(r"[A-Z]+", end).group(0))
                end_row = int(re.search(r"\d+", end).group(0)) - 1

                value = matrix[start_row][start_col]
                for r in range(start_row, end_row + 1):
                    for c in range(start_col, end_col + 1):
                        matrix[r][c] = value

        return sheet_name, matrix


def find_header(matrix: list[list[str]]) -> tuple[int, int | None, int | None, list[int]]:
    for index, row in enumerate(matrix):
        cleaned = [clean(cell).casefold() for cell in row]
        room_column = None
        for i, val in enumerate(cleaned):
            if "phòng" in val or "dịch vụ" in val:
                room_column = i
                break

        time_column = None
        for i, val in enumerate(cleaned):
            if "thời gian" in val or "giờ" in val or "ca trực" in val:
                time_column = i
                break

        day_columns = []
        for i, val in enumerate(cleaned):
            if any(day in val for day in ("thứ", "chủ nhật", "t2", "t3", "t4", "t5", "t6", "t7", "cn")):
                day_columns.append(i)

        if len(day_columns) == 7 and room_column is not None and time_column is not None:
            return index, room_column, time_column, day_columns
    raise HTTPException(422, "Không tìm thấy hàng tiêu đề Phòng/Thời gian/Thứ 2–Chủ nhật.")


def is_schedule_time(value: str) -> bool:
    return bool(re.search(r"\d{1,2}\s*[\.:-]\s*\d{2}", value)) or any(
        kw in value.casefold() for kw in ("sáng", "chiều", "ngày", "trực", "hành chính")
    )


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
        return "empty", None
    if value.casefold() == "nghỉ":
        return "closed", None
    return "working", value


def parse_cell(value: str) -> dict[str, tuple[str, str | None]]:
    """Map a source cell to exact morning and afternoon states."""
    value = clean(value)
    markers = list(re.finditer(r"(?im)^\s*(sáng|chiều)\b\s*:?[ \t]*(?:\n)?", value))
    if not markers:
        parsed = shift_value(value)
        return {"morning": parsed, "afternoon": parsed}
    result = {"morning": ("empty", None), "afternoon": ("empty", None)}
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(value)
        shift = "morning" if marker.group(1).casefold() == "sáng" else "afternoon"
        result[shift] = shift_value(value[marker.end() : end])
    return result


def import_excel(path: Path, original_name: str, week_start_str: str | None = None) -> str:
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

    fs_client = _firestore_client()
    import_id = str(uuid.uuid4())

    import_data = {
        "id": import_id,
        "original_name": original_name,
        "file_path": str(path),
        "sheet_name": sheet_name,
        "title": title,
        "week_start": next((item for item in dates if item), None),
        "week_end": next((item for item in reversed(dates) if item), None),
        "facility": facility,
        "status": "draft",
        "created_at": now,
        "approved_at": None
    }

    # Set metadata
    fs_client.collection("schedule_imports").document(import_id).set(import_data)

    batch = fs_client.batch()
    batch_size = 0

    area_order = room_order = 0
    current_area = initial_area
    for source_row in matrix[header_index + 1 :]:
        row = source_row + [""] * max(0, max(day_columns) + 1 - len(source_row))
        room_name, work_time = clean(row[room_column]), clean(row[time_column])
        if not room_name or not is_schedule_time(work_time):
            continue

        if area_column is not None:
            parsed_area = clean(row[area_column])
            if parsed_area and parsed_area != current_area:
                current_area = parsed_area
                area_order += 1
                room_order = 0

        room_order += 1

        for day_idx, (label_str, date_str) in enumerate(zip(labels, dates, strict=True), 1):
            cell_value = clean(row[day_columns[day_idx - 1]])
            parsed_shifts = parse_cell(cell_value)

            for shift_name in ("morning", "afternoon"):
                state, doctor = parsed_shifts[shift_name]
                shift_id = str(uuid.uuid4())

                shift_data = {
                    "id": shift_id,
                    "import_id": import_id,
                    "area_name": current_area or "Phòng khám chung",
                    "area_sort": area_order,
                    "room_name": room_name,
                    "room_sort": room_order,
                    "work_time": work_time,
                    "work_date": date_str,
                    "day_label": label_str,
                    "day_sort": day_idx,
                    "shift": shift_name,
                    "state": state,
                    "value": doctor,
                    "import_status": "draft",
                    "booked_count": 0,
                    "updated_at": now
                }
                
                doc_ref = fs_client.collection("schedule_shifts").document(shift_id)
                batch.set(doc_ref, shift_data)
                batch_size += 1

                if batch_size >= 400:
                    batch.commit()
                    batch = fs_client.batch()
                    batch_size = 0

    if batch_size > 0:
        batch.commit()

    return import_id


@router.get("/")
def get_dashboard() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@router.get("/api/sources")
def list_sources() -> list[dict[str, Any]]:
    fs_client = _firestore_client()
    docs = fs_client.collection("schedule_imports").order_by("created_at", direction="DESCENDING").stream()
    return [doc.to_dict() for doc in docs]


@router.post("/api/sources")
async def upload_source(
    file: UploadFile = File(...),
    week_start: str = Form(None)
) -> dict[str, Any]:
    if not file.filename or Path(file.filename).suffix.casefold() != ".xlsx":
        raise HTTPException(415, "Chỉ nhận file Excel định dạng .xlsx.")
    target = UPLOADS / f"{uuid.uuid4().hex}.xlsx"
    with target.open("wb") as output:
        shutil.copyfileobj(file.file, output)
    try:
        source_id = import_excel(target, file.filename, week_start)
        return {"id": source_id, "status": "draft"}
    except Exception:
        target.unlink(missing_ok=True)
        raise


@router.get("/api/sources/{source_id}")
def get_source(source_id: str) -> dict[str, Any]:
    fs_client = _firestore_client()
    source_doc = fs_client.collection("schedule_imports").document(source_id).get()
    if not source_doc.exists:
        raise HTTPException(404, "Không tìm thấy lịch.")
    source = source_doc.to_dict()

    docs = fs_client.collection("schedule_shifts").where("import_id", "==", source_id).stream()
    shifts_list = [doc.to_dict() for doc in docs]

    days_map = {}
    for s in shifts_list:
        day_key = s["work_date"]
        if day_key not in days_map:
            days_map[day_key] = {
                "id": day_key,
                "label": s["day_label"],
                "work_date": s["work_date"],
                "sort_order": s["day_sort"]
            }
    days = sorted(days_map.values(), key=lambda x: x["sort_order"])

    areas_map = {}
    for s in shifts_list:
        a_name = s["area_name"]
        r_name = s["room_name"]

        if a_name not in areas_map:
            areas_map[a_name] = {
                "id": a_name,
                "name": a_name,
                "sort_order": s["area_sort"],
                "rooms": {}
            }

        a_rooms = areas_map[a_name]["rooms"]
        room_key = f"{r_name}_{s['room_sort']}"
        if room_key not in a_rooms:
            a_rooms[room_key] = {
                "id": room_key,
                "name": r_name,
                "work_time": s["work_time"],
                "sort_order": s["room_sort"],
                "shifts": {}
            }

        shift_key = f"{s['work_date']}:{s['shift']}"
        a_rooms[room_key]["shifts"][shift_key] = {
            "id": s["id"],
            "shift": s["shift"],
            "state": s["state"],
            "value": s["value"],
            "booked_count": s.get("booked_count", 0)
        }

    formatted_areas = []
    for a_name, a_data in sorted(areas_map.items(), key=lambda x: x[1]["sort_order"]):
        rooms_list = []
        for r_key, r_data in sorted(a_data["rooms"].items(), key=lambda x: x[1]["sort_order"]):
            rooms_list.append({
                "id": r_data["id"],
                "name": r_data["name"],
                "work_time": r_data["work_time"],
                "shifts": r_data["shifts"]
            })
        formatted_areas.append({
            "id": a_data["id"],
            "name": a_data["name"],
            "rooms": rooms_list
        })

    return {"source": source, "days": days, "areas": formatted_areas}


class ShiftUpdate(BaseModel):
    state: str = Field(pattern="^(working|closed|empty)$")
    value: str | None = None


@router.patch("/api/shifts/{shift_id}")
def update_shift(shift_id: str, update: ShiftUpdate) -> dict[str, str]:
    value = clean(update.value or "") if update.state == WORKING else None
    if update.state == WORKING and not value:
        raise HTTPException(422, "Ca làm việc cần có tên bác sĩ hoặc nội dung trực.")
    
    fs_client = _firestore_client()
    doc_ref = fs_client.collection("schedule_shifts").document(shift_id)
    if not doc_ref.get().exists:
        raise HTTPException(404, "Không tìm thấy ca trực.")

    doc_ref.update({
        "state": update.state,
        "value": value,
        "updated_at": datetime.utcnow().isoformat()
    })
    return {"status": "saved"}


@router.post("/api/sources/{source_id}/approve")
def approve_source(source_id: str) -> dict[str, str]:
    fs_client = _firestore_client()
    doc_ref = fs_client.collection("schedule_imports").document(source_id)
    if not doc_ref.get().exists:
        raise HTTPException(404, "Không tìm thấy lịch.")

    doc_ref.update({
        "status": "published",
        "approved_at": datetime.utcnow().isoformat()
    })

    shifts_docs = fs_client.collection("schedule_shifts").where("import_id", "==", source_id).stream()
    batch = fs_client.batch()
    for s_doc in shifts_docs:
        batch.update(s_doc.reference, {"import_status": "published"})
    batch.commit()

    return {"status": "published"}


@router.get("/api/schedule/view")
def get_schedule_view(week_start: str, facility: int) -> dict[str, Any]:
    fs_client = _firestore_client()
    docs = fs_client.collection("schedule_shifts") \
        .where("import_status", "==", "published") \
        .where("week_start", "==", week_start) \
        .where("facility", "==", facility) \
        .stream()

    shifts = [doc.to_dict() for doc in docs]
    
    mapped_shifts = []
    days_map = {}
    for s in shifts:
        mapped_shifts.append({
            "import_id": s["import_id"],
            "area_name": s["area_name"],
            "room_name": s["room_name"],
            "work_time": s["work_time"],
            "work_date": s["work_date"],
            "label": s["day_label"],
            "shift": s["shift"],
            "state": s["state"],
            "value": s["value"]
        })
        
        day_key = s["work_date"]
        if day_key not in days_map:
            days_map[day_key] = {
                "work_date": s["work_date"],
                "label": s["day_label"],
                "sort_order": s["day_sort"]
            }
            
    days = sorted(days_map.values(), key=lambda x: x["sort_order"])
    
    def sort_key(x):
        s = next((s for s in shifts if s["import_id"] == x["import_id"] and s["area_name"] == x["area_name"] and s["room_name"] == x["room_name"] and s["work_date"] == x["work_date"] and s["shift"] == x["shift"]), None)
        if s:
            return (s["work_date"], s["area_sort"], s["room_sort"], s["shift"])
        return (x["work_date"], 0, 0, x["shift"])
        
    mapped_shifts.sort(key=sort_key)
    return {"status": "success", "shifts": mapped_shifts, "days": days}


@router.get("/api/schedule")
def published_schedule(work_date: str | None = None) -> list[dict[str, Any]]:
    fs_client = _firestore_client()
    query = fs_client.collection("schedule_shifts").where("import_status", "==", "published").where("state", "==", "working")
    if work_date:
        query = query.where("work_date", "==", work_date)
    
    docs = query.stream()
    results = []
    for doc in docs:
        s = doc.to_dict()
        results.append({
            "import_id": s["import_id"],
            "area_name": s["area_name"],
            "room_name": s["room_name"],
            "work_time": s["work_time"],
            "work_date": s["work_date"],
            "label": s["day_label"],
            "shift": s["shift"],
            "state": s["state"],
            "value": s["value"]
        })
        
    results.sort(key=lambda x: (x["work_date"], x["area_name"], x["room_name"], x["shift"]))
    return results


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

    fs_client = _firestore_client()
    shifts_docs = fs_client.collection("schedule_shifts") \
        .where("import_status", "==", "published") \
        .where("work_date", "==", request.date) \
        .where("shift", "==", shift) \
        .where("value", "==", request.doctorId) \
        .stream()

    shifts = [doc.to_dict() for doc in shifts_docs]
    if not shifts:
        raise HTTPException(422, f"Bác sĩ {request.doctorId} không có ca trực đã publish vào ngày {request.date} ({'Sáng' if shift == 'morning' else 'Chiều'}).")

    selected_shift = shifts[0]
    shift_id = selected_shift["id"]
    current_booked = selected_shift.get("booked_count", 0)
    max_bookings = get_max_bookings()

    if current_booked >= max_bookings:
        raise HTTPException(409, f"Ca trực của bác sĩ đã đầy (tối đa {max_bookings} người đăng ký).")

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

    fs_client.collection("schedule_shifts").document(shift_id).update({
        "booked_count": current_booked + 1
    })

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
    fs_client = _firestore_client()
    docs = fs_client.collection("schedule_shifts") \
        .where("import_status", "==", "published") \
        .where("week_start", "==", week_start) \
        .where("facility", "==", facility) \
        .where("state", "==", "working") \
        .stream()

    shifts = [doc.to_dict() for doc in docs]
    results = []
    for s in shifts:
        results.append({
            "shift_id": s["id"],
            "area_name": s["area_name"],
            "room_name": s["room_name"],
            "work_time": s["work_time"],
            "work_date": s["work_date"],
            "day_label": s["day_label"],
            "shift": s["shift"],
            "doctor_name": s["value"],
            "booked_count": s.get("booked_count", 0)
        })

    results.sort(key=lambda x: (
        x["work_date"],
        next((s["area_sort"] for s in shifts if s["id"] == x["shift_id"]), 0),
        next((s["room_sort"] for s in shifts if s["id"] == x["shift_id"]), 0),
        x["shift"]
    ))
    return results


@router.get("/api/appointments/by-shift/{shift_id}")
async def get_appointments_by_shift(shift_id: str) -> list[dict[str, Any]]:
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
    return application


def mount_schedule(host_app: FastAPI, path: str = "/schedule") -> None:
    """Attach the full schedule UI/API as a component of a host FastAPI app."""
    host_app.mount(path, create_schedule_app())


app = create_schedule_app()

__all__ = ["app", "create_schedule_app", "import_excel", "init_db", "mount_schedule"]
