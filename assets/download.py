from pathlib import Path
import re
import requests
import json

raw_html_path = Path(__file__).parent / "raw_html.txt"

with open(raw_html_path, "r", encoding="utf-8") as f:
    raw_html = f.read()

links = re.findall(r'class="card-content-inner"><img data-v-0d68f878="" data-src="(.+?)"', raw_html)
names = re.findall(r'class="card-footer-inner"><span data-v-0d68f878="">(.+?)</span>', raw_html)

for link, name in zip(links, names):
    print(name, link)

target_folder = Path(__file__).parent / "imgs"
target_folder.mkdir(exist_ok=True)

metadata = []

for link, name in zip(links, names):
    metadata.append({
        "name": name,
        "file": link.split("/")[-1]
    })

    # download the image
    response = requests.get(link)
    with open(target_folder / metadata[-1]["file"], "wb") as f:
        f.write(response.content)
    
with open(target_folder / "metadata.json", "w", encoding="utf-8") as f:
    json.dump(metadata, f, ensure_ascii=False, indent=4)
