from typing import List
from bs4 import BeautifulSoup

from vitap_vtop_client.exceptions.exception import VtopParsingError
from vitap_vtop_client.payments.model.pending_payments_model import PendingPayment


def parse_pending_payments(html: str) -> List[PendingPayment]:
    try:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")

        if not table:
            # Check if the "no dues" message is present
            message = soup.find(string="There is no payment dues in your account!")
            if message is not None:
                return []  # No pending payments
            raise VtopParsingError("Unable to find the pending payments table")

        rows = table.find_all("tr")
        if len(rows) <= 1:
            return []  # Table exists but only header

        pending_payments = []

        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) < 7:
                continue  # Skip malformed rows

            payment = PendingPayment(
                s_no=cols[0].text.strip(),
                fprefno=cols[1].text.strip(),
                fees_heads=cols[2].text.strip(),
                end_date=cols[3].text.strip(),
                amount=cols[4].text.strip(),
                fine=cols[5].text.strip(),
                total_amount=cols[6].text.strip(),
            )
            pending_payments.append(payment)

        return pending_payments

    except Exception as e:
        raise VtopParsingError(f"Failed to parse pending payments: {e}")
