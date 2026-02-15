from pydantic import BaseModel


class OutingInfoModel(BaseModel):
    registration_number: str
    name: str
    application_no: str
    gender: str
    hostel_block: str
    room_number: str
    parent_contact_number: str
