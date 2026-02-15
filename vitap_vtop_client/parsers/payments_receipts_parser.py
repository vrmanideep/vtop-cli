from bs4 import BeautifulSoup
import re
from typing import List
from vitap_vtop_client.exceptions.exception import VtopParsingError
from vitap_vtop_client.payments.model.payment_receipt_model import PaymentReceipt


def parse_payment_receipts(html: str) -> List[PaymentReceipt]:
    try:
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.find_all("tr")[1:]  # Skip header

        if not rows:
            return []  # No receipts

        payments = []
        pattern = r"javascript:doDuplicateReceipt\('([^']*)'\);"

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue  # Skip malformed row

            button = cols[4].find("button")
            onclick_value = (
                button["onclick"] if button and "onclick" in button.attrs else None
            )

            if not onclick_value:
                raise VtopParsingError("Missing or malformed receipt button")

            match = re.search(pattern, onclick_value)
            if not match:
                raise VtopParsingError(
                    "Unable to extract receiptNo from onclick attribute"
                )

            receipt_no = match.group(1)

            payment = PaymentReceipt(
                receipt_number=cols[0].text.strip(),
                date=cols[1].text.strip(),
                amount=cols[2].text.strip(),
                campus_code=cols[3].text.strip(),
                payment_status="Paid",
                receipt_no=receipt_no,
            )
            payments.append(payment)

        return payments

    except Exception as e:
        raise VtopParsingError(f"Failed to parse payment receipts: {e}")
