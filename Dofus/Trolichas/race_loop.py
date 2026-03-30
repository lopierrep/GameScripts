import sys
import os
import pyautogui
import time
import random

_DOFUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _DOFUS_DIR not in sys.path:
    sys.path.insert(0, _DOFUS_DIR)

from shared.automation.mouse import smooth_move
from Trolichas.config import (
    DELAY_BEFORE_CYCLE, DELAY_AFTER_NPC, DELAY_AFTER_OPTION, RACE_DURATION,
    JITTER_NPC, JITTER_OPTION_X, JITTER_OPTION_Y, JITTER_START_BTN,
    MOUSE_STEP_DELAY, OPTION_WEIGHTS,
)

pyautogui.FAILSAFE = True


_OPTION_KEYS = ["OptionLocation1", "OptionLocation2", "OptionLocation3", "OptionLocation4"]


def run_race_loop(calibration, is_running, on_status, on_race_count, on_consume_ticket=None):
    race_count = 0

    while is_running():
        if on_consume_ticket and not on_consume_ticket():
            on_status("Sin tickets.")
            break
        delay = random.uniform(*DELAY_BEFORE_CYCLE)
        on_status(f"Iniciando en {delay:.1f}s...")
        time.sleep(delay)
        if not is_running():
            break

        try:
            # 1. Click NPC
            npc = calibration["NPCLocation"]
            tx = npc[0] + random.uniform(*JITTER_NPC)
            ty = npc[1] + random.uniform(*JITTER_NPC)
            on_status("Moviendo al NPC...")
            smooth_move(tx, ty, step_delay=random.uniform(*MOUSE_STEP_DELAY))
            pyautogui.click()
            time.sleep(random.uniform(*DELAY_AFTER_NPC))
            if not is_running():
                break

            # 2. Click race option (weighted)
            option_key = random.choices(_OPTION_KEYS, weights=OPTION_WEIGHTS)[0]
            opt = calibration[option_key]
            tx = opt[0] + random.uniform(*JITTER_OPTION_X)
            ty = opt[1] + random.uniform(*JITTER_OPTION_Y)
            on_status("Seleccionando opción...")
            smooth_move(tx, ty, step_delay=random.uniform(*MOUSE_STEP_DELAY))
            pyautogui.click()
            time.sleep(random.uniform(*DELAY_AFTER_OPTION))
            if not is_running():
                break

            # 3. Click start race
            btn = calibration["StartButtonLocation"]
            tx = btn[0] + random.uniform(*JITTER_START_BTN)
            ty = btn[1] + random.uniform(*JITTER_START_BTN)
            on_status("Iniciando carrera...")
            smooth_move(tx, ty, step_delay=random.uniform(*MOUSE_STEP_DELAY))
            pyautogui.click()

        except KeyError as e:
            on_status(f"Error: falta clave de calibración {e}")
            break

        race_count += 1
        on_race_count(race_count)

        # 4. Wait race duration
        race_dur = random.uniform(*RACE_DURATION)
        end_time = time.time() + race_dur
        while is_running() and time.time() < end_time:
            remaining = end_time - time.time()
            on_status(f"Carrera en curso... {remaining:.0f}s")
            time.sleep(0.5)

    on_status("Proceso terminado.")
