from paddleocr import PaddleOCR
from PIL import Image
from .generic import get_assets_dir, get_project_root

import json
import cv2
import numpy as np

engine = PaddleOCR(
    use_doc_orientation_classify=False, 
    use_doc_unwarping=False, 
    use_textline_orientation=False,
)

def ocr(image: Image.Image) -> str:
    """
    Perform OCR on a PIL Image and return the detected text.
    Args:
        image (PIL.Image.Image): The image to process.
    Returns:
        str: The text detected in the image.
    """
    result = engine.predict(np.array(image.convert("RGB")))[0]
    texts, boxes = result['rec_texts'], result['rec_boxes']

    predicted = ""
    last_right_bottom_y = 0
    for text, box in zip(texts, boxes):
        if box[1] >= last_right_bottom_y - 2:
            predicted += "\n"
        predicted += text
        last_right_bottom_y = box[3]

    return predicted.strip()

def compute_descriptor(img: Image.Image) -> np.ndarray:
    """
    Compute a descriptor for an image.
    Args:
        img (PIL.Image.Image): The image to compute the descriptor for.
    Returns:
        np.ndarray: The descriptor for the image.
    """
    orb = cv2.ORB_create()
    kp, des = orb.detectAndCompute(np.array(img.convert("RGB")), None)
    return des

echo_imgs_folder = get_assets_dir() / "imgs"

with open(echo_imgs_folder / "metadata.json", "r", encoding="utf-8") as f:
    metadata = json.load(f)

img_descriptors = {}
for entry in metadata:
    img_path = echo_imgs_folder / entry["file"]
    img = Image.open(img_path)
    img_descriptors[entry["name"]] = compute_descriptor(img)

bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

def classify_echo(img: Image.Image) -> str:
    """
    Classify an image as an echo.
    Args:
        img (PIL.Image.Image): The image to classify.
    Returns:
        str: The name of the echo.
    """
    descriptor = compute_descriptor(img)
    max_matches = 0
    best_match = None
    for name, descriptor in img_descriptors.items():
        matches = bf.match(descriptor, img_descriptors[name])
        if len(matches) > max_matches:
            max_matches = len(matches)
            best_match = name
    return best_match
