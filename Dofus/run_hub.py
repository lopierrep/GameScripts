"""Punto de entrada para PyInstaller — no manipula sys.path (PyInstaller lo gestiona)."""
import sys
import os

# En modo desarrollo, asegurar que el directorio raíz esté en sys.path
if not getattr(sys, "frozen", False):
    _root = os.path.dirname(os.path.abspath(__file__))
    if _root not in sys.path:
        sys.path.insert(0, _root)

from hub.main import main

if __name__ == "__main__":
    main()
