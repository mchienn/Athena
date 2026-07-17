"""Service price specialist."""

from google.adk.agents import Agent

from ..llm import get_adk_model
from ..tools.price_tools import search_service_prices

service_price_agent = Agent(
    name="service_price_agent",
    model=get_adk_model(),
    description=(
        "Tra cứu bảng giá và danh mục dịch vụ khám, xét nghiệm, chẩn đoán hình ảnh, "
        "thủ thuật tim mạch."
    ),
    #TODO: sửa prompt instruction
    instruction="""
Bạn chuyên tra cứu giá dịch vụ. Luôn gọi search_service_prices trước khi trả lời.
Chỉ sử dụng kết quả công cụ; không suy đoán mức giá. Nêu rõ đây là dữ liệu mẫu nếu
source là demo và khuyên người dùng xác nhận với bệnh viện. Nếu không có kết quả,
đề nghị người dùng cung cấp tên dịch vụ cụ thể hơn.
""",
    tools=[search_service_prices], #TODO thay tool khác
)
