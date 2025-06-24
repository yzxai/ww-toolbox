from rapidocr import RapidOCR, EngineType
from PIL import Image, ImageFilter
from dataclasses import dataclass

import re
import numpy as np

engine = None

def setup_ocr():
    global engine
    engine = RapidOCR(
        params={
            "Det.engine_type": EngineType.OPENVINO,
            "Cls.engine_type": EngineType.OPENVINO,
            "Rec.engine_type": EngineType.OPENVINO,
        }
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
    image = image.convert("L").convert("RGB").filter(ImageFilter.SHARPEN)
    result = engine(np.array(image))
    texts, boxes = result.txts, result.boxes

    predicted = ""
    last_right_bottom_y = 0
    for text, box in zip(texts, boxes):
        if box[0][1] >= last_right_bottom_y - 2:
            predicted += "\n"
        predicted += text + ' '
        last_right_bottom_y = box[2][1]

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

    image = image.convert("L").convert("RGB").filter(ImageFilter.SHARPEN)
    result = engine(np.array(image))
    texts, boxes, scores = result.txts, result.boxes, result.scores

    results = []
    for text, box, score in zip(texts, boxes, scores):
        if re.search(pattern, text):
            matched_text = re.search(pattern, text).group(0)
            results.append(OCRResult(matched_text, (box[0][0], box[0][1], box[2][0], box[2][1]), score))

    return results

if __name__ == "__main__":
    setup_ocr()
    img = Image.open("test.png")
    img.show()
    img.filter(ImageFilter.SHARPEN).convert("L").convert("RGB").show()
    print(ocr(img))
    print(ocr_pattern(img, "\d+\.?\d*%"))
