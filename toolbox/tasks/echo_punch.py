from toolbox.tasks.echo_task import EchoTask, Page
from toolbox.core.profile import EchoProfile
from toolbox.utils.ocr import ocr_pattern, ocr
from toolbox.utils.logger import logger
import time

class EchoPunch(EchoTask):
    """
    Upgrade the echo to the next stage, punch the echo and return the upgraded profile.
    After finished, we will stay on the upgrade page.
    """
    def run(self, profile: EchoProfile, work_state: dict) -> EchoProfile:
        self.interaction.ensure_connected()
        self.to_page(Page.UPGRADE)
        self.interaction.click_ocr("阶段放入", region=(0, 0.6, 0.5, 1))
        time.sleep(0.5)

        screenshot = self.interaction.screenshot_region(0.466, 0.18, 0.534, 0.212)
        if len(ocr_pattern(screenshot, "不足")) > 0:
            logger.critical("Not enough materials") 
            raise Exception("Not enough materials")

        while True:
            if work_state["cancel_requested"]: return None
            self.interaction.click_ocr("强化", region=(0, 0.8, 0.5, 1))

            time.sleep(0.8)
            validation_img = self.interaction.screenshot_region(0, 0.8, 0.5, 1)
            if len(ocr_pattern(validation_img, "强化")) == 0:
                break

            logger.warning("Failed to click the upgrade button, retrying...")

        screenshot = self.interaction.screenshot_region(0.5, 0.6, 1, 1)
        overflow = False
        if len(ocr_pattern(screenshot, "确认")) > 0: 
            logger.info("Current echo is about to reach the max level")
            self.interaction.click_ocr("确认", region=(0.5, 0.7, 1, 1))
            overflow = True
            time.sleep(0.5)

        time.sleep(1)
        captured = False
        for _ in range(10):
            if work_state["cancel_requested"]: return None
            screenshot = self.interaction.screenshot_region(0.546, 0.35, 1, 1)
            result = ocr_pattern(screenshot, "\d+")

            if len(result) > 0:
                level = int(result[0].text)
                if (profile.level + 10) // 5 * 5 >= level > profile.level:
                    logger.info(f"Echo level after upgrade: {level}")
                    captured = True
                    break
                
            logger.info(f"Captured result: {result}")
            logger.warning("Failed to get the level of the current echo, retrying...")
            time.sleep(0.5)
        
        if not captured:
            logger.critical("Failed to capture the level after 10 retries, returning...")
            # screenshot.show()
            raise Exception("Failed to capture the level after 10 retries")

        self.interaction.send_key("esc")
        time.sleep(0.5)

        if overflow:
            self.interaction.send_key("esc")
            time.sleep(0.5)

        self.to_page(Page.TUNE)
        self.interaction.click_ocr("调谐", region=(0, 0.87, 0.5, 1))
        time.sleep(1)

        while True:
            screenshot = self.interaction.screenshot_region(0.346, 0.371, 0.679, 0.402)
            entry_str = ocr(screenshot)

            result_profile = profile.upgrade(level, entry_str)
            if result_profile is not None:
                logger.info(f"Upgraded echo to level {level} with entry {entry_str}")
                profile = result_profile
                break 

            logger.warning("Failed to recognize the new entry, retrying...")
            if work_state["cancel_requested"]: return None
            time.sleep(0.5)
        
        self.interaction.send_key("esc")
        time.sleep(0.5)
        self.interaction.send_key("esc")
        return profile


