import httpx

from vitap_vtop_client.constants import HEADERS, VTOP_PRELOGIN_URL
from vitap_vtop_client.exceptions.exception import VtopConnectionError


async def pre_login(client: httpx.AsyncClient, csrf_token: str):
    """
    Sends async pre-login request to VTOP website using an async client.
    This request seems to be necessary to set session state before actual login.

    Args:
        client (httpx.AsyncClient): Async client object for making HTTP requests.
        csrf_token (str): CSRF token fetched from the initial page.

    Returns:
        None

    Raises:
         VtopConnectionError: If the pre-login request does not succeed based on response status or If the HTTP request fails.
    """
    try:
        data = {"_csrf": csrf_token, "flag": "VTOP"}
        response = await client.post(VTOP_PRELOGIN_URL, data=data, headers=HEADERS)

        if response.is_success:
            print("Pre-login successful.")
        else:
            print(f"Pre-login returned non-success status: {response.status_code}")
            raise VtopConnectionError(
                f"Pre-login failed with status {response.status_code}",
                status_code=response.status_code,
            )

    except httpx.RequestError as e:
        print(f"Pre-login request failed: {e}")
        raise VtopConnectionError(
            f"Pre-login request failed: {e}",
            original_exception=e,
            status_code=502,
        )

    except VtopConnectionError:
        raise

    except Exception as e:
        print(f"Pre-login failed unexpectedly: {e}")
        raise VtopConnectionError(f"Pre-login failed unexpectedly: {e}") from e