import requests
import re
import json
import uuid

base_url = "https://mc.appfeng.com"

html = requests.get(base_url + "/avatar").text

names = re.findall(r'<div class="name"><span>(.+?)</span></div>', html)
links = re.findall(r'<div class="head"><img src="(.+?)"></div>', html)

metadata = {
    "characters": []
}

for (name, link) in zip(names, links):
    full_link = base_url + link
    print(full_link)
    img_data = requests.get(full_link).content
    index = uuid.uuid5(uuid.NAMESPACE_DNS, name).hex
    with open(f"{index}.png", "wb") as img_file:
        img_file.write(img_data)
    metadata["characters"].append({
        "name": name,
        "file": f"{index}.png"
    })

with open("metadata.json", "w", encoding="utf-8") as meta_file:
    json.dump(metadata, meta_file, ensure_ascii=False, indent=4)
    
print(names, links)