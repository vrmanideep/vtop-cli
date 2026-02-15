from pydantic import BaseModel


class BiometricModel(BaseModel):
    time: str
    location: str