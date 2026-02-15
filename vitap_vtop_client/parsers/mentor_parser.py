from bs4 import BeautifulSoup

from vitap_vtop_client.exceptions.exception import VtopParsingError
from vitap_vtop_client.mentor.model import MentorModel

def parse_mentor_details(html) -> MentorModel:
    soup = BeautifulSoup(html, "html.parser")

    # Initialize the main dictionary
    mentor_details = {}

    # Temporary dictionary for collecting data
    temp_dict = {
        'faculty_id': None,
        'faculty_name': None,
        'faculty_designation': None,
        'school': None,
        'cabin': None,
        'faculty_department': None,
        'faculty_email': None,
        'faculty_intercom': None,
        'faculty_mobile_number': None
    }
    
    try:
        # Find the relevant table or structure
        rows = soup.find_all('tr')
        for row in rows:
            columns = row.find_all('td')
            values = [cell.get_text().strip() for cell in columns]

            if len(values) < 2:
                continue

            # Map values to the corresponding keys in temp_dict
            if 'Faculty ID' in values:
                temp_dict['faculty_id'] = values[1]
            elif 'Faculty Name' in values:
                temp_dict['faculty_name'] = values[1]
            elif 'Faculty Designation' in values:
                temp_dict['faculty_designation'] = values[1]
            elif 'School' in values:
                temp_dict['school'] = values[1]
            elif 'Cabin' in values:
                temp_dict['cabin'] = values[1]
            elif 'Faculty Department' in values:
                temp_dict['faculty_department'] = values[1]
            elif 'Faculty Email' in values:
                temp_dict['faculty_email'] = values[1]
            elif 'Faculty intercom' in values:
                temp_dict['faculty_intercom'] = values[1]
            elif 'Faculty Mobile Number' in values:
                temp_dict['faculty_mobile_number'] = values[1]

        # Construct the final dictionary from the temporary one
        mentor_details = {key: value for key, value in temp_dict.items() if value is not None}
        return MentorModel(**mentor_details)
    
    except Exception as e:
       raise VtopParsingError(f"An error occured while parsing Mentor Details: {e}")
