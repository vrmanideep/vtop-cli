from pydantic import BaseModel
class AttendanceModel(BaseModel):
    course_id : str
    course_code : str
    course_name : str
    course_type : str
    course_slot : str
    attended_classes : str
    total_classes : str
    attendance_percentage : str
    within_attendance_percentage : str
    debar_status : str