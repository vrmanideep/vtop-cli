import re
from vitap_vtop_client.exceptions.exception import VtopLoginError

# Right now  this client supports users with only this registation_number format
def validate_registration_number(registration_number: str):
    # Pattern: 2 digits + 3 letters (case-insensitive) + 1 or more digits
    pattern = r"^\d{2}[A-Za-z]{3}\d+$"

    if not re.fullmatch(pattern, registration_number):
        raise VtopLoginError(
            "Invalid registration number format.", status_code=400
        )
