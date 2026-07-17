import pytest
from fastapi.testclient import TestClient
from hanoi_heart_assistant.auth.main import app
from hanoi_heart_assistant.auth.routes import db_service

client = TestClient(app)

# In-memory mock database
mock_users = {}
mock_patients = {}
mock_records = {}

def mock_get_user_by_phone(phone: str) -> dict | None:
    for u in mock_users.values():
        if u["phone"] == phone:
            return u
    return None

def mock_create_user_and_patient(
    phone: str,
    password_hash: str,
    full_name: str,
    dob: str,
    gender: str,
    bhyt_code: str | None = None,
    address: str | None = None,
    records: list[dict] | None = None,
) -> tuple[str, str]:
    user_id = f"mock-user-{len(mock_users) + 1}"
    patient_id = f"mock-patient-{len(mock_patients) + 1}"
    
    mock_patients[patient_id] = {
        "patient_id": patient_id,
        "full_name": full_name,
        "phone": phone,
        "dob": dob,
        "gender": gender,
        "bhyt_code": bhyt_code,
        "address": address,
        "updated_at": "2026-07-17T15:00:00",
    }
    
    mock_users[user_id] = {
        "user_id": user_id,
        "phone": phone,
        "password_hash": password_hash,
        "patient_id": patient_id,
        "created_at": "2026-07-17T15:00:00",
    }

    if records:
        for idx, rec in enumerate(records):
            rec_id = f"mock-record-{patient_id}-{idx + 1}"
            mock_records[rec_id] = {
                "record_id": rec_id,
                "patient_id": patient_id,
                **rec,
                "created_at": "2026-07-17T15:00:00"
            }
            
    return user_id, patient_id

def mock_get_patient_by_id(patient_id: str) -> dict | None:
    return mock_patients.get(patient_id)

def mock_update_patient(patient_id: str, data: dict) -> None:
    if patient_id in mock_patients:
        filtered_data = {
            k: v for k, v in data.items() 
            if k in {"full_name", "dob", "gender", "bhyt_code", "address"}
        }
        mock_patients[patient_id].update(filtered_data)
        mock_patients[patient_id]["updated_at"] = "2026-07-17T16:00:00"

def mock_get_medical_records_by_patient_id(patient_id: str) -> list[dict]:
    results = [rec for rec in mock_records.values() if rec["patient_id"] == patient_id]
    results.sort(key=lambda x: x.get("visit_date", ""), reverse=True)
    return results


@pytest.fixture(autouse=True)
def setup_mock_db(monkeypatch):
    mock_users.clear()
    mock_patients.clear()
    mock_records.clear()
    monkeypatch.setattr(db_service, "get_user_by_phone", mock_get_user_by_phone)
    monkeypatch.setattr(db_service, "create_user_and_patient", mock_create_user_and_patient)
    monkeypatch.setattr(db_service, "get_patient_by_id", mock_get_patient_by_id)
    monkeypatch.setattr(db_service, "update_patient", mock_update_patient)
    monkeypatch.setattr(db_service, "get_medical_records_by_patient_id", mock_get_medical_records_by_patient_id)


def test_register_and_login_flow():
    # 1. Register a new user
    register_payload = {
        "phone": "0987654321",
        "password": "mysecretpassword",
        "full_name": "Nguyen Van Test",
        "dob": "1995-10-10",
        "gender": "Nam",
        "bhyt_code": "GD4010123456789",
        "address": "Ha Noi",
    }
    resp = client.post("/api/auth/register", json=register_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "success"
    assert "user_id" in data
    assert "patient_id" in data

    # 2. Register again with same phone should fail
    resp_duplicate = client.post("/api/auth/register", json=register_payload)
    assert resp_duplicate.status_code == 400
    assert "đã được đăng ký" in resp_duplicate.json()["detail"]

    # 3. Login with correct credentials
    login_payload = {
        "phone": "0987654321",
        "password": "mysecretpassword",
    }
    resp_login = client.post("/api/auth/login", json=login_payload)
    assert resp_login.status_code == 200
    login_data = resp_login.json()
    assert login_data["status"] == "success"
    assert "access_token" in login_data
    token = login_data["access_token"]

    # 4. Login with wrong password should fail
    resp_wrong_pass = client.post("/api/auth/login", json={"phone": "0987654321", "password": "wrongpassword"})
    assert resp_wrong_pass.status_code == 401


def test_patient_profile_and_history_management():
    # Setup a mock user with a mock medical record
    user_id, patient_id = mock_create_user_and_patient(
        phone="0911223344",
        password_hash="some-hash",
        full_name="Tran Thi Test",
        dob="1988-08-08",
        gender="Nữ",
        records=[
            {
                "visit_date": "2026-05-15",
                "department": "Nội tim mạch",
                "doctor_name": "BS. Nguyễn Hoàng Nam",
                "diagnosis": "Tăng huyết áp vô căn",
                "symptoms": "Đau đầu nhẹ",
                "treatment_plan": "Nghỉ ngơi, ăn nhạt",
                "prescription": [{"medicine_name": "Amlodipine 5mg", "dosage": "1 viên/ngày", "quantity": 30}],
                "next_appointment_date": "2026-06-15"
            }
        ]
    )
    
    # Generate token
    from hanoi_heart_assistant.auth.auth_service import AuthService
    token_payload = {
        "user_id": user_id,
        "patient_id": patient_id,
        "phone": "0911223344",
    }
    token = AuthService.create_access_token(token_payload)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get profile
    resp_profile = client.get("/api/patients/me", headers=headers)
    assert resp_profile.status_code == 200
    profile_data = resp_profile.json()
    assert profile_data["status"] == "success"
    assert profile_data["profile"]["full_name"] == "Tran Thi Test"
    assert profile_data["profile"]["gender"] == "Nữ"

    # 2. Get medical records
    resp_records = client.get("/api/patients/me/records", headers=headers)
    assert resp_records.status_code == 200
    records_data = resp_records.json()
    assert records_data["status"] == "success"
    assert len(records_data["records"]) == 1
    assert records_data["records"][0]["diagnosis"] == "Tăng huyết áp vô căn"
    assert records_data["records"][0]["doctor_name"] == "BS. Nguyễn Hoàng Nam"

    # 3. Update profile
    update_payload = {
        "full_name": "Tran Thi Updated",
        "gender": "Nữ",
        "bhyt_code": "GD4019999999999",
    }
    resp_update = client.put("/api/patients/me", json=update_payload, headers=headers)
    assert resp_update.status_code == 200
    update_data = resp_update.json()
    assert update_data["status"] == "success"
    assert update_data["profile"]["full_name"] == "Tran Thi Updated"
    assert update_data["profile"]["bhyt_code"] == "GD4019999999999"


def test_bulk_mock_generation_with_records():
    # Call mock endpoint
    resp = client.post("/api/patients/mock", json={"count": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert len(data["patients"]) == 5
    assert data["default_password"] == "password123"
    
    # Check if they exist in mock DB with records
    for p in data["patients"]:
        phone = p["phone"]
        user = mock_get_user_by_phone(phone)
        assert user is not None
        assert user["patient_id"] == p["patient_id"]
        
        patient = mock_get_patient_by_id(p["patient_id"])
        assert patient is not None
        assert patient["full_name"] == p["full_name"]
        
        # Verify medical records count
        recs = mock_get_medical_records_by_patient_id(p["patient_id"])
        assert len(recs) == p["medical_records_count"]
        assert len(recs) >= 1
        assert recs[0]["doctor_name"] is not None
