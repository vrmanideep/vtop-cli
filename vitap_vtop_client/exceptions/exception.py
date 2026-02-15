import httpx


class VitapVtopClientError(Exception):
    """Base exception for all VITAP VTOP client errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class VtopConnectionError(VitapVtopClientError):
    """Raised for network-related errors during VTOP communication."""

    def __init__(
        self,
        message: str,
        original_exception: httpx.RequestError | None = None,
        status_code: int | None = None,
    ):
        super().__init__(message, status_code)
        self.original_exception = original_exception


class VtopLoginError(VitapVtopClientError):
    """Raised when login fails due to invalid credentials, server-side validation, etc."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopAttendanceError(VitapVtopClientError):
    """Raised when fetching attendance fails due to attendance parsing, invalid semSubId, server-side validation, etc."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopTimetableError(VitapVtopClientError):
    """Raised when fetching timetable fails due to data parsing, invalid semSubId, server-side validation, etc."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopGradeHistoryError(VitapVtopClientError):
    """Raised when fetching greades history fails due to data parsing, invalid semester id, server-side validation, etc."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopMentorError(VitapVtopClientError):
    """Raised when fetching biometric fails due to data parsing, server-side validation, etc."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopBiometricError(VitapVtopClientError):
    """Raised when fetching biometric fails due to data parsing, invalid date, server-side validation, etc."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopProfileError(VitapVtopClientError):
    """Raised when fetching biometric fails due to data parsing, server-side validation, etc."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopExamScheduleError(VitapVtopClientError):
    """Raised when fetching exam schedule fails due to data parsing, invalid semester id, server-side validation, etc."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopMarksError(VitapVtopClientError):
    """Raised when fetching marks fails due to data parsing, invalid semester id, server-side validation, etc."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopGeneralOutingError(VitapVtopClientError):
    """Raised when fetching/posting marks fails due to data parsing, invalid semester id, server-side validation, etc."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopWeekendOutingError(VitapVtopClientError):
    """Raised when fetching/posting marks fails due to data parsing, invalid semester id, server-side validation, etc."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopCaptchaError(VtopLoginError):
    """Raised for errors specifically related to CAPTCHA fetching."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopCaptchaSolvingError(VtopLoginError):
    """Raised for errors specifically related to CAPTCHA solving."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopCsrfError(VtopLoginError):
    """Raised for errors specifically related to CSRF scraping and fetching."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopParsingError(VitapVtopClientError):
    """Raised when data parsing fails unexpectedly (e.g., new HTML format)."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)


class VtopSessionError(VitapVtopClientError):
    """Raised when an operation requires an active session but one is not available or valid."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message, status_code)
