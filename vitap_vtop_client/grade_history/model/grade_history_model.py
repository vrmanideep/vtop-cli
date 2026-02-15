from pydantic import BaseModel
from typing import Optional


class GradeHistoryModel(BaseModel):
    credits_registered: str = "N/A"
    credits_earned: str = "N/A"
    cgpa: str = "N/A"
