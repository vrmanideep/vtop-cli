from bs4 import BeautifulSoup

def find_registration_number(html: str)  -> str | None:
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.select_one('input[type="hidden"][name="authorizedIDX"]')
    if element:
        value = element.get('value')
        return  value
    return None

