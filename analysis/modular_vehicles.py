"""
Modular vehicle (VM) analysis.

Questions answered:
  1. What fraction of the fleet carried passengers?      → _fleet_overview
  2. How efficiently did the fleet use its km?           → _distance_time_metrics, _km_efficiency
  3. How many trips did each VM make?                    → _vm_reuse
  4. How many passengers per trip?                       → _trip_occupancy

Report:  modular_vehicles.txt
Charts:
  modular_vehicles_fleet_overview.png  — pie: VMs with vs without passengers
  modular_vehicles_km_efficiency.png   — two pies: km composition + boarding lane utilization
  modular_vehicles_vm_reuse.png        — bar: trips per active VM
  modular_vehicles_trip_occupancy.png  — bar: passengers per trip

Required event types (SP3+): vm_created, vm_run_summary, vm_trip_completed

Usage:
  python -c "from analysis.modular_vehicles import run; run()"
"""

import matplotlib.pyplot as plt
from analysis._shared import resolve_run, connect, get_output_dir, save_fig, get_event_types, Reporter
from analysis._style  import setup, PALETTE, TITLE_SIZE, FIG_SQUARE, FIG_BAR, FIG_DUAL, BAR_KWARGS, PIE_KWARGS

def run(events_path=None):
    if events_path is None:
        events_path = resolve_run()
    con = connect(events_path)
    out_dir = get_output_dir(events_path)
    rep = Reporter(out_dir, "modular_vehicles")
    setup()

    types = get_event_types(events_path, con)

    rep.print("\n=== VEHÍCULOS ===")

    if 'vm_created' in types or 'vm_run_summary' in types:
        _fleet_overview(con, rep, out_dir)
    else:
        rep.print("  [sin datos] Sin registro de flota.")

    if 'vm_run_summary' in types:
        _distance_time_metrics(con, rep)

    if 'vm_run_summary' in types and 'vm_trip_completed' in types:
        _km_efficiency(con, rep, out_dir)

    if 'vm_trip_completed' in types:
        _vm_reuse(con, rep, out_dir)
        _trip_occupancy(con, rep, out_dir)
    else:
        rep.print("  [sin datos] Sin viajes registrados.")

    rep.save()
    con.close()

def _fleet_overview(con, rep, out_dir):
    """
    Pie chart and summary of fleet composition.

    Questions: What fraction of VMs carried passengers? How many were always idle?
    Text: fleet size, active VMs (%), idle VMs (%)
    Chart: modular_vehicles_fleet_overview.png
    Needs: vm_created OR vm_run_summary, passenger_boarded
    """
    r = con.execute("""
        SELECT
            (SELECT COUNT(DISTINCT vm_id) FROM events WHERE type = 'vm_created') AS total_flota,
            COUNT(DISTINCT b.vm_id) AS con_pasajeros
        FROM events s
        LEFT JOIN (SELECT DISTINCT vm_id FROM events WHERE type = 'passenger_boarded') b
            ON s.vm_id = b.vm_id
        WHERE s.type = 'vm_run_summary'
    """).fetchone()
    total_flota, con_p = r[0] or 0, r[1] or 0
    vacios = total_flota - con_p

    rep.print("\n[ Composición de la flota ]")
    rep.print("  Un VM (Vehículo Modular) circula por el carril inferior y sube a")
    rep.print("  estaciones bajo demanda para recoger pasajeros.")

    rep.print(f"  Flota total:              {total_flota} VMs")
    rep.print(f"  Con pasajeros:            {con_p}  ({100*con_p/total_flota:.1f}%)")
    rep.print(f"  Siempre vacíos:           {vacios}  ({100*vacios/total_flota:.1f}%)")

    fig, ax = plt.subplots(figsize=FIG_SQUARE)
    fig.suptitle("Utilización de flota", fontsize=TITLE_SIZE)
    _, _, autotexts = ax.pie(
        [con_p, vacios],
        labels=["Con pasajeros", "Siempre vacíos"],
        colors=[PALETTE["azul"], PALETTE["naranja"]],
        autopct="%1.1f%%",
        startangle=90,
        **PIE_KWARGS,
    )
    for at in autotexts:
        at.set_fontweight("bold")
    plt.tight_layout()
    save_fig("modular_vehicles_fleet_overview", out_dir)
    plt.show()

def _distance_time_metrics(con, rep):
    """
    Distance and time efficiency metrics for the fleet.

    Questions: How far did the fleet travel? What fraction was useful km?
    Text: total km, useful km (%), avg per VM, operational time, completed trips
    Needs: vm_run_summary, vm_trip_completed
    """
    r = con.execute("""
        SELECT
            SUM(total_distance)                 AS dist_total,
            AVG(total_distance)                 AS dist_prom,
            SUM(distance_carrying_passengers)   AS dist_pax_total,
            AVG(distance_carrying_passengers)   AS dist_pax_prom,
            SUM(operational_time)               AS tiempo_total,
            AVG(operational_time)               AS tiempo_prom
        FROM events WHERE type = 'vm_run_summary'
    """).fetchone()
    dist_total, dist_prom, dist_pax_total, dist_pax_prom, tiempo_total, tiempo_prom = r


    total_viajes = con.execute("""
        SELECT COUNT(*) FROM events
        WHERE type = 'vm_trip_completed' AND passenger_count > 0
    """).fetchone()[0] or 0

    pct_util = 100.0 * dist_pax_total / dist_total if dist_total > 0 else 0.0

    rep.print("\n[ Eficiencia operacional ]")
    rep.print("  El VM circula la mayor parte del tiempo sin pasajeros: es inherente")
    rep.print("  al diseño de carril circular, que no puede detener ni desviar VMs.")
    rep.print(f"  Kilómetros totales:              {dist_total/1000:.1f} km")
    rep.print(f"  Kilómetros útiles (con pax):     {dist_pax_total/1000:.1f} km  ({pct_util:.1f}%)")
    rep.print(f"  Kilómetros útiles prom. por VM:  {dist_pax_prom:.0f} m")
    rep.print(f"  Distancia prom. por VM:          {dist_prom:.0f} m")
    rep.print(f"\n[ Tiempos de operación ]")
    rep.print(f"  Tiempo total de la flota:    {tiempo_total/3600:.2f} h")
    rep.print(f"  Tiempo promedio por VM:      {tiempo_prom:.0f} s  (~{tiempo_prom/3600:.1f} h)")
    rep.print(f"  Viajes completados (boarding lane con ≥1 pax):  {total_viajes}")

def _km_efficiency(con, rep, out_dir):
    """
    Useful km vs idle km, and boarding lane pass utilization.

    Questions: What % of km was the fleet carrying passengers?
               What % of boarding lane passes had passengers?
    Text: total passes, with/without passengers (%)
    Chart: modular_vehicles_km_efficiency.png (two pies)
    Needs: vm_run_summary, vm_trip_completed
    """
    r = con.execute("""
        SELECT
            SUM(total_distance)               AS dist_total,
            SUM(distance_carrying_passengers) AS dist_util
        FROM events WHERE type = 'vm_run_summary'
    """).fetchone()
    dist_total, dist_util = r[0] or 0.0, r[1] or 0.0
    dist_vacio = dist_total - dist_util

    r2 = con.execute("""
        SELECT
            COUNT(*)                                               AS total_pasadas,
            SUM(CASE WHEN passenger_count > 0 THEN 1 ELSE 0 END)  AS con_pax
        FROM events WHERE type = 'vm_trip_completed'
    """).fetchone()
    total_pasadas, con_pax = r2[0] or 0, r2[1] or 0
    sin_pax = total_pasadas - con_pax

    pct_util_km = 100.0 * dist_util  / dist_total    if dist_total    > 0 else 0.0
    pct_con_pax = 100.0 * con_pax    / total_pasadas  if total_pasadas > 0 else 0.0

    rep.print(f"\n[ Utilización del boarding lane ]")
    rep.print("  Cada VM que entra al boarding lane puede o no encontrar pasajeros.")
    rep.print("  Las pasadas vacías ocurren cuando no hay demanda asignada en ese momento.")
    rep.print(f"  Total de pasadas:              {total_pasadas}")
    rep.print(f"  Con pasajeros (viaje válido):  {con_pax}  ({pct_con_pax:.1f}%)")
    rep.print(f"  Sin pasajeros (pasada vacía):  {sin_pax}  ({100 - pct_con_pax:.1f}%)")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIG_DUAL)
    fig.suptitle("Eficiencia operacional de la flota", fontsize=TITLE_SIZE)

    ax1.set_title("Composición de km")
    _, _, autotexts1 = ax1.pie(
        [dist_util, dist_vacio],
        labels=["km útiles\n(con pasajeros a bordo)", "km vacíos"],
        colors=[PALETTE["azul"], PALETTE["naranja"]],
        autopct="%1.1f%%",
        startangle=90,
        **PIE_KWARGS,
    )
    for at in autotexts1:
        at.set_fontweight("bold")

    ax2.set_title("Utilización del boarding lane")
    _, _, autotexts2 = ax2.pie(
        [con_pax, sin_pax],
        labels=["con pasajeros", "sin pasajeros"],
        colors=[PALETTE["azul"], PALETTE["naranja"]],
        autopct="%1.1f%%",
        startangle=90,
        **PIE_KWARGS,
    )
    for at in autotexts2:
        at.set_fontweight("bold")

    plt.tight_layout()
    save_fig("modular_vehicles_km_efficiency", out_dir)
    plt.show()


def _vm_reuse(con, rep, out_dir):
    """
    How many trips each active VM made.

    Questions: How many VMs made at least 1 trip? What is the trip count distribution?
    Text: active VM count, min/max/avg trips
    Chart: modular_vehicles_vm_reuse.png (bar)
    Needs: vm_trip_completed
    """
    df = con.execute("""
        SELECT viajes, COUNT(*) AS vms
        FROM (
            SELECT vm_id, COUNT(*) AS viajes
            FROM events
            WHERE type = 'vm_trip_completed' AND passenger_count > 0
            GROUP BY vm_id
        )
        GROUP BY viajes ORDER BY viajes
    """).df()

    if df.empty:
        rep.print("\n  Sin datos de reutilización.")
        return

    total_activos = int(df["vms"].sum())
    total_trips   = int((df["viajes"] * df["vms"]).sum())
    min_v = int(df["viajes"].min())
    max_v = int(df["viajes"].max())
    avg_v = total_trips / total_activos if total_activos > 0 else 0.0

    rep.print("\n[ Reutilización de VMs ]")
    rep.print("  Un 'viaje' = el VM completó el boarding lane con ≥1 pasajero a bordo.")
    rep.print(f"  VMs activos (≥1 viaje):  {total_activos}")
    rep.print(f"  Viajes por VM activo:    mín {min_v} · máx {max_v} · prom {avg_v:.1f}  (ver gráfico)")

    fig, ax = plt.subplots(figsize=FIG_BAR)
    fig.suptitle("Reutilización de VMs (viajes con pasajeros)", fontsize=TITLE_SIZE)
    ax.bar(df["viajes"], df["vms"], color=PALETTE["violeta"], **BAR_KWARGS)
    ax.set_xlabel("viajes realizados")
    ax.set_ylabel("cantidad de VMs")
    ax.set_xticks(df["viajes"])
    ax.grid(True, axis="y")
    plt.tight_layout()
    save_fig("modular_vehicles_vm_reuse", out_dir)
    plt.show()

def _trip_occupancy(con, rep, out_dir):
    """
    Passenger count per trip (how full was the VM per trip).

    Questions: Do VMs usually carry 1 or multiple passengers?
    Text: trips by passenger count
    Chart: modular_vehicles_trip_occupancy.png (bar)
    Needs: passenger_boarded
    """
    df = con.execute("""
        SELECT trip_size, COUNT(*) AS viajes
        FROM (
            SELECT vm_id, t, COUNT(*) AS trip_size
            FROM events WHERE type = 'passenger_boarded'
            GROUP BY vm_id, t
        )
        GROUP BY trip_size ORDER BY trip_size
    """).df()
    total_viajes = int(df["viajes"].sum())
    uno = int(df[df["trip_size"] == 1]["viajes"].sum()) if not df[df["trip_size"] == 1].empty else 0
    mas = total_viajes - uno

    rep.print("\n[ Ocupación por viaje ]")
    rep.print("  Pasajeros transportados por viaje. El VM tiene capacidad para varios,")
    rep.print("  pero la demanda baja genera mayormente viajes de 1 pasajero.")
    rep.print(f"  1 pasajero:   {uno} viajes  ({100 * uno / total_viajes:.1f}%)")
    if mas > 0:
        rep.print(f"  2+ pasajeros:  {mas} viajes  ({100 * mas / total_viajes:.1f}%)  (ver gráfico)")

    fig, ax = plt.subplots(figsize=FIG_BAR)
    fig.suptitle("Distribución de ocupación por viaje", fontsize=TITLE_SIZE)
    ax.bar(df["trip_size"], df["viajes"], color=PALETTE["azul"], **BAR_KWARGS)    
    ax.set_xlabel("pasajeros en el viaje")
    ax.set_ylabel("nº de viajes")
    ax.set_xticks(df["trip_size"])
    ax.grid(True, axis="y")
    plt.tight_layout()
    save_fig("modular_vehicles_trip_occupancy", out_dir)
    plt.show()
