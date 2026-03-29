"""Configuracion compartida para sincronizacion via Google Sheets."""

import os

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
SPREADSHEET_ID   = "1S7B58S_tkt4kx4vopK9fVzP9rMbWybUC3xrWUrqBuT8"
SCOPES           = ["https://www.googleapis.com/auth/spreadsheets"]
