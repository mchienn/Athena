# Trợ lý CSKH Bệnh viện Tim Hà Nội (Google ADK)

Bộ khung multi-agent gồm một agent điều phối và ba agent con:

```text
hanoi_heart_customer_care_coordinator
├── service_price_agent       # tra bảng giá dịch vụ
├── medical_knowledge_agent   # tra kiến thức tim mạch an toàn
└── appointment_agent         # xem lịch và tiếp nhận yêu cầu đặt khám
```

Agent điều phối dùng cơ chế `sub_agents` của Google ADK để tự động chuyển giao yêu cầu.
Các tool hiện dùng **dữ liệu demo**, được cô lập để có thể thay bằng API bảng giá/HIS,
kho tri thức RAG đã kiểm duyệt và API đặt lịch thật.

## Chạy bằng uv

Yêu cầu: `uv` và thông tin xác thực cho OpenAI-compatible endpoint.

```powershell
Copy-Item .env.example .env
# Điền OPENAI_BASE_URL và chọn API key tĩnh hoặc Google ADC trong .env
uv sync
uv run adk web --port 8000
```

Nếu endpoint dùng API key tĩnh, đặt `OPENAI_API_KEY` trong `.env`. Nếu dùng Vertex AI,
để biến này trống và đăng nhập Google Application Default Credentials:

```powershell
gcloud auth application-default login
```

Ứng dụng tự refresh OAuth access token trước mỗi request. Hàm `_openai_client()` trong
`hanoi_heart_assistant/llm.py` cũng dùng cùng cơ chế khi cần gọi OpenAI SDK trực tiếp;
các ADK agent dùng `get_adk_model()` thông qua LiteLLM.

Mở `http://localhost:8000`, chọn `hanoi_heart_assistant` và thử:

- `Siêu âm tim giá bao nhiêu?`
- `Đau ngực khi nào cần đi cấp cứu?`
- `Tôi muốn đặt lịch khám tim mạch ngày 2026-08-01.`

Chạy CLI và kiểm tra mã nguồn:

```powershell
uv run adk run hanoi_heart_assistant
uv run pytest
uv run ruff check .
```

## Tích hợp website qua REST/SSE

Chạy API server từ thư mục gốc:

```powershell
uv run adk api_server --port 8000
```

Tạo session cho mỗi phiên chat:

```http
POST /apps/hanoi_heart_assistant/users/{user_id}/sessions/{session_id}
Content-Type: application/json

{}
```

Gửi tin nhắn qua `POST /run`; dùng `/run_sse` và `"streaming": true` nếu widget cần
streaming. Payload cơ bản:

```json
{
  "appName": "hanoi_heart_assistant",
  "userId": "web-user-123",
  "sessionId": "chat-session-456",
  "newMessage": {
    "role": "user",
    "parts": [{"text": "Siêu âm tim giá bao nhiêu?"}]
  }
}
```

Trong production, đặt một backend/BFF của bệnh viện trước ADK API để xử lý xác thực,
rate limit, CORS, audit log, che dữ liệu nhạy cảm và không để API key lộ ở trình duyệt.
`adk web` chỉ dành cho phát triển; widget website nên gọi backend của bệnh viện.

## Các điểm cần thay trước production

1. Thay `PRICE_CATALOG` trong `tools/price_tools.py` bằng nguồn bảng giá chính thức có
   ngày hiệu lực, đối tượng BHYT và cơ chế cache.
2. Thay `KNOWLEDGE_BASE` bằng RAG chỉ truy xuất tài liệu đã được bệnh viện phê duyệt;
   lưu nguồn, phiên bản và ngày duyệt để câu trả lời có trích dẫn.
3. Nối `appointment_tools.py` với API lịch khám thật, có giữ chỗ idempotent, OTP xác
   nhận, đổi/hủy lịch và thông báo SMS; không log dữ liệu sức khỏe thô.
4. Bổ sung consent, chính sách lưu trữ/xóa dữ liệu, phân quyền, mã hóa, quan sát hệ thống,
   bộ đánh giá định tuyến và kiểm thử red-team y khoa.
5. Đưa hotline, địa chỉ, quy trình cấp cứu và nội dung y khoa chính thức của bệnh viện
   vào cấu hình sau khi được đơn vị nghiệp vụ xác nhận.

## Tài liệu tham khảo

- [ADK Python quickstart](https://adk.dev/get-started/python/)
- [ADK agent team và automatic delegation](https://adk.dev/tutorials/agent-team/)
- [ADK API server](https://adk.dev/runtime/api-server/)
