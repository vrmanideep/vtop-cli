import base64
import io
import json
import numpy as np
from PIL import Image
import importlib.resources

from vitap_vtop_client.exceptions.exception import VtopCaptchaError

try:
    weights_data_str = importlib.resources.read_text('vitap_vtop_client.resources', 'weights.json')
    model_config = json.loads(weights_data_str)
    weights = np.array(model_config.get("weights"))
    biases = np.array(model_config.get("biases"))
except FileNotFoundError:
    print("Error: weights.json not found in package data.")
except json.JSONDecodeError:
    print("Error: weights.json is not valid JSON.")
except Exception as e:
    print(f"Error loading captcha weights.json: {e}")


def partition_img(img: np.ndarray) -> list[np.ndarray]:
    """Partitions the captcha image into 6 character images."""
    parts = []
    try:
        for i in range(6):
            x1 = (i + 1) * 25 + 2
            y1 = 7 + 5 * (i % 2) + 1
            x2 = (i + 2) * 25 + 1
            y2 = 35 - 5 * ((i + 1) % 2)
            part = img[y1:y2, x1:x2]
            parts.append(part)
        return parts
    except Exception as e:
        print(f"Error during captcha image partitioning: {e}")
        raise ValueError(f"Failed to partition captcha image: {e}") from e


def convert_to_abs_bw(img: np.ndarray) -> np.ndarray:
    """Converts an image part to absolute black and white based on average pixel value."""
    if img.size == 0:
        raise ValueError("Cannot process empty image part.")
    avg = np.sum(img)
    avg /= 24 * 22
    return np.where(img > avg, 0, 1)

def solve_captcha_ml(img: list[np.ndarray]) -> str:
    LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    captcha = ""
    for single_letter in img:
        dw_img = convert_to_abs_bw(single_letter)
        dw_img = dw_img.flatten()
        x = np.dot(dw_img, weights) + biases
        x = np.exp(x)
        captcha += LETTERS[np.argmax(x)]
    if len(captcha) != 6:
        print(f"Warning: Captcha solving resulted in unexpected output: {captcha}")
        raise VtopCaptchaError(f"Warning: Captcha solving resulted in unexpected output: {captcha}")
    return captcha

def solve_captcha(captcha_base64: str) -> str:
    """
    Solves the given base64 encoded captcha image using the loaded ML model.

    Args:
        captcha_base64 (str): Base64 encoded captcha image data (excluding prefix).

    Returns:
        str: The predicted captcha text.
    """
    try:
        img = _str_to_img(captcha_base64)
        # Optional: Apply convert_to_abs_bw here
        # img = convert_to_abs_bw(img)
        parts = partition_img(img)
        return solve_captcha_ml(parts)

    except VtopCaptchaError as e:
        raise e

    except Exception as e:
        print(f"An unexpected error occurred during captcha solving: {e}")
        raise VtopCaptchaError(f"An unexpected error occurred during captcha solving: {e}")


def _str_to_img(src: str) -> np.ndarray:
    """Decodes base64 string to a grayscale NumPy array."""
    try:
        im = base64.b64decode(src)
        img = Image.open(io.BytesIO(im)).convert("L")
        img = np.array(img)
        return img
    except Exception as e:
        print(f"Error decoding base64 to image: {e}")
        raise ValueError(f"Failed to decode base64 to image: {e}") from e