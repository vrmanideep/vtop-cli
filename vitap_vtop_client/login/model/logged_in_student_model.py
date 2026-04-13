from pydantic import BaseModel

class LoggedInStudent(BaseModel):
    registration_number: str
    post_login_csrf_token: str