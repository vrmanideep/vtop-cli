from typing import Dict, List
from pydantic import BaseModel


# One day's schedule:
class Course(BaseModel):
    time: str
    course_name: str
    slot: str
    venue: str
    faculty: str
    course_code: str
    course_type: str


# Weekly timetable: key is the day, value is list of time slots (lectures)
class TimetableModel(BaseModel):
    Monday: List[Course] = []
    Tuesday: List[Course] = []
    Wednesday: List[Course] = []
    Thursday: List[Course] = []
    Friday: List[Course] = []
    Saturday: List[Course] = []
    Sunday: List[Course] = []
