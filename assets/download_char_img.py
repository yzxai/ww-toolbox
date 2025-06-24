import requests
import json
import os
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from pathlib import Path

def download_char_images():
    raw_html_path = Path(__file__).parent / "raw_html.txt"
    target_folder = Path(__file__).parent / "imgs" / "char"

    # 读取HTML文件
    with open(raw_html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # 解析HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 创建目录
    os.makedirs(target_folder, exist_ok=True)
    
    # 存储角色信息
    characters = []
    
    # 查找所有角色项
    char_items = soup.find_all('li', class_=['s4', 's5'])
    
    for item in char_items:
        # 获取头像图片URL
        head_img = item.find('div', class_='head').find('img')
        if head_img and head_img.get('src'):
            img_src = head_img['src']
            
            # 获取角色名称
            name_div = item.find('div', class_='name')
            if name_div:
                name_span = name_div.find('span')
                if name_span:
                    char_name = name_span.text.strip()
                    
                    # 生成文件名（使用URL的哈希或时间戳）
                    import hashlib
                    import time
                    file_hash = hashlib.md5(img_src.encode()).hexdigest()
                    filename = f"{file_hash}.png"
                    
                    # 下载图片
                    try:
                        # 构建完整URL
                        base_url = "https://mc.appfeng.com/"
                        full_url = urljoin(base_url, img_src)
                        
                        # 下载图片
                        response = requests.get(full_url, timeout=10)
                        response.raise_for_status()
                        
                        # 保存图片
                        filepath = os.path.join(target_folder, filename)
                        with open(filepath, 'wb') as img_file:
                            img_file.write(response.content)
                        
                        # 添加到角色列表
                        characters.append({
                            "name": char_name,
                            "file": filename
                        })
                        
                        print(f"下载成功: {char_name} -> {filename}")
                        
                    except Exception as e:
                        print(f"下载失败 {char_name}: {e}")
    
    # 生成metadata.json
    metadata = {
        "characters": characters
    }
    
    with open(target_folder / 'metadata.json', 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)
    
    print(f"\n总共下载了 {len(characters)} 个角色图片")
    print("metadata.json 已生成")

if __name__ == "__main__":
    download_char_images()
