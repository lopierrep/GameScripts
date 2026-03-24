import json
import os
import sys

if getattr(sys, "frozen", False):
    BASE_PATH = os.path.dirname(sys.executable)
else:
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))

CALIBRATION_FILE = os.path.join(BASE_PATH, "calibration.json")

CALIBRATION_POINTS = [
    ("NPCLocation",         "el NPC"),
    ("OptionLocation1",     "la opción de raza 1"),
    ("OptionLocation2",     "la opción de raza 2"),
    ("OptionLocation3",     "la opción de raza 3"),
    ("OptionLocation4",     "la opción de raza 4 (85%)"),
    ("StartButtonLocation", "el botón de iniciar carrera"),
]


def load_calibration():
    if not os.path.exists(CALIBRATION_FILE):
        return None
    with open(CALIBRATION_FILE, "r") as f:
        return json.load(f)
