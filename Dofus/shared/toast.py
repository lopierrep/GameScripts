import tkinter as tk

_active_toast: tk.Label | None = None


def show_copy_toast(root, name: str, *, bg: str, fg: str):
    """Muestra una notificación temporal de copiado en la esquina inferior derecha."""
    global _active_toast
    if _active_toast is not None:
        _active_toast.destroy()

    toast = tk.Label(
        root, text=f"✓ Copiado: {name}",
        bg=bg, fg=fg,
        font=("Segoe UI", 9, "bold"), padx=12, pady=6,
        relief="flat",
    )
    toast.place(relx=1.0, rely=1.0, anchor="se", x=-16, y=-16)
    _active_toast = toast
    root.after(1800, lambda: _dismiss(toast))


def _dismiss(toast: tk.Label):
    global _active_toast
    if _active_toast is toast:
        _active_toast = None
    toast.destroy()
