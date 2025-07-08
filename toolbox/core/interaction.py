import win32gui, win32ui, win32api, win32con
import numpy as np
import time
import random

from ctypes import windll
from PIL import Image
from toolbox.utils.logger import logger
from toolbox.utils.ocr import ocr_pattern, match_single_object_template
from toolbox.utils.generic import get_assets_dir
from enum import Enum

class Element(Enum):
    COST1 = "cost1.png"
    COST3 = "cost3.png"
    COST4 = "cost4.png"
    ECHO_FILTER = "echo_filter.png"
    ECHO_SORT = "echo_sort.png"
    SUIT_FILTER = "suit_filter.png"
    TUNE = "tune.png"
    UPGRADE = "upgrade.png"
    TRASH = "trash.png"
    CONFIG = "config.png"

    def to_img(self) -> Image.Image:
        path = get_assets_dir() / "imgs" / "game" / self.value
        return Image.open(path)

class Interaction:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.connected = False
        self.game_hwnd = None
        self.scale_factor = None
    
    def connect(self) -> bool:
        """
        Connect to the game window.
        Returns:
            bool: True if the connection was successful, False otherwise.
        """
        self.reset()

        def locate_game_window(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                class_name = win32gui.GetClassName(hwnd)
                if class_name == "UnrealWindow":
                    self.game_hwnd = hwnd
                    self.connected = True
                    logger.debug(f'Connected to game window: {self.game_hwnd}')
                    return False
            return True
        
        win32gui.EnumWindows(locate_game_window, None)
        return self.connected
    
    def ensure_connected(self):
        """
        Ensure that the game window is connected.
        If the game window is not connected, attempt to reconnect.
        If the reconnection fails, raise an exception.
        """
        if self.connected:
            if win32gui.IsWindow(self.game_hwnd):
                return True 
        logger.debug('Game window not found, attempting to reconnect...')
        status = self.connect()
        if not status:
            logger.critical('Failed to reconnect to game window')
            raise Exception('Failed to reconnect to game window')
        
    def get_app_window_size(self) -> tuple[int, int]:
        """
        Get the size of the game window in pixels.
        Returns:
            tuple[int, int]: The width and height of the game window.
        """
        self.ensure_connected()
        left, top, right, bottom = win32gui.GetClientRect(self.game_hwnd)
        return right - left, bottom - top
    
    def get_scale_factor(self) -> float:
        """
        Get the scale factor of the game window.
        Returns:
            float: The scale factor of the game window.
        """
        if self.scale_factor is None:
            windll.shcore.SetProcessDpiAwareness(1)
            self.scale_factor = windll.shcore.GetScaleFactorForDevice(0) / 100
        return self.scale_factor
    
    def screenshot(self) -> Image.Image:
        """
        Take a screenshot of the game window.
        Returns:
            Image.Image: The screenshot of the game window.
        """
        self.ensure_connected()

        app_hwnd_dc = win32gui.GetWindowDC(self.game_hwnd)
        mfcDC = win32ui.CreateDCFromHandle(app_hwnd_dc)
        saveDC = mfcDC.CreateCompatibleDC()

        width, height = self.get_app_window_size()
        scale_factor = self.get_scale_factor()
        width, height = int(width * scale_factor), int(height * scale_factor)

        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(bmp)

        result = windll.user32.PrintWindow(self.game_hwnd, saveDC.GetSafeHdc(), 3)

        bmpinfo = bmp.GetInfo()
        img = np.frombuffer(bmp.GetBitmapBits(True), dtype=np.uint8)
        img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)
        img = Image.fromarray(img[:, :, [2, 1, 0, 3]], mode='RGBA')

        win32gui.DeleteObject(bmp.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(self.game_hwnd, app_hwnd_dc)

        if result == 1:
            return img
        
        logger.critical(f'Failed to get screenshot. Please make sure the \
                        game is running and this program is running as administrator.')
        raise Exception('Failed to get screenshot')

    def screenshot_region(self, x_0: float, y_0: float, x_1: float, y_1: float) -> Image.Image:
        """
        Take a screenshot of a specific region of the game window.
        Args:
            x_0 (float): The x coordinate of the top-left corner of the region.
            y_0 (float): The y coordinate of the top-left corner of the region.
            x_1 (float): The x coordinate of the bottom-right corner of the region.
            y_1 (float): The y coordinate of the bottom-right corner of the region.
        Returns:
            Image.Image: The screenshot of the specified region.
        """
        self.ensure_connected()
        screenshot = self.screenshot()

        if screenshot is None:
            return None

        width, height = self.get_app_window_size()
        x_0, y_0, x_1, y_1 = int(width * x_0), int(height * y_0), int(width * x_1), int(height * y_1)
        return screenshot.crop((x_0, y_0, x_1, y_1))
    
    def click(self, x_ratio: float, y_ratio: float, rand: bool = True, press_time: float = 0.05):
        """
        Click on the game window at the specified coordinates.
        This method works even if the window is in the background or obscured.
        Args:
            x_ratio (float): The x coordinate of the click.
            y_ratio (float): The y coordinate of the click.
            rand (bool): Whether to randomize the click position.
        """
        self.ensure_connected()

        if not 0 <= x_ratio <= 1 or not 0 <= y_ratio <= 1:
            logger.error(f'Invalid coordinates: ({x_ratio}, {y_ratio}). Ignoring...')
            return None

        width, height = self.get_app_window_size()
        x = int(width * x_ratio)
        y = int(height * y_ratio)

        if rand:
            x, y = x + random.randint(-2, 2), y + random.randint(-2, 2)
            # clamp x and y to the window size
            x = max(0, min(x, width))
            y = max(0, min(y, height))

        position = win32api.MAKELONG(x, y)

        # Make the window think it's being activated.
        win32api.PostMessage(self.game_hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
        
        # Now send the standard click messages
        win32api.PostMessage(self.game_hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, position)
        time.sleep(press_time)
        win32api.PostMessage(self.game_hwnd, win32con.WM_LBUTTONUP, 0, position)
        time.sleep(0.1)
    
    def scroll(self, x_ratio: float, y_ratio: float, delta: int):
        """
        Scroll the game window at the specified coordinates.
        This method works even if the window is in the background or obscured.
        Args:
            x_ratio (float): The x coordinate of the scroll.
            y_ratio (float): The y coordinate of the scroll.
            delta (int): The amount to scroll down.
        """
        self.ensure_connected()
        
        width, height = self.get_app_window_size()
        x, y = int(width * x_ratio), int(height * y_ratio)

        # Make the window think it's being activated.
        win32api.PostMessage(self.game_hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)
        time.sleep(0.05)
        win32api.PostMessage(self.game_hwnd, win32con.WM_MOUSEMOVE, 0, win32api.MAKELONG(x, y))

        # For WM_MOUSEWHEEL, lParam needs to be screen coordinates.
        screen_coords = win32gui.ClientToScreen(self.game_hwnd, (x, y))
        screen_position = win32api.MAKELONG(screen_coords[0], screen_coords[1])
        
        # for press and release, it uses client coordinates.
        client_position = win32api.MAKELONG(x, y)

        # Send the scroll messages
        win32api.PostMessage(self.game_hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, client_position)
        w_param = win32api.MAKELONG(0, int(-delta * 120))
        win32api.PostMessage(self.game_hwnd, win32con.WM_MOUSEWHEEL, w_param, screen_position)
        win32api.PostMessage(self.game_hwnd, win32con.WM_LBUTTONUP, 0, client_position)
        time.sleep(0.05)
    
    def send_text(self, text: str):
        """
        Input text into the game window.
        Args:
            text (str): The text to input.
        """
        self.ensure_connected()

        # Send the text to the game window
        for char in text:
            win32api.SendMessage(self.game_hwnd, win32con.WM_CHAR, ord(char), 0)
            time.sleep(0.03)

    def send_key(self, key: str):
        """
        Send a key to the game window.
        Args:
            key (str): The key to send. Can be a single character, or a special key (enter, space, backspace, 
            tab, shift, ctrl, alt, esc, delete, left, right, up, down).
        """
        self.ensure_connected() 

        # Handle special keys
        key_aliases = {
            'enter': win32con.VK_RETURN, 'space': win32con.VK_SPACE, 'backspace': win32con.VK_BACK, 'tab': win32con.VK_TAB,
            'shift': win32con.VK_SHIFT, 'ctrl': win32con.VK_CONTROL, 'alt': win32con.VK_MENU, 'esc': win32con.VK_ESCAPE,
            'delete': win32con.VK_DELETE, 'left': win32con.VK_LEFT, 'right': win32con.VK_RIGHT, 'up': win32con.VK_UP,
            'down': win32con.VK_DOWN
        }

        if key in key_aliases:
            vk_code = key_aliases[key]
        elif len(key) == 1:
            # For single characters, get the virtual key code
            vk_code = win32api.VkKeyScan(key) & 0xFF
        else:
            logger.error(f"Invalid key passed to send_key: {key}")
            return

        # Send the key to the game window
        win32api.SendMessage(self.game_hwnd, win32con.WM_KEYDOWN, vk_code, 0)
        time.sleep(0.03)
        win32api.SendMessage(self.game_hwnd, win32con.WM_KEYUP, vk_code, 0)
        time.sleep(0.02)
    
    def _recognize_region(self, region: tuple[float, float, float, float] | str) -> tuple[float, float, float, float] | None:
        if isinstance(region, str):
            region_presets = {
                'left': (0, 0, 0.3, 1),
                'right': (0.7, 0, 1, 1),
                'top': (0, 0, 1, 0.3),
                'bottom': (0, 0.7, 1, 1),
                'left_top': (0, 0, 0.3, 0.3),
                'right_top': (0.7, 0, 1, 0.3),
                'left_bottom': (0, 0.7, 0.3, 1),
                'right_bottom': (0.7, 0.7, 1, 1),
            }

            if region not in region_presets:
                logger.error(f'Invalid region: {region}. Ignoring...')
                return None
            
            region = region_presets[region]
        
        return region

    def click_ocr(
        self, 
        pattern: str, 
        region: tuple[float, float, float, float] | str = None, 
        max_retries: int = 5, 
        press_time: float = 0.05
    ):
        """
        Click on the game window at the specified coordinates.
        Args:
            pattern (str): The pattern to search for, can be a regex pattern.
            region (tuple[float, float, float, float] | str): The region to search in.
        """
        self.ensure_connected()

        region = self._recognize_region(region)
        
        for _ in range(max_retries):
            if region is None:
                screenshot = self.screenshot()
            else:
                screenshot = self.screenshot_region(*region)
            
            if screenshot is None:
                return
            
            results = ocr_pattern(screenshot, pattern)

            if len(results) != 1:
                logger.warning(f'Found {len(results)} results for pattern: {pattern}. Retrying...')
                time.sleep(1)
                continue

            result = results[0]
            width, height = self.get_app_window_size()
            x, y = (result.box[0] + result.box[2]) / 2 / width, (result.box[1] + result.box[3]) / 2 / height

            if region is not None:
                self.click(x + region[0], y + region[1], rand=False, press_time=press_time)
            else:
                self.click(x, y, rand=False, press_time=press_time)

            return
        
        logger.critical(f'Failed to click on pattern: {pattern} after {max_retries} retries.')
        # screenshot.show()
        raise Exception(f'Failed to click on pattern: {pattern} after {max_retries} retries.')
        
    def click_img_template(
        self, 
        target: Element, 
        region: tuple[float, float, float, float] | str = None, 
        max_retries: int = 5, 
        debug: bool = False, 
        tolerant: bool = False
    ):
        """
        Find a template image on the screen and click its center.
        Args:
            target (Element): The template image to search for.
            region (tuple[float, float, float, float] | str, optional): The region to search in. Defaults to None (full screen).
            max_retries (int, optional): Number of retries if the image is not found. Defaults to 5.
            debug (bool, optional): Whether to display matching visualization. Defaults to False.
        """
        self.ensure_connected()

        region_coords = self._recognize_region(region)

        for i in range(max_retries):
            if region_coords is None:
                screenshot = self.screenshot()
            else:
                screenshot = self.screenshot_region(*region_coords)
            
            if screenshot is None:
                logger.warning("Failed to get screenshot, retrying...")
                time.sleep(1)
                continue

            logger.info(f"Matching template: {target.value}")
            coords = match_single_object_template(target.to_img(), screenshot, debug=debug)

            if coords is None:
                if not tolerant:
                    logger.warning(f'Template not found. Retrying... ({i+1}/{max_retries})')
                time.sleep(1)
                continue

            center_x, center_y = coords
            
            width, height = self.get_app_window_size()
            x_ratio = center_x / width
            y_ratio = center_y / height
            
            if region_coords is not None:
                self.click(x_ratio + region_coords[0], y_ratio + region_coords[1])
            else:
                self.click(x_ratio, y_ratio)
            
            return
        
        if not tolerant:
            logger.critical(f'Failed to find target after {max_retries} retries.')
            # screenshot.show()
            raise Exception('Failed to find target.')
        
        