from datetime import date, timedelta

from hanoi_heart_assistant.tools.appointment_tools import (
    list_appointment_slots,
    submit_appointment_request,
)
from hanoi_heart_assistant.tools.medical_tools import search_medical_knowledge
from hanoi_heart_assistant.tools.price_tools import search_service_prices


def test_price_search_is_accent_insensitive() -> None:
    result = search_service_prices("sieu am tim")
    assert result["status"] == "success"
    assert result["matches"][0]["code"] == "DEMO-ECHO"


def test_medical_search_flags_emergency() -> None:
    result = search_medical_knowledge("Tôi đau ngực dữ dội")
    assert result["emergency"] is True
    assert result["emergency_action"]


def test_rejects_past_appointment_date() -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert list_appointment_slots("tim_mach", yesterday)["status"] == "error"


def test_appointment_is_pending_not_confirmed() -> None:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    result = submit_appointment_request(
        "Nguyễn Văn An", "0912345678", "tim_mach", tomorrow, "08:00", "Khám định kỳ"
    )
    assert result["status"] == "pending_confirmation"
    assert result["request_id"].startswith("DEMO-")

