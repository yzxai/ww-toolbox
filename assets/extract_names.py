from pathlib import Path
import re

raw_html_path = Path(__file__).parent / "raw_html.txt"
characters_txt_path = Path(__file__).parent / "characters.txt"

with open(raw_html_path, "r", encoding="utf-8") as f:
    raw_html = f.read()

# Find all Chinese characters (including full CJK Unified Ideographs)
chinese_chars = re.findall(r'[\u4e00-\u9fff]', raw_html)

# Remove duplicates while preserving order
seen = set()
unique_chars = []
for char in chinese_chars:
    if char not in seen:
        seen.add(char)
        unique_chars.append(char)

with open(characters_txt_path, "w", encoding="utf-8") as f:
    f.write("".join(unique_chars))
