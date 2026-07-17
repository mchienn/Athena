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
    monkeypatch.setattr(schedule_api, "DB", tmp_path / "schedule.db")
    schedule_api.init_db()
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
