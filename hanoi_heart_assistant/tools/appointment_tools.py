"""Appointment adapter utilizing Google Cloud Firestore for slot limits and bookings."""

import re
import os
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

DEPARTMENTS = {"tim_mach": "Tim mạch", "noi_tim_mach": "Nội tim mạch"}
DEMO_SLOTS = ("08:00", "09:30", "14:00", "15:30")


def _parse_future_date(value: str) -> date | None:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed >= date.today() else None


def list_appointment_slots(department: str, appointment_date: str) -> dict:
    """List demo appointment slots for a department and date in YYYY-MM-DD format."""
    parsed_date = _parse_future_date(appointment_date)
    if parsed_date is None:
        return {
            "status": "error",
            "message": "Ngày khám phải có dạng YYYY-MM-DD và không ở quá khứ.",
        }
    if department not in DEPARTMENTS:
        return {
            "status": "error",
            "message": "Chuyên khoa chưa được hỗ trợ.",
            "departments": DEPARTMENTS,
        }
    return {
        "status": "success",
        "source": "demo_slots_not_live",
        "department": DEPARTMENTS[department],
        "date": parsed_date.isoformat(),
        "slots": list(DEMO_SLOTS),
        "notice": "Khung giờ minh họa, chưa phản ánh lịch trống thực tế của bệnh viện.",
    }


def submit_appointment_request(
    full_name: str,
    phone: str,
    department: str,
    appointment_date: str,
    appointment_time: str,
    reason: str,
    doctor_name: str | None = None,
) -> dict:
    """Validate and submit an appointment request directly to Firestore, verifying slot limits."""
    if len(full_name.strip()) < 2:
        return {"status": "error", "message": "Họ tên chưa hợp lệ."}
    if not re.fullmatch(r"(?:\+84|0)\d{9,10}", phone.replace(" ", "")):
        return {"status": "error", "message": "Số điện thoại chưa hợp lệ."}

    parsed_date = _parse_future_date(appointment_date)
    if parsed_date is None:
        return {
            "status": "error",
            "message": "Ngày khám phải có dạng YYYY-MM-DD và không ở quá khứ.",
        }

    try:
        hour = int(appointment_time.split(":")[0])
        shift = "morning" if hour < 12 else "afternoon"
    except (ValueError, IndexError):
        return {"status": "error", "message": "Giờ khám không hợp lệ (HH:MM)."}

    # Query Firestore schedule_shifts
    try:
        from hanoi_heart_assistant.tools.firebase_vector_tools import _firestore_client
        fs = _firestore_client()
        
        query = fs.collection("schedule_shifts") \
            .where("import_status", "==", "published") \
            .where("work_date", "==", parsed_date.isoformat()) \
            .where("shift", "==", shift)
            
        if doctor_name:
            query = query.where("value", "==", doctor_name)
        else:
            query = query.where("state", "==", "working")
            
        docs = query.stream()
        shifts = [doc.to_dict() for doc in docs]
    except Exception as e:
        return {"status": "error", "message": f"Lỗi kết nối Firebase: {str(e)}"}

    if not shifts:
        doctor_info = f" bác sĩ {doctor_name}" if doctor_name else ""
        return {
            "status": "error",
            "message": f"Không tìm thấy ca trực nào của{doctor_info} vào ngày {parsed_date.isoformat()} ca {'Sáng' if shift == 'morning' else 'Chiều'}."
        }

    # Pick the shift with the least booked_count if no specific doctor_name was given
    if not doctor_name:
        shifts.sort(key=lambda x: x.get("booked_count", 0))

    selected_shift = shifts[0]
    shift_id = selected_shift["id"]
    active_doctor = selected_shift["value"]
    facility_id = f"Cơ sở {selected_shift['facility']}"
    current_booked = selected_shift.get("booked_count", 0)

    try:
        max_bookings = int(os.getenv("MAX_BOOKINGS_PER_SHIFT", "6"))
    except ValueError:
        max_bookings = 6

    if current_booked >= max_bookings:
        return {
            "status": "error",
            "message": f"Ca trực của bác sĩ {active_doctor} đã đầy (tối đa {max_bookings} người)."
        }

    # Write to Firestore appointments
    try:
        code = f"BVT-{uuid.uuid4().hex[:8].upper()}"
        app_id = str(uuid.uuid4())
        
        appointment_data = {
            "id": app_id,
            "code": code,
            "doctorId": active_doctor,
            "doctorName": active_doctor,
            "specialtyId": department,
            "specialty": DEPARTMENTS.get(department, department),
            "facilityId": facility_id,
            "facilityName": f"Bệnh viện Tim Hà Nội — {facility_id}",
            "date": parsed_date.isoformat(),
            "time": appointment_time,
            "status": "upcoming",
            "patientName": full_name.strip(),
            "patientPhone": phone.replace(" ", ""),
            "patientEmail": "",
            "patientDob": "",
            "patientGender": "",
            "symptoms": reason.strip(),
            "shift_id": shift_id,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Save appointment doc
        fs.collection("appointments").document(app_id).set(appointment_data)
        
        # Increment booked_count on schedule_shifts doc
        fs.collection("schedule_shifts").document(shift_id).update({
            "booked_count": current_booked + 1
        })
    except Exception as e:
        return {
            "status": "error",
            "message": f"Lỗi kết nối Firebase khi lưu đặt lịch: {str(e)}"
        }

    return {
        "status": "success",
        "code": code,
        "appointment": appointment_data,
        "message": f"Đặt lịch thành công cho bệnh nhân {full_name} khám bác sĩ {active_doctor} lúc {appointment_time} ngày {parsed_date.isoformat()}."
    }
