"""
Trolichas - Configuración centralizada
=======================================
Todos los parámetros ajustables del proyecto en un solo lugar.
"""

# ── Opciones de carrera ──────────────────────────────────────────────────────
# Pesos de cada opción al elegir carrera (OptionLocation1..4)
OPTION_WEIGHTS = [5, 5, 5, 85]

# ── Timing (segundos) ────────────────────────────────────────────────────────
# Rango de espera antes de iniciar cada ciclo
DELAY_BEFORE_CYCLE = (0.5, 1.0)
# Rango de espera tras click en NPC
DELAY_AFTER_NPC = (0.5, 1.0)
# Rango de espera tras seleccionar opción
DELAY_AFTER_OPTION = (2, 3)
# Rango de duración estimada de la carrera
RACE_DURATION = (32, 35)
# Segundos estimados por ticket (para cálculo de ETA)
SECONDS_PER_TICKET = 39

# ── Movimiento del ratón ─────────────────────────────────────────────────────
# Jitter en píxeles al hacer click en cada elemento
JITTER_NPC = (-2.5, 2.5)
JITTER_OPTION_X = (-5, 5)
JITTER_OPTION_Y = (-2.5, 2.5)
JITTER_START_BTN = (-15, 15)
# Rango de delay entre pasos del movimiento suave
MOUSE_STEP_DELAY = (0.001, 0.003)

# ── Alerta de sin tickets ───────────────────────────────────────────────────
ALERT_BEEP_FREQ = 800       # frecuencia en Hz
ALERT_BEEP_DURATION = 300   # duración en ms
ALERT_BEEP_INTERVAL = 3     # segundos entre beeps

# ── Hotkey ───────────────────────────────────────────────────────────────────
STOP_HOTKEY = "s"
