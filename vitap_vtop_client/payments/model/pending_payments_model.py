from pydantic import BaseModel


class PendingPayment(BaseModel):
    s_no: str
    fprefno: str
    fees_heads: str
    end_date: str
    amount: str
    fine: str
    total_amount: str
    payment_status: str = "Unpaid"
