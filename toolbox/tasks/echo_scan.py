from dataclasses import dataclass
import time

from tqdm import tqdm

from toolbox.tasks.echo_task import EchoTask, Page
from toolbox.core.profile import EchoProfile
from toolbox.utils.ocr import ocr_pattern
from toolbox.utils.logger import logger

class EchoScan(EchoTask):
    """
    Scan all the echos in the main page and return the list of profiles.
    """
    def run(self) -> list[EchoProfile]:
        self.interaction.ensure_connected()
        logger.info("Scanning all echos in the main page")

        # 1. Ensure we are in the echo inspection page 
        self.to_page(Page.MAIN)

        for i in range(10):
            time.sleep(0.1)
            self.interaction.scroll(0.192, 0.244, -30)

        # 2. Scan all presented echo in the first page
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

            # 2.1 check if (x_ratio, y_ratio) points to an echo
            pixel = screenshot.getpixel((int(width * x_ratio), int(height * y_ratio)))

            logger.info(f"greyscale value: {greyscale_value(pixel)}")
            if greyscale_value(pixel) > 50:
                break

            # 2.2 click on the echo 
            self.interaction.click(x_ratio, y_ratio)

            # 2.3 extract the echo profile 
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
        
        # 3. Scoll down to bottom line by line and scan each echo 
        last_line_valid = True
        continuous_valid_lines, continuous_invalid_lines = 0, 0

        self.interaction.scroll(0.192, 0.544, 9.0)
        while True:
            self.interaction.scroll(0.192, 0.544, 0.08)

            _tmp_screenshot = self.interaction.screenshot()
            pixel = _tmp_screenshot.getpixel((int(width * 0.125), int(height * 0.268)))

            if greyscale_value(pixel) <= 50:
                if last_line_valid is False:
                    for i in range(3):
                        x_ratio = left_top[0] + (i % 3) * (right_bottom[0] - left_top[0]) / 2
                        y_ratio = 0.856 

                        pixel = _tmp_screenshot.getpixel((int(width * x_ratio), int(height * y_ratio)))
                        if greyscale_value(pixel) <= 50:
                            # click on the echo 
                            self.interaction.click(x_ratio, 0.836)

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

                    self.interaction.scroll(0.192, 0.544, 5.4)

                last_line_valid = True
                continuous_valid_lines += 1
                continuous_invalid_lines = 0
            else:
                last_line_valid = False
                continuous_valid_lines = 0
                continuous_invalid_lines += 1
            
            # we reach the bottom of the whole page
            if continuous_valid_lines >= 20 or continuous_invalid_lines >= 20:
                break
        
        logger.info(f"Scanned {len(profiles)} echos")

        return profiles
        
