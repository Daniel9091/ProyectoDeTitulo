"""
Métricas de vehículos modulares (VMs).

Preguntas que responde:
  1. ¿Qué fracción de la flota fue utilizada? (pie chart)
  2. ¿Cuántos metros recorrió la flota en total y en promedio?
  3. ¿Cuánto tiempo operó la flota en tránsito?
  4. ¿Cuántos metros recorrieron los VMs solo durante viajes con pasajeros?
  5. ¿Cuántos viajes hizo cada VM? (reutilización — bar chart)
     Un viaje = boarding lane completado con ≥1 pasajero.
  6. ¿Cuántos pasajeros suelen ir juntos en un viaje? (ocupación — bar chart)

Requiere: vm_created, vm_run_summary, vm_trip_completed en el log (SP3 activo).

Uso individual:
  python -c "from analysis.modular_vehicles import run; run()"
"""

import matplotlib.pyplot as plt
from analysis._shared import resolve_run, connect, plot_style, get_output_dir, save_fig, Reporter

def run(events_path=None):
    if events_path is None:
        events_path = resolve_run()
    con = connect(events_path)
    out_dir = get_output_dir(events_path)
    rep = Reporter(out_dir, "modular_vehicles")
    plot_style()

    rep.print("\n=== VEHÍCULOS ===")
    _fleet_overview(con, rep, out_dir)
    _metricas_distancia_tiempo(con, rep)
    _reutilizacion_vms(con, rep, out_dir)
    _ocupacion_por_viaje(con, rep, out_dir)

    rep.save()
    con.close()


def _fleet_overview(con, rep, out_dir):
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

    rep.print(f"  Flota total:              {total_flota} VMs")
    rep.print(f"  Con pasajeros:            {con_p}  ({100*con_p/total_flota:.1f}%)")
    rep.print(f"  Siempre vacíos:           {vacios}  ({100*vacios/total_flota:.1f}%)")

    fig, ax = plt.subplots(figsize=(5, 5))
    fig.suptitle("Utilización de flota", fontsize=13)
    wedges, texts, autotexts = ax.pie(
        [con_p, vacios],
        labels=["Con pasajeros", "Siempre vacíos"],
        colors=["#89b4fa", "#45475a"],
        autopct="%1.1f%%",
        startangle=90,
        wedgeprops={"edgecolor": "#1e1e2e", "linewidth": 2},
    )
    for at in autotexts:
        at.set_color("#1e1e2e")
        at.set_fontweight("bold")
    plt.tight_layout()
    save_fig("modular_vehicles_utilizacion", out_dir)
    plt.show()


def _metricas_distancia_tiempo(con, rep):
    r = con.execute("""
        SELECT
            SUM(total_distance)    AS dist_total,
            AVG(total_distance)    AS dist_prom,
            SUM(operational_time)  AS tiempo_total,
            AVG(operational_time)  AS tiempo_prom
        FROM events WHERE type = 'vm_run_summary'
    """).fetchone()
    dist_total, dist_prom, tiempo_total, tiempo_prom = r

    r2 = con.execute("""
        SELECT
            COUNT(*)            AS total_viajes,
            SUM(lane_length)    AS dist_en_viajes
        FROM events
        WHERE type = 'vm_trip_completed' AND passenger_count > 0
    """).fetchone()
    total_viajes, dist_en_viajes = r2[0] or 0, r2[1] or 0.0

    rep.print(f"\n  Distancia total flota:        {dist_total/1000:.1f} km")
    rep.print(f"  Distancia prom. por VM:       {dist_prom:.0f} m")
    rep.print(f"  Viajes con pasajeros:         {total_viajes}")
    rep.print(f"  Distancia en viajes (c/pas.): {dist_en_viajes/1000:.1f} km")
    rep.print(f"  Tiempo en tránsito total:     {tiempo_total/3600:.2f} h")
    rep.print(f"  Tiempo en tránsito prom.:     {tiempo_prom:.0f} s")

def _reutilizacion_vms(con, rep, out_dir):
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
    rep.print(f"\n  VMs con ≥1 viaje: {total_activos}")
    for _, row in df.iterrows():
        n, v = int(row["viajes"]), int(row["vms"])
        rep.print(f"  {v:4d} VMs hicieron {n} viaje{'s' if n > 1 else ''}")

    fig, ax = plt.subplots(figsize=(7, 4))
    fig.suptitle("Reutilización de VMs (viajes con pasajeros por VM)", fontsize=13)
    ax.bar(df["viajes"], df["vms"], color="#f38ba8", edgecolor="#1e1e2e")
    ax.set_xlabel("viajes realizados")
    ax.set_ylabel("cantidad de VMs")
    ax.set_xticks(df["viajes"])
    ax.grid(True, axis="y")
    plt.tight_layout()
    save_fig("modular_vehicles_reutilizacion", out_dir)
    plt.show()

def _ocupacion_por_viaje(con, rep, out_dir):
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
    rep.print(f"\n  Distribución de ocupación ({total_viajes} viajes):")
    for _, row in df.iterrows():
        n, v = int(row["trip_size"]), int(row["viajes"])
        rep.print(f"  {n} pasajero{'s' if n > 1 else ''}:  {v} viajes  ({100*v/total_viajes:.1f}%)")

    fig, ax = plt.subplots(figsize=(7, 4))
    fig.suptitle("Distribución de ocupación por viaje", fontsize=13)
    ax.bar(df["trip_size"], df["viajes"], color="#89b4fa", edgecolor="#1e1e2e")
    ax.set_xlabel("pasajeros en el viaje")
    ax.set_ylabel("nº de viajes")
    ax.set_xticks(df["trip_size"])
    ax.grid(True, axis="y")
    plt.tight_layout()
    save_fig("modular_vehicles_ocupacion_viaje", out_dir)
    plt.show()
