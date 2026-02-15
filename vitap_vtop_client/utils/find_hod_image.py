import re


def find_hod_image(html : str) -> str | None:
    """
    Finds and returns the base64 code of the HOD or Dean's profile photo from HTML content.

    Args:
        html (str): The HTML content to search for the captcha.

    Returns:
        str: The base64 code of the HOD or Dean's profile photo if found, otherwise None.
    """
    pattern = r'data:JPEG;base64,([^"]+)'
    match=re.search(pattern, html)
    if match:
        return match.group(1)
    else:
        print('Unable to find HOD\'s profile photo')
        return None