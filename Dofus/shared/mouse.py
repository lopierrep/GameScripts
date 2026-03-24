import random
import time

import pyautogui


def smooth_move(x, y, steps=4, step_delay=0.002):
    x0, y0 = pyautogui.position()
    for i in range(1, steps + 1):
        t = i / steps
        pyautogui.moveTo(
            x0 + (x - x0) * t + random.randint(-2, 2),
            y0 + (y - y0) * t + random.randint(-2, 2),
        )
        time.sleep(step_delay)
    pyautogui.moveTo(x, y)
