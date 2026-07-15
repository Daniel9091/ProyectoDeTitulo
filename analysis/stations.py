"""
Análisis de estaciones.

Con SP2: demanda generada y llegadas por estación.
Pendiente SP6 (snapshots): cola en andén a lo largo del tiempo.
"""
from analysis._shared import resolve_run, connect, get_output_dir, Reporter


def run(events_path=None):
    if events_path is None:
        events_path = resolve_run()
    con = connect(events_path)
    out_dir = get_output_dir(events_path)
    rep = Reporter(out_dir, "stations")

    rep.print("\n=== ESTACIONES ===")
    _demanda_y_llegadas(con, rep)

    rep.save()
    con.close()


def _demanda_y_llegadas(con, rep: Reporter):
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

    rep.print(f"  {'Estación':>10}  {'Generados':>10}  {'Llegaron':>10}")
    for _, row in df.iterrows():
        rep.print(f"  S{int(row['station']):>9}  {int(row['generados']):>10}  {int(row['llegaron']):>10}")
