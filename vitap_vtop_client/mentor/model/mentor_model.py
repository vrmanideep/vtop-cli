from pydantic import BaseModel
from typing import Optional

class MentorModel(BaseModel):
    faculty_id: Optional[str]
    faculty_name: Optional[str]
    faculty_designation: Optional[str]
    school: Optional[str]
    cabin: Optional[str]
    faculty_department: Optional[str]
    faculty_email: Optional[str]
    faculty_intercom: Optional[str]
    faculty_mobile_number: Optional[str]
