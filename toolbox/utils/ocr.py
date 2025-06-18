from paddleocr import PaddleOCR
from PIL import Image
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
