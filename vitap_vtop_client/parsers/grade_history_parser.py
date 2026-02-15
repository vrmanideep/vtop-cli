from bs4 import BeautifulSoup

from vitap_vtop_client.exceptions import VtopParsingError
from vitap_vtop_client.grade_history.model import GradeHistoryModel


def parse_grade_history(html: str) -> GradeHistoryModel:
    try:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", {"class": "table table-hover table-bordered"})

        # Check if the main table exists
        if not table:
            print("Grade history table not found, returning empty grade history")
            return GradeHistoryModel()
        
        tbody = table.find("tbody")
        if not tbody:
            print("Grade history tbody not found, returning empty grade history")
            return GradeHistoryModel()
        
        data_row = tbody.find("tr")
        if not data_row:
            print("Grade history data row not found, returning empty grade history")
            return GradeHistoryModel()

        # Extract the specific data points
        columns = data_row.find_all("td")
        if len(columns) < 3:
            print(
                "Insufficient grade history columns found, returning empty grade history"
            )
            return GradeHistoryModel()

        grades: dict[str, str] = {
            "credits_registered": columns[0].get_text(strip=True),
            "credits_earned": columns[1].get_text(strip=True),
            "cgpa": columns[2].get_text(strip=True),
        }

        return GradeHistoryModel(**grades)

    except Exception as e:
        print(f"Error parsing grade history: {str(e)}")
        raise VtopParsingError(f"An error occured while parsing grade history: {e}")
