import re

def find_csrf(html: str) -> str | None: # Returns str or None
    """
    Finds and returns the CSRF token from HTML content.

    Args:
        html (str): The HTML content to search for the CSRF token.

    Returns:
        str or None: The CSRF token if found, otherwise None.
    """
    pattern = r'<input type="hidden" name="_csrf" value="([0-9a-f-]+)"'
    match = re.search(pattern, html)
    if match:
        return match.group(1)
    else:
        return None