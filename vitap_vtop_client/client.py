from typing import List
import httpx
import asyncio
import json
import os

from .constants import VTOP_BASE_URL

from .exceptions import (
    VtopLoginError,
    VtopCaptchaError,
    VtopCaptchaSolvingError,
    VtopConnectionError,
    VtopSessionError,
    VitapVtopClientError,
)

from .login import (
    fetch_csrf_token,
    pre_login,
    fetch_captcha,
    student_login,
    LoggedInStudent,
)

from .utils import solve_captcha


class VtopClient:
    """
    An asynchronous client for interacting with the VIT-AP VTOP portal.
    Includes session persistence to bypass CAPTCHA and 2FA on subsequent runs.
    """

    def __init__(
        self,
        registration_number: str,
        password: str,
        max_login_retries: int = 3,
        captcha_retries: int = 5,
    ):
        if not registration_number or not password:
            raise VtopLoginError(
                "Registration number and password are required.",
                status_code=400,
            )

        self.username = registration_number.upper()
        self.password = password
        self.max_login_retries = max_login_retries
        self.captcha_retries = captcha_retries
        self._logged_in_student: LoggedInStudent | None = None
        self._login_lock = asyncio.Lock()

        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            base_url=VTOP_BASE_URL,
            verify=False,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                "Connection": "keep-alive",
            },
        )
        
        # Automatically load saved session cookies on startup
        self._load_session()

    def _save_session(self):
        """Saves the current httpx cookies to a local file, handling duplicate names safely."""
        try:
            cookie_data = []
            # Dig into the underlying CookieJar to avoid the dictionary key collision
            for cookie in self._client.cookies.jar:
                cookie_data.append({
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                })
                
            with open("vtop_session.json", "w") as f:
                json.dump(cookie_data, f, indent=4)
                
        except Exception as e:
            print(f"VtopClient: Failed to save session cookies: {e}")

    def _load_session(self):
        """Loads saved cookies from file into the httpx client."""
        if os.path.exists("vtop_session.json"):
            try:
                with open("vtop_session.json", "r") as f:
                    cookie_data = json.load(f)
                    # Reconstruct the cookies with their specific domains and paths
                    for c in cookie_data:
                        self._client.cookies.set(
                            c["name"], 
                            c["value"], 
                            domain=c["domain"], 
                            path=c["path"]
                        )
            except Exception as e:
                print(f"VtopClient: Failed to load session cookies: {e}")

    def _load_session(self):
        """Loads saved cookies from file into the httpx client."""
        if os.path.exists("vtop_session.json"):
            try:
                with open("vtop_session.json", "r") as f:
                    cookies = json.load(f)
                    self._client.cookies.update(cookies)
            except Exception:
                pass

    async def _perform_login_sequence(self) -> LoggedInStudent:
        """
        Handles the complete login sequence including fetching tokens, solving CAPTCHA, and 2FA.
        """
        for attempt in range(self.max_login_retries):
            print(
                f"VtopClient: Login attempt {attempt + 1}/{self.max_login_retries} for user {self.username[:5]}****"
            )
            try:
                csrf_token = await fetch_csrf_token(self._client)
                print(f"VtopClient: CSRF TOKEN: {csrf_token[:8]} - **** - **** - ************")

                await pre_login(self._client, csrf_token)

                captcha_base64 = await fetch_captcha(self._client, retries=self.captcha_retries)
                captcha_value = await asyncio.to_thread(solve_captcha, captcha_base64)
                print(f"VtopClient: Solved captcha: {captcha_value}")

                logged_in_student = await student_login(
                    self._client,
                    csrf_token,
                    self.username,
                    self.password,
                    captcha_value,
                )
                self._logged_in_student = logged_in_student
                
                # --- Save the trusted session to disk after successful login/2FA ---
                self._save_session()
                
                print(f"VtopClient: Login successful for {self.username[:5]}****")
                return logged_in_student

            except VtopCaptchaError as e:
                print(f"VtopClient: Captcha error during login: {e}")
                if attempt == self.max_login_retries - 1:
                    raise
                await asyncio.sleep(1)

            except VtopCaptchaSolvingError as e:
                print(f"VtopClient: Captcha solving failed during login: {e}")
                if attempt == self.captcha_retries - 1:
                    raise
                await asyncio.sleep(1)

            except VtopLoginError as e:
                print(f"VtopClient: Login failed due to invalid credentials or format: {e}")
                raise

            except VtopConnectionError as e:
                raise

            except VtopSessionError as e:
                print(f"Session error (e.g., CSRF/session expired): {e}")
                raise

            except Exception as e:
                print(f"VtopClient: Unexpected error during login: {e}")
                if attempt == self.max_login_retries - 1:
                    raise VitapVtopClientError(
                        f"Login failed after {self.max_login_retries} attempts due to unexpected error: {e}"
                    )
                await asyncio.sleep(attempt + 1)

        raise VitapVtopClientError(
            f"Login failed for user {self.username} after {self.max_login_retries} attempts."
        )

    async def _ensure_logged_in(self) -> LoggedInStudent:
        """
        Ensures the client is logged in. Tests saved cookies first, 
        and falls back to a fresh login sequence if they are expired.
        """
        if self._logged_in_student is not None:
            return self._logged_in_student

        async with self._login_lock:
            # 1. Test the saved session (if cookies exist)
            if self._client.cookies:
                try:
                    from vitap_vtop_client.constants import HEADERS, VTOP_CONTENT_URL
                    from vitap_vtop_client.utils.find_registration_number import find_registration_number
                    from vitap_vtop_client.utils import find_csrf

                    print("VtopClient: Found saved session. Validating with VTOP...")
                    test_resp = await self._client.get(VTOP_CONTENT_URL, headers=HEADERS)

                    if "Dashboard" in test_resp.text or "StudentProfile" in test_resp.text:
                        # Session is valid! Extract the fresh CSRF token and we are done.
                        reg_num = find_registration_number(test_resp)
                        post_login_csrf = find_csrf(test_resp.text)
                        
                        self._logged_in_student = LoggedInStudent(
                            registration_number=reg_num,
                            post_login_csrf_token=post_login_csrf
                        )
                        print(f"VtopClient: Saved session restored seamlessly for {reg_num[:5]}****")
                        return self._logged_in_student
                    else:
                        print("VtopClient: Saved session expired. Proceeding to fresh login.")
                        self._client.cookies.clear() # Wipe the dead cookies
                        
                except Exception as e:
                    print(f"VtopClient: Session validation failed ({e}). Proceeding to fresh login.")
                    self._client.cookies.clear()

            # 2. Proceed to fresh login sequence if cookies were dead or missing
            if self._logged_in_student is None:
                print(f"VtopClient: Not logged in for {self.username[:5]}****. Initiating login.")
                await self._perform_login_sequence()

            if self._logged_in_student is None:
                raise VitapVtopClientError("VtopClient: Failed to establish a login session.")

            return self._logged_in_student

    async def close(self):
        """
        Closes the underlying HTTP client.
        """
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

        