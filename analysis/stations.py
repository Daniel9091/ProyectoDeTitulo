"""
Station analysis.

Questions answered:
  1. How many passengers were generated per station?    → _demand_and_arrivals
  2. How many completed their journey from each origin? → _demand_and_arrivals

Report: stations.txt
Charts: (none — SP6 snapshots pending)

Required event types: passenger_spawned, passenger_arrived

Usage:
  python -c "from analysis.stations import run; run()"
"""


from analysis._shared import resolve_run, connect, get_output_dir, Reporter


def run(events_path=None):
    if events_path is None:
        events_path = resolve_run()
    con = connect(events_path)
    out_dir = get_output_dir(events_path)
    rep = Reporter(out_dir, "stations")

    rep.print("\n=== ESTACIONES ===")
    _demand_and_arrivals(con, rep)


    rep.save()
    con.close()


def _demand_and_arrivals(con, rep: Reporter):
    """
    Demand and arrival summary per origin station.

    Questions: How many passengers were generated per station? How many arrived?
    Text: per-station table (generated, arrived)
    Needs: passenger_spawned, passenger_arrived
    """
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
    rep.print("  Pasajeros generados en cada estación y cuántos llegaron a destino correcto.")
    rep.print(f"  {'Estación':>10}  {'Generados':>10}  {'Llegaron':>10}")

    for _, row in df.iterrows():
        rep.print(f"  S{int(row['station']):>9}  {int(row['generados']):>10}  {int(row['llegaron']):>10}")
