from typing import List
from pydantic import BaseModel, RootModel


class WeekendOutingRequest(BaseModel):
    registration_number: str
    hostel_block: str
    room_number: str
    place_of_visit: str
    purpose_of_visit: str
    time: str
    contact_number: str
    parent_contact_number: str
    date: str
    booking_id: str
    action: str
    status: str


class WeekendOutingModel(RootModel):
    root: List[WeekendOutingRequest]
