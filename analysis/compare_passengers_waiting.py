"""
Comparación de dos corridas: pasajeros en cola por estación, lado a lado,
con eje Y compartido para que sean directamente comparables.

No depende de los otros módulos de analysis (trees, passengers, slot_labels,
modular_vehicles): solo lee eventos station_snapshot de las dos corridas
indicadas abajo y dibuja el gráfico. No corre el análisis completo.

Uso:
    1. Copia este archivo dentro de la carpeta analysis/ de tu proyecto.
    2. Si quieres comparar otras corridas, edita RUN_A / RUN_B / LABEL_A /
       LABEL_B más abajo (el run_id es el nombre de la carpeta dentro de runs/).
    3. Desde la raíz del proyecto (donde está pyproject.toml), con el venv
       activado:

         python -m analysis.compare_passengers_waiting

    El gráfico queda guardado en analysis/output/stations_passengers_waiting_comparison.png
"""

from pathlib import Path
from collections import defaultdict

import matplotlib.pyplot as plt

from analysis._shared import resolve_run, connect
from analysis._style import setup

# ── Edita esto para comparar otras corridas ──────────────────────────────────
RUN_A, LABEL_A = "linea_1_edit_seed42_20260901-172547", "Base"
RUN_B, LABEL_B = "linea_1_edit_seed42_20260902-163548", "Densidad 0.7"
OUT_DIR = Path("analysis/output")
# ──────────────────────────────────────────────────────────────────────────────

_ALL_COLORS = list(plt.get_cmap('tab20').colors) + list(plt.get_cmap('tab20b').colors)


def _station_color(i: int):
    return _ALL_COLORS[i % len(_ALL_COLORS)]


def _load_queue_by_station(events_path):
    """Carga, para una corrida, la serie de tiempo de cola por estación."""
    con = connect(events_path)
    rows = con.execute("""
        SELECT t, station_id, andenes
        FROM events WHERE type = 'station_snapshot'
        ORDER BY t, station_id
    """).fetchall()
    con.close()

    by_station = defaultdict(lambda: {'t': [], 'queue': []})
    for t, sid, andenes in rows:
        by_station[sid]['t'].append(t / 60)
        by_station[sid]['queue'].append(sum(a['queue_total'] for a in andenes))
    return by_station


def main():
    setup()

    print(f"Cargando {LABEL_A} ({RUN_A})...")
    data_a = _load_queue_by_station(resolve_run(RUN_A))
    print(f"Cargando {LABEL_B} ({RUN_B})...")
    data_b = _load_queue_by_station(resolve_run(RUN_B))

    y_max = max(
        max(s['queue'], default=0)
        for d in (data_a, data_b) for s in d.values()
    )
    y_top = y_max * 1.06  # un poco por sobre el máximo real, para dar aire arriba

    fig, axes = plt.subplots(1, 2, figsize=(18, 8), sharey=True,
                              gridspec_kw={'wspace': 0.03})

    handles = {}
    for ax, data in zip(axes, (data_a, data_b)):
        for i, sid in enumerate(sorted(data)):
            d = data[sid]
            line, = ax.plot(d['t'], d['queue'], marker='o', markersize=2.2,
                             linewidth=1.1, color=_station_color(i))
            handles[f"S{sid}"] = line
        ax.yaxis.grid(True)
        ax.set_axisbelow(True)
        ax.tick_params(axis='both', labelsize=14)
        ax.set_ylim(0, y_top)

    axes[1].tick_params(axis='y', labelleft=False)
    axes[0].set_ylabel("Pasajeros en cola", fontsize=16)
    fig.suptitle("Pasajeros esperando VM — serie de tiempo", fontsize=20, y=1.0)
    fig.text(0.5, 0.015, "Tiempo (min)", ha='center', fontsize=16)

    ordered = sorted(handles, key=lambda s: int(s[1:]))
    fig.legend([handles[l] for l in ordered], ordered,
               loc='center left', bbox_to_anchor=(1.0, 0.5),
               fontsize=13, ncol=2, framealpha=0.9, markerscale=2.4,
               handlelength=2.5, labelspacing=0.6, columnspacing=1.2)

    plt.tight_layout(rect=[0, 0.03, 0.86, 0.96])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "stations_passengers_waiting_comparison.png"
    plt.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Listo: {out_path}")


if __name__ == "__main__":
    main()