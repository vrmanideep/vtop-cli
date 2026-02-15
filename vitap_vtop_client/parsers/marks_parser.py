from bs4 import BeautifulSoup
from typing import List
from vitap_vtop_client.exceptions.exception import VtopParsingError
from vitap_vtop_client.marks.model.marks_model import (
    MarksModel,
    SubjectMark,
    MarkDetail,
)


def parse_marks(html: str) -> MarksModel:
    soup = BeautifulSoup(html, "html.parser")

    try:
        main_table = soup.find("table", class_="customTable")
        if not main_table:
            return MarksModel(root=[])

        rows = main_table.find_all("tr", class_="tableContent")
        subjects: List[SubjectMark] = []

        for i in range(0, len(rows), 2):
            basic_info_row = rows[i].find_all("td")
            basic_info = {
                "serial_number": basic_info_row[0].text.strip(),
                "class_id": basic_info_row[1].text.strip(),
                "course_code": basic_info_row[2].text.strip(),
                "course_title": basic_info_row[3].text.strip(),
                "course_type": basic_info_row[4].text.strip(),
                "course_system": basic_info_row[5].text.strip(),
                "faculty": basic_info_row[6].text.strip(),
                "slot": basic_info_row[7].text.strip(),
                "details": [],
            }

            if i + 1 < len(rows):
                nested_table = rows[i + 1].find("table", class_="customTable-level1")
                if nested_table:
                    nested_rows = nested_table.find_all("tr")[1:]
                    for nested_row in nested_rows:
                        nested_cols = nested_row.find_all("td")
                        detail = MarkDetail(
                            serial_number=nested_cols[0].text.strip(),
                            mark_title=nested_cols[1].text.strip(),
                            max_mark=nested_cols[2].text.strip(),
                            weightage=nested_cols[3].text.strip(),
                            status=nested_cols[4].text.strip(),
                            scored_mark=nested_cols[5].text.strip(),
                            weightage_mark=nested_cols[6].text.strip(),
                            remark=nested_cols[7].text.strip(),
                        )
                        basic_info["details"].append(detail)

            subjects.append(SubjectMark(**basic_info))

        return MarksModel(root=subjects)

    except Exception as e:
        print(f"Failed to parse marks: {e}")
        raise VtopParsingError(f"Failed to parse marks: {e}")
