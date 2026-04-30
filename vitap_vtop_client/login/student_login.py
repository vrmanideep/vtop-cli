import httpx
import json
import os
import asyncio
from bs4 import BeautifulSoup

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


async def student_login(
    client: httpx.AsyncClient,
    csrf_token: str,
    registration_number: str,
    password: str,
    captcha_value: str,
) -> LoggedInStudent:
    """
    Attempts to log in to the VTOP system using provided credentials and captcha.
    Handles standard login, error redirects, and Two-Factor Authentication (OTP).

    Args:
        client (httpx.AsyncClient): Async client object for making HTTP requests.
        csrf_token (str): Cross-Site Request Forgery token required for the login request (from pre-login).
        registration_number (str): Student Registration Number for logging in.
        password (str): VTOP Password for logging in.
        captcha_value (str): Value of the CAPTCHA image solved by the solver.

    Returns:
        LoggedInStudent: A model containing login success status and the post-login CSRF token.

    Raises:
        VtopConnectionError: If a network-related issue occurs during the POST request.
        VtopLoginError: If login fails due to invalid credentials, unexpected redirects, or OTP failures.
        VtopCaptchaSolvingError: If login fails due to an invalid captcha.
    """
    try:
        data = {
            "_csrf": csrf_token,
            "username": registration_number,
            "password": password,
            "captchaStr": captcha_value,
        }
        response = await client.post(VTOP_LOGIN_URL, data=data, headers=HEADERS)

        # 1. Standard Success (No 2FA required)
        if response.url == VTOP_BASE_URL + VTOP_CONTENT_URL:
            print(f"Login successful for user {registration_number[:5]}****. Redirected to content page.")
            content_resp = await client.get(VTOP_CONTENT_URL, headers=HEADERS)

            reg_num = find_registration_number(content_resp)
            post_login_csrf = find_csrf(content_resp.text)
            
            return LoggedInStudent(
                registration_number=reg_num,
                post_login_csrf_token=post_login_csrf,
            )

        # 2. OTP 2FA Check (Intercepting the pending state)
        elif "var securityOtpPending = true;" in response.text:
            print(f"\n   [!] VTOP has requested Two-Factor Authentication for {registration_number}.")
            print("   [!] An OTP has been sent to your registered email.")
            
            # Extract the specific CSRF token for the OTP form
            soup = BeautifulSoup(response.text, 'html.parser')
            otp_form = soup.find('form', id='securityOtpForm')
            if otp_form and otp_form.find('input', {'name': '_csrf'}):
                otp_csrf = otp_form.find('input', {'name': '_csrf'})['value']
            else:
                otp_csrf = csrf_token

            # Safely prompt the user for the OTP without blocking the async event loop
            otp_code = await asyncio.to_thread(input, "   [>] Enter the 6-digit OTP: ")
            otp_code = otp_code.strip()

            # Submit the OTP
            otp_url = f"{VTOP_BASE_URL}/vtop/validateSecurityOtp"
            otp_data = {
                "otpCode": otp_code,
                "_csrf": otp_csrf
            }
            
            otp_headers = HEADERS.copy()
            otp_headers["X-Requested-With"] = "XMLHttpRequest" # Required for VTOP AJAX
            otp_headers["Referer"] = str(response.url)

            print("   [.] Verifying OTP...")
            otp_response = await client.post(otp_url, data=otp_data, headers=otp_headers)

            try:
                result = otp_response.json()
                
                if result.get("status") == "SUCCESS" and result.get("redirectUrl"):
                    redirect_url = result.get("redirectUrl")
                    if redirect_url.startswith("/"):
                        redirect_url = VTOP_BASE_URL + redirect_url
                        
                    # Follow the redirect to finalize the session
                    content_resp = await client.get(redirect_url, headers=HEADERS)
                    
                    reg_num = find_registration_number(content_resp)
                    post_login_csrf = find_csrf(content_resp.text)
                    
                    print("   [✓] OTP Verified Successfully!")
                    return LoggedInStudent(
                        registration_number=reg_num,
                        post_login_csrf_token=post_login_csrf,
                    )
                    
                elif result.get("status") in ["INVALID", "EXPIRED"]:
                    error_msg = result.get("message", "Invalid or Expired OTP.")
                    raise VtopLoginError(f"OTP Verification Failed: {error_msg}", status_code=401)
                else:
                    raise VtopLoginError(f"OTP Error: {result.get('message', 'Unknown Error')}", status_code=400)
                    
            except json.JSONDecodeError:
                raise VtopLoginError("Failed to parse OTP validation response from VTOP.", status_code=500)

        # 3. Standard Login Failure (Wrong password/captcha)
        elif response.url == VTOP_BASE_URL + VTOP_LOGIN_ERROR_URL:
            error_message = find_login_response.login_error_identifier(response.text)
            print(f"Login Credential Error: {error_message}")
            if error_message == "Invalid Captcha":
                raise VtopCaptchaSolvingError(f"{error_message}", status_code=401)
            else:
                raise VtopLoginError(f"{error_message}", status_code=401)

        # 4. Unknown State
        else:
            print(f"Login failed for user {registration_number}. Unexpected redirection to {response.url}. Status: {response.status_code}")
            raise VtopLoginError(
                f"Login failed: Unexpected redirection after POST to {response.url}",
                status_code=response.status_code,
            )

    except httpx.RequestError as e:
        print(f"Login POST request failed: Network Error {e}")
        raise VtopConnectionError(
            f"Login request failed: {e}", original_exception=e, status_code=502
        )
    except (VtopLoginError, VtopCaptchaSolvingError) as e:
        raise e
    except Exception as e:
        print(f"An unexpected error occurred during login process: {e}")
        raise VtopLoginError(f"An unexpected error occurred during login: {e}") from e