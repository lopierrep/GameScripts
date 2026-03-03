


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

def CustomMoveWithNoise(x1, y1, x2, y2):
    Steps = int(random.uniform(3, 5))
    for i in range(Steps):
        t = i / Steps
        x = x1 + (x2 - x1) * t + random.randint(-2, 2)
        y = y1 + (y2 - y1) * t + random.randint(-2, 2)
        pyautogui.moveTo(x, y)
        time.sleep(random.uniform(0.000001, 0.000003))
    pyautogui.moveTo(x2, y2)

IsPC = True
PC_NPCLocation = (980, 985), (480, 485)
PC_OptionLocation = (1155, 1165), (600, 605)
PC_StartButtonLocation = (1400, 1540), (920, 945)
PC_EscButtonLocation = (970, 1030), (795, 810)

Laptop_NPCLocation = (980, 985), (480, 485)
Laptop_OptionLocation = (1155, 1165), (600, 605)
Laptop_StartButtonLocation = (1450, 1580), (915, 940)
Laptop_EscButtonLocation = (925, 990), (865, 880)
    
while not ManualStop:
    keyboard.on_press(OnPress)

    # print(pyautogui.position())
    # time.sleep(1)
    RandomStartTime = random.uniform(0.5, 1)
    print(f"Starting in {RandomStartTime} seconds...")
    time.sleep(RandomStartTime)
    print("Starting process...")

    # 1️ Guardar posición originaly
    NPCLocation = PC_NPCLocation if IsPC else Laptop_NPCLocation
    NPCLocation = (random.uniform(NPCLocation[0][0], NPCLocation[0][1]), random.uniform(NPCLocation[1][0], NPCLocation[1][1]))
    # 2️ Click en posición actual
    print("Moving to NPC location: ", NPCLocation)
    x1, y1 = pyautogui.position()
    CustomMoveWithNoise(x1, y1, NPCLocation[0], NPCLocation[1])
    pyautogui.click()    
    SleepTime = random.uniform(0.5, 1)
    time.sleep(SleepTime)
    
    # 3️ Mover a coordenadas específicas
    OptionLocation = PC_OptionLocation if IsPC else Laptop_OptionLocation
    OptionLocation = (random.uniform(OptionLocation[0][0], OptionLocation[0][1]), random.uniform(OptionLocation[1][0], OptionLocation[1][1]))
    print("Moving to option location: ", OptionLocation)
    x1, y1 = pyautogui.position()
    CustomMoveWithNoise(x1, y1, OptionLocation[0], OptionLocation[1])
    pyautogui.click()
    SleepTime = random.uniform(2, 3)
    time.sleep(SleepTime)

    # 5️ Start Race
    print("Pressing F1 to start the race...")
    StartButtonLocation = PC_StartButtonLocation if IsPC else Laptop_StartButtonLocation
    StartButtonLocation = (random.uniform(StartButtonLocation[0][0], StartButtonLocation[0][1]), random.uniform(StartButtonLocation[1][0], StartButtonLocation[1][1]))
    x1, y1 = pyautogui.position()
    CustomMoveWithNoise(x1, y1, StartButtonLocation[0], StartButtonLocation[1])
    pyautogui.click()

    RaceDuration = random.uniform(32, 35)
    print(f"Waiting for {RaceDuration} seconds for the race to end ...")
    time.sleep(RaceDuration)

    # 7️ Press ESC to exit result screen
    EscButtonLocation = PC_EscButtonLocation if IsPC else Laptop_EscButtonLocation
    EscButtonLocation = (random.uniform(EscButtonLocation[0][0], EscButtonLocation[0][1]), random.uniform(EscButtonLocation[1][0], EscButtonLocation[1][1]))
    print("Moving to ESC button location: ", EscButtonLocation)
    x1, y1 = pyautogui.position()
    CustomMoveWithNoise(x1, y1, EscButtonLocation[0], EscButtonLocation[1])
    CustomMoveWithNoise(pyautogui.position()[0], pyautogui.position()[1], EscButtonLocation[0], EscButtonLocation[1])
    pyautogui.click()

print("Process finished.")