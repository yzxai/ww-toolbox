from enum import Enum
import time
from toolbox.core.interaction import Element
from toolbox.tasks.base_task import BaseTask
from toolbox.utils.ocr import ocr_pattern
from toolbox.utils.logger import logger

class Page(Enum):
    MAIN = 0
    SORT = 1
    FILTER = 2
    UPGRADE = 3
    TUNE = 4

class EchoTask(BaseTask):
    def __init__(self):
        super().__init__()
        # setup trasmission graph between pages
        self.graph = {
            Page.MAIN: {
                Page.SORT: { "action": self.interaction.click_img_template, "args": (Element.ECHO_SORT, (0.085, 0.9, 0.3, 1)) },
                Page.FILTER: { "action": self.interaction.click_img_template, "args": (Element.ECHO_FILTER, (0.085, 0.9, 0.3, 1)) },
                Page.UPGRADE: { "action": self.interaction.click_ocr, "args": ("培养", "right_bottom") },
            },
            Page.SORT: {
                Page.MAIN: { "action": self.interaction.send_key, "args": ("esc",) },
            },
            Page.FILTER: {
                Page.MAIN: { "action": self.interaction.send_key, "args": ("esc",) },
            },
            Page.UPGRADE: {
                Page.MAIN: { "action": self.interaction.send_key, "args": ("esc",) },
                Page.TUNE: { "action": self.interaction.click_img_template, "args": (Element.TUNE, (0, 0, 0.3, 0.5)) },
            },
            Page.TUNE: {
                Page.MAIN: { "action": self.interaction.send_key, "args": ("esc",) },
                Page.UPGRADE: { "action": self.interaction.click_img_template, "args": (Element.UPGRADE, (0, 0, 0.3, 0.5)) },
            },
        }
    
    def is_in_main_page(self) -> bool:
        screenshot = self.interaction.screenshot()
        width, height = self.interaction.get_app_window_size()
        return len(ocr_pattern(screenshot.crop((width * 0.8, 0, width, height * 0.1)), "简述")) > 0
    
    def current_page(self) -> Page:
        screenshot = self.interaction.screenshot()

        width, height = self.interaction.get_app_window_size()

        if len(ocr_pattern(screenshot.crop((width * 0.8, 0, width, height * 0.1)), "简述")) > 0:
            return Page.MAIN

        if len(ocr_pattern(screenshot.crop((0, 0, width * 0.2, height * 0.1)), "强化")) > 0:
            return Page.UPGRADE

        if len(ocr_pattern(screenshot.crop((0, 0, width * 0.2, height * 0.1)), "调谐")) > 0:
            return Page.TUNE

        if len(ocr_pattern(screenshot.crop((0, 0, width * 0.2, height * 0.2)), "排序")) > 0:
            return Page.SORT

        if len(ocr_pattern(screenshot.crop((0, 0, width * 0.094, height * 0.134)), "筛选")) > 0:
            return Page.FILTER
        
        logger.critical("Unknown page")
        raise Exception("Unknown page")

    def to_page(self, target: Page):
        logger.info(f"To page: {target}")
        time.sleep(0.5)

        # bfs to find the shortest path
        def bfs(start: Page) -> list[Page]:
            queue = [(start, [])]
            visited = {start}
            
            while queue:
                current, path = queue.pop(0)
                if current == target:
                    return path
                
                for next_page in self.graph[current]:
                    if next_page not in visited:
                        visited.add(next_page)
                        queue.append((next_page, path + [next_page]))
            
            return None
        
        while True:
            current_page = self.current_page()
            if current_page == target:
                return

            path = bfs(current_page)
            if path is None:
                raise Exception(f"No path found from {current_page} to {target}")
            
            for page in path:
                action = self.graph[current_page][page]
                action["action"](*action["args"])
                current_page = page
                time.sleep(0.5)