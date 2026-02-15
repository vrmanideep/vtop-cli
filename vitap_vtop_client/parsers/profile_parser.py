from bs4 import BeautifulSoup
from vitap_vtop_client.exceptions import VtopParsingError
from vitap_vtop_client.profile.model import StudentProfileModel
from vitap_vtop_client.utils import extract_pfp_base64

def parse_student_profile(html: str) -> StudentProfileModel :
    """
    Parses the HTML content of the student profile data

    Args:
        html (str): The raw HTML string containing the student profile data.

    Returns:
        list: A list of dictionaries, each representing a biometric log with timestamp, time, and location.
    
    Raises:
        VtopParsingError: If parsing fails due to malformed HTML or unexpected structure.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        user_data = soup.find_all('td')

        profile_data = {
            "base64_pfp": extract_pfp_base64(html),
        }

        for i in range(len(user_data)):
            text = user_data[i].get_text().strip()
            if text == "APPLICATION NUMBER":
                profile_data["application_number"] = user_data[i+1].get_text().strip()
            elif text == "STUDENT NAME":
                profile_data["student_name"] = user_data[i+1].get_text().strip()
            elif text == "DATE OF BIRTH":
                profile_data["dob"] = user_data[i+1].get_text().strip()
            elif text == "GENDER":
                profile_data["gender"] = user_data[i+1].get_text().strip()
            elif text == "BLOOD GROUP":
                profile_data["blood_group"] = user_data[i+1].get_text().strip()
            elif text == "EMAIL":
                profile_data["email"] = user_data[i+1].get_text().strip()

        return StudentProfileModel(**profile_data, grade_history=None,mentor_details=None)

    except Exception as e:
        raise VtopParsingError(f"Failed to parse biometric data: {e}")
