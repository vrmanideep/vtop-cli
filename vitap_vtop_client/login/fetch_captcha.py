import httpx
import asyncio

from vitap_vtop_client.constants import VTOP_LOGIN_URL, HEADERS
from vitap_vtop_client.utils import find_captcha
from vitap_vtop_client.exceptions import VtopConnectionError, VtopCaptchaError


async def fetch_captcha(client: httpx.AsyncClient, retries: int) -> str:
    """
    Fetches the VTOP login page and extracts the base64 encoded captcha image in it.

    Args:
        client (httpx.AsyncClient): Client object for making HTTP requests.
        retries (int): Number of retries for fetching captcha.

    Returns:
        str: Base64 encoded captcha image data (excluding the data URI prefix)

    Raises:
        VtopConnectionError: If the HTTP request fails after all retries.
        VtopCaptchaError: If captcha image is not found in the response after all retries.
    """
    last_exception = None

    for attempt in range(retries):
        print(f"Fetching captcha, attempt {attempt + 1}/{retries}...")
        try:
            response = await client.get(VTOP_LOGIN_URL, headers=HEADERS)
            response.raise_for_status()

            base64_code = find_captcha.find_captcha(response.text)

            if base64_code:
                print("Captcha base64 found.")
                return base64_code
            else:
                print("Captcha base64 not found in response.")
                last_exception = VtopCaptchaError(
                    f"Captcha image not found in response on attempt {attempt + 1}.",
                    status_code=response.status_code,
                )

        except httpx.RequestError as e:
            print(f"Network error on captcha fetch attempt {attempt + 1}: {e}")
            last_exception = VtopConnectionError(
                f"Network error on captcha fetch attempt {attempt + 1}: {e}",
                original_exception=e,
                status_code=502,
            )

        except VtopCaptchaError as e:
            last_exception = e

        except Exception as e:
            print(f"Unexpected error during captcha fetch attempt {attempt + 1}: {e}")
            last_exception = VtopCaptchaError(
                f"Unexpected error during captcha fetch attempt {attempt + 1}: {e}",
                status_code=None,
            )

        if attempt < retries - 1:
            await asyncio.sleep(1)

    raise VtopCaptchaError(
        f"Failed to fetch captcha page after {retries} attempts.",
        status_code=502,
    ) from last_exception