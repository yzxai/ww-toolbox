from paddleocr import PaddleOCR
from PIL import Image
from dataclasses import dataclass

import re
import numpy as np

engine = None

def setup_ocr():
    global engine
    engine = PaddleOCR(
        use_doc_orientation_classify=False, 
        use_doc_unwarping=False, 
        use_textline_orientation=False,
    )

@dataclass
class OCRResult:
    text: str
    box: tuple[int, int, int, int]
    confidence: float

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

def ocr_pattern(image: Image.Image, pattern: str) -> list[OCRResult]:
    """
    Perform OCR on a PIL Image and return the detected texts with their boxes and confidence scores.
    Args:
        image (PIL.Image.Image): The image to process.
    Returns:
        list[OCRResult]: The detected texts with their boxes and confidence scores.
    """

    # ensure pattern is a legal regex pattern
    try:
        re.compile(pattern)
    except re.error:
        raise ValueError(f'Invalid pattern: {pattern}')

    result = engine.predict(np.array(image.convert("RGB")))[0]
    texts, boxes, scores = result['rec_texts'], result['rec_boxes'], result['rec_scores']

    results = []
    for text, box, score in zip(texts, boxes, scores):
        if re.search(pattern, text):
            matched_text = re.search(pattern, text).group(0)
            results.append(OCRResult(matched_text, box, score))

    return results

