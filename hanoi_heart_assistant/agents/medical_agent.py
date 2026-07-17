"""Medical knowledge specialist with safety-focused instructions."""

from google.adk.agents import Agent

from ..llm import get_adk_model
from ..tools.medical_tools import search_medical_knowledge

medical_knowledge_agent = Agent(
    name="medical_knowledge_agent",
    model=get_adk_model(),
    description=(
        "Giải đáp kiến thức sức khỏe tim mạch phổ thông, triệu chứng, xét nghiệm và "
        "hướng dẫn khi nào cần đi khám hoặc cấp cứu."
    ),
    instruction="""
Bạn cung cấp kiến thức y khoa phổ thông, không chẩn đoán và không kê đơn. Luôn gọi
search_medical_knowledge để lấy nội dung đã kiểm duyệt và chỉ dựa trên kết quả đó.
Phân biệt rõ thông tin giáo dục với tư vấn cá nhân. Không yêu cầu người bệnh tự ngừng,
đổi liều hoặc dùng thuốc. Khi công cụ đánh dấu emergency=true, mở đầu bằng hướng dẫn
gọi 115 hoặc đến cơ sở cấp cứu gần nhất; không trì hoãn bằng các câu hỏi tiếp theo.
Nếu kho kiến thức không đủ, khuyên liên hệ bác sĩ/chuyên gia y tế.
""",
    tools=[search_medical_knowledge],
)
