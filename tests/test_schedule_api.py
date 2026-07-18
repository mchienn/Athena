import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from hanoi_heart_assistant import schedule_api


def _cell(column: int, row: int, value: str) -> str:
    letter = chr(64 + column)
    return f'<c r="{letter}{row}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'


def _write_xlsx(path: Path, rows: list[list[str]], merges: list[str] | None = None) -> Path:
    xml_rows = []
    for row_index, values in enumerate(rows, 1):
        cells = "".join(
            _cell(column, row_index, value)
            for column, value in enumerate(values, 1)
            if value
        )
        xml_rows.append(f'<row r="{row_index}">{cells}</row>')
    merge_xml = "".join(f'<mergeCell ref="{item}"/>' for item in merges or [])
    worksheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(xml_rows)}</sheetData>'
        f'<mergeCells count="{len(merges or [])}">{merge_xml}</mergeCells>'
        "</worksheet>"
    )
    workbook = (
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheets><sheet name="Lịch" sheetId="1"/></sheets></workbook>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)
    return path


@pytest.mark.parametrize(
    ("rows", "merges", "expected_rooms"),
    [
        (
            [
                ["LỊCH PHÒNG KHÁM ĐA KHOA"],
                ["Tuần từ ngày 13/7/2026 đến ngày 19/7/2026"],
                [
                    "Phòng",
                    "Thời gian",
                    "Thứ 2",
                    "Thứ 3",
                    "Thứ 4",
                    "Thứ 5",
                    "Thứ 6",
                    "Thứ 7",
                    "Chủ nhật",
                ],
                ["RHM (P401)", "7.30 - 16.30", "BS A", "", "", "", "", "Nghỉ", "Nghỉ"],
                ["TMH (P402)", "7.30 - 16.30", "BS B", "", "", "", "", "Nghỉ", "Nghỉ"],
            ],
            [],
            2,
        ),
        (
            [
                ["LỊCH KHU TỰ NGUYỆN"],
                ["Tuần từ ngày 13/7/2026 đến ngày 19/7/2026"],
                [
                    "Dịch vụ",
                    "Phòng khám",
                    "Thời gian",
                    "Thứ 2",
                    "Thứ 3",
                    "Thứ 4",
                    "Thứ 5",
                    "Thứ 6",
                    "Thứ 7",
                    "Chủ nhật",
                ],
                ["Khu tự nguyện", "Phòng khám số 306", "7.00 - 16.30", "Sáng\nBS A\nChiều nghỉ"],
                ["", "Phòng khám số 309", "7.00 - 16.30", "BS B"],
            ],
            ["A4:A5"],
            2,
        ),
    ],
)
def test_imports_supported_schedule_templates(tmp_path, monkeypatch, rows, merges, expected_rooms):
    db_store = {}
    
    class MockDocumentReference:
        def __init__(self, coll_name, doc_id):
            self.coll_name = coll_name
            self.doc_id = doc_id
        def get(self):
            data = db_store[self.coll_name].get(self.doc_id)
            class MockDoc:
                def __init__(self, d):
                    self.exists = (d is not None)
                    self._d = d
                def to_dict(self):
                    return self._d
            return MockDoc(data)
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

    class MockBatch:
        def __init__(self):
            self.writes = []
        def set(self, doc_ref, data):
            self.writes.append((doc_ref, data))
        def commit(self):
            for doc_ref, data in self.writes:
                db_store[doc_ref.coll_name][doc_ref.doc_id] = data

    class MockFirestore:
        def collection(self, name):
            if name not in db_store:
                db_store[name] = {}
            return self
        def document(self, doc_id):
            return MockDocumentReference(name, doc_id) # wait, let's pass collection name
        def document_by_name(self, coll_name, doc_id):
            return MockDocumentReference(coll_name, doc_id)
        def where(self, field, op, val):
            return MockQuery("schedule_shifts", [(field, op, val)])
        def batch(self):
            return MockBatch()
            
    # Redefine MockFirestore document method to capture correct collection name
    class MockFirestore:
        def __init__(self):
            pass
        def collection(self, name):
            if name not in db_store:
                db_store[name] = {}
            self.last_coll = name
            return self
        def document(self, doc_id):
            return MockDocumentReference(self.last_coll, doc_id)
        def where(self, field, op, val):
            return MockQuery(self.last_coll, [(field, op, val)])
        def batch(self):
            return MockBatch()

    from hanoi_heart_assistant.tools import firebase_vector_tools
    monkeypatch.setattr(firebase_vector_tools, "_firestore_client", lambda: MockFirestore())

    source_id = schedule_api.import_excel(
        _write_xlsx(tmp_path / "schedule.xlsx", rows, merges), "schedule.xlsx"
    )

    preview = schedule_api.get_source(source_id)

    assert len(preview["days"]) == 7
    assert sum(len(area["rooms"]) for area in preview["areas"]) == expected_rooms
    assert [day["work_date"] for day in preview["days"]] == [
        f"2026-07-{13 + index:02d}" for index in range(7)
    ]


def test_parses_line_oriented_morning_and_afternoon_values():
    assert schedule_api.parse_cell("Sáng\nBS A\nChiều nghỉ") == {
        "morning": ("working", "BS A"),
        "afternoon": ("closed", None),
    }


def test_schedule_time_does_not_accept_phone_contact_text():
    assert schedule_api.is_schedule_time("7.30 - 16.30") is True
    assert schedule_api.is_schedule_time(
        "Số điện thoại liên hệ: 0961.972.097 (Giờ hành chính)"
    ) is False
