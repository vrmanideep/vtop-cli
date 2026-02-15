from bs4 import BeautifulSoup
from vitap_vtop_client.attendance.model.attendance_model import AttendanceModel
from vitap_vtop_client.exceptions.exception import VtopParsingError

def parse_attendance(html: str) -> list[AttendanceModel]:
    """
    Parses the HTML content of a VIT attendance table and extracts attendance details
    INCLUDING FACULTY NAME for each course.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        data_list: list[AttendanceModel] = []
        
        # Locate the attendance table
        table = soup.find('table', id='AttendanceDetailDataTable')
        if not table:
            return [] # Return empty if table doesn't exist

        rows = table.find_all('tr')[1:]  # Skip header row
        
        for row in rows:
            cells = row.find_all('td')

            # --- 1. Course Details ---
            course_description = cells[2].get_text(strip=True)
            # Handle cases where splitting might fail
            if ' - ' in course_description:
                course_code, course_name_type = course_description.split(' - ', 1)
                course_name, course_type = course_name_type.rsplit(' - ', 1)
            else:
                course_code, course_name, course_type = "N/A", course_description, "N/A"
            
            # --- 2. Class ID & Slot ---
            class_detail = cells[3].get_text(strip=True)
            if ' - ' in class_detail:
                course_id = class_detail.split(' - ', 1)[0]
                course_slot = class_detail.split(' - ')[1]
            else:
                course_id, course_slot = class_detail, "N/A"
            
            # --- 3. FACULTY NAME (The Missing Piece!) ---
            # The original code skipped cell[4], which is where the faculty name lives.
            faculty_name = cells[4].get_text(strip=True)
            
            # --- 4. Stats ---
            attended_classes = cells[5].get_text(strip=True)
            total_classes = cells[6].get_text(strip=True)
            attendance_percentage = cells[7].get_text(strip=True).rstrip('%')
            within_attendance_percentage = cells[8].get_text(strip=True).rstrip('%')
            debar_status = cells[9].get_text(strip=True).rstrip('%')
            
            course_data = {
                "course_id": course_id,
                "course_code": course_code,
                "course_name": course_name,
                "course_type": course_type,
                "course_slot": course_slot,
                "faculty_name": faculty_name,
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