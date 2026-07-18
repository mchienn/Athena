"""Appointment specialist."""

from google.adk.agents import Agent

from ..llm import get_adk_model
from ..observability import agent_observability_callbacks
from ..tools.appointment_tools import open_booking_page
from ..tools.schedule_tools import search_published_schedule

appointment_agent = Agent(
    name="appointment_agent",
    model=get_adk_model(),
    description=(
        "Tra cứu lịch bác sĩ đã duyệt và chuyển người dùng muốn đặt lịch đến biểu mẫu "
        "đặt lịch khám trên website."
    ),
    instruction="""
Bạn hỗ trợ tra cứu lịch khám và hướng người dùng đến biểu mẫu đặt lịch. Dùng
search_published_schedule để tìm các ca bác sĩ đã được duyệt theo ngày, phòng hoặc ca;
không tự suy đoán lịch.
Khi người dùng thể hiện ý định muốn đặt lịch (ví dụ "Tôi muốn đặt lịch", "Đặt lịch khám"),
phải gọi open_booking_page ngay để chuyển họ đến biểu mẫu đặt lịch trên website, đồng thời phải hiển thị đường dẫn đến trang được trả về.
Không hỏi thêm thông tin đặt lịch trong chat trước khi gọi tool này.
""",
    tools=[search_published_schedule, open_booking_page],
    **agent_observability_callbacks(),
)
