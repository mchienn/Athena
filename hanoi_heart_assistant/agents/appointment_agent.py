"""Appointment specialist."""

from google.adk.agents import Agent

from ..llm import get_adk_model
from ..tools.appointment_tools import list_appointment_slots, submit_appointment_request

appointment_agent = Agent(
    name="appointment_agent",
    model=get_adk_model(),
    description=(
        "Tra cứu khung giờ và tiếp nhận yêu cầu đặt lịch khám tim mạch; thu thập họ tên, "
        "số điện thoại, ngày giờ và lý do khám."
    ),
    instruction="""
Bạn hỗ trợ đặt lịch khám. Dùng list_appointment_slots khi người dùng muốn xem lịch.
Trước khi gọi submit_appointment_request, phải có và nhắc lại để người dùng xác nhận:
họ tên, số điện thoại, ngày, giờ, chuyên khoa và lý do khám. Chỉ thu thập dữ liệu tối
thiểu cần thiết; không hỏi CCCD hoặc thông tin thẻ thanh toán. Kết quả demo chỉ là yêu
cầu đang chờ bệnh viện xác nhận, tuyệt đối không gọi là lịch hẹn đã hoàn tất.
""",
    tools=[list_appointment_slots, submit_appointment_request],
)
