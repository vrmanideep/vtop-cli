from pydantic import BaseModel


class PaymentReceipt(BaseModel):
    receipt_number: str
    date: str
    amount: str
    campus_code: str
    payment_status: str
    receipt_no: str
