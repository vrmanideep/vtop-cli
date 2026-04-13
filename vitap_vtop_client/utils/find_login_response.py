from bs4 import BeautifulSoup


def login_error_identifier(html : str) -> str | None:
    """
    Extracts the login error message from HTML content.

    Args:
        html (str): The HTML content containing the login page.

    Returns:
        str or None: The extracted login error message if found, otherwise None.
    """
    try:
        soup = BeautifulSoup(html, 'html.parser')
        err_msg = soup.find('strong')
        
        if err_msg:
            # Return the text content of the error message
            return err_msg.get_text(strip=True)
        else:
            return None
    
    except Exception as e:
        print(f"Warning: Error parsing login response HTML: {e}")
        return None