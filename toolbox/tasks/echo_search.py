import time
from toolbox.tasks.echo_task import EchoTask, Page
from toolbox.core.profile import EchoProfile
from toolbox.utils.ocr import ocr_pattern
from toolbox.utils.logger import logger

class EchoSearch(EchoTask):
    """
    Search for the target echo in the main page and return the profile if found, None otherwise.
    After finished, we will stay on the main page with the target echo selected.
    """
    def run(self, profile: EchoProfile, main_entry_filter: str = None) -> EchoProfile:
        logger.info(f"Searching for echo: {profile}")
        logger.info(f"Main entry filter: {main_entry_filter}")

        self.interaction.ensure_connected()
        self.to_page(Page.MAIN)

        for i in range(10):
            self.interaction.scroll(0.192, 0.244, -30)
            time.sleep(0.1)

        time.sleep(0.5)
        width, height = self.interaction.get_app_window_size()
        screenshot = self.interaction.screenshot()

        left_top = (0.125, 0.278)
        right_bottom = (0.260, 0.844) 

        def greyscale_value(pixel: tuple[int, int, int]) -> float:
            return 0.299 * pixel[0] + 0.587 * pixel[1] + 0.114 * pixel[2]
        
        num_checked = 0

        def check_profile_matched() -> EchoProfile:
            while True:
                profile_img = self.interaction.screenshot_region(0.7356, 0.1264, 0.952, 0.458)
                curr_profile = EchoProfile().from_image(profile_img)

                if curr_profile.validate():
                    if hash(curr_profile) == hash(profile):
                        # double check the main entry 
                        if main_entry_filter is not None:
                            entry_img = self.interaction.screenshot_region(0.5828, 0.2215, 0.8545, 0.2472)
                            if len(ocr_pattern(entry_img, main_entry_filter)) == 0:
                                return None

                        return curr_profile
                    break

                time.sleep(1)
            return None


        for i in range(15):
            x_ratio = left_top[0] + (i  % 3) * (right_bottom[0] - left_top[0]) / 2
            y_ratio = left_top[1] + (i // 3) * (right_bottom[1] - left_top[1]) / 4 

            # check if (x_ratio, y_ratio) points to an echo
            pixel = screenshot.getpixel((int(width * x_ratio), int(height * y_ratio)))
            if greyscale_value(pixel) > 50:
                break

            num_checked += 1
                
            # quick check on the level 
            while True:
                _screenshot = self.interaction.screenshot_region(x_ratio, y_ratio - 0.017, x_ratio + 0.04, y_ratio + 0.017)
                level = ocr_pattern(_screenshot, "^\+\d+")
                if len(level) > 0:
                    level = int(level[0].text[1:])
                    break

                logger.info(f"ocr failed, retrying...")
                _screenshot.show()
                time.sleep(0.5)
            
            if level > profile.level:
                continue

            if level < profile.level:
                return None

            # click on the echo 
            self.interaction.click(x_ratio, y_ratio)

            # extract the echo profile 
            curr_profile = check_profile_matched()
            if curr_profile is not None:
                return curr_profile
        
        if num_checked < 15:
            return None 
        
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
                        y_ratio = 0.845

                        pixel = _tmp_screenshot.getpixel((int(width * x_ratio), int(height * y_ratio)))

                        if greyscale_value(pixel) <= 50:
                            # quick check on the level 
                            while True:
                                _screenshot = self.interaction.screenshot_region(x_ratio, y_ratio - 0.017, x_ratio + 0.036, y_ratio + 0.023)
                                level = ocr_pattern(_screenshot, "^\+\d+")
                                if len(level) > 0:
                                    level = int(level[0].text[1:])
                                    break
                            
                            if level > profile.level:
                                continue
                            
                            if level < profile.level:
                                return None

                            # click on the echo 
                            self.interaction.click(x_ratio, y_ratio)

                            # extract the echo profile 
                            curr_profile = check_profile_matched()
                            if curr_profile is not None:
                                return curr_profile

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

        return None