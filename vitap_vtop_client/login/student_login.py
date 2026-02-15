import httpx
from vitap_vtop_client.constants import (
    VTOP_BASE_URL,
    VTOP_LOGIN_ERROR_URL,
    VTOP_LOGIN_URL,
    VTOP_CONTENT_URL,
    HEADERS,
)
from vitap_vtop_client.exceptions.exception import (
    VtopCaptchaSolvingError,
    VtopConnectionError,
    VtopLoginError,
)
from vitap_vtop_client.login.model.logged_in_student_model import LoggedInStudent
from vitap_vtop_client.utils import find_login_response
from vitap_vtop_client.utils import find_csrf
from vitap_vtop_client.utils.find_registration_number import find_registration_number


# TODO: Implement retry mechanism for Captch Failures
async def student_login(
    client: httpx.AsyncClient,
    csrf_token: str,
    registration_number: str,
    password: str,
    captcha_value: str,
) -> LoggedInStudent:
    """
    Attempts to log in to the VTOP system using provided credentials and captcha.

    Args:
        client (httpx.AsyncClient): Async client object for making HTTP requests.
        csrf_token (str): Cross-Site Request Forgery token required for the login request (from pre-login).
        registration_number (str): Student Registration Number for logging in.
        password (str): VTOP Password for logging in.
        captcha_value (str): Value of the CAPTCHA image solved by the solver.

    Returns:
        dict: A dictionary containing login success status and potentially the
              post-login CSRF token. Example: {"success": True, "message": "Logged in", "post_login_csrf": "..."}

    Raises:
        httpx.RequestError: If a network-related issue occurs during the POST request.
        ValueError: If login fails due to invalid credentials or captcha.
        RuntimeError: If the login succeeds but the expected post-login page or CSRF is not found.
        Exception: For other unexpected issues.
    """
    try:
        data = {
            "_csrf": csrf_token,
            "username": registration_number,
            "password": password,
            "captchaStr": captcha_value,
        }
        response = await client.post(VTOP_LOGIN_URL, data=data, headers=HEADERS)

        if response.url == VTOP_BASE_URL + VTOP_CONTENT_URL:

            print(
                f"Login successful for user {registration_number[:5]}****. Redirected to content page."
            )
            # After successful login, we need to get the new CSRF token from the content page
            # for subsequent requests.
            content_resp = await client.get(VTOP_CONTENT_URL, headers=HEADERS)

            # This should'nt be null
            registration_number = find_registration_number(content_resp)
            print(f"registration number is {registration_number[:5]}****")
            post_login_csrf = find_csrf(content_resp.text)
            logged_in_student = {
                "registration_number": registration_number,
                "post_login_csrf_token": post_login_csrf,
            }
            return LoggedInStudent(**logged_in_student)

        elif response.url == VTOP_BASE_URL + VTOP_LOGIN_ERROR_URL:
            error_message = find_login_response.login_error_identifier(response.text)
            print(f"Login Credential Error: {error_message}")
            if error_message == "Invalid Captcha":
                raise VtopCaptchaSolvingError(f"{error_message}", status_code=401)
            else:
                raise VtopLoginError(f"{error_message}", status_code=401)

        else:
            # Landed on an unexpected page after login POST
            print(
                f"Login failed for user {registration_number}. Unexpected redirection to {response.url}. Status: {response.status_code}"
            )
            raise VtopLoginError(
                f"Login failed: Unexpected redirection after POST to {response.url}",
                status_code=response.status_code,
            )

    except httpx.RequestError as e:
        print(f"Login POST request failed: Network Error {e}")
        raise VtopConnectionError(
            f"Login request failed: {e}", original_exception=e, status_code=502
        )
    except VtopLoginError as e:
        raise e

    except Exception as e:
        print(f"An unexpected error occurred during login process: {e}")
        raise VtopLoginError(f"An unexpected error occurred during login: {e}") from e
