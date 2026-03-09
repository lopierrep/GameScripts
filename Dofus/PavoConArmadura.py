


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


NPCLocation = (982.5, 482.5)
OptionLocation = (1160, 602.5)
StartButtonLocation = (1515, 930)
EscButtonLocation = (955, 870)

UseCustomValues = True

CustomNPCLocation = (982.5, 482.5)
CustomOptionLocation = (1160, 602.5)
CustomStartButtonLocation = (1515, 930)
CustomEscButtonLocation = (955, 870)
    
while not ManualStop:
    keyboard.on_press(OnPress)

    # print(pyautogui.position())
    # time.sleep(1)
    RandomStartTime = random.uniform(0.5, 1)
    print(f"Starting in {RandomStartTime} seconds...")
    time.sleep(RandomStartTime)
    print("Starting process...")

    # 1️ Guardar posición original
    NPCLocation = CustomNPCLocation if UseCustomValues else NPCLocation
    NPCLocation = ((NPCLocation[0]+random.uniform(-2.5, 2.5)), (NPCLocation[1]+random.uniform(-2.5, 2.5)))
    # 2️ Click en posición actual
    print("Moving to NPC location: ", NPCLocation)
    x1, y1 = pyautogui.position()
    CustomMoveWithNoise(x1, y1, NPCLocation[0], NPCLocation[1])
    pyautogui.click()    
    SleepTime = random.uniform(0.5, 1)
    time.sleep(SleepTime)
    
    # 3️ Mover a coordenadas específicas
    OptionLocation = CustomOptionLocation if UseCustomValues else OptionLocation
    OptionLocation = ((OptionLocation[0]+random.uniform(-5, 5)), (OptionLocation[1]+random.uniform(-2.5, 2.5)))
    print("Moving to option location: ", OptionLocation)
    x1, y1 = pyautogui.position()
    CustomMoveWithNoise(x1, y1, OptionLocation[0], OptionLocation[1])
    pyautogui.click()
    SleepTime = random.uniform(2, 3)
    time.sleep(SleepTime)

    # 5️ Start Race
    print("Pressing F1 to start the race...")
    StartButtonLocation = CustomStartButtonLocation if UseCustomValues else StartButtonLocation
    StartButtonLocation = ((StartButtonLocation[0]+random.uniform(-15.0, 15.0)), (StartButtonLocation[1]+random.uniform(-15.0, 15.0)))
    x1, y1 = pyautogui.position()
    CustomMoveWithNoise(x1, y1, StartButtonLocation[0], StartButtonLocation[1])
    pyautogui.click()

    RaceDuration = random.uniform(32, 35)
    print(f"Waiting for {RaceDuration} seconds for the race to end ...")
    time.sleep(RaceDuration)

    # 7️ Clic ESC to exit result screen
    EscButtonLocation = CustomEscButtonLocation if UseCustomValues else EscButtonLocation
    EscButtonLocation = ((EscButtonLocation[0]+random.uniform(-15.0, 15.0)), (EscButtonLocation[1]+random.uniform(-15.0, 15.0)))
    print("Moving to ESC button location: ", EscButtonLocation)
    x1, y1 = pyautogui.position()
    CustomMoveWithNoise(x1, y1, EscButtonLocation[0], EscButtonLocation[1])
    CustomMoveWithNoise(pyautogui.position()[0], pyautogui.position()[1], EscButtonLocation[0], EscButtonLocation[1])
    pyautogui.click()

print("Process finished.")