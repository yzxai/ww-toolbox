import time
from toolbox.tasks.echo_task import EchoTask, Page
from toolbox.core.profile import EchoProfile
from toolbox.utils.ocr import detect_and_merge_rectangles_pil, ocr_pattern
from toolbox.utils.logger import logger

class EchoSearch(EchoTask):
    """
    Search for the target echo in the main page and return the profile if found, None otherwise.
    After finished, we will stay on the main page with the target echo selected.
    """
    def run(self, profile: EchoProfile, work_state: dict, main_entry_filter: str = None) -> EchoProfile:
        logger.info(f"Searching for echo: {profile}")
        logger.info(f"Main entry filter: {main_entry_filter}")

        self.interaction.ensure_connected()
        self.to_page(Page.MAIN)

        for i in range(10):
            self.interaction.scroll(0.192, 0.244, -30)
            time.sleep(0.1)

        time.sleep(0.5)
        width, height = self.interaction.get_app_window_size()
        left_top = (0.092, 0.231)
        right_bottom = (0.294, 0.835) 
        screenshot = self.interaction.screenshot_region(left_top[0], left_top[1], right_bottom[0], right_bottom[1])
        
        boxes = detect_and_merge_rectangles_pil(screenshot)
        
        num_checked = 0

        def check_profile_matched() -> EchoProfile:
            while True:
                if work_state["cancel_requested"]: return None
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

        for box in boxes:
            if work_state["cancel_requested"]: return None

            x, y, w, h = box
            x_ratio = (x + w / 2) / width + left_top[0]
            y_ratio = (y + h / 2) / height + left_top[1]

            num_checked += 1
                
            # quick check on the level 
            while True:
                _screenshot = self.interaction.screenshot_region(x_ratio - 0.05, y_ratio + 0.01, x_ratio + 0.05, y_ratio + 0.05)
                level = ocr_pattern(_screenshot, "^\+\d+")
                if len(level) > 0:
                    level = int(level[0].text[1:])
                    break

                logger.info(f"ocr failed when checking the level, retrying...")
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

        self.interaction.scroll(0.192, 0.544, 8.0)
        while True:
            if work_state["cancel_requested"]: return None
            self.interaction.scroll(0.192, 0.544, 0.7)

            left_top = (0.087, 0.738)
            right_bottom = (0.297, 0.828)

            _tmp_screenshot = self.interaction.screenshot_region(left_top[0], left_top[1], right_bottom[0], right_bottom[1])
            boxes = detect_and_merge_rectangles_pil(_tmp_screenshot)

            if len(boxes) > 0:
                if last_line_valid is False:
                    for box in boxes:
                        x, y, w, h = box
                        x_ratio = (x + w / 2) / width + left_top[0]
                        y_ratio = (y + h / 2) / height + left_top[1]

                        # quick check on the level 
                        while True:
                            _screenshot = self.interaction.screenshot_region(x_ratio - 0.05, y_ratio + 0.01, x_ratio + 0.05, y_ratio + 0.05)
                            level = ocr_pattern(_screenshot, "^\+\d+")
                            if len(level) > 0:
                                level = int(level[0].text[1:])
                                break

                            logger.info(f"ocr failed when checking the level, retrying...")
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

                    self.interaction.scroll(0.192, 0.544, 4)

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