from datetime import date, timedelta

from hanoi_heart_assistant.tools.appointment_tools import (
    list_appointment_slots,
    open_booking_page,
    submit_appointment_request,
)
from hanoi_heart_assistant.tools.medical_tools import search_medical_knowledge


def test_medical_search_flags_emergency() -> None:
    result = search_medical_knowledge("Tôi đau ngực dữ dội")
    assert result["emergency"] is True
    assert result["emergency_action"]


def test_rejects_past_appointment_date() -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert list_appointment_slots("tim_mach", yesterday)["status"] == "error"


def test_open_booking_page_uses_frontend_url(monkeypatch) -> None:
    monkeypatch.setenv("FRONTEND_URL", "https://hospital.example/")

    assert open_booking_page() == {
        "status": "success",
        "action": "navigate",
        "url": "https://hospital.example/dat-lich",
        "message": "Đang chuyển người dùng đến trang đặt lịch.",
    }


def test_open_booking_page_rejects_invalid_frontend_url(monkeypatch) -> None:
    monkeypatch.setenv("FRONTEND_URL", "javascript:alert(1)")

    assert open_booking_page()["status"] == "error"


def test_appointment_is_pending_not_confirmed(monkeypatch) -> None:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    
    db_store = {
        "schedule_shifts": {
            "shift_1": {
                "id": "shift_1",
                "import_id": "import_1",
                "area_name": "Khu tự nguyện",
                "room_name": "Phòng 306",
                "work_time": "08:00 - 16:30",
                "work_date": tomorrow,
                "day_label": "Thứ 2",
                "day_sort": 1,
                "shift": "morning",
                "state": "working",
                "value": "TS.BS Phạm Như Hùng",
                "import_status": "published",
                "facility": 1,
                "booked_count": 0
            }
        },
        "appointments": {}
    }
    
    class MockDocumentReference:
        def __init__(self, coll_name, doc_id):
            self.coll_name = coll_name
            self.doc_id = doc_id
        def update(self, data):
            db_store[self.coll_name][self.doc_id].update(data)
        def set(self, data):
            db_store[self.coll_name][self.doc_id] = data
            
    class MockQuery:
        def __init__(self, coll_name, filters):
            self.coll_name = coll_name
            self.filters = filters
        def where(self, field, op, val):
            self.filters.append((field, op, val))
            return self
        def stream(self):
            results = []
            for doc_id, data in db_store[self.coll_name].items():
                match = True
                for f, o, v in self.filters:
                    if data.get(f) != v:
                        match = False
                        break
                if match:
                    class MockDoc:
                        def __init__(self, d):
                            self._d = d
                        def to_dict(self):
                            return self._d
                    results.append(MockDoc(data))
            return results

    class MockFirestore:
        def collection(self, name):
            if name not in db_store:
                db_store[name] = {}
            self.last_coll = name
            return self
        def document(self, doc_id):
            return MockDocumentReference(self.last_coll, doc_id)
        def where(self, field, op, val):
            return MockQuery(self.last_coll, [(field, op, val)])
            
    from hanoi_heart_assistant.tools import firebase_vector_tools
    monkeypatch.setattr(firebase_vector_tools, "_firestore_client", lambda: MockFirestore())
    
    result = submit_appointment_request(
        "Nguyễn Văn An", "0912345678", "tim_mach", tomorrow, "08:00", "Khám định kỳ", "TS.BS Phạm Như Hùng"
    )
    assert result["status"] == "success"
    assert result["code"].startswith("BVT-")
    assert db_store["schedule_shifts"]["shift_1"]["booked_count"] == 1

