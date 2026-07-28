"""
Visual standards for NSim analysis charts.

Edit this file to change any color, size, or style — one edit propagates
to all analysis modules. No hex literals should appear in the analysis
modules themselves; import from here instead.
"""
import matplotlib.pyplot as plt

# ── Surfaces ─────────────────────────────────────────────────────────────────
SURFACE      = "#1e1e2e"   # chart and figure background (Catppuccin Mocha base)
EDGE_COLOR   = "#1e1e2e"   # bar/wedge borders (blends with background)
TEXT_PRIMARY = "#cdd6f4"   # axis labels, tick labels, legend text
GRID_COLOR   = "#313244"   # grid lines

# ── Data palette ─────────────────────────────────────────────────────────────
# Validated with dataviz skill (dark mode, surface #1e1e2e).
# All 4 slots pass CVD separation, contrast, lightness, and chroma checks.
# Reference: dataviz palette.md — dark slots 1, 5, 6, 7.
PALETTE = {
    "azul":    "#3987e5",   # slot 1 — active, with passengers, useful
    "verde":   "#199e70",   # slot 5 — correct, arrived at destination
    "naranja": "#d95926",   # slot 6 — idle, without passengers, wrong
    "violeta": "#9085e9",   # slot 7 — single-series distributions
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
    """Apply dark Catppuccin Mocha theme to all subsequent matplotlib figures."""
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


