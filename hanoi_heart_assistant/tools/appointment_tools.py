"""Demo appointment adapter; replace these functions with the hospital scheduling API."""

import re
from datetime import date
from uuid import uuid4

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
) -> dict:
    """Validate and submit a demo appointment request pending hospital confirmation."""
    if len(full_name.strip()) < 2:
        return {"status": "error", "message": "Họ tên chưa hợp lệ."}
    if not re.fullmatch(r"(?:\+84|0)\d{9,10}", phone.replace(" ", "")):
        return {"status": "error", "message": "Số điện thoại chưa hợp lệ."}
    if department not in DEPARTMENTS:
        return {
            "status": "error",
            "message": "Chuyên khoa chưa được hỗ trợ.",
            "departments": DEPARTMENTS,
        }
    parsed_date = _parse_future_date(appointment_date)
    if parsed_date is None:
        return {
            "status": "error",
            "message": "Ngày khám phải có dạng YYYY-MM-DD và không ở quá khứ.",
        }
    if appointment_time not in DEMO_SLOTS:
        return {"status": "error", "message": "Khung giờ chưa hợp lệ.", "slots": list(DEMO_SLOTS)}
    if not reason.strip():
        return {"status": "error", "message": "Vui lòng cung cấp lý do khám ngắn gọn."}

    # Integration boundary: POST this validated payload to the real scheduling service.
    return {
        "status": "pending_confirmation",
        "request_id": f"DEMO-{uuid4().hex[:8].upper()}",
        "appointment": {
            "full_name": full_name.strip(),
            "phone": phone.replace(" ", ""),
            "department": DEPARTMENTS[department],
            "date": parsed_date.isoformat(),
            "time": appointment_time,
            "reason": reason.strip(),
        },
        "notice": (
            "Đây là yêu cầu demo, chưa được lưu vào hệ thống bệnh viện và chưa phải lịch hẹn "
            "đã xác nhận."
        ),
    }
