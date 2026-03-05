from typing import List
from pydantic import BaseModel, RootModel


class ExamEntry(BaseModel):
    serial_number: str
    course_code: str
    course_title: str
    type: str
    registration_number: str
    slot: str
    date: str
    session: str
    reporting_time: str
    exam_time: str
    venue: str
    seat_location: str
    seat_number: str


class ExamScheduleGroup(BaseModel):
    exam_type: str
    subjects: List[ExamEntry]


class ExamScheduleModel(RootModel[List[ExamScheduleGroup]]):
    pass
