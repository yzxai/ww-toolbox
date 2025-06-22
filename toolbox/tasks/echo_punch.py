from toolbox.tasks.echo_task import EchoTask, Page
from toolbox.config.profile import EchoProfile
from toolbox.utils.ocr import ocr_pattern, ocr
from toolbox.utils.logger import logger
import time

class EchoPunch(EchoTask):
    def run(self, profile: EchoProfile) -> EchoProfile:
        self.interaction.ensure_connected()
        self.to_page(Page.UPGRADE)
        self.interaction.click(0.288, 0.70)
        time.sleep(0.3)

        screenshot = self.interaction.screenshot_region(0.466, 0.18, 0.534, 0.212)
        if len(ocr_pattern(screenshot, "不足")) > 0:
            logger.warning("Not enough materials") 
            return profile

        self.interaction.click(0.227, 0.922)
        time.sleep(0.5)
        self.interaction.send_key("esc")
        time.sleep(0.5)

        self.to_page(Page.TUNE)
        self.interaction.click(0.227, 0.922)
        time.sleep(0.5)

        while True:
            screenshot = self.interaction.screenshot_region(0.346, 0.371, 0.679, 0.402)
            entry_str = ocr(screenshot)

            result_profile = profile.upgrade(entry_str)
            if result_profile is not None:
                profile = result_profile
                break 

            time.sleep(0.5)
        
        self.interaction.send_key("esc")
        return profile


