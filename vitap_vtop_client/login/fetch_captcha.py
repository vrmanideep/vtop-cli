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
                if attempt < retries - 1:
                    print("Retrying captcha fetch...")
                    await asyncio.sleep(1)
                else:
                    raise VtopCaptchaError(
                        f"Captcha image not found in response after {retries} attempts.",
                        status_code=response.status_code
                    )

        except httpx.RequestError as e:
            
            raise VtopConnectionError(
                f"Failed to fetch captcha page after {retries} attempts.",
                original_exception=e,
                status_code=502
            )

        except VtopCaptchaError as e:
            raise e

        except Exception as e:
            print(f"An unexpected error occurred during captcha fetch attempt {attempt + 1}: {e}")
            raise VtopCaptchaError(
                    f"Unexpected error during captcha fetch after {retries} attempts: {e}",
                    status_code=getattr(getattr(e, 'response', None), 'status_code', None)
            ) from e
                

    raise RuntimeError("Unexpected flow in fetch_captcha — reached end of function unexpectedly.")
