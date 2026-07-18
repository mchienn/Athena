"""Booking availability API backed by the published Firestore schedule."""

from __future__ import annotations

import os
import uuid
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.api_core.exceptions import PermissionDenied
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel

from hanoi_heart_assistant.auth.auth_service import AuthService
from hanoi_heart_assistant.auth.routes import router as auth_router
from hanoi_heart_assistant.tools.firebase_vector_tools import _firestore_client

ShiftCode = Literal["morning", "afternoon"]

SHIFT_ORDER: dict[str, int] = {"morning": 0, "afternoon": 1}
SHIFT_LABELS: dict[str, str] = {
    "morning": "Buổi sáng",
    "afternoon": "Buổi chiều",
}
SHIFT_DEFAULT_TIMES: dict[str, str] = {
    "morning": os.getenv("MORNING_APPOINTMENT_TIME", "07:30"),
    "afternoon": os.getenv("AFTERNOON_APPOINTMENT_TIME", "13:30"),
}
WEEKDAY_LABELS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]


class FacilityItem(BaseModel):
    id: str
    name: str
    shortName: str
    address: str
    phone: str
    hours: str
    image: str


class DoctorAvailabilityItem(BaseModel):
    name: str
    facilities: list[str]
    available_shift_count: int
    first_available_date: date


class DoctorCatalogItem(BaseModel):
    id: str
    title: str
    content: str
    zone: str = ""
    facility_id: str = ""
    image: str = "/images/doctor-placeholder.svg"


class AvailableShift(BaseModel):
    shift: ShiftCode
    label: str
    appointment_time: str
    remaining_capacity: int
    doctor_count: int
    doctors: list[str]
    shift_ids: list[str]


class AvailableDay(BaseModel):
    date: date
    label: str
    shifts: list[AvailableShift]


class AvailabilityResponse(BaseModel):
    facility_id: str | None
    doctor: str | None
    from_date: date
    to_date: date | None
    max_bookings_per_shift: int
    days: list[AvailableDay]


class FrontendTimeSlot(BaseModel):
    id: str
    time: str
    status: Literal["available"] = "available"
    shift: ShiftCode
    label: str
    remaining_capacity: int


class FrontendScheduleDay(BaseModel):
    date: str
    label: str
    slots: list[FrontendTimeSlot]


class BookingRequest(BaseModel):
    facilityId: str
    specialtyId: str = ""
    doctorId: str = ""
    date: date
    time: str
    patientName: str
    patientPhone: str
    patientEmail: str = ""
    patientDob: str = ""
    patientGender: str = ""
    patientAddress: str = ""
    patientHometown: str = ""
    patientCccd: str = ""
    symptoms: str = ""


FACILITIES = [
    FacilityItem(
        id="cs1",
        name="Bệnh viện Tim Hà Nội — Cơ sở 1",
        shortName="Cơ sở 1",
        address="Số 92 Trần Hưng Đạo, phường Cửa Nam, Hà Nội",
        phone="19001082",
        hours="07:00–17:00",
        image="/images/hospital-campus.svg",
    ),
    FacilityItem(
        id="cs2",
        name="Bệnh viện Tim Hà Nội — Cơ sở 2",
        shortName="Cơ sở 2",
        address="Số 695 Lạc Long Quân, phường Tây Hồ, Hà Nội",
        phone="19001082",
        hours="07:00–17:00",
        image="/images/hospital-building.svg",
    ),
]


router = APIRouter(prefix="/api")
security = HTTPBearer(auto_error=False)


def _optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any] | None:
    if credentials is None:
        return None
    payload = AuthService.decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(401, "Token không hợp lệ hoặc đã hết hạn.")
    return payload


def _current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(401, "Vui lòng đăng nhập để xem lịch khám.")
    payload = AuthService.decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(401, "Token không hợp lệ hoặc đã hết hạn.")
    return payload


def _max_bookings() -> int:
    try:
        value = int(os.getenv("MAX_BOOKINGS_PER_SHIFT", "6"))
    except ValueError:
        value = 6
    return max(value, 1)


def _normalise_facility(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None

    normalised = value.strip().casefold().replace("_", "").replace("-", "")
    mapping = {
        "1": 1,
        "cs1": 1,
        "fac1": 1,
        "facility1": 1,
        "cơsở1": 1,
        "coso1": 1,
        "2": 2,
        "cs2": 2,
        "fac2": 2,
        "facility2": 2,
        "cơsở2": 2,
        "coso2": 2,
    }
    facility = mapping.get(normalised.replace(" ", ""))
    if facility is None:
        raise HTTPException(422, "Cơ sở phải là cs1 hoặc cs2.")
    return facility


def _facility_id(value: int) -> str:
    return f"cs{value}"


def _clean_doctor_name(value: Any) -> str:
    return " ".join(str(value or "").split())


def _doctor_facility_id(zone: str, content: str) -> str:
    searchable = f"{zone} {content}".casefold()
    if "cơ sở 2" in searchable or "co so 2" in searchable:
        return "cs2"
    if "cơ sở 1" in searchable or "co so 1" in searchable:
        return "cs1"
    return ""


def _doctor_catalog_item(snapshot: Any) -> DoctorCatalogItem:
    data = snapshot.to_dict() or {}
    title = _clean_doctor_name(data.get("title")) or "Bác sĩ"
    content = " ".join(str(data.get("content") or "").split())
    zone = _clean_doctor_name(data.get("zone"))
    return DoctorCatalogItem(
        id=snapshot.id,
        title=title,
        content=content,
        zone=zone,
        facility_id=_doctor_facility_id(zone, content),
    )


def _date_label(value: date) -> str:
    return f"{WEEKDAY_LABELS[value.weekday()]} ({value.day}/{value.month})"


def _load_import_facilities() -> dict[str, int]:
    firestore = _firestore_client()
    result: dict[str, int] = {}
    for snapshot in firestore.collection("schedule_imports").stream():
        data = snapshot.to_dict()
        try:
            result[snapshot.id] = int(data.get("facility", 1))
        except (TypeError, ValueError):
            result[snapshot.id] = 1
    return result


def _load_available_rows(
    *,
    facility: int | None,
    doctor: str | None,
    from_date: date,
    to_date: date | None,
) -> list[dict[str, Any]]:
    if to_date is not None and to_date < from_date:
        raise HTTPException(422, "to_date không được nhỏ hơn from_date.")

    firestore = _firestore_client()
    max_bookings = _max_bookings()
    import_facilities = _load_import_facilities()
    query = (
        firestore.collection("schedule_shifts")
        .where(filter=FieldFilter("import_status", "==", "published"))
        .where(filter=FieldFilter("state", "==", "working"))
    )

    expected_doctor = _clean_doctor_name(doctor).casefold() if doctor else None
    rows: list[dict[str, Any]] = []

    try:
        snapshots = query.stream()
        for snapshot in snapshots:
            item = snapshot.to_dict()
            item_date_raw = item.get("work_date")
            try:
                item_date = date.fromisoformat(str(item_date_raw))
            except (TypeError, ValueError):
                continue

            if item_date < from_date or (to_date is not None and item_date > to_date):
                continue

            import_id = str(item.get("import_id", ""))
            item_facility = item.get("facility", import_facilities.get(import_id, 1))
            try:
                item_facility = int(item_facility)
            except (TypeError, ValueError):
                item_facility = 1
            if facility is not None and item_facility != facility:
                continue

            shift = str(item.get("shift", ""))
            if shift not in SHIFT_ORDER:
                continue

            doctor_name = _clean_doctor_name(item.get("value"))
            if not doctor_name:
                continue
            if expected_doctor and doctor_name.casefold() != expected_doctor:
                continue

            try:
                booked_count = max(int(item.get("booked_count", 0)), 0)
            except (TypeError, ValueError):
                booked_count = 0
            if booked_count >= max_bookings:
                continue

            rows.append(
                {
                    **item,
                    "id": str(item.get("id") or snapshot.id),
                    "doctor_name": doctor_name,
                    "facility": item_facility,
                    "work_date_value": item_date,
                    "booked_count": booked_count,
                    "remaining_capacity": max_bookings - booked_count,
                }
            )
    except Exception as error:
        raise HTTPException(503, f"Không thể truy vấn lịch khám từ Firestore: {error}") from error

    rows.sort(
        key=lambda item: (
            item["work_date_value"],
            SHIFT_ORDER[item["shift"]],
            int(item.get("area_sort", 0)),
            int(item.get("room_sort", 0)),
            item["doctor_name"].casefold(),
        )
    )
    return rows


def _group_available_days(rows: list[dict[str, Any]]) -> list[AvailableDay]:
    grouped: dict[date, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    day_labels: dict[date, str] = {}

    for item in rows:
        work_date = item["work_date_value"]
        grouped[work_date][item["shift"]].append(item)
        day_labels.setdefault(work_date, _date_label(work_date))

    days: list[AvailableDay] = []
    for work_date in sorted(grouped):
        shifts: list[AvailableShift] = []
        for shift_name in sorted(grouped[work_date], key=SHIFT_ORDER.__getitem__):
            shift_rows = grouped[work_date][shift_name]
            doctors = sorted(
                {item["doctor_name"] for item in shift_rows},
                key=str.casefold,
            )
            shifts.append(
                AvailableShift(
                    shift=shift_name,
                    label=SHIFT_LABELS[shift_name],
                    appointment_time=SHIFT_DEFAULT_TIMES[shift_name],
                    remaining_capacity=sum(item["remaining_capacity"] for item in shift_rows),
                    doctor_count=len(doctors),
                    doctors=doctors,
                    shift_ids=[item["id"] for item in shift_rows],
                )
            )
        days.append(
            AvailableDay(
                date=work_date,
                label=day_labels[work_date],
                shifts=shifts,
            )
        )
    return days


def _shift_from_time(value: str) -> ShiftCode:
    try:
        hour, minute = (int(part) for part in value.split(":", maxsplit=1))
    except (TypeError, ValueError):
        raise HTTPException(422, "Giờ khám phải có định dạng HH:MM.") from None
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise HTTPException(422, "Giờ khám phải có định dạng HH:MM.")
    return "morning" if hour < 12 else "afternoon"


@router.get("/facilities", response_model=list[FacilityItem])
def list_facilities() -> list[FacilityItem]:
    """Return the two hospital facilities in the shape expected by the frontend."""
    return FACILITIES


@router.get("/doctors", response_model=list[DoctorCatalogItem])
def list_doctors() -> list[DoctorCatalogItem]:
    """Return doctor profiles stored in Firestore doctor_capabilities."""
    try:
        snapshots = _firestore_client().collection("doctor_capabilities").stream()
        doctors = [_doctor_catalog_item(snapshot) for snapshot in snapshots]
    except Exception as error:
        raise HTTPException(
            503,
            f"Không thể tải danh sách bác sĩ từ Firestore: {error}",
        ) from error

    doctors.sort(key=lambda item: item.title.casefold())
    return doctors


@router.get("/doctors/{doctor_id}", response_model=DoctorCatalogItem)
def get_doctor(doctor_id: str) -> DoctorCatalogItem:
    """Return one doctor profile from Firestore doctor_capabilities."""
    try:
        snapshot = (
            _firestore_client()
            .collection("doctor_capabilities")
            .document(doctor_id)
            .get()
        )
    except Exception as error:
        raise HTTPException(
            503,
            f"Không thể tải thông tin bác sĩ từ Firestore: {error}",
        ) from error
    if not snapshot.exists:
        raise HTTPException(404, "Không tìm thấy bác sĩ.")
    return _doctor_catalog_item(snapshot)


@router.get("/booking/doctors", response_model=list[DoctorAvailabilityItem])
def list_available_doctors(
    facility_id: str | None = Query(default=None),
    from_date: date = Query(default_factory=date.today),
    to_date: date | None = Query(default=None),
) -> list[DoctorAvailabilityItem]:
    """Return doctors who have at least one future published shift with capacity."""
    facility = _normalise_facility(facility_id)
    rows = _load_available_rows(
        facility=facility,
        doctor=None,
        from_date=from_date,
        to_date=to_date,
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in rows:
        grouped[item["doctor_name"]].append(item)

    result = [
        DoctorAvailabilityItem(
            name=name,
            facilities=sorted({_facility_id(item["facility"]) for item in items}),
            available_shift_count=len(items),
            first_available_date=min(item["work_date_value"] for item in items),
        )
        for name, items in grouped.items()
    ]
    result.sort(key=lambda item: (item.first_available_date, item.name.casefold()))
    return result


@router.get("/booking/availability", response_model=AvailabilityResponse)
def get_booking_availability(
    facility_id: str | None = Query(default=None),
    doctor: str | None = Query(default=None, min_length=1),
    from_date: date = Query(default_factory=date.today),
    to_date: date | None = Query(default=None),
) -> AvailabilityResponse:
    """Return only available dates and morning/afternoon shifts, optionally by doctor."""
    facility = _normalise_facility(facility_id)
    clean_doctor = _clean_doctor_name(doctor) or None
    rows = _load_available_rows(
        facility=facility,
        doctor=clean_doctor,
        from_date=from_date,
        to_date=to_date,
    )
    return AvailabilityResponse(
        facility_id=_facility_id(facility) if facility else None,
        doctor=clean_doctor,
        from_date=from_date,
        to_date=to_date,
        max_bookings_per_shift=_max_bookings(),
        days=_group_available_days(rows),
    )


@router.get("/schedules", response_model=list[FrontendScheduleDay])
def list_frontend_schedules(
    doctor: str | None = Query(default=None),
    facility: str | None = Query(default=None),
    from_date: date = Query(default_factory=date.today),
    to_date: date | None = Query(default=None),
) -> list[FrontendScheduleDay]:
    """Compatibility endpoint for the current frontend scheduleService.list()."""
    availability = get_booking_availability(
        facility_id=facility,
        doctor=doctor,
        from_date=from_date,
        to_date=to_date,
    )
    return [
        FrontendScheduleDay(
            date=item.date.isoformat(),
            label=item.label,
            slots=[
                FrontendTimeSlot(
                    id=f"{item.date.isoformat()}-{shift.shift}",
                    time=shift.appointment_time,
                    shift=shift.shift,
                    label=shift.label,
                    remaining_capacity=shift.remaining_capacity,
                )
                for shift in item.shifts
            ],
        )
        for item in availability.days
    ]


@router.post("/appointments")
def create_appointment(
    request: BookingRequest,
    current_user: dict[str, Any] | None = Depends(_optional_user),
) -> dict[str, Any]:
    """Reserve an available shift; assign the least-booked doctor when omitted."""
    facility = _normalise_facility(request.facilityId)
    if facility is None:
        raise HTTPException(422, "Vui lòng chọn cơ sở khám.")
    shift = _shift_from_time(request.time)
    doctor = _clean_doctor_name(request.doctorId) or None
    candidates = _load_available_rows(
        facility=facility,
        doctor=doctor,
        from_date=request.date,
        to_date=request.date,
    )
    candidates = [item for item in candidates if item["shift"] == shift]
    candidates.sort(
        key=lambda item: (
            item["booked_count"],
            item["doctor_name"].casefold(),
            item["id"],
        )
    )
    if not candidates:
        message = (
            f"Bác sĩ {doctor} không còn lịch"
            if doctor
            else "Không còn bác sĩ nhận khám"
        )
        raise HTTPException(
            409,
            f"{message} vào {SHIFT_LABELS[shift].lower()} ngày {request.date.isoformat()}.",
        )

    client = _firestore_client()
    max_bookings = _max_bookings()
    appointment_id = str(uuid.uuid4())
    appointment_ref = client.collection("appointments").document(appointment_id)

    class ShiftNoLongerAvailable(Exception):
        pass

    for candidate in candidates:
        shift_ref = client.collection("schedule_shifts").document(candidate["id"])
        transaction = client.transaction()

        @firestore.transactional
        def reserve(current_transaction: Any) -> dict[str, Any]:
            snapshot = shift_ref.get(transaction=current_transaction)
            if not snapshot.exists:
                raise ShiftNoLongerAvailable
            current = snapshot.to_dict()
            current_booked = int(current.get("booked_count", 0) or 0)
            if (
                current.get("import_status") != "published"
                or current.get("state") != "working"
                or current_booked >= max_bookings
            ):
                raise ShiftNoLongerAvailable

            active_doctor = _clean_doctor_name(current.get("value"))
            if doctor and active_doctor.casefold() != doctor.casefold():
                raise ShiftNoLongerAvailable

            code = f"BVT-{uuid.uuid4().hex[:8].upper()}"
            appointment = {
                "id": appointment_id,
                "code": code,
                "doctorId": active_doctor,
                "doctorName": active_doctor,
                "specialtyId": request.specialtyId,
                "specialty": request.specialtyId,
                "facilityId": _facility_id(facility),
                "facilityName": f"Bệnh viện Tim Hà Nội — Cơ sở {facility}",
                "date": request.date.isoformat(),
                "time": request.time,
                "shift": shift,
                "status": "upcoming",
                "patientName": request.patientName.strip(),
                "patientPhone": request.patientPhone.replace(" ", ""),
                "patientEmail": request.patientEmail.strip(),
                "patientDob": request.patientDob,
                "patientGender": request.patientGender,
                "patientAddress": request.patientAddress.strip(),
                "patientHometown": request.patientHometown.strip(),
                "patientCccd": request.patientCccd.strip(),
                "symptoms": request.symptoms.strip(),
                "shift_id": candidate["id"],
                "user_id": current_user.get("user_id") if current_user else None,
                "patient_id": current_user.get("patient_id") if current_user else None,
                "created_at": datetime.utcnow().isoformat(),
            }
            current_transaction.update(
                shift_ref,
                {"booked_count": current_booked + 1},
            )
            current_transaction.set(appointment_ref, appointment)
            return appointment

        try:
            return reserve(transaction)
        except ShiftNoLongerAvailable:
            continue

    raise HTTPException(
        409,
        "Ca khám vừa hết chỗ. Vui lòng tải lại lịch và chọn buổi khác.",
    )


@router.get("/appointments/me")
def list_my_appointments(
    current_user: dict[str, Any] = Depends(_current_user),
) -> list[dict[str, Any]]:
    """Return appointments belonging to the authenticated hospital account."""
    client = _firestore_client()
    user_id = str(current_user.get("user_id") or "")
    phone = str(current_user.get("phone") or "")
    appointments: dict[str, dict[str, Any]] = {}

    try:
        if user_id:
            snapshots = (
                client.collection("appointments")
                .where(filter=FieldFilter("user_id", "==", user_id))
                .stream()
            )
            for snapshot in snapshots:
                appointments[snapshot.id] = snapshot.to_dict()

        # Include older bookings created before user_id was stored.
        if phone:
            snapshots = (
                client.collection("appointments")
                .where(filter=FieldFilter("patientPhone", "==", phone))
                .stream()
            )
            for snapshot in snapshots:
                appointments[snapshot.id] = snapshot.to_dict()
    except Exception as error:
        raise HTTPException(503, f"Không thể tải lịch hẹn từ Firestore: {error}") from error

    result = list(appointments.values())
    result.sort(key=lambda item: (str(item.get("date", "")), str(item.get("time", ""))))
    return result


def create_app() -> FastAPI:
    application = FastAPI(
        title="Hanoi Heart Hospital Booking Service",
        version="1.0.0",
    )
    origins = [
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router)
    application.include_router(auth_router, prefix="/api")

    @application.exception_handler(PermissionDenied)
    async def firestore_permission_error(_, __):
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "Backend chưa có quyền truy cập Firestore. "
                    "Hãy cấp role Cloud Datastore User cho tài khoản đang chạy API."
                )
            },
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy", "service": "booking-availability"}

    return application


app = create_app()


__all__ = ["app", "create_app", "router"]
