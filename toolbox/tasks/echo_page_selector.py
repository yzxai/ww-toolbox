from toolbox.core.interaction import Element
from toolbox.tasks.echo_task import EchoTask, Page
from toolbox.utils.logger import logger
from dataclasses import dataclass, field
import time

from toolbox.utils.ocr import ocr_pattern

@dataclass 
class EchoFilter:
    cost: int
    name: str = field(default="") 
    suit: str = field(default="")
    main_entry: str = field(default="")

class EchoPageSelector(EchoTask):
    """
    Filter the echos in the main page according to the properties.
    """
    def run(self, filter: EchoFilter):
        logger.info(f"Running EchoPageSelector with filter: {filter}")
        self.interaction.ensure_connected()

        self.to_page(Page.MAIN)
        time.sleep(0.3)
        x_offset = 0.168 if filter.cost == 1 else 0.220 if filter.cost == 3 else 0.272
        self.interaction.click(x_offset, 0.053)

        # 1. filter the echos by name 
        time.sleep(0.3)
        self.interaction.click(0.27, 0.875)
        if filter.name != "":
            self.to_page(Page.FILTER)

            # 1.1 reset the filter 
            self.interaction.click_ocr("重置", region="bottom")

            # 1.2 type the name and select
            self.interaction.click_ocr("输入搜索内容", region="left_top")
            self.interaction.send_text(filter.name)
            self.interaction.send_key("enter")
            time.sleep(0.5)
            self.interaction.click(0.3, 0.3)
            self.interaction.click_ocr("确认", region="bottom")
        
        # 2. filter the echos by suit 
        if filter.suit != "":
            self.to_page(Page.MAIN)

            # 2.1 check if the target suit is already selected
            _screen_shot = self.interaction.screenshot_region(0.118, 0.102, 0.201, 0.131)
            if len(ocr_pattern(_screen_shot, filter.suit)) == 0:
                time.sleep(0.2)
                self.interaction.click_img_template(Element.SUIT_FILTER, region="left_top")
                time.sleep(0.3)
                self.interaction.click_ocr(filter.suit, region=(0.117, 0.201, 0.213, 0.700))
        
        # 3. filter the echos by main entry 
        if filter.main_entry != "":
            self.to_page(Page.SORT)

            # 3.1 reset the filter 
            self.interaction.click_ocr("重置", region="bottom")
            self.interaction.scroll(0.5, 0.5, 22)
            time.sleep(0.3)
            # special case for "暴击"
            if filter.main_entry == "暴击":
                self.interaction.click_ocr("暴击率")
            else:
                self.interaction.click_ocr("主属性" + filter.main_entry)
            self.interaction.click_ocr("确认", region="bottom")


        
        



