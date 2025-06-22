from dataclasses import dataclass
import time

from tqdm import tqdm

from toolbox.tasks.echo_task import EchoTask, Page
from toolbox.config.profile import EchoProfile
from toolbox.utils.ocr import ocr_pattern
from toolbox.utils.logger import logger

class EchoScan(EchoTask):
    def run(self) -> list[EchoProfile]:
        self.interaction.ensure_connected()

        # 1. Ensure we are in the echo inspection page 
        self.to_page(Page.MAIN)
        
        # 2. Identify the selected cost 
        while True:
            screenshot = self.interaction.screenshot_region(0.7429, 0.1674, 0.7977, 0.1896)
            cost = ocr_pattern(screenshot, "\d+")
            if len(cost) == 0:
                # ocr failed or no available echo 
                logger.warning("Scanner ended with no available echo. Please ensure you have at list one echo before scanning.")
                return []

            cost = int(cost[0].text)
            if cost in [1, 3, 4]:
                break

            logger.warning(f"Invalid cost: {cost}, retrying...")

            # this indicates our ocr encountered a problem, we need to retry
            time.sleep(1)

        logger.info(f"Selected cost: {cost}")

        # 3. Scroll to the top 
        self.interaction.click(0.220 if cost != 3 else 0.168, 0.053)
        time.sleep(0.3)
        x_offset = 0.168 if cost == 1 else 0.220 if cost == 3 else 0.272
        self.interaction.click(x_offset, 0.053)

        # 4. Scan all presented echo in the first page
        time.sleep(0.5)
        profiles = []
        width, height = self.interaction.get_app_window_size()
        screenshot = self.interaction.screenshot()

        left_top = (0.125, 0.278)
        right_bottom = (0.260, 0.844) 

        def greyscale_value(pixel: tuple[int, int, int]) -> float:
            return 0.299 * pixel[0] + 0.587 * pixel[1] + 0.114 * pixel[2]

        for i in range(15):
            x_ratio = left_top[0] + (i  % 3) * (right_bottom[0] - left_top[0]) / 2
            y_ratio = left_top[1] + (i // 3) * (right_bottom[1] - left_top[1]) / 4 

            # 4.1 check if (x_ratio, y_ratio) points to an echo
            pixel = screenshot.getpixel((int(width * x_ratio), int(height * y_ratio)))
            if greyscale_value(pixel) > 30:
                break

            # 4.2 click on the echo 
            self.interaction.click(x_ratio, y_ratio)

            # 4.3 extract the echo profile 
            while True:
                profile_img = self.interaction.screenshot_region(0.7356, 0.1264, 0.952, 0.458)
                profile = EchoProfile().from_image(profile_img)

                if profile.validate():
                    if profile.level == 0:
                        # all following echos are not upgraded yet, skip the rest and return
                        return profiles
                        
                    profiles.append(profile)
                    break

                time.sleep(1)
            
        if len(profiles) < 15:
            # this indicates all echos have been scanned 
            logger.info("All echos have been scanned.")
            return profiles
        
        # 5. Scoll down to bottom line by line and scan each echo 
        last_line_valid = True
        continuous_valid_lines = 0

        self.interaction.scroll(0.192, 0.844, 5.1)
        while True:
            self.interaction.scroll(0.192, 0.844, 0.08)

            _tmp_screenshot = self.interaction.screenshot()
            pixel = _tmp_screenshot.getpixel((int(width * 0.125), int(height * 0.278)))

            if greyscale_value(pixel) <= 30:
                if last_line_valid is False:
                    # we find another line of echos 
                    logger.info("Found another line of echos")

                    for i in range(3):
                        x_ratio = left_top[0] + (i % 3) * (right_bottom[0] - left_top[0]) / 2
                        y_ratio = 0.856 

                        pixel = _tmp_screenshot.getpixel((int(width * x_ratio), int(height * y_ratio)))
                        if greyscale_value(pixel) <= 30:
                            # click on the echo 
                            self.interaction.click(x_ratio, y_ratio)

                            # extract the echo profile 
                            while True:
                                profile_img = self.interaction.screenshot_region(0.7356, 0.1264, 0.952, 0.458)
                                profile = EchoProfile().from_image(profile_img)

                                if profile.validate():
                                    if profile.level == 0:
                                        # all following echos are not upgraded yet, skip the rest and return
                                        return profiles

                                    profiles.append(profile)
                                    break

                                time.sleep(1)

                    self.interaction.scroll(0.192, 0.844, 5.4)

                last_line_valid = True
                continuous_valid_lines += 1
            else:
                last_line_valid = False
                continuous_valid_lines = 0
            
            # we reach the bottom of the whole page
            if continuous_valid_lines >= 10:
                break

        return profiles
        
