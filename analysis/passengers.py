"""
passengers.py — Ciclo de vida de pasajeros.

Preguntas que responde:
  1. ¿Cuántos pasajeros llegaron a destino? (tasa de completitud)
  2. ¿Cuánto esperaron antes de abordar? (wait_time)
  3. ¿Cuánto duró el viaje total? (travel_time)
  4. ¿Cuántas estaciones intermedias visitaron? (transit stops)

Uso individual:
  python -c "from analysis.passengers import run; run()"
"""
import matplotlib.pyplot as plt
from analysis._shared import resolve_run, connect, plot_style, save_fig


def run(events_path=None):
    if events_path is None:
        events_path = resolve_run()
    con = connect(events_path)
    plot_style()

    print("\n=== PASAJEROS ===")
    _stats_generales(con)
    _histogramas_tiempos(con)
    _embudo_por_estacion(con)
    _transit_stops(con)
    con.close()


def _stats_generales(con):
    row = con.execute("""
        SELECT
            COUNT(*) FILTER (WHERE type = 'passenger_spawned') AS spawned,
            COUNT(*) FILTER (WHERE type = 'passenger_boarded') AS boarded,
            COUNT(*) FILTER (WHERE type = 'passenger_arrived') AS arrived,
            AVG(t - spawn_time) FILTER (WHERE type = 'passenger_boarded')  AS avg_wait,
            AVG(t - spawn_time) FILTER (WHERE type = 'passenger_arrived')  AS avg_travel
        FROM events
    """).fetchone()
    spawned, boarded, arrived, avg_wait, avg_travel = row
    print(f"  Generados:       {spawned}")
    print(f"  Abordaron:       {boarded}  ({100 * boarded / spawned:.1f}%)")
    print(f"  Llegaron:        {arrived}  ({100 * arrived / spawned:.1f}%)")
    print(f"  Espera promedio: {avg_wait:.1f}s")
    print(f"  Viaje promedio:  {avg_travel:.1f}s")


def _histogramas_tiempos(con):
    wait   = con.execute("""
        SELECT t - spawn_time AS v FROM events WHERE type = 'passenger_boarded'
    """).df()["v"]
    travel = con.execute("""
        SELECT t - spawn_time AS v FROM events WHERE type = 'passenger_arrived'
    """).df()["v"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Distribución de tiempos de pasajeros", fontsize=13)

    ax1.hist(wait,   bins=30, color="#89b4fa", edgecolor="#1e1e2e")
    ax1.set_title("Tiempo de espera (spawned → boarded)")
    ax1.set_xlabel("segundos")
    ax1.set_ylabel("pasajeros")
    ax1.grid(True)

    ax2.hist(travel, bins=30, color="#a6e3a1", edgecolor="#1e1e2e")
    ax2.set_title("Tiempo de viaje total (spawned → arrived)")
    ax2.set_xlabel("segundos")
    ax2.set_ylabel("pasajeros")
    ax2.grid(True)

    plt.tight_layout()
    save_fig("passengers_tiempos")
    plt.show()


def _embudo_por_estacion(con):
    df = con.execute("""
        SELECT
            origin_station_id AS station,
            COUNT(*) FILTER (WHERE type = 'passenger_spawned') AS spawned,
            COUNT(*) FILTER (WHERE type = 'passenger_arrived') AS arrived
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

    stations  = [f"S{int(s)}" for s in df["station"]]
    x         = range(len(stations))
    width     = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.suptitle("Generados vs. Llegaron por estación origen", fontsize=13)
    ax.bar([i - width/2 for i in x], df["spawned"], width, label="generados",  color="#89b4fa")
    ax.bar([i + width/2 for i in x], df["arrived"], width, label="llegaron",   color="#a6e3a1")
    ax.set_xticks(list(x))
    ax.set_xticklabels(stations)
    ax.set_ylabel("pasajeros")
    ax.legend()
    ax.grid(True, axis="y")
    plt.tight_layout()
    save_fig("passengers_embudo_estaciones")
    plt.show()


def _transit_stops(con):
    df = con.execute("""
        SELECT passenger_id, COUNT(*) AS stops
        FROM events WHERE type = 'passenger_transit'
        GROUP BY passenger_id
    """).df()

    if df.empty:
        print("  Sin eventos passenger_transit registrados.")
        return

    print(f"\n  Pasajeros con tránsito intermedio: {len(df)}")
    print(f"  Máx. estaciones intermedias:       {int(df['stops'].max())}")
    print(f"  Promedio:                          {df['stops'].mean():.1f}")

    fig, ax = plt.subplots(figsize=(7, 4))
    fig.suptitle("Estaciones intermedias visitadas por pasajero")
    max_stops = int(df["stops"].max())
    ax.hist(df["stops"], bins=range(1, max_stops + 2), color="#fab387",
            edgecolor="#1e1e2e", align="left")
    ax.set_xlabel("nº de estaciones intermedias")
    ax.set_ylabel("pasajeros")
    ax.set_xticks(range(1, max_stops + 1))
    ax.grid(True, axis="y")
    plt.tight_layout()
    save_fig("passengers_transit")
    plt.show()
