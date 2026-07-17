import os
import re
import uuid
from datetime import datetime
from typing import Any
import google.auth
from google.cloud import firestore

# Reuse same logic to identify Firebase Project ID
def _firebase_project_id() -> str:
    configured = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    if configured:
        return configured
    base_url = os.getenv("OPENAI_BASE_URL", "")
    match = re.search(r"/projects/([^/]+)", base_url)
    if match:
        return match.group(1)
    try:
        _, adc_project = google.auth.default()
        if adc_project:
            return adc_project
    except Exception:
        pass
    return "demo-project"  # Fallback for local testing if no credentials are configured

def get_firestore_client() -> firestore.Client:
    return firestore.Client(
        project=_firebase_project_id(),
        database=os.getenv("FIRESTORE_DATABASE", "(default)").strip() or "(default)",
    )

class DBService:
    def __init__(self):
        self.db = get_firestore_client()
        self.users_col = os.getenv("FIRESTORE_USERS_COLLECTION", "users").strip()
        self.patients_col = os.getenv("FIRESTORE_PATIENTS_COLLECTION", "patients").strip()
        self.records_col = os.getenv("FIRESTORE_RECORDS_COLLECTION", "medical_records").strip()

    def get_user_by_phone(self, phone: str) -> dict[str, Any] | None:
        """Find a user by phone number."""
        query = self.db.collection(self.users_col).where("phone", "==", phone.strip()).limit(1).stream()
        for doc in query:
            data = doc.to_dict()
            data["user_id"] = doc.id
            return data
        return None

    def bind_firebase_uid(self, user_id: str, firebase_uid: str) -> None:
        """Allow a verified hospital account to use a Firebase Auth identity for chat."""
        self.db.collection(self.users_col).document(user_id).update(
            {"firebase_uids": firestore.ArrayUnion([firebase_uid])}
        )

    def create_user_and_patient(
        self,
        phone: str,
        password_hash: str,
        full_name: str,
        dob: str,
        gender: str,
        bhyt_code: str | None = None,
        address: str | None = None,
        cccd: str | None = None,
        hometown: str | None = None,
        records: list[dict[str, Any]] | None = None,
    ) -> tuple[str, str]:
        """Create a patient record, user account, and optional medical records atomically."""
        user_id = str(uuid.uuid4())
        patient_id = str(uuid.uuid4())
        now = datetime.utcnow()

        patient_data = {
            "patient_id": patient_id,
            "full_name": full_name.strip(),
            "phone": phone.strip(),
            "dob": dob.strip(),
            "gender": gender.strip(),
            "bhyt_code": bhyt_code.strip() if bhyt_code else None,
            "address": address.strip() if address else None,
            "cccd": cccd.strip() if cccd else None,
            "hometown": hometown.strip() if hometown else None,
            "updated_at": now,
        }

        user_data = {
            "user_id": user_id,
            "phone": phone.strip(),
            "password_hash": password_hash,
            "patient_id": patient_id,
            "created_at": now,
        }

        # Write atomically using batch
        batch = self.db.batch()
        
        patient_ref = self.db.collection(self.patients_col).document(patient_id)
        batch.set(patient_ref, patient_data)

        user_ref = self.db.collection(self.users_col).document(user_id)
        batch.set(user_ref, user_data)

        # Write optional mock medical records
        if records:
            for rec in records:
                rec_id = str(uuid.uuid4())
                rec_data = {
                    "record_id": rec_id,
                    "patient_id": patient_id,
                    "visit_date": rec.get("visit_date"),
                    "department": rec.get("department"),
                    "doctor_name": rec.get("doctor_name"),
                    "diagnosis": rec.get("diagnosis"),
                    "symptoms": rec.get("symptoms"),
                    "treatment_plan": rec.get("treatment_plan"),
                    "prescription": rec.get("prescription") or [],
                    "next_appointment_date": rec.get("next_appointment_date"),
                    "created_at": now,
                }
                rec_ref = self.db.collection(self.records_col).document(rec_id)
                batch.set(rec_ref, rec_data)

        batch.commit()
        return user_id, patient_id

    def get_patient_by_id(self, patient_id: str) -> dict[str, Any] | None:
        """Retrieve patient details by patient_id."""
        doc_ref = self.db.collection(self.patients_col).document(patient_id)
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            # Convert datetime to string for JSON serialization
            if "updated_at" in data and isinstance(data["updated_at"], datetime):
                data["updated_at"] = data["updated_at"].isoformat()
            return data
        return None

    def update_patient(self, patient_id: str, update_data: dict[str, Any]) -> None:
        """Update patient details."""
        doc_ref = self.db.collection(self.patients_col).document(patient_id)
        
        # Strip potential keys we don't want updated directly
        filtered_data = {
            k: v for k, v in update_data.items() 
            if k in {"full_name", "dob", "gender", "bhyt_code", "address", "cccd", "hometown"}
        }
        filtered_data["updated_at"] = datetime.utcnow()
        
        doc_ref.update(filtered_data)

    def get_medical_records_by_patient_id(self, patient_id: str) -> list[dict[str, Any]]:
        """Retrieve all medical records for a patient sorted by visit date descending."""
        query = (
            self.db.collection(self.records_col)
            .where("patient_id", "==", patient_id)
            .stream()
        )
        records = []
        for doc in query:
            data = doc.to_dict()
            if "created_at" in data and isinstance(data["created_at"], datetime):
                data["created_at"] = data["created_at"].isoformat()
            records.append(data)
        # Sort by visit_date descending
        records.sort(key=lambda x: x.get("visit_date", ""), reverse=True)
        return records

