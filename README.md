# Trợ lý CSKH Bệnh viện Tim Hà Nội (Google ADK)

Bộ khung multi-agent gồm một agent điều phối và ba agent con:

```text
hanoi_heart_customer_care_coordinator
├── service_price_agent       # tra bảng giá dịch vụ
├── medical_knowledge_agent   # tra kiến thức tim mạch an toàn
└── appointment_agent         # xem lịch và tiếp nhận yêu cầu đặt khám
```

Agent điều phối dùng cơ chế `sub_agents` của Google ADK để tự động chuyển giao yêu cầu.
Tool đặt lịch và một phần kho kiến thức y khoa vẫn dùng **dữ liệu demo**. Price agent đã dùng
Firestore Vector Search chứa dữ liệu website/PDF/ảnh được crawl và OCR ngoại tuyến.

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


## Đồng bộ website, PDF, ảnh vào Firestore Vector Search

`service_price_agent` không duyệt web trong phiên chat. Việc crawl website, tải Google Drive,
đọc PDF/ảnh và Vision OCR chạy ngoại tuyến; kết quả được chia chunk, tạo embedding qua
`OPENAI_BASE_URL` và lưu vào Cloud Firestore của Firebase. Agent chỉ có tool
`search_hospital_vector_database` để semantic search dữ liệu đã đồng bộ.

Mặc định `DOCUMENT_EXTRACTION_BACKEND=auto`: nếu có `GEMINI_API_KEY`, pipeline dùng Files API;
nếu không, pipeline gửi PDF/ảnh inline qua `OPENAI_BASE_URL` và dùng cùng API key hoặc Google ADC
như agent trong `llm.py`. Có thể ép backend thành `files_api` hoặc `openai_compatible`. Sau đó cài
Chromium một lần và chạy:

```powershell
uv sync
uv run playwright install chromium
uv run python -m hanoi_heart_assistant.tools.firebase_ingestion --max-pages 40
uv run pytest
```

Kết quả mặc định được ghi nguyên tử vào
`hanoi_heart_assistant/data/hospital_knowledge.json`; file cũ chỉ bị thay sau khi crawl và trích xuất
hoàn tất. Nên chạy lệnh này bằng scheduler, kiểm duyệt `crawl_errors` và các mức giá mới trước khi
phát hành. File tải tạm nằm dưới `.cache/hospital_documents` và không được commit.

Nếu JSON đã được crawl/OCR trước đó, có thể chỉ tạo embeddings và ghi Firestore:

```powershell
uv run python -m hanoi_heart_assistant.tools.firebase_ingestion --skip-crawl
```

Tạo vector index một lần (dimension phải khớp `.env`):

```powershell
uv run python -m hanoi_heart_assistant.tools.firebase_ingestion --create-index
```

Để bổ sung raw text của website mà không OCR lại PDF/ảnh đã xử lý:

```powershell
uv run python -m hanoi_heart_assistant.tools.firebase_ingestion --crawl-web-only --max-pages 40
```

Ingestion dùng chunk ID theo SHA-256. Các lần chạy sau chỉ tạo embedding cho chunk mới hoặc khi
model/dimension thay đổi; chunks cũ được tái sử dụng và dữ liệu không còn trong corpus sẽ được xóa
nếu `FIREBASE_VECTOR_PRUNE_STALE=true`.

Firestore không tự tạo embedding. Endpoint OpenAI-compatible hiện tại không expose `/embeddings`,
vì vậy pipeline mặc định dùng Google Gen AI SDK trên Vertex AI với cùng project/ADC, model
`gemini-embedding-001` và giảm đầu ra còn 768 chiều. Vẫn có thể đặt backend thành
`openai_compatible` nếu endpoint khác hỗ trợ embeddings. Firestore hỗ trợ tối đa 2048 chiều.


## Nhập và duyệt lịch khám (Module 4)

Module 4 đã được nối vào backend hiện tại qua cùng SQLite database. Chạy API review
và frontend preview bằng:

```powershell
uv sync
uv run uvicorn hanoi_heart_assistant.schedule_api:app --reload --port 8001
```

Mở `http://127.0.0.1:8001`. Upload `.xlsx` tại màn hình này sẽ tạo bản nháp trong
`hanoi_heart_assistant/data/schedule.db`, tách mỗi ô thành ca sáng/chiều, cho phép sửa từng ca và
chỉ đưa vào truy vấn chatbot sau khi bấm **Duyệt & publish**. Các endpoint import/review
là `POST /api/sources`, `GET /api/sources/{id}`, `PATCH /api/shifts/{id}` và
`POST /api/sources/{id}/approve`.

Agent đặt lịch dùng `search_published_schedule` để đọc các ca đã publish từ chính DB này.

`hanoi_heart_assistant.schedule_api` là một component độc lập: lệnh trên chạy riêng
để duyệt lịch. Nếu dự án có FastAPI host chung, mount UI/API lịch tại `/schedule`:

```python
from fastapi import FastAPI
from hanoi_heart_assistant.schedule_api import mount_schedule

app = FastAPI()
mount_schedule(app)  # /schedule và /schedule/api/...
```


## Tích hợp website qua REST/SSE

Chạy backend website (xác thực, hồ sơ, lịch khám và đặt lịch) từ thư mục gốc:

```powershell
uv run uvicorn hanoi_heart_assistant.service:app --reload --port 8002
```

API xác thực và booking cùng nằm dưới `http://127.0.0.1:8002/api`; không cần chạy
`hanoi_heart_assistant.auth.main` riêng. Để frontend dùng backend này, đặt
`VITE_API_BASE_URL=http://127.0.0.1:8002/api` trong `frontend/.env`.

Chạy ADK API server từ thư mục gốc:

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

1. Lập lịch chạy `firebase_ingestion`, kiểm duyệt dữ liệu OCR, theo dõi trạng thái vector index,
   quota/cost Firestore và giữ ngày hiệu lực cùng phạm vi BHYT trong metadata nguồn.
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
