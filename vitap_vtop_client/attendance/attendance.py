import httpx
import time
from datetime import datetime, timezone
from vitap_vtop_client.attendance.model.attendance_model import AttendanceModel
from vitap_vtop_client.exceptions.exception import VtopAttendanceError, VtopConnectionError, VtopParsingError
from vitap_vtop_client.parsers import attendance_parser
from vitap_vtop_client.constants import VIEW_ATTENDANCE_URL, ATTENDANCE_URL, HEADERS

async def fetch_attendance(
    client: httpx.AsyncClient,
    registration_number: str,
    semSubID: str,
    csrf_token: str
) -> list[AttendanceModel]:
    """
    Retrieves the attendance details for a specific user and semester subject.

    Parameters:
        client (httpx.AsyncClient): The active httpx async client.
        registration_number (str): The registration_number of the student.
        semSubID (str): The identifier for the semester subject.
        csrf_token (str): The CSRF token.

    Returns:
        list[AttendanceModel]: A list containing the parsed attendance data.

    Raises:
        VtopConnectionError: If an HTTP request fails.
        VtopAttendanceError: If the initial POST or the attendance data request fails or returns unexpected content.
        VtopParsingError: For parsing errors.
    """
    try:
        # First POST to verify menu/session
        data_initial = {
            "verifyMenu": "true",
            "authorizedID": registration_number,
            "_csrf": csrf_token,
            "nocache": int(round(time.time() * 1000)),
        }
        # Use await client.post
        initial_response = await client.post(ATTENDANCE_URL, data=data_initial, headers=HEADERS)
        initial_response.raise_for_status() # Raise exception for bad status codes

        # Check if the initial POST was successful in setting up the page context
        # This might involve checking the response content or status,
        # but raise_for_status is a good start for HTTP errors.
        # More specific checks might be needed based on VTOP's responses.
    
    except httpx.RequestError as e:
        print(f"Attendance initial POST failed: {e}")
        raise VtopConnectionError(
                f"Failed to initialize attendance page: {e}",
                original_exception=e,
                status_code=502
            )
    except Exception as e:
         print(f"An unexpected error occurred during attendance initial POST: {e}")
         raise VtopAttendanceError(f"Failed to initialize attendance page: {e}") from e

    try:
        # Second POST to fetch attendance data
        data_fetch = {
            "_csrf": csrf_token,
            "semesterSubId": semSubID,
            "authorizedID": registration_number,
            "x": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
        }
        attendance_response = await client.post(VIEW_ATTENDANCE_URL, data=data_fetch, headers=HEADERS)
        attendance_response.raise_for_status() # Raise exception for bad status codes

        # Parse the HTML content
        parsed_data = attendance_parser.parse_attendance(attendance_response.text)

        return parsed_data
    
    except VtopParsingError as e:
        raise e

    except httpx.RequestError as e:
        print(f"Attendance data fetch failed: {e}")
        raise VtopConnectionError(
                f"Failed to fetch attendance data: {e}",
                original_exception=e,
                status_code=502
            )
    except Exception as e:
        print(f"An unexpected error occurred while fetching or parsing attendance: {e}")
        raise VtopAttendanceError(f"An unexpected error occurred while fetching attendance for semester {semSubID}: {e}") from e