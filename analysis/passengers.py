"""
Passenger lifecycle analysis.

Questions answered:
  1. How many passengers completed their trip?        → _summary_stats
  2. How long did passengers wait before boarding?    → _time_histograms
  3. How long was the total journey?                  → _time_histograms
  4. Did any passengers use intermediate stations?    → _transit_stops

Report:  passengers.txt
Charts:
  passengers_time_histograms.png  — histograms: wait time + travel time
  passengers_station_funnel.png   — bar: generated vs arrived per station
  passengers_transit.png          — histogram: intermediate stops per passenger

Required event types (SP2+): passenger_spawned, passenger_boarded,
                              passenger_arrived, passenger_arrived_wrong

Usage:
  python -c "from analysis.passengers import run; run()"
"""

import matplotlib.pyplot as plt
from analysis._shared import resolve_run, connect, get_output_dir, save_fig, get_event_types, Reporter
from analysis._style  import setup, PALETTE, TITLE_SIZE, FIG_BAR, FIG_WIDE, BAR_KWARGS,FIG_DUAL


def run(events_path=None):
    if events_path is None:
        events_path = resolve_run()
    con = connect(events_path)
    types = get_event_types(events_path, con)
    out_dir = get_output_dir(events_path)
    rep = Reporter(out_dir, "passengers")
    setup()

    rep.print("\n=== PASAJEROS ===")
    if {'passenger_spawned', 'passenger_boarded'} <= types:
        _summary_stats(con, rep)
        _time_histograms(con, out_dir)

    else:
        rep.print("  [sin datos] No hubo embarques en esta corrida.")

    if 'passenger_spawned' in types:
        _station_funnel(con, rep, out_dir)

    else:
        rep.print("  [sin datos] No se generaron pasajeros.")

    if 'passenger_transit' in types:
        _transit_stops(con, rep, out_dir)
    else:
        rep.print("  [sin datos] No hubo estaciones intermedias.")

    rep.save()
    con.close()

def _summary_stats(con, rep: Reporter):
    """
    General service summary from passenger lifecycle events.

    Questions: How many passengers completed their trip? How many arrived at the
               wrong destination? How many were still in transit when the sim closed?
    Text: generated, boarded, arrived (correct/wrong), in-transit, avg wait, avg travel
    Needs: passenger_spawned, passenger_boarded, passenger_arrived, passenger_arrived_wrong
    """
    row = con.execute("""
        SELECT
            COUNT(*) FILTER (WHERE type = 'passenger_spawned')        AS spawned,
            COUNT(*) FILTER (WHERE type = 'passenger_boarded')        AS boarded,
            COUNT(*) FILTER (WHERE type = 'passenger_arrived')        AS arrived_correct,
            COUNT(*) FILTER (WHERE type = 'passenger_arrived_wrong')  AS arrived_wrong,
            AVG(t - spawn_time) FILTER (WHERE type = 'passenger_boarded')       AS avg_wait,
            AVG(t - spawn_time) FILTER (WHERE type = 'passenger_arrived')       AS avg_travel
        FROM events
    """).fetchone()
    spawned, boarded, correct, wrong, avg_wait, avg_travel = row
    arrived = correct + wrong
    in_transit = spawned - arrived
    rep.print("\n[ Resumen del servicio ]")
    rep.print("  Estado de todos los pasajeros al cierre de la simulación.")
    rep.print(f"  Generados:              {spawned}")
    rep.print(f"  Abordaron:              {boarded}   ({100 * boarded / spawned:.1f}%)")
    rep.print(f"  Llegaron a destino:     {correct}   ({100 * correct / spawned:.1f}%)")
    rep.print(f"  Llegaron mal:           {wrong}   ({100 * wrong / spawned:.1f}%)")
    rep.print(f"  En tránsito al cerrar:  {in_transit}   ({100 * in_transit / spawned:.1f}%)")
    rep.print("    (pasajeros cuyo viaje no terminó antes del cierre de la simulación)")
    rep.print(f"\n[ Tiempos de servicio ]")
    rep.print(f"  Espera promedio (spawn → abordó):  {avg_wait:.1f} s")
    rep.print(f"  Viaje promedio  (spawn → llegó):   {avg_travel:.1f} s")

def _time_histograms(con, out_dir):
    """
    Wait time and travel time histograms.

    Questions: How long do passengers wait before boarding? How long is the total journey?
    Chart: passengers_time_histograms.png — two histograms side by side
    Needs: passenger_boarded (wait time), passenger_arrived (travel time)
    """
    wait   = con.execute("""
        SELECT t - spawn_time AS v FROM events WHERE type = 'passenger_boarded'
    """).df()["v"]
    travel = con.execute("""
        SELECT t - spawn_time AS v FROM events WHERE type = 'passenger_arrived'
    """).df()["v"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIG_WIDE)
    fig.suptitle("Distribución de tiempos de pasajeros", fontsize=TITLE_SIZE)

    ax1.hist(wait,   bins=30, color=PALETTE["azul"],  **BAR_KWARGS)
    ax1.set_title("Tiempo de espera (spawn → abordó)")
    ax1.set_xlabel("segundos")
    ax1.set_ylabel("pasajeros")
    ax1.grid(True)

    ax2.hist(travel, bins=30, color=PALETTE["verde"], **BAR_KWARGS)
    ax2.set_title("Tiempo de viaje total (spawn → llegó)")
    ax2.set_xlabel("segundos")
    ax2.set_ylabel("pasajeros")
    ax2.grid(True)

    plt.tight_layout()
    save_fig("passengers_time_histograms", out_dir)
    plt.show()

def _station_funnel(con, rep: Reporter, out_dir):
    """
    Passenger funnel per origin station.

    Questions: How many passengers per station reached their destination?
               How many arrived at the wrong station?
    Text: per-station table (generated, correct, wrong, in-transit)
    Chart: passengers_station_funnel.png
    Needs: passenger_spawned, passenger_arrived, passenger_arrived_wrong
    """
    df = con.execute("""
        SELECT
            s.origin_station_id                                          AS station,
            COUNT(*)                                                     AS spawned,
            COUNT(a.passenger_id)  FILTER (WHERE a.type = 'passenger_arrived')       AS correct,
            COUNT(a.passenger_id)  FILTER (WHERE a.type = 'passenger_arrived_wrong') AS wrong
        FROM events s
        LEFT JOIN events a ON s.passenger_id = a.passenger_id
            AND a.type IN ('passenger_arrived', 'passenger_arrived_wrong')
        WHERE s.type = 'passenger_spawned'
        GROUP BY s.origin_station_id
        ORDER BY station
    """).df()

    rep.print("\n[ Embudo por estación origen ]")
    rep.print("  Pasajeros generados en cada estación y cuántos completaron su viaje.")
    rep.print(f"  {'Estación':>10}  {'Generados':>10}  {'Dest OK':>10}  {'Dest MAL':>10}  {'En tránsito':>12}")
    for _, row in df.iterrows():
        s = int(row["station"])
        sp = int(row["spawned"])
        ok = int(row["correct"])
        mal = int(row["wrong"])
        transit = sp - ok - mal
        rep.print(f"  S{s:>9}  {sp:>10}  {ok:>10}  {mal:>10}  {transit:>12}")

    stations = [f"S{int(s)}" for s in df["station"]]
    x     = list(range(len(stations)))
    w     = 0.35
    fig, ax = plt.subplots(figsize=FIG_DUAL)
    fig.suptitle("Generados vs llegadas por estación origen", fontsize=TITLE_SIZE)

    ax.bar([i - w/2 for i in x], df["spawned"], w,
           label="generados",          color=PALETTE["azul"])
    ax.bar([i + w/2 for i in x], df["correct"], w,
           label="llegaron a destino", color=PALETTE["verde"])
    ax.bar([i + w/2 for i in x], df["wrong"], w,
           bottom=df["correct"],
           label="llegaron mal",       color=PALETTE["naranja"])

    ax.set_xticks(x)
    ax.set_xticklabels(stations)
    ax.set_ylabel("pasajeros")
    ax.legend()
    ax.grid(True, axis="y")
    plt.tight_layout()
    save_fig("passengers_station_funnel", out_dir)
    plt.show()

def _transit_stops(con, rep: Reporter, out_dir):
    """
    Distribution of intermediate transit stops per passenger.

    Questions: How many passengers had to transfer? How many stops on average?
    Text: passenger count with transit, max and avg stops
    Chart: passengers_transit.png
    Needs: passenger_transit
    """
    df = con.execute("""
        SELECT passenger_id, COUNT(*) AS stops
        FROM events WHERE type = 'passenger_transit'
        GROUP BY passenger_id
    """).df()

    if df.empty:
        rep.print("  Sin eventos passenger_transit registrados.")
        return

    rep.print("\n[ Estaciones intermedias ]")
    rep.print("  Pasajeros que visitaron al menos una estación de tránsito en su ruta.")
    rep.print(f"  Pasajeros con tránsito:   {len(df)}")
    rep.print(f"  Máx. estaciones interm.:  {int(df['stops'].max())}")
    rep.print(f"  Promedio:                 {df['stops'].mean():.1f}")

    fig, ax = plt.subplots(figsize=FIG_BAR)
    fig.suptitle("Estaciones intermedias visitadas por pasajero", fontsize=TITLE_SIZE)
    max_stops = int(df["stops"].max())
    ax.hist(df["stops"], bins=range(1, max_stops + 2), color=PALETTE["violeta"],
            align="left", **BAR_KWARGS)
    ax.set_xlabel("nº de estaciones intermedias")
    ax.set_ylabel("pasajeros")
    ax.set_xticks(range(1, max_stops + 1))
    ax.grid(True, axis="y")
    plt.tight_layout()
    save_fig("passengers_transit", out_dir)
    plt.show()
