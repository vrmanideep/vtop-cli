import httpx
import asyncio

from vitap_vtop_client.constants import VTOP_URL, HEADERS
from vitap_vtop_client.exceptions.exception import VtopConnectionError, VtopCsrfError
from vitap_vtop_client.utils import find_csrf


async def fetch_csrf_token(client: httpx.AsyncClient, max_retries: int = 3) -> str:
    last_exception = None

    for attempt in range(max_retries):
        print(f"Fetching initial CSRF token, attempt {attempt + 1}/{max_retries}...")
        try:
            response = await client.get(VTOP_URL, headers=HEADERS)
            response.raise_for_status()

            csrf_token = find_csrf(response.text)

            if csrf_token:
                print("Initial CSRF token found.")
                return csrf_token
            else:
                print("Initial CSRF token not found in response.")
                last_exception = VtopCsrfError(
                    f"Initial CSRF token not found on attempt {attempt + 1}.",
                    status_code=response.status_code,
                )

        except httpx.RequestError as e:
            print(f"Network error on CSRF fetch attempt {attempt + 1}: {e}")
            last_exception = VtopConnectionError(
                f"Network error on CSRF fetch attempt {attempt + 1}: {e}",
                original_exception=e,
                status_code=502,
            )

        except VtopCsrfError as e:
            last_exception = e

        except Exception as e:
            print(f"Unexpected error during CSRF fetch attempt {attempt + 1}: {e}")
            last_exception = VtopCsrfError(
                f"Unexpected error during CSRF fetch attempt {attempt + 1}: {e}",
                status_code=None,
            )

        if attempt < max_retries - 1:
            await asyncio.sleep(1)

    raise VtopCsrfError(
        f"Failed to fetch CSRF token after {max_retries} attempts.",
        status_code=502,
    ) from last_exception