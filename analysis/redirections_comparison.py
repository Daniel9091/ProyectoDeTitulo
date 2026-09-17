"""
Comparación de cuellos de botella (VMs redirigidos por saturación de árbol)
entre tres corridas, con letras y números más grandes.

No depende de los otros módulos de analysis: solo lee eventos vm_redirected
de las tres corridas indicadas abajo y dibuja el gráfico.

Nota sobre la escala: cada panel usa su propio eje X porque los tres
escenarios difieren en casi un orden de magnitud (cientos vs miles). Forzar
el mismo eje lineal en los tres dejaría dos paneles casi invisibles. Si
prefieres compararlos en una sola escala logarítmica compartida, cambia
LOG_SCALE a True más abajo (ojo: los tramos "sin pasajeros", ya angostos,
se leen peor en escala log).

Uso:
    1. Copia este archivo dentro de la carpeta analysis/ de tu proyecto.
    2. Si quieres comparar otras corridas, edita la lista RUNS más abajo
       (el run_id es el nombre de la carpeta dentro de runs/).
    3. Desde la raíz del proyecto, con el venv activado:

         python -m analysis.redirections_comparison

    El gráfico queda guardado en analysis/output/stations_redirections_comparison.png
"""

from pathlib import Path

import matplotlib.pyplot as plt

from analysis._shared import resolve_run, connect
from analysis._style import setup, PALETTE

# ── Edita esto para comparar otras corridas ──────────────────────────────────
RUNS = [
    ("linea_1_edit_seed42_20260901-202100", "Subdimensionado"),
    ("linea_1_edit_seed42_20260901-172547", "Base"),
    ("linea_1_edit_seed42_20260902-190629", "Sobredimensionado"),
]
OUT_DIR = Path("analysis/output")
LOG_SCALE = False  # cambia a True para eje X compartido en escala logarítmica
# ──────────────────────────────────────────────────────────────────────────────


def _load_redirections(events_path):
    """Carga, para una corrida, redirecciones por estación (con/sin pasajeros)."""
    con = connect(events_path)
    df = con.execute("""
        SELECT
            blocked_station_id                           AS station,
            COUNT(*)                                      AS total,
            COUNT(*) FILTER (WHERE passenger_count > 0)  AS con_pax,
            COUNT(*) FILTER (WHERE passenger_count = 0)  AS sin_pax
        FROM events
        WHERE type = 'vm_redirected'
        GROUP BY blocked_station_id
        ORDER BY total DESC
    """).df()
    con.close()
    return df


def main():
    setup()

    fig, axes = plt.subplots(1, len(RUNS), figsize=(7.5 * len(RUNS), 11))

    for ax, (run_id, label) in zip(axes, RUNS):
        print(f"Cargando {label} ({run_id})...")
        df = _load_redirections(resolve_run(run_id))

        labels  = [f"S{int(s)}" for s in df["station"]]
        con_pax = df["con_pax"].tolist()
        sin_pax = df["sin_pax"].tolist()
        y = list(range(len(labels)))

        ax.barh(y, con_pax, color=PALETTE["naranja"], label="Con pasajeros")
        ax.barh(y, sin_pax, left=con_pax, color=PALETTE["azul"], alpha=0.6,
                label="Sin pasajeros")

        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=12)
        ax.invert_yaxis()
        ax.set_xlabel("VMs redirigidos", fontsize=15, labelpad=8)
        ax.set_title(label, fontsize=17, pad=10)
        ax.tick_params(axis='x', labelsize=13)
        ax.xaxis.grid(True)
        ax.set_axisbelow(True)
        if LOG_SCALE:
            ax.set_xscale("log")

    fig.suptitle("Cuellos de botella — redirecciones por saturación de árbol",
                 fontsize=21, y=1.0)

    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc='upper center', bbox_to_anchor=(0.5, 0.02),
               ncol=2, fontsize=15, frameon=False)

    plt.tight_layout(rect=[0, 0.04, 1, 0.95])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "stations_redirections_comparison.png"
    plt.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close()
    print(f"Listo: {out_path}")


if __name__ == "__main__":
    main()