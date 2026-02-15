from bs4 import BeautifulSoup
from vitap_vtop_client.biometric.model.biometric_model import BiometricModel
from vitap_vtop_client.exceptions.exception import VtopParsingError

def parse_biometric(html: str) -> list[BiometricModel]:
    """
    Parses the HTML content of the VIT biometric logs table and extracts each log
    into a list of dictionaries with time and location details.

    Args:
        html (str): The raw HTML string containing the biometric log table.

    Returns:
        list: A list of dictionaries, each representing a biometric log with timestamp, time, and location.
    
    Raises:
        VtopParsingError: If parsing fails due to malformed HTML or unexpected structure.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        bio_data = soup.find_all('td')  # Flattened list of all <td> elements

        biometric_logs: list[BiometricModel] = []  # Final list to hold each log entry as a dictionary

        # Biometric log data is grouped in sets of 4 <td> tags per entry
        for i in range(4, len(bio_data), 4):  # Skip header or non-data cells (start at index 4)
            biometric_log = {
                "time": bio_data[i + 2].get_text(strip=True),
                "location": bio_data[i + 3].get_text(strip=True).replace(' ', '')
            }
            biometric_logs.append(BiometricModel(**biometric_log)) 

        return biometric_logs

    except Exception as e:
        raise VtopParsingError(f"Failed to parse biometric data: {e}")
