import pyautogui
import keyboard
import time
import random
import json
import os

CALIBRATION_FILE = os.path.join(os.path.dirname(__file__), "calibration.json")

CALIBRATION_POINTS = [
    ("NPCLocation",          "el NPC"),
    ("OptionLocation1",      "la opción de raza 1"),
    ("OptionLocation2",      "la opción de raza 2"),
    ("OptionLocation3",      "la opción de raza 3"),
    ("OptionLocation4",      "la opción de raza 4 (la más frecuente, 85%)"),
    ("StartButtonLocation",  "el botón de iniciar carrera"),
]

# Security delay to give you time to move the mouse to a corner if something goes wrong
pyautogui.FAILSAFE = True


def RunCalibration():
    print("\n=== CALIBRACIÓN ===")
    print("Para cada punto, mueve el ratón a la posición correcta en pantalla y pulsa ENTER.")
    print("Pulsa ESC en cualquier momento para cancelar.\n")
    calibration = {}
    for key, description in CALIBRATION_POINTS:
        while True:
            print(f"  Mueve el ratón a: {description}")
            print("  Pulsa C para capturar la posición...")
            event = keyboard.read_event()
            while event.event_type != keyboard.KEY_DOWN:
                event = keyboard.read_event()
            pressed = event.name
            if pressed == "esc":
                print("Calibración cancelada.")
                return None
            if pressed == "c":
                pos = pyautogui.position()
                calibration[key] = [pos.x, pos.y]
                print(f"  ✓ {key} = {calibration[key]}\n")
                break
    with open(CALIBRATION_FILE, "w") as f:
        json.dump(calibration, f, indent=2)
    print(f"Calibración guardada en {CALIBRATION_FILE}\n")
    return calibration


def LoadCalibration():
    if not os.path.exists(CALIBRATION_FILE):
        print(f"No se encontró el archivo de calibración ({CALIBRATION_FILE}).")
        return RunCalibration()
    with open(CALIBRATION_FILE, "r") as f:
        calibration = json.load(f)
    print(f"Calibración cargada desde {CALIBRATION_FILE}")
    return calibration


def CustomMoveWithNoise(x1, y1, x2, y2):
    Steps = int(random.uniform(3, 5))
    for i in range(Steps):
        t = i / Steps
        x = x1 + (x2 - x1) * t + random.randint(-2, 2)
        y = y1 + (y2 - y1) * t + random.randint(-2, 2)
        pyautogui.moveTo(x, y)
        time.sleep(random.uniform(0.000001, 0.000003))
    pyautogui.moveTo(x2, y2)


calibration = LoadCalibration()
if calibration is None:
    print("No se puede continuar sin calibración. Saliendo.")
    exit(1)

ManualStop = False
def OnPress(event):
    global ManualStop
    print("event.name: ", event.name)
    if event.name == "y":
        ManualStop = True
        print("Press wil not repeat after this iteration")

keyboard.on_press(OnPress)

while not ManualStop:

    RandomStartTime = random.uniform(0.5, 1)
    print(f"Starting in {RandomStartTime} seconds...")
    time.sleep(RandomStartTime)
    print("Starting process...")

    # 1️ Move and click on NPC
    npc = calibration["NPCLocation"]
    NPCLocation = (npc[0] + random.uniform(-2.5, 2.5), npc[1] + random.uniform(-2.5, 2.5))
    print("Moving to NPC location: ", NPCLocation)
    x1, y1 = pyautogui.position()
    CustomMoveWithNoise(x1, y1, NPCLocation[0], NPCLocation[1])
    pyautogui.click()
    time.sleep(random.uniform(0.5, 1))

    # 3️ Move and click in the race option
    option_key = random.choices(
        ["OptionLocation1", "OptionLocation2", "OptionLocation3", "OptionLocation4"],
        weights=[5, 5, 5, 85]
    )[0]
    opt = calibration[option_key]
    OptionLocation = (opt[0] + random.uniform(-5, 5), opt[1] + random.uniform(-2.5, 2.5))
    print("Moving to option location: ", OptionLocation)
    x1, y1 = pyautogui.position()
    CustomMoveWithNoise(x1, y1, OptionLocation[0], OptionLocation[1])
    pyautogui.click()
    time.sleep(random.uniform(2, 3))

    # 5️ Move and click on Start Race
    print("Pressing Start Race button...")
    btn = calibration["StartButtonLocation"]
    StartButtonLocation = (btn[0] + random.uniform(-15.0, 15.0), btn[1] + random.uniform(-15.0, 15.0))
    x1, y1 = pyautogui.position()
    CustomMoveWithNoise(x1, y1, StartButtonLocation[0], StartButtonLocation[1])
    pyautogui.click()

    RaceDuration = random.uniform(32, 35)
    print(f"Waiting for {RaceDuration} seconds for the race to end ...")
    time.sleep(RaceDuration)

print("Process finished.")
