from typing import List
import httpx
import asyncio

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

    async def _perform_login_sequence(self) -> LoggedInStudent:
        """
        Handles the complete login sequence.
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
        Ensures the client is logged in. If not, performs login.
        """
        if self._logged_in_student is not None:
            return self._logged_in_student

        async with self._login_lock:
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