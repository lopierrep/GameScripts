import sys
import os
import pyautogui
import time
import random

_DOFUS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _DOFUS_DIR not in sys.path:
    sys.path.insert(0, _DOFUS_DIR)

from shared.mouse import smooth_move

pyautogui.FAILSAFE = True



def run_race_loop(calibration, is_running, on_status, on_race_count):
    race_count = 0

    while is_running():
        delay = random.uniform(0.5, 1)
        on_status(f"Iniciando en {delay:.1f}s...")
        time.sleep(delay)
        if not is_running():
            break

        race_count += 1
        on_race_count(race_count)

        # 1. Click NPC
        npc = calibration["NPCLocation"]
        tx = npc[0] + random.uniform(-2.5, 2.5)
        ty = npc[1] + random.uniform(-2.5, 2.5)
        on_status("Moviendo al NPC...")
        smooth_move(tx, ty, step_delay=random.uniform(0.000001, 0.000003))
        pyautogui.click()
        time.sleep(random.uniform(0.5, 1))
        if not is_running():
            break

        # 2. Click race option (weighted)
        option_key = random.choices(
            ["OptionLocation1", "OptionLocation2", "OptionLocation3", "OptionLocation4"],
            weights=[5, 5, 5, 85]
        )[0]
        opt = calibration[option_key]
        tx = opt[0] + random.uniform(-5, 5)
        ty = opt[1] + random.uniform(-2.5, 2.5)
        on_status("Seleccionando opción...")
        smooth_move(tx, ty, step_delay=random.uniform(0.000001, 0.000003))
        pyautogui.click()
        time.sleep(random.uniform(2, 3))
        if not is_running():
            break

        # 3. Click start race
        btn = calibration["StartButtonLocation"]
        tx = btn[0] + random.uniform(-15, 15)
        ty = btn[1] + random.uniform(-15, 15)
        on_status("Iniciando carrera...")
        smooth_move(tx, ty, step_delay=random.uniform(0.000001, 0.000003))
        pyautogui.click()

        # 4. Wait race duration
        race_dur = random.uniform(32, 35)
        end_time = time.time() + race_dur
        while is_running() and time.time() < end_time:
            remaining = end_time - time.time()
            on_status(f"Carrera en curso... {remaining:.0f}s")
            time.sleep(0.5)

    on_status("Proceso terminado.")
