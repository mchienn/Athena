"""Small reviewed demo knowledge base; replace with an approved RAG service."""

import unicodedata

EMERGENCY_TERMS = (
    "đau ngực dữ dội",
    "khó thở dữ dội",
    "bất tỉnh",
    "ngừng tim",
    "méo miệng",
    "yếu liệt",
)

KNOWLEDGE_BASE = (
    {
        "keywords": ("tăng huyết áp", "cao huyết áp", "huyết áp"),
        "title": "Tăng huyết áp",
        "content": (
            "Tăng huyết áp thường ít triệu chứng. Đo đúng kỹ thuật và theo dõi nhiều lần "
            "giúp bác sĩ đánh giá; không tự ý ngừng hoặc đổi thuốc huyết áp."
        ),
    },
    {
        "keywords": ("đau ngực", "tức ngực"),
        "title": "Đau ngực",
        "content": (
            "Đau ngực có nhiều nguyên nhân. Đau thắt hoặc đè nặng, lan tay/hàm/lưng, kèm "
            "khó thở, vã mồ hôi, buồn nôn hoặc choáng cần được đánh giá cấp cứu."
        ),
    },
    {
        "keywords": ("điện tâm đồ", "ecg", "điện tim"),
        "title": "Điện tâm đồ",
        "content": (
            "Điện tâm đồ ghi hoạt động điện của tim, hỗ trợ phát hiện rối loạn nhịp và một "
            "số bất thường khác; kết quả phải được diễn giải cùng triệu chứng và khám bệnh."
        ),
    },
)


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.casefold())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def search_medical_knowledge(query: str) -> dict:
    """Search a reviewed demo cardiovascular knowledge base and flag emergencies."""
    normalized_query = _normalize(query)
    emergency = any(_normalize(term) in normalized_query for term in EMERGENCY_TERMS)
    matches = [
        {"title": item["title"], "content": item["content"]}
        for item in KNOWLEDGE_BASE
        if any(_normalize(keyword) in normalized_query for keyword in item["keywords"])
    ]
    return {
        "status": "success",
        "source": "demo_reviewed_content",
        "emergency": emergency,
        "emergency_action": (
            "Gọi 115 hoặc đến cơ sở cấp cứu gần nhất ngay; không tự lái xe nếu không an toàn."
            if emergency
            else None
        ),
        "matches": matches,
        "notice": "Thông tin giáo dục, không thay thế chẩn đoán hoặc chỉ định của bác sĩ.",
    }

