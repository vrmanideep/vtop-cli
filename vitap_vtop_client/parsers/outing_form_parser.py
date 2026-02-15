from bs4 import BeautifulSoup
from vitap_vtop_client.exceptions.exception import VtopParsingError
from vitap_vtop_client.outing.model.outing_info_model import OutingInfoModel


def parse_outing_form(html_content: str) -> OutingInfoModel:
    soup = BeautifulSoup(html_content, "html.parser")
    try:
        outing_info = OutingInfoModel(
            registration_number=soup.find("input", {"id": "regNo"})["value"],
            name=soup.find("input", {"id": "name"})["value"],
            application_no=soup.find("input", {"id": "applicationNo"})["value"],
            gender=soup.find("input", {"id": "gender"})["value"],
            hostel_block=soup.find("input", {"id": "hostelBlock"})["value"],
            room_number=soup.find("input", {"id": "roomNo"})["value"],
            parent_contact_number=soup.find("input", {"id": "parentContactNumber"})[
                "value"
            ],
        )
    except Exception as e:
        print(f"Error parsing outing form information: {e}")
        raise VtopParsingError(f"Error parsing outing form information: {e}")

    return outing_info
