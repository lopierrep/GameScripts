


import pyautogui
import keyboard
import time
import random


# Tiempo de seguridad para que puedas mover el mouse a una esquina si algo falla
pyautogui.FAILSAFE = True

ManualStop = False
def OnPress(event):
    global ManualStop
    print("event.name: ", event.name)
    if event.name == "y":
        ManualStop = True
        print("Press wil not repeat after this iteration")

while not ManualStop:
    keyboard.on_press(OnPress)

    # print(pyautogui.position())
    # time.sleep(1)
    RandomStartTime = random.uniform(0.5, 1)
    print(f"Starting in {RandomStartTime} seconds...")
    time.sleep(RandomStartTime)
    print("Starting process...")

    # 1️ Guardar posición originaly
    NPCLocation = (random.uniform(980, 985), random.uniform(480, 485))
    # 2️ Click en posición actual
    print("Moving to NPC location: ", NPCLocation)
    MoveDuration = random.uniform(0.25, 0.5)
    pyautogui.moveTo(NPCLocation[0], NPCLocation[1], duration=MoveDuration)
    pyautogui.click()    
    SleepTime = random.uniform(0.5, 1)
    time.sleep(SleepTime)
    
    # 3️ Mover a coordenadas específicas
    OptionLocation = (random.uniform(1155, 1165), random.uniform(600, 605))
    MoveDuration = random.uniform(0.25, 0.5)
    print("Moving to option location: ", OptionLocation)
    pyautogui.moveTo(OptionLocation[0], OptionLocation[1], duration=MoveDuration)
    pyautogui.click()
    SleepTime = random.uniform(2, 3)
    time.sleep(SleepTime)

    # 5️ Start Race
    print("Pressing F1 to start the race...")
    StartButtonLocation = (random.uniform(1400, 1540), random.uniform(920, 945))
    MoveDuration = random.uniform(0.25, 0.5)
    pyautogui.moveTo(StartButtonLocation[0], StartButtonLocation[1], duration=MoveDuration)
    pyautogui.click()

    RaceDuration = random.uniform(32, 35)
    print(f"Waiting for {RaceDuration} seconds for the race to end ...")
    time.sleep(RaceDuration)

    # 7️ Press ESC to exit result screen
    EscButtonLocation = (random.uniform(970, 1030), random.uniform(795, 810))
    print("Moving to ESC button location: ", EscButtonLocation)
    MoveDuration = random.uniform(0.25, 0.5)
    pyautogui.moveTo(EscButtonLocation[0], EscButtonLocation[1], duration=MoveDuration)
    pyautogui.click()

print("Process finished.")