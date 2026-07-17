from hanoi_heart_assistant.tools import schedule_tools


def test_schedule_lookup_returns_empty_when_database_is_not_present(monkeypatch):
    class MockFirestore:
        def collection(self, name):
            return self
        def where(self, field, op, value):
            return self
        def stream(self):
            return []
            
    from hanoi_heart_assistant.tools import firebase_vector_tools
    monkeypatch.setattr(firebase_vector_tools, "_firestore_client", lambda: MockFirestore())

    result = schedule_tools.search_published_schedule(work_date="2026-07-16")

    assert result["status"] == "success"
    assert result["matches"] == []


def test_schedule_lookup_rejects_unknown_shift():
    result = schedule_tools.search_published_schedule(shift="evening")

    assert result == {"status": "error", "message": "Ca chỉ có thể là morning hoặc afternoon."}
