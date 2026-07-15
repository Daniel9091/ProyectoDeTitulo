"""
Utilidades compartidas para los módulos de análisis.
"""
import json
import duckdb
import matplotlib.pyplot as plt
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "output"


def resolve_run(run_arg: str | None = None) -> Path:
    """
    Resuelve el path al events.jsonl de una corrida.
      - Sin argumento: última línea de runs/index.jsonl
      - Solo run_id (sin runs/): prepone runs/ automáticamente
      - Path completo: lo usa directo
    """
    if run_arg is None:
        index = Path("runs") / "index.jsonl"
        last = json.loads(index.read_text().strip().splitlines()[-1])
        return Path(last["events_path"])
    if run_arg.endswith(".jsonl"):
        return Path(run_arg)
    if run_arg.startswith("runs/"):
        return Path(run_arg) / "events.jsonl"
    return Path("runs") / run_arg / "events.jsonl"


def connect(events_path: Path) -> duckdb.DuckDBPyConnection:
    """Abre DuckDB en memoria con el JSONL registrado como vista 'events'."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW events AS SELECT * FROM read_ndjson_auto('{events_path}')")
    return con


def plot_style():
    """Estilo oscuro consistente para todos los gráficos."""
    plt.rcParams.update({
        "figure.facecolor": "#1e1e2e",
        "axes.facecolor":   "#1e1e2e",
        "axes.edgecolor":   "#cdd6f4",
        "axes.labelcolor":  "#cdd6f4",
        "xtick.color":      "#cdd6f4",
        "ytick.color":      "#cdd6f4",
        "text.color":       "#cdd6f4",
        "grid.color":       "#313244",
        "grid.linestyle":   "--",
        "grid.alpha":       0.5,
    })


def save_fig(name: str):
    """Guarda la figura activa en analysis/output/<name>.png."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  → guardado: {path}")
