from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google.api_core.exceptions import PermissionDenied
from .routes import router

app = FastAPI(
    title="Hanoi Heart Hospital Customer Care Auth API",
    description="Hệ thống Backend Xác thực & Quản lý Hồ sơ Bệnh nhân mẫu.",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(PermissionDenied)
async def firestore_permission_error(_, __):
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "Backend chưa có quyền truy cập Firestore. "
                "Hãy cấp role Cloud Datastore User cho tài khoản đang chạy API."
            )
        },
    )

# Mount Routers under /api
app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "Hanoi Heart Customer Care Auth API",
        "documentation": "/docs"
    }
