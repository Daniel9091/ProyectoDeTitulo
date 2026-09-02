"""
Visual standards for NSim analysis charts.

Edit this file to change any color, size, or style — one edit propagates
to all analysis modules. No hex literals should appear in the analysis
modules themselves; import from here instead.
"""
import matplotlib.pyplot as plt

# ── Surfaces ─────────────────────────────────────────────────────────────────
SURFACE      = "#ffffff"   # chart and figure background (white for printed report)
EDGE_COLOR   = "#ffffff"   # bar/wedge borders (blends with background)
TEXT_PRIMARY = "#1a1a2e"   # axis labels, tick labels, legend text
GRID_COLOR   = "#e0e0e0"   # grid lines

# ── Data palette ─────────────────────────────────────────────────────────────
# Light-mode palette (surface #ffffff). Semantic roles are fixed.
# Slightly darker than the original dark-mode values to hold contrast on white.
# Reference: dataviz palette.md — light-adapted from dark slots 1, 5, 6, 7.
PALETTE = {
    "azul":    "#2271d1",   # activo, con pasajeros, útil
    "verde":   "#157a57",   # correcto, llegó a destino
    "naranja": "#c44b1a",   # vacío, sin pasajeros, incorrecto
    "violeta": "#6b5ed6",   # distribuciones de una sola serie
}

# ── Figure sizes ─────────────────────────────────────────────────────────────
FIG_SQUARE = (5, 5)    # single pie chart
FIG_BAR    = (7, 4)    # single bar chart
FIG_DUAL   = (10, 5)   # side-by-side pies or bars
FIG_WIDE   = (12, 5)   # dual histograms

# ── Reusable kwargs ──────────────────────────────────────────────────────────
TITLE_SIZE = 13
BAR_KWARGS = {"edgecolor": EDGE_COLOR}
PIE_KWARGS = {"wedgeprops": {"edgecolor": EDGE_COLOR, "linewidth": 2}}

# ── Theme setup ──────────────────────────────────────────────────────────────
def setup() -> None:
    """Apply light theme to all subsequent matplotlib figures (white background for report)."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor":   SURFACE,
        "axes.edgecolor":   TEXT_PRIMARY,
        "axes.labelcolor":  TEXT_PRIMARY,
        "xtick.color":      TEXT_PRIMARY,
        "ytick.color":      TEXT_PRIMARY,
        "text.color":       TEXT_PRIMARY,
        "grid.color":       GRID_COLOR,
        "grid.linestyle":   "--",
        "grid.alpha":       0.5,
    })

def fig_for_stations(n_stations: int, height: float = 4.5) -> tuple:
    """Ancho dinámico para gráficos con muchas estaciones en eje X."""
    width = max(8, min(n_stations * 0.55, 20))
    return (width, height)


