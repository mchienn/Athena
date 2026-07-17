"""Demo price lookup; replace PRICE_CATALOG with the hospital HIS/API source."""

import unicodedata

PRICE_CATALOG = (
    {"code": "DEMO-KHAM-TM", "name": "Khám chuyên khoa tim mạch", "price_vnd": 200_000},
    {"code": "DEMO-ECG", "name": "Điện tâm đồ thường", "price_vnd": 80_000},
    {"code": "DEMO-ECHO", "name": "Siêu âm tim Doppler màu", "price_vnd": 350_000},
    {"code": "DEMO-HOLTER", "name": "Holter điện tâm đồ 24 giờ", "price_vnd": 650_000},
)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def search_service_prices(query: str) -> dict:
    """Search demo hospital service prices by a Vietnamese name or service code."""
    keyword = _normalize(query.strip())
    if not keyword:
        return {"status": "error", "message": "Vui lòng nhập tên hoặc mã dịch vụ."}

    matches = [
        item
        for item in PRICE_CATALOG
        if keyword in _normalize(f"{item['code']} {item['name']}")
    ]
    return {
        "status": "success",
        "source": "demo_data_not_official",
        "matches": matches,
        "notice": (
            "Giá chỉ dùng để minh họa kỹ thuật, không phải bảng giá chính thức. "
            "Cần kết nối API/HIS và xác nhận với Bệnh viện Tim Hà Nội trước khi sử dụng."
        ),
    }

