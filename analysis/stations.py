"""
Station analysis.

Questions answered:
  1. Cuántos pasajeros generó cada estación y cuántos llegaron    → _demand_and_arrivals
  2. Cómo evoluciona la cola de pasajeros en el tiempo            → _passengers_waiting_over_time (SP6)
  3. Qué hacen los VMs en cada lane a lo largo de la simulación  → _vm_states_over_time (SP6)
  4. Cómo evoluciona la demanda pendiente de VMs                  → _pending_demand_over_time (SP6)

Report: stations.txt
Charts:
  stations_passengers_waiting.png — línea: pasajeros en cola por estación
  stations_vm_states.png          — barras apiladas: estados de VM en lane por estación
  stations_pending_demand.png     — línea: demanda pendiente por estación

Required: passenger_spawned, passenger_arrived
SP6:      station_snapshot
"""

import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict

from analysis._shared import resolve_run, connect, get_output_dir, save_fig, get_event_types, Reporter
from analysis._style  import setup, PALETTE, TITLE_SIZE, FIG_BAR, BAR_KWARGS

def run(events_path=None):
    if events_path is None:
        events_path = resolve_run()
    con = connect(events_path)
    out_dir = get_output_dir(events_path)
    rep = Reporter(out_dir, "stations")
    setup()

    types = get_event_types(events_path, con)

    rep.print("\n=== ESTACIONES ===")
    _demand_and_arrivals(con, rep)

    if 'station_snapshot' in types:
        _snapshot_overview(con, rep)
        _passengers_waiting_over_time(con, rep, out_dir)
        _vm_states_over_time(con, rep, out_dir)
        _pending_demand_over_time(con, rep, out_dir)
    else:
        rep.print("\n  [SP6 no disponible] No hay station_snapshot en esta corrida.")

    rep.save()
    con.close()

def _demand_and_arrivals(con, rep):
    df = con.execute("""
        SELECT
            origin_station_id AS station,
            COUNT(*) FILTER (WHERE type = 'passenger_spawned') AS generados,
            COUNT(*) FILTER (WHERE type = 'passenger_arrived') AS llegaron
        FROM (
            SELECT type, origin_station_id FROM events WHERE type = 'passenger_spawned'
            UNION ALL
            SELECT e2.type, e1.origin_station_id
            FROM events e1
            JOIN events e2 ON e1.passenger_id = e2.passenger_id
            WHERE e1.type = 'passenger_spawned' AND e2.type = 'passenger_arrived'
        )
        GROUP BY origin_station_id
        ORDER BY station
    """).df()

    rep.print("\n[ Demanda generada por estación ]")
    rep.print(f"  {'Estación':>10}  {'Generados':>10}  {'Llegaron':>10}")
    for _, row in df.iterrows():
        rep.print(f"  S{int(row['station']):>9}  {int(row['generados']):>10}  {int(row['llegaron']):>10}")

def _snapshot_overview(con, rep):
    rows = con.execute("""
        SELECT station_id, COUNT(*) AS n,
               ROUND(MIN(t), 0) AS first_t, ROUND(MAX(t), 0) AS last_t
        FROM events WHERE type = 'station_snapshot'
        GROUP BY station_id ORDER BY station_id
    """).fetchall()
    rep.print("\n[ Snapshots de estación (SP6) ]")
    for sid, n, first, last in rows:
        rep.print(f"  S{sid}: {n} snapshots — t=[{int(first)}s, {int(last)}s]")

_STATION_COLORS = {1: PALETTE["azul"], 2: PALETTE["verde"], 3: PALETTE["naranja"]}

def _passengers_waiting_over_time(con, rep, out_dir):
    """Cola de pasajeros en espera por estación a lo largo del tiempo."""
    rows = con.execute("""
        SELECT t, station_id, andenes
        FROM events WHERE type = 'station_snapshot'
        ORDER BY t, station_id
    """).fetchall()

    by_station = defaultdict(lambda: {'t': [], 'queue': []})
    for t, sid, andenes in rows:
        by_station[sid]['t'].append(t / 60)
        by_station[sid]['queue'].append(sum(a['queue_total'] for a in andenes))

    fig, ax = plt.subplots(figsize=FIG_BAR)
    for sid in sorted(by_station):
        d = by_station[sid]
        ax.plot(d['t'], d['queue'], marker='o', markersize=4, linewidth=1.5,
                label=f"S{sid}", color=_STATION_COLORS.get(sid, PALETTE["violeta"]))

    ax.set_xlabel("Tiempo (min)")
    ax.set_ylabel("Pasajeros en cola")
    ax.set_title("Pasajeros esperando VM — serie de tiempo", size=TITLE_SIZE)
    ax.legend()
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    plt.tight_layout()
    save_fig("stations_passengers_waiting", out_dir)
    plt.close()

_VM_STATE_KEYS = ['vms_committed_pax', 'vms_boarding', 'vms_empty_pre', 'vms_empty_post']
_VM_STATE_LABELS = {
    'vms_committed_pax': "Comprometidos con pasajeros",
    'vms_boarding':      "Abordando (pre-commit con pax)",
    'vms_empty_pre':     "Vacíos pre-commit",
    'vms_empty_post':    "Vacíos post-commit",
}
_VM_STATE_COLORS = {
    'vms_committed_pax': PALETTE["verde"],
    'vms_boarding':      PALETTE["azul"],
    'vms_empty_pre':     PALETTE["naranja"],
    'vms_empty_post':    PALETTE["violeta"],
}

def _vm_states_over_time(con, rep, out_dir):
    """Qué hacen los VMs en cada boarding lane, apilado por estado, por estación."""
    rows = con.execute("""
        SELECT t, station_id, andenes
        FROM events WHERE type = 'station_snapshot'
        ORDER BY t, station_id
    """).fetchall()

    by_station = defaultdict(lambda: {k: [] for k in ['t'] + _VM_STATE_KEYS})
    for t, sid, andenes in rows:
        d = by_station[sid]
        d['t'].append(t / 60)
        for key in _VM_STATE_KEYS:
            d[key].append(sum(a[key] for a in andenes))

    stations = sorted(by_station)
    fig, axes = plt.subplots(1, len(stations), figsize=(5 * len(stations), 4), sharey=False)
    if len(stations) == 1:
        axes = [axes]

    for ax, sid in zip(axes, stations):
        d = by_station[sid]
        ts = np.array(d['t'])
        bottoms = np.zeros(len(ts))
        for key in _VM_STATE_KEYS:
            vals = np.array(d[key], dtype=float)
            ax.bar(ts, vals, bottom=bottoms, width=0.7,
                   label=_VM_STATE_LABELS[key],
                   color=_VM_STATE_COLORS[key], alpha=0.85)
            bottoms += vals
        ax.set_title(f"S{sid} — VMs en boarding lane", size=TITLE_SIZE)
        ax.set_xlabel("Tiempo (min)")
        ax.set_ylabel("VMs")
        ax.yaxis.grid(True)
        ax.set_axisbelow(True)

    axes[0].legend(loc='upper left', fontsize=8, framealpha=0.8)
    plt.tight_layout()
    save_fig("stations_vm_states", out_dir)
    plt.close()

def _pending_demand_over_time(con, rep, out_dir):
    """Demanda pendiente de VMs por estación a lo largo del tiempo."""
    rows = con.execute("""
        SELECT t, station_id, pending_demand
        FROM events WHERE type = 'station_snapshot'
        ORDER BY t, station_id
    """).fetchall()

    by_station = defaultdict(lambda: {'t': [], 'demand': []})
    for t, sid, demand in rows:
        by_station[sid]['t'].append(t / 60)
        by_station[sid]['demand'].append(demand)

    fig, ax = plt.subplots(figsize=FIG_BAR)
    for sid in sorted(by_station):
        d = by_station[sid]
        ax.plot(d['t'], d['demand'], marker='o', markersize=4, linewidth=1.5,
                label=f"S{sid}", color=_STATION_COLORS.get(sid, PALETTE["violeta"]))

    ax.axhline(0, color='gray', linewidth=0.8, linestyle='--', alpha=0.6)
    ax.set_xlabel("Tiempo (min)")
    ax.set_ylabel("VMs demandados")
    ax.set_title("Demanda pendiente de VMs — serie de tiempo", size=TITLE_SIZE)
    ax.legend()
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    plt.tight_layout()
    save_fig("stations_pending_demand", out_dir)
    plt.close()
