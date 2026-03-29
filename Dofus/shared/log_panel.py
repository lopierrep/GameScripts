"""
LogPanel – Panel de log reutilizable para cualquier UI.
=======================================================
Widget tk.Frame con text area, close button, scrollbar y auto-tagging.
"""

import tkinter as tk

from shared.colors import C
from shared.font import FONT, SMALL


def _auto_tag(text: str) -> str:
    u = text.upper()
    if "[OK]"     in u: return "ok"
    if "[SKIP]"   in u: return "skip"
    if "[ERROR]"  in u or "ERROR —" in u: return "error"
    if "[DONE]"   in u: return "done"
    if "[AVISO]"  in u: return "warn"
    if "[MANUAL]" in u: return "manual"
    return "info"


class LogPanel(tk.Frame):
    """
    Panel de log colapsable: close button, Text widget, scrollbar.

    Uso:
        self.log_panel = LogPanel(parent, root, font_family="Consolas")
        self.log_panel.log("Mensaje", "ok")
        self.log_panel.show(fill="x", padx=10, pady=(0, 8))
        self.log_panel.hide()
        self.log_panel.clear()
    """

    def __init__(self, parent, root: tk.Tk, *, font_family: str = None):
        super().__init__(parent, bg=C["surface"])
        self._root = root
        _font = font_family or FONT

        btn_close = tk.Button(
            self, text="x", bg=C["red"], fg=C["bg"],
            font=(_font, SMALL, "bold"), relief="flat", bd=0,
            padx=6, pady=1, cursor="hand2", command=self.hide)
        btn_close.pack(side="top", anchor="ne", padx=4, pady=(4, 0))

        self._text = tk.Text(
            self, bg=C["surface"], fg=C["text"],
            font=(_font, SMALL), relief="flat",
            state="disabled", wrap="word", height=6,
            selectbackground=C["accent"],
        )
        sb = tk.Scrollbar(
            self, orient="vertical", command=self._text.yview,
            bg=C["surface"], troughcolor=C["bg"],
            activebackground=C["dim"], highlightthickness=0,
            borderwidth=0, width=12)
        self._text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._text.pack(side="left", fill="both", expand=True, padx=2, pady=2)

        for tag, color in (
            ("ok",     C["green"]),
            ("skip",   C["dim"]),
            ("error",  C["red"]),
            ("info",   C["accent"]),
            ("warn",   C["yellow"]),
            ("manual", C["yellow"]),
            ("done",   C["green"]),
        ):
            self._text.tag_config(tag, foreground=color)

    # ── API pública ──────────────────────────────────────────────────────

    def log(self, text: str, tag: str = None):
        """Thread-safe: programa append en el hilo principal."""
        self._root.after(0, self._append, text, tag)

    def clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")

    def show(self, **pack_kwargs):
        if not self.winfo_manager():
            self.pack(**pack_kwargs)

    def hide(self):
        self.pack_forget()

    # ── Internos ─────────────────────────────────────────────────────────

    def _write(self, text: str, tag: str):
        self._text.configure(state="normal")
        self._text.insert("end", text + "\n", tag)
        self._text.see("end")
        self._text.configure(state="disabled")

    def _append(self, raw: str, tag: str = None):
        if "\r" in raw and not raw.startswith("\n"):
            parts = raw.split("\r")
            text = parts[-1].strip()
            if not text:
                return
            self._text.configure(state="normal")
            idx = self._text.index("end-2l linestart")
            self._text.delete(idx, "end-1c")
            self._text.configure(state="disabled")
            self._write(text, tag or _auto_tag(text))
            return
        text = raw.strip()
        if not text:
            return
        self._write(text, tag or _auto_tag(text))
