from typing import List
from pydantic import BaseModel, RootModel


class MarkDetail(BaseModel):
    serial_number: str
    mark_title: str
    max_mark: str
    weightage: str
    status: str
    scored_mark: str
    weightage_mark: str
    remark: str


class SubjectMark(BaseModel):
    serial_number: str
    class_id: str
    course_code: str
    course_title: str
    course_type: str
    course_system: str
    faculty: str
    slot: str
    details: List[MarkDetail]


class MarksModel(RootModel[List[SubjectMark]]):
    pass
