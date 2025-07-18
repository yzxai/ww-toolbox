import subprocess
import time
import keyboard
import win32gui
from toolbox.core.profile import DiscardScheduler, EchoProfile, EntryCoef
from toolbox.tasks.echo_task import EchoTask
from toolbox.utils.logger import logger
from toolbox.utils.ocr import setup_ocr
from toolbox.utils.generic import get_assets_dir

class EchoManipulate(EchoTask):
    def run(self, coef: EntryCoef, score_thres: float, scheduler: DiscardScheduler, work_state: dict, locked_keys: list = None):
        self.interaction.ensure_connected()

        widget_dir = get_assets_dir() / "widget"
        
        widget_subprocess = subprocess.Popen(
            [str(widget_dir / "widget.exe")],
            stdin = subprocess.PIPE,
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE,
            text = True,
            cwd = str(widget_dir)
        )

        press_count = 0
        
        current_profile, current_state = None, "clear"
        supress = False
        def update_widget_state(state: str, prob: float = None):
            nonlocal current_state
            current_state = state
            if supress or state == "clear":
                widget_subprocess.stdin.write(f"clear\n")
            else:
                widget_subprocess.stdin.write(f"{current_state} {prob}\n")
            widget_subprocess.stdin.flush()

        def on_key_press(event):
            nonlocal press_count, supress
            if event.name.lower() == 'f':
                press_count += 1
                if press_count % 2 == 1:
                    supress = False
                    update_widget_state(current_state)
                else:
                    supress = True
                    update_widget_state("clear")
            elif event.name.lower() == 'g':
                self.interaction.click(0.9, 0.922, move_cursor=True)
                time.sleep(0.5)
                self.interaction.click(0.28, 0.69, move_cursor=True)
                self.interaction.click(0.23, 0.922, move_cursor=True)
                time.sleep(0.5)


                click_count = 20 if current_profile is not None and current_profile.level >= 23 else 5
                for _ in range(click_count):
                    self.interaction.click(0.694, 0.720, move_cursor=True)
                    time.sleep(0.3)

                self.interaction.click(0.0382, 0.282, move_cursor=True)
                time.sleep(0.3)
                self.interaction.click(0.23, 0.922, move_cursor=True)
                time.sleep(1.2)
                self.interaction.send_key("esc")
                time.sleep(0.8)
                self.interaction.send_key("esc")


        keyboard.on_press(on_key_press)
        
        try:
            while True:
                if work_state["cancel_requested"]:
                    break

                if self.is_in_main_page():
                    profile_img = self.interaction.screenshot_region(0.7356, 0.1264, 0.952, 0.458)
                    profile = EchoProfile().from_image(profile_img)
                    if profile != current_profile:
                        current_profile = profile
                        if profile.validate():
                            prob = profile.prob_above_score(coef, score_thres, locked_keys)
                            prob_thres = 0 if profile.level < 5 else scheduler.level_5_9 if profile.level < 10 else scheduler.level_10_14 \
                                if profile.level < 15 else scheduler.level_15_19 if profile.level < 20 else scheduler.level_20_24 if profile.level < 25 else 1
                            if prob < prob_thres:
                                update_widget_state("fail", prob)
                            else:
                                update_widget_state("ok", prob)
                        else:
                            current_profile = None
                            update_widget_state("clear")
                else:
                    current_profile = None
                    update_widget_state("clear")
        finally:
            keyboard.unhook_all()
            widget_subprocess.stdin.close()
            widget_subprocess.terminate()
            widget_subprocess.wait()

if __name__ == "__main__":
    setup_ocr()
    EchoManipulate().run(EntryCoef(), 0, DiscardScheduler())