import time
from typing import List
import httpx

from vitap_vtop_client.constants import HEADERS, PAYMENT_RECEIPT_URL
from vitap_vtop_client.parsers.payments_receipts_parser import parse_payment_receipts
from vitap_vtop_client.exceptions import (
    VtopConnectionError,
    VtopProfileError,
    VtopParsingError,
)
from vitap_vtop_client.payments.model.payment_receipt_model import PaymentReceipt


async def fetch_payment_receipts(
    client: httpx.AsyncClient,
    registration_number: str,
    csrf_token: str,
) -> List[PaymentReceipt]:
    """
    Asynchronously retrieves and parses payment receipts for a user from the VTOP system.

    Parameters
    ----------
    client : httpx.AsyncClient
        Shared async HTTP client.
    registration_number : str
        Student’s registration number.
    csrf_token : str
        CSRF token for authentication.

    Returns
    -------
    list
        A list of parsed payment receipts.
        • On success: list with one item per receipt
        • On parsing failure: raises VtopParsingError
        • On connection failure: raises VtopConnectionError
        • For any other error: raises VtopProfileError
    """

    try:
        data = {
            "verifyMenu": "true",
            "authorizedID": registration_number,
            "_csrf": csrf_token,
            "nocache": int(round(time.time() * 1000)),
        }

        response = await client.post(PAYMENT_RECEIPT_URL, data=data, headers=HEADERS)
        response.raise_for_status()

        receipts = parse_payment_receipts(response.text)
        return receipts

    except VtopParsingError:
        raise

    except httpx.RequestError as e:
        raise VtopConnectionError(
            f"Failed to fetch payment receipts: {e}",
            original_exception=e,
            status_code=502,
        ) from e

    except Exception as e:
        raise VtopProfileError(
            f"Unexpected error while fetching payment receipts: {e}"
        ) from e
