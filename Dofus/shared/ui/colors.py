# Paleta de colores compartida entre todas las UIs (tema oscuro)
C = {
    "bg":         "#191724",
    "bg2":        "#161520",
    "surface":    "#1f1d2e",
    "overlay":    "#26233a",
    "border":     "#2a283e",
    "accent":     "#89b4fa",
    "accent_bg":  "#1c2842",
    "green":      "#a6e3a1",
    "green_bg":   "#1c3027",
    "red":        "#f38ba8",
    "yellow":     "#f9e2af",
    "orange":     "#fab387",
    "mauve":      "#cba6f7",
    "text":       "#cdd6f4",
    "subtext":    "#908caa",
    "dim":        "#6c7086",
    "today":      "#2d3250",
    "alt_row":    "#252535",
}


def style_scrollbar(style):
    """Aplica estilo unificado al TScrollbar."""
    style.configure("TScrollbar",
                    background=C["surface"], troughcolor=C["bg"],
                    bordercolor=C["bg"], arrowcolor=C["dim"],
                    borderwidth=0, arrowsize=12, relief="flat")
