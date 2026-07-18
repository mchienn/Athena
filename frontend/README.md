# Bệnh viện Tim Hà Nội — Frontend

Website React + TypeScript được tái cấu trúc từ bundle Figma `Redesign Hanoi Heart Hospital Website.zip`. Toàn bộ mã nguồn chạy nằm trực tiếp trong thư mục `frontend`.

## Chạy dự án

Yêu cầu Node.js 20.19+ hoặc 22.12+.

```bash
npm install
cp .env.example .env
npm run dev
```

Kiểm tra production:

```bash
npm run typecheck
npm run build
npm run preview
```

## Biến môi trường

- `VITE_API_BASE_URL`: base URL Hospital Backend (ví dụ `http://127.0.0.1:8002/api`) cho xác thực, hồ sơ, lịch khám và đặt lịch. Để trống để chạy hoàn toàn bằng mock.
- `VITE_BOOKING_API_BASE_URL`: tuỳ chọn; chỉ dùng khi Booking API được triển khai tách backend. Mặc định dùng `VITE_API_BASE_URL`.
- `VITE_APP_NAME`: tên ứng dụng.
- `VITE_DEFAULT_LANGUAGE`: ngôn ngữ mặc định.
- `VITE_ADK_API_BASE_URL`: đường dẫn Google ADK API Server. Development dùng `/adk-api` và Vite chuyển tiếp tới `http://127.0.0.1:8000`.
- `VITE_ADK_APP_NAME`: tên thư mục agent, hiện là `hanoi_heart_assistant`.
- `VITE_FIREBASE_*`: cấu hình Firebase Web App dùng cho Anonymous Auth và Firestore.

File `.env.example` cũng ghi chú tên tương đương `NEXT_PUBLIC_*` nếu chuyển dự án sang Next.js.

## Điểm nối REST API

Tất cả request đi qua `src/services/apiClient.ts`. Khi `VITE_API_BASE_URL` có giá trị, các service tự chuyển từ mock sang REST:

- `authService`: `/auth/login`, `/auth/register`, `/auth/forgot-password`.
- `doctorService`: `/doctors`, `/doctors/:id`, `/specialties`.
- `scheduleService`: `/facilities`, `/schedules`.
- `appointmentService`: `/appointments`.
- `pricingService`: `/pricing`.
- `assistantService`: ADK `/apps/{app}/users/{user}/sessions/{session}` và `/run`.

Chạy Hospital Backend tại thư mục gốc trước khi chạy frontend:

```powershell
uv run uvicorn hanoi_heart_assistant.service:app --reload --port 8002
```

## Chatbot trang đặt lịch

Chatbot tại `/dat-lich`, trang AI và widget popup dùng chung một hook và một nguồn dữ liệu. Firebase UID làm ADK `userId`; ID cuộc trò chuyện Firestore làm ADK `sessionId`. Document `users/{uid}` giữ `activeChatId`, danh sách chat nằm tại `users/{uid}/chats`, còn tin nhắn nằm trong subcollection `messages`. Không lưu nội dung chat hoặc session ID trong `localStorage`.

Trong Firebase Console, bật **Authentication → Anonymous** và deploy `firestore.rules`. Sau đó chạy ADK API Server tại thư mục gốc dự án:

```powershell
uv run adk api_server --port 8000 --allow_origins http://localhost:3000 --session_service_uri sqlite:///./adk_sessions.db
```

SQLite giữ state/event của ADK qua các lần restart; Firestore giữ danh sách và lịch sử hiển thị cho từng người dùng.

Response backend nên được map về type trong `src/types/index.ts`. Nếu schema API khác UI model, thêm mapper cạnh service thay vì sửa component.

## Route

- `/`: trang chủ.
- `/bac-si`, `/bac-si/:id`: danh sách và chi tiết bác sĩ.
- `/chuyen-khoa`, `/lich-kham`, `/dat-lich`, `/dat-lich/xac-nhan`.
- `/tro-ly-ai`: trợ lý thông tin bệnh viện.
- `/dang-nhap`, `/dang-ky`, `/quen-mat-khau`.
- `/tai-khoan`, `/tai-khoan/lich-hen`, `/tai-khoan/ho-so`, `/tai-khoan/bao-mat`.

## Asset đã sử dụng

- `public/logos/hanoi-heart-hospital.svg`: logo tái dựng từ biểu tượng tim/y tế trong prototype.
- `public/images/hero-hospital.svg`: minh họa hero.
- `public/images/hospital-campus.svg`, `hospital-building.svg`: hai cơ sở.
- `public/images/doctor-*.svg`: sáu ảnh đại diện bác sĩ demo.

ZIP Figma không chứa binary asset; prototype gốc dùng URL Unsplash. Các SVG local được dùng để project chạy độc lập, không nhúng base64 và không phụ thuộc ảnh từ bên ngoài.

## Cấu trúc

```text
frontend/
├── public/
│   ├── images/              # Ảnh minh họa local
│   ├── icons/               # SVG icon riêng khi có
│   └── logos/               # Logo thương hiệu
├── src/
│   ├── app/                 # Router và app root
│   ├── components/
│   │   ├── common/          # AppShell, PageHero, DoctorCard, state UI
│   │   ├── home/            # Section riêng của trang chủ
│   │   ├── booking/         # Stepper và 6 step độc lập
│   │   ├── assistant/       # Widget, message và structured cards
│   │   ├── auth/            # Form đăng nhập/đăng ký/quên mật khẩu
│   │   └── account/         # Layout và lịch hẹn tài khoản
│   ├── pages/               # Component cấp route; chỉ ghép section/dữ liệu
│   ├── services/            # API client, error handling và domain service
│   ├── hooks/               # State dùng lại, gồm booking draft
│   ├── mocks/               # Dữ liệu demo thay được bằng API
│   ├── types/               # UI/domain model TypeScript
│   └── styles/              # Reset và design token dùng chung
├── .env.example
└── package.json
```

Mỗi component/page chính có CSS Module riêng. Không có inline style, styled-components hoặc CSS-in-JS.
