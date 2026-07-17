import random
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from .db_service import DBService
from .auth_service import AuthService

router = APIRouter()
db_service = DBService()
security = HTTPBearer()

# --- Pydantic Models ---
class RegisterRequest(BaseModel):
    phone: str = Field(..., description="Số điện thoại dùng để đăng ký", json_schema_extra={"example": "0912345678"})
    password: str = Field(..., min_length=6, description="Mật khẩu tối thiểu 6 ký tự", json_schema_extra={"example": "password123"})
    full_name: str = Field(..., description="Họ và tên đầy đủ", json_schema_extra={"example": "Nguyễn Văn A"})
    dob: str = Field(..., description="Ngày sinh định dạng YYYY-MM-DD", json_schema_extra={"example": "1990-01-01"})
    gender: str = Field(..., description="Giới tính (Nam/Nữ/Khác)", json_schema_extra={"example": "Nam"})
    bhyt_code: Optional[str] = Field(None, description="Mã thẻ BHYT", json_schema_extra={"example": "GD4010123456789"})
    address: Optional[str] = Field(None, description="Địa chỉ thường trú", json_schema_extra={"example": "Hoàn Kiếm, Hà Nội"})
    cccd: Optional[str] = Field(None, description="Căn cước công dân", json_schema_extra={"example": "001090123456"})
    hometown: Optional[str] = Field(None, description="Quê quán", json_schema_extra={"example": "Hải Phòng"})

class LoginRequest(BaseModel):
    phone: str = Field(..., json_schema_extra={"example": "0912345678"})
    password: str = Field(..., json_schema_extra={"example": "password123"})

class PatientUpdate(BaseModel):
    full_name: Optional[str] = Field(None, json_schema_extra={"example": "Nguyễn Văn B"})
    dob: Optional[str] = Field(None, json_schema_extra={"example": "1990-02-02"})
    gender: Optional[str] = Field(None, json_schema_extra={"example": "Nữ"})
    bhyt_code: Optional[str] = Field(None, json_schema_extra={"example": "GD4010123456999"})
    address: Optional[str] = Field(None, json_schema_extra={"example": "Hai Bà Trưng, Hà Nội"})
    cccd: Optional[str] = Field(None, json_schema_extra={"example": "001090123456"})
    hometown: Optional[str] = Field(None, json_schema_extra={"example": "Hải Phòng"})

class MockRequest(BaseModel):
    count: int = Field(5, ge=1, le=50, description="Số lượng bệnh nhân mẫu cần sinh")


# --- Dependency ---
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Validate JWT token and return token payload."""
    token = credentials.credentials
    payload = AuthService.decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# --- Endpoints ---

@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest):
    """Register a new user and create their patient profile."""
    # Check if user already exists
    existing_user = db_service.get_user_by_phone(req.phone)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số điện thoại này đã được đăng ký."
        )

    # Hash password
    password_hash = AuthService.hash_password(req.password)

    # Save to Firestore
    user_id, patient_id = db_service.create_user_and_patient(
        phone=req.phone,
        password_hash=password_hash,
        full_name=req.full_name,
        dob=req.dob,
        gender=req.gender,
        bhyt_code=req.bhyt_code,
        address=req.address,
        cccd=req.cccd,
        hometown=req.hometown
    )

    return {
        "status": "success",
        "message": "Đăng ký tài khoản thành công.",
        "user_id": user_id,
        "patient_id": patient_id
    }


@router.post("/auth/login")
async def login(req: LoginRequest):
    """Authenticate credentials and return a JWT access token."""
    user = db_service.get_user_by_phone(req.phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Số điện thoại hoặc mật khẩu không chính xác."
        )

    # Verify password hash
    is_valid = AuthService.verify_password(req.password, user["password_hash"])
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Số điện thoại hoặc mật khẩu không chính xác."
        )

    # Generate token
    token_payload = {
        "user_id": user["user_id"],
        "patient_id": user["patient_id"],
        "phone": user["phone"]
    }
    access_token = AuthService.create_access_token(token_payload)

    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user["user_id"],
        "patient_id": user["patient_id"]
    }


@router.get("/patients/me")
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    """Retrieve profile of the authenticated patient."""
    patient_id = current_user.get("patient_id")
    if not patient_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy mã bệnh nhân liên kết."
        )

    profile = db_service.get_patient_by_id(patient_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hồ sơ bệnh nhân tương ứng."
        )

    return {
        "status": "success",
        "profile": profile
    }


@router.put("/patients/me")
async def update_my_profile(req: PatientUpdate, current_user: dict = Depends(get_current_user)):
    """Update profile of the authenticated patient."""
    patient_id = current_user.get("patient_id")
    if not patient_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy mã bệnh nhân liên kết."
        )

    # Remove None values from request
    update_dict = {k: v for k, v in req.model_dump().items() if v is not None}
    if not update_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không có thông tin nào cần cập nhật."
        )

    db_service.update_patient(patient_id, update_dict)
    
    # Retrieve updated profile to return
    updated_profile = db_service.get_patient_by_id(patient_id)
    return {
        "status": "success",
        "message": "Cập nhật hồ sơ thành công.",
        "profile": updated_profile
    }


@router.get("/patients/me/records")
async def get_my_medical_records(current_user: dict = Depends(get_current_user)):
    """Retrieve medical history/records of the authenticated patient."""
    patient_id = current_user.get("patient_id")
    if not patient_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy mã bệnh nhân liên kết."
        )

    records = db_service.get_medical_records_by_patient_id(patient_id)
    return {
        "status": "success",
        "records": records
    }



# --- Mock Data Generation Endpoints ---

HO_LIST = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Phan", "Vũ", "Võ", "Đặng", "Bùi"]
DEM_LIST = ["Văn", "Thị", "Minh", "Tuấn", "Đức", "Hoàng", "Khánh", "Hữu", "Thành", "Ngọc"]
TEN_LIST = ["Anh", "Bình", "Cường", "Dũng", "Hải", "Hùng", "Huy", "Linh", "Nam", "Sơn", "Trang", "Tuấn", "Vy"]

def generate_random_name():
    return f"{random.choice(HO_LIST)} {random.choice(DEM_LIST)} {random.choice(TEN_LIST)}"

def generate_random_phone():
    # Format: 09XXXXXXXX (Ensure it's 10 digits)
    return f"09{random.randint(10000000, 99999999)}"

def generate_random_dob():
    year = random.randint(1950, 2010)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{year:04d}-{month:02d}-{day:02d}"

def generate_random_gender():
    return random.choice(["Nam", "Nữ"])

def generate_random_bhyt():
    return f"GD401{random.randint(1000000000, 9999999999)}"

HOMETOWN_LIST = ["Hà Nội", "Hải Phòng", "Nam Định", "Thái Bình", "Hưng Yên", "Hải Dương", "Bắc Ninh", "Vĩnh Phúc", "Thanh Hóa", "Nghệ An", "Quảng Ninh", "Hòa Bình", "Hà Nam"]

def generate_random_hometown():
    return random.choice(HOMETOWN_LIST)

def generate_random_cccd():
    prefix = f"{random.randint(1, 30):03d}"
    gender_birth_century = str(random.choice([0, 1, 2, 3]))
    birth_year_short = f"{random.randint(50, 99):02d}"
    suffix = f"{random.randint(100000, 999999):06d}"
    return f"{prefix}{gender_birth_century}{birth_year_short}{suffix}"


CLINICAL_CASES = [
    {
        "department": "Nội tim mạch",
        "doctor_name": "BS. Nguyễn Hoàng Nam",
        "diagnosis": "Tăng huyết áp vô căn độ II, Rối loạn lipid máu",
        "symptoms": "Đau đầu nhẹ vùng chẩm vào buổi sáng, thỉnh thoảng chóng mặt.",
        "treatment_plan": "Duy trì uống thuốc đều đặn vào buổi sáng, hạn chế ăn mặn, tập thể dục nhẹ nhàng. Tái khám sau 30 ngày.",
        "prescription": [
            {"medicine_name": "Amlodipine 5mg", "dosage": "1 viên/ngày, uống sáng sau ăn", "quantity": 30},
            {"medicine_name": "Lipitor 10mg", "dosage": "1 viên/ngày, uống tối trước khi đi ngủ", "quantity": 30}
        ]
    },
    {
        "department": "Nội tim mạch",
        "doctor_name": "BS. Trần Minh Đức",
        "diagnosis": "Bệnh tim thiếu máu cục bộ mạn tính, Suy tim độ II",
        "symptoms": "Đau thắt ngực trái khi gắng sức (đi bộ khoảng 200m), khó thở nhẹ.",
        "treatment_plan": "Nghỉ ngơi khi có cơn đau ngực. Dùng Nitroglycerin xịt dưới lưỡi nếu đau nhiều không giảm. Hạn chế gắng sức mạnh. Tái khám định kỳ.",
        "prescription": [
            {"medicine_name": "Concor 5mg", "dosage": "1/2 viên/ngày, uống sáng", "quantity": 15},
            {"medicine_name": "Vastarel MR 35mg", "dosage": "2 viên/ngày, chia 2 lần sáng tối", "quantity": 60},
            {"medicine_name": "Plavix 75mg", "dosage": "1 viên/ngày, uống sáng", "quantity": 30}
        ]
    },
    {
        "department": "Nhịp học",
        "doctor_name": "BS. Phan Thanh Hải",
        "diagnosis": "Rung nhĩ cơn, Hẹp nhẹ van hai lá",
        "symptoms": "Hồi hộp, đánh trống ngực từng cơn kéo dài 10-15 phút kèm theo mệt mỏi.",
        "treatment_plan": "Theo dõi nhịp tim bằng máy đo tại nhà. Tránh các chất kích thích (trà, cà phê, rượu bia). Tái khám ngay nếu có cơn hồi hộp kéo dài kèm khó thở.",
        "prescription": [
            {"medicine_name": "Sintrom 4mg", "dosage": "1/4 viên/ngày, uống vào 20h hàng ngày", "quantity": 7},
            {"medicine_name": "Concor 2.5mg", "dosage": "1 viên/ngày, uống sáng", "quantity": 30}
        ]
    },
    {
        "department": "Suy tim",
        "doctor_name": "BS. Lê Thị Thu Hà",
        "diagnosis": "Suy tim mạn tính sau nhồi máu cơ tim, EF=40%",
        "symptoms": "Khó thở nhẹ khi leo cầu thang, phù nhẹ hai chi dưới về chiều, mệt mỏi.",
        "treatment_plan": "Hạn chế uống nhiều nước (dưới 1.5 lít/ngày cả canh). Ăn nhạt tuyệt đối. Theo dõi cân nặng hàng ngày (báo bác sĩ nếu tăng trên 2kg trong 3 ngày).",
        "prescription": [
            {"medicine_name": "Verospiron 25mg", "dosage": "1 viên/ngày, uống sáng", "quantity": 30},
            {"medicine_name": "Forxiga 10mg", "dosage": "1 viên/ngày, uống sáng", "quantity": 30},
            {"medicine_name": "Furosemid 40mg", "dosage": "1 viên/ngày, uống sáng cách nhật", "quantity": 15}
        ]
    }
]

from datetime import date, timedelta

def generate_random_visit_date():
    # Random date within last 180 days
    days_ago = random.randint(30, 180)
    visit_date = date.today() - timedelta(days=days_ago)
    next_date = visit_date + timedelta(days=30)
    return visit_date.isoformat(), next_date.isoformat()


@router.post("/patients/mock")
async def generate_mock_patients(req: MockRequest):
    """Bulk generate mock patients, user accounts, and medical history."""
    created_users = []
    default_password = "password123"
    hashed_password = AuthService.hash_password(default_password)

    for _ in range(req.count):
        # Ensure we generate a unique random phone number
        phone = generate_random_phone()
        while db_service.get_user_by_phone(phone) is not None:
            phone = generate_random_phone()

        full_name = generate_random_name()
        dob = generate_random_dob()
        gender = generate_random_gender()
        bhyt = generate_random_bhyt()
        cccd = generate_random_cccd()
        hometown = generate_random_hometown()
        address = "Hà Nội, Việt Nam"

        # Generate 1 to 2 random medical records for this patient
        num_records = random.randint(1, 2)
        mock_records = []
        chosen_cases = random.sample(CLINICAL_CASES, num_records)
        
        for case in chosen_cases:
            v_date, next_date = generate_random_visit_date()
            mock_records.append({
                "visit_date": v_date,
                "department": case["department"],
                "doctor_name": case["doctor_name"],
                "diagnosis": case["diagnosis"],
                "symptoms": case["symptoms"],
                "treatment_plan": case["treatment_plan"],
                "prescription": case["prescription"],
                "next_appointment_date": next_date
            })

        user_id, patient_id = db_service.create_user_and_patient(
            phone=phone,
            password_hash=hashed_password,
            full_name=full_name,
            dob=dob,
            gender=gender,
            bhyt_code=bhyt,
            address=address,
            cccd=cccd,
            hometown=hometown,
            records=mock_records
        )

        created_users.append({
            "phone": phone,
            "password": default_password,
            "full_name": full_name,
            "dob": dob,
            "gender": gender,
            "bhyt_code": bhyt,
            "cccd": cccd,
            "hometown": hometown,
            "user_id": user_id,
            "patient_id": patient_id,
            "medical_records_count": len(mock_records)
        })

    return {
        "status": "success",
        "message": f"Đã sinh thành công {req.count} bệnh nhân giả lập cùng lịch sử khám bệnh.",
        "default_password": default_password,
        "patients": created_users
    }

