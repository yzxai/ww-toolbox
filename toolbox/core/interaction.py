import win32gui, win32ui, win32api, win32con
import numpy as np
import time
import random

from ctypes import windll
from PIL import Image
from toolbox.utils.logger import logger

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
                    logger.info(f'Connected to game window: {self.game_hwnd}')
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
        logger.warning('Game window not found, attempting to reconnect...')
        status = self.connect()
        if not status:
            logger.critical('Failed to reconnect to game window')
            raise Exception('Failed to reconnect to game window')
        
    def get_app_window_size(self) -> tuple[int, int]:
        """
        Get the size of the game window.
        Returns:
            tuple[int, int]: The width and height of the game window.
        """
        self.ensure_connected()
        left, top, right, bottom = win32gui.GetWindowRect(self.game_hwnd)
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
        logger.info(f'Scale factor: {self.scale_factor}')
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
    
    def click(self, x_ratio: float, y_ratio: float, rand: bool = True):
        """
        Click on the game window at the specified coordinates.
        This method works even if the window is in the background or obscured.
        Args:
            x_ratio (float): The x coordinate of the click.
            y_ratio (float): The y coordinate of the click.
            rand (bool): Whether to randomize the click position.
        """
        self.ensure_connected()

        width, height = self.get_app_window_size()
        scale_factor = self.get_scale_factor()
        x = int(width * x_ratio * scale_factor)
        y = int(height * y_ratio * scale_factor)

        if rand:
            x, y = x + random.randint(-3, 3), y + random.randint(-3, 3)
            # clamp x and y to the window size
            x = max(0, min(x, int(width * scale_factor)))
            y = max(0, min(y, int(height * scale_factor)))
            
        logger.info(f'Clicked at {x_ratio:.2f}, {y_ratio:.2f} ({x}, {y})')
        
        position = win32api.MAKELONG(x, y)

        # This message makes the window think it's being activated by a mouse click.
        # This is crucial for games that check for active state before processing clicks.
        lparam_mouse_activate = win32api.MAKELONG(win32con.HTCLIENT, win32con.WM_LBUTTONDOWN)
        win32api.SendMessage(self.game_hwnd, win32con.WM_MOUSEACTIVATE, self.game_hwnd, lparam_mouse_activate)
        
        # Now send the standard click messages
        win32api.SendMessage(self.game_hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, position)
        time.sleep(0.05)
        win32api.SendMessage(self.game_hwnd, win32con.WM_LBUTTONUP, 0, position)
        time.sleep(0.1)


        
