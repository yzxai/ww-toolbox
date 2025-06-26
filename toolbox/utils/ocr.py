from rapidocr import RapidOCR, EngineType
from PIL import Image, ImageFilter, ImageEnhance
from dataclasses import dataclass

import math
import re
import numpy as np
import cv2

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

def match_single_object_akaze(query_img: Image.Image, target_img: Image.Image, debug=False) -> tuple[int, int] | None:
    """
    Finds the unique matching position of query_img in target_img using AKAZE features
    and histogram equalization on grayscale images.

    Args:
        query_img (PIL.Image.Image): The smaller image to be matched (grayscale or color).
        target_img (PIL.Image.Image): The image to search within (grayscale or color).
        debug (bool): Whether to display matching visualization.

    Returns:
        tuple[int, int] | None: center coordinates (x, y) of the matched bounding box or None if not found.
    """
    # Convert PIL Image to numpy array
    query_img_np = np.array(query_img)
    target_img_np = np.array(target_img)

    # Convert RGB (from PIL) to BGR (for OpenCV)
    if query_img_np.ndim == 3:
        query_img_np = cv2.cvtColor(query_img_np, cv2.COLOR_RGB2BGR)
    if target_img_np.ndim == 3:
        target_img_np = cv2.cvtColor(target_img_np, cv2.COLOR_RGB2BGR)
    
    def preprocess(img):
        if img.ndim == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.equalizeHist(img)  # Equalize histogram to improve brightness robustness

    # Preprocess both images
    query_gray = preprocess(query_img_np)
    target_gray = preprocess(target_img_np)

    # AKAZE feature extraction
    akaze = cv2.AKAZE_create()
    kp1, des1 = akaze.detectAndCompute(query_gray, None)
    kp2, des2 = akaze.detectAndCompute(target_gray, None)

    if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
        return None

    # Matching (using Euclidean distance)
    bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=True)
    matches = bf.match(des1, des2)
    if len(matches) < 4:
        return None

    # Sort by distance
    matches = sorted(matches, key=lambda x: x.distance)

    # RANSAC geometric verification
    src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

    M, mask = cv2.estimateAffinePartial2D(src_pts, dst_pts)
    if M is None or mask is None or mask.sum() < 4:
        return None

    # Decompose the affine matrix to remove the rotational component, as we assume
    # the matching does not involve rotation. This provides a more stable bounding box
    # for scale-only transformations.
    # M = [[s*cos(t), -s*sin(t), tx], [s*sin(t), s*cos(t), ty]]
    scale = np.sqrt(M[0, 0]**2 + M[1, 0]**2)
    tx = M[0, 2]
    ty = M[1, 2]
    M_no_rotation = np.float32([[scale, 0, tx], [0, scale, ty]])

    # Map query border to target using the rotation-free matrix
    h, w = query_gray.shape
    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    dst_corners = cv2.transform(corners, M_no_rotation)

    # Calculate the center of the bounding box
    x_coords = dst_corners[:, 0, 0]
    y_coords = dst_corners[:, 0, 1]
    center_x = (np.min(x_coords) + np.max(x_coords)) / 2
    center_y = (np.min(y_coords) + np.max(y_coords)) / 2

    if debug:
        target_vis = target_img_np.copy()
        if target_vis.ndim == 2:
            target_vis = cv2.cvtColor(target_vis, cv2.COLOR_GRAY2BGR)
            
        cv2.polylines(target_vis, [np.int32(dst_corners)], isClosed=True, color=(0, 255, 0), thickness=2)
        cv2.imshow("Match Visualization", target_vis)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return int(center_x), int(center_y)

def detect_and_merge_rectangles_pil(
    pil_image: Image.Image,
    aspect_ratio_range=(0.8, 1.2),
    area_range=(300, 1e3),
    iou_threshold=0.2,
    debug=False
) -> list[tuple[int, int, int, int]]:
    """
    Detects and merges all rectangular (or rounded rectangular) regions from a PIL image.

    Args:
        pil_image (PIL.Image): The input image.
        aspect_ratio_range (tuple): The aspect ratio range (min_ratio, max_ratio).
        area_range (tuple): The area range (min_area, max_area).
        iou_threshold (float): The IoU threshold for merging rectangles.
        debug (bool): Whether to visualize the results.

    Returns:
        list[tuple[int, int, int, int]]: A list of merged rectangles as (x, y, w, h).
    """
    # Convert to OpenCV format
    image = np.array(pil_image)
    if image.ndim == 2:
        gray = image.copy()
    elif image.shape[2] == 4:
        gray = cv2.cvtColor(image, cv2.COLOR_RGBA2GRAY)
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

    # Edge detection
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    # Contour extraction (RETR_LIST supports nested structures)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    rects = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < area_range[0] or area > area_range[1]:
            continue

        epsilon = 0.02 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)

        if len(approx) != 4:
            continue

        def angle(pt1, pt2, pt0):
            """Helper to compute angle between three points."""
            dx1 = pt1[0] - pt0[0]
            dy1 = pt1[1] - pt0[1]
            dx2 = pt2[0] - pt0[0]
            dy2 = pt2[1] - pt0[1]
            return (dx1 * dx2 + dy1 * dy2) / (math.hypot(dx1, dy1) * math.hypot(dx2, dy2) + 1e-8)

        pts = approx.reshape(-1, 2)
        max_cos = max(abs(angle(pts[i], pts[(i + 2) % 4], pts[(i + 1) % 4])) for i in range(4))
        if max_cos > 0.3:
            continue

        x, y, w, h = cv2.boundingRect(approx)
        aspect_ratio = w / h if h > 0 else 0
        if not (aspect_ratio_range[0] <= aspect_ratio <= aspect_ratio_range[1]):
            continue

        rects.append((x, y, w, h))

    # Merge rectangles
    merged = merge_rectangles(rects, iou_threshold)

    if debug:
        vis = cv2.cvtColor(blur, cv2.COLOR_GRAY2BGR)
        for x, y, w, h in merged:
            cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.imshow("Merged Rectangles", vis)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return merged


def merge_rectangles(rects: list[tuple[int, int, int, int]], iou_thresh=0.2) -> list[tuple[int, int, int, int]]:
    """
    Merges a group of overlapping or adjacent rectangles based on IoU.

    Args:
        rects (list[tuple[int, int, int, int]]): The input rectangles (x, y, w, h).
        iou_thresh (float): The IoU threshold for merging.

    Returns:
        list[tuple[int, int, int, int]]: A list of merged rectangles.
    """
    if not rects:
        return []

    rects = np.array(rects).astype(float).tolist()
    merged = []

    while rects:
        base = rects.pop(0)
        i = 0
        while i < len(rects):
            if compute_iou(base, rects[i]) > iou_thresh:
                x1 = min(base[0], rects[i][0])
                y1 = min(base[1], rects[i][1])
                x2 = max(base[0] + base[2], rects[i][0] + rects[i][2])
                y2 = max(base[1] + base[3], rects[i][1] + rects[i][3])
                base = [x1, y1, x2 - x1, y2 - y1]
                rects.pop(i)
                i = 0  # Restart scan since base has changed
            else:
                i += 1
        merged.append(tuple(map(int, base)))

    return merged


def compute_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """
    Computes the Intersection over Union (IoU) between two rectangles.
    
    Args:
        a (tuple[int, int, int, int]): The first rectangle (x, y, w, h).
        b (tuple[int, int, int, int]): The second rectangle (x, y, w, h).
        
    Returns:
        float: The IoU score, a value between 0 and 1.
    """
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[0] + a[2], b[0] + b[2])
    y2 = min(a[1] + a[3], b[1] + b[3])

    inter_area = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = a[2] * a[3]
    area_b = b[2] * b[3]
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0

if __name__ == "__main__":
    setup_ocr()
    img = Image.open("tests/test.png")
    print(ocr(img))
    print(ocr_pattern(img, "\d+\.?\d*%"))

    # --- Image matching tests ---
    print("\n--- Testing match_single_object_akaze ---")
    
    # Set to True to visually inspect each test case
    DEBUG_MATCHING = False 

    try:
        template_img_orig = Image.open("tests/test-template.png")
        match_img_orig = Image.open("tests/test-match.png")

        print("Running baseline test...")
        coords = match_single_object_akaze(template_img_orig, match_img_orig, debug=DEBUG_MATCHING)
        print(f"  Result: {coords}")

        # Test with color adjustments
        print("\nRunning color jitter test...")
        enhancer = ImageEnhance.Brightness(match_img_orig)
        jittered_img = enhancer.enhance(1.5) # Increase brightness
        enhancer = ImageEnhance.Contrast(jittered_img)
        jittered_img = enhancer.enhance(1.5) # Increase contrast
        coords = match_single_object_akaze(template_img_orig, jittered_img, debug=DEBUG_MATCHING)
        print(f"  Result on color-jittered image: {coords}")
        if DEBUG_MATCHING:
            jittered_img.show()
            
        # Test with slight scaling
        print("\nRunning scaling test...")
        w, h = match_img_orig.size
        # Scale down to 90%
        scaled_img = match_img_orig.resize((int(w * 0.9), int(h * 0.9)))
        coords = match_single_object_akaze(template_img_orig, scaled_img, debug=DEBUG_MATCHING)
        print(f"  Result on scaled (0.9x) image: {coords}")
        if DEBUG_MATCHING:
            scaled_img.show()

        # Test with slight cropping of the template
        print("\nRunning template cropping test...")
        w, h = template_img_orig.size
        # Crop 5% from each side of the template
        cropped_template = template_img_orig.crop((int(w * 0.05), int(h * 0.05), int(w * 0.95), int(h * 0.95)))
        coords = match_single_object_akaze(cropped_template, match_img_orig, debug=DEBUG_MATCHING)
        print(f"  Result with cropped template: {coords}")
        if DEBUG_MATCHING:
            cropped_template.show()

    except FileNotFoundError:
        print("\nSkipping image matching tests: 'test-template.png' or 'test-match.png' not found.")

    # --- Rectangle detection tests ---
    print("\n--- Testing detect_and_merge_rectangles_pil ---")
    try:
        rect_img = Image.open("tests/test-rect2.png")
        print("Running rectangle detection test...")
        rects = detect_and_merge_rectangles_pil(rect_img, debug=True)
        print(f"  Found {len(rects)} rectangles.")
        for i, r in enumerate(rects):
            print(f"    Rect {i+1}: {r}")
            
    except FileNotFoundError:
        print("\nSkipping rectangle detection tests: 'test-rect.png' not found.")
