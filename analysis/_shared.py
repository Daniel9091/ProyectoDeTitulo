"""
Utilidades compartidas para los módulos de análisis.
"""
import json
import duckdb
from pathlib import Path
import matplotlib.pyplot as plt


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
    con.execute(f"CREATE VIEW events AS SELECT * FROM read_ndjson_auto('{events_path}', sample_size=-1)")
    return con

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

def read_manifest(events_path: Path) -> set[str] | None:
    """
    Lee la última línea del JSONL para obtener los tipos de evento disponibles.
    Retorna set de tipos si hay manifest, None si no hay (fallback a scan completo).
    O(longitud de la última línea) — esencialmente O(1).
    """
    try:
        with open(events_path, 'rb') as f:
            f.seek(0, 2)
            end = f.tell()
            if end == 0:
                return set()
            pos = end - 1
            f.seek(pos)
            if f.read(1) == b'\n':
                pos -= 1
            while pos > 0:
                f.seek(pos)
                if f.read(1) == b'\n':
                    break
                pos -= 1
            last_line = f.read().decode('utf-8').strip()
        event = json.loads(last_line)
        if event.get('type') == 'run_manifest':
            return set(event['event_types'])
    except Exception:
        pass
    return None

def get_event_types(events_path: Path, con) -> set[str]:
    """Intenta leer manifest; si falla, hace scan completo como fallback."""
    types = read_manifest(events_path)
    if types is not None:
        return types
    # fallback: simulación sin manifest (crash o JSONL antiguo)
    print("  [aviso] Sin manifest — escaneando tipos (más lento).")
    return {row[0] for row in con.execute(
        "SELECT DISTINCT type FROM events"
    ).fetchall()}

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
