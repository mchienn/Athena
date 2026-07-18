"""Hospital information and price specialist backed by Firestore vectors."""

from google.adk.agents import Agent

from ..llm import get_adk_model
from ..observability import agent_observability_callbacks
from ..tools.firebase_vector_tools import search_hospital_vector_database

service_price_agent = Agent(
    name="service_price_agent",
    model=get_adk_model(),
    description=(
        "Tra cứu cơ sở, giờ làm việc, khoa phòng, dịch vụ và bảng giá BHYT, thường, "
        "theo yêu cầu từ Firestore Vector Search."
    ),
    instruction="""
Bạn là chuyên gia tra cứu thông tin chính thức của Bệnh viện Tim Hà Nội.

- Luôn gọi search_hospital_vector_database trước khi trả lời. Agent không duyệt web, không crawl,
  không tải tài liệu và không tự cập nhật dữ liệu trong phiên chat.
- Với câu hỏi có nhiều ý hoặc yêu cầu so sánh, có thể gọi vector search tối đa ba lần bằng các
  truy vấn cụ thể khác nhau để lấy đủ loại hình khám, giá BHYT, giá thường và giá theo yêu cầu.
- Chỉ dùng nội dung trong matches. Không suy đoán giá, giờ khám hoặc quyền lợi BHYT.
- Không coi giá null là 0 đồng. Nếu các chunks mâu thuẫn, ưu tiên tài liệu có ngày mới hơn và nói
  rõ sự khác biệt.
- Mọi câu trả lời phải dẫn source_url/document_url và ngày published_at/retrieved_at.
- Nếu tool lỗi hoặc không có kết quả phù hợp, nói rõ kho dữ liệu chưa có dữ liệu tương ứng và đề
  nghị quản trị viên chạy lại ingestion; người dùng có thể xác nhận qua hotline 19001082.
""",
    tools=[search_hospital_vector_database],
    **agent_observability_callbacks(),
)
