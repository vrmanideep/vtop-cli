from bs4 import BeautifulSoup

from vitap_vtop_client.attendance.model.attendance_model import AttendanceModel
from vitap_vtop_client.exceptions.exception import VtopParsingError

def parse_attendance(html: str) -> list[AttendanceModel]:
    """
    Parses the HTML content of a VIT attendance table and extracts attendance details
    for each course into a list of AttendanceModels.

    Args:
        html (str): The raw HTML string containing the attendance table.

    Returns:
        list[AttendanceModel]: A list of AttendanceModels, each representing one course's attendance details.

    Raises:
        VtopParsingError: When failed to parse attendance data(usually due to unexpected html format).
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        data_list: list[AttendanceModel] = []
        
        # Locate the attendance table and get all its rows (skipping the header row)
        rows = soup.find('table', id='AttendanceDetailDataTable').find_all('tr')[1:]  # Skip header row
        
        for row in rows:
             # Get all <td> cells in the current row
            cells = row.find_all('td')

            # Extract and parse the course code, name, and type
            course_description = cells[2].get_text(strip=True)
            course_code, course_name_type = course_description.split(' - ', 1)
            course_name, course_type = course_name_type.rsplit(' - ', 1)
            
            # Extract course ID and slot from the class detail field
            class_detail = cells[3].get_text(strip=True)
            course_id = class_detail.split(' - ', 1)[0]
            course_slot = class_detail.split(' - ')[1]
            
            # Extract attendance numbers and percentages
            attended_classes = cells[5].get_text(strip=True)
            total_classes = cells[6].get_text(strip=True)
            attendance_percentage = cells[7].get_text(strip=True).rstrip('%')
            within_attendance_percentage = cells[8].get_text(strip=True).rstrip('%')
            
             # Extract debar status
            debar_status = cells[9].get_text(strip=True).rstrip('%')
            
            # Create dictionary for the current course
            course_data = {
                "course_id": course_id,
                "course_code": course_code,
                "course_name": course_name,
                "course_type": course_type,
                "course_slot": course_slot,
                "attended_classes": attended_classes,
                "total_classes": total_classes,
                "attendance_percentage": attendance_percentage,
                "within_attendance_percentage": within_attendance_percentage,
                "debar_status": debar_status
            }
            
            data_list.append(AttendanceModel(**course_data))
        
        return data_list
    except Exception as e:
       raise VtopParsingError(f"Failed to parse attendance data: {e}")
