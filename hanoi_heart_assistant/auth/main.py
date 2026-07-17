from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes import router

app = FastAPI(
    title="Hanoi Heart Hospital Customer Care Auth API",
    description="Hệ thống Backend Xác thực & Quản lý Hồ sơ Bệnh nhân mẫu.",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
