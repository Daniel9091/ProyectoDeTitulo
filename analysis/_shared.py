"""
Utilidades compartidas para los módulos de análisis.
"""
import json
import duckdb
import matplotlib.pyplot as plt
from pathlib import Path


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

def get_output_dir(events_path: Path) -> Path:
    """Carpeta de salida para esta corrida: analysis/output/<run_id>/"""
    run_id = events_path.parent.name
    out = Path(__file__).parent / "output" / run_id
    out.mkdir(parents=True, exist_ok=True)
    return out

def save_fig(name: str, output_dir: Path):
    """Guarda la figura activa en output_dir/<name>.png."""
    path = output_dir / f"{name}.png"
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  → guardado: {path}")

class Reporter:
    """Imprime a terminal y acumula líneas para guardar en un .txt al final."""

    def __init__(self, output_dir: Path, name: str):
        self._lines: list[str] = []
        self._path = output_dir / f"{name}.txt"

    def print(self, text: str = ""):
        print(text)
        self._lines.append(text)

    def save(self):
        self._path.write_text("\n".join(self._lines), encoding="utf-8")
        print(f"  → guardado: {self._path}")
