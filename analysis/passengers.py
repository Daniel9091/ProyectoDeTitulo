"""
Ciclo de vida de pasajeros.

Preguntas que responde:
  1. ¿Cuántos pasajeros llegaron a destino? (tasa de completitud)
  2. ¿Cuánto esperaron antes de abordar? (wait_time)
  3. ¿Cuánto duró el viaje total? (travel_time)
  4. ¿Cuántas estaciones intermedias visitaron? (transit stops)

Uso individual:
  python -c "from analysis.passengers import run; run()"
"""
import matplotlib.pyplot as plt
from analysis._shared import resolve_run, connect, plot_style, get_output_dir, save_fig, Reporter


def run(events_path=None):
    if events_path is None:
        events_path = resolve_run()
    con = connect(events_path)
    out_dir = get_output_dir(events_path)
    rep = Reporter(out_dir, "passengers")
    plot_style()

    rep.print("\n=== PASAJEROS ===")
    _stats_generales(con, rep)
    _histogramas_tiempos(con, out_dir)
    _embudo_por_estacion(con, rep, out_dir)
    _transit_stops(con, rep, out_dir)

    rep.save()
    con.close()

def _stats_generales(con, rep: Reporter):
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
    rep.print(f"  Generados:              {spawned}")
    rep.print(f"  Abordaron:              {boarded}   ({100 * boarded / spawned:.1f}%)")
    rep.print(f"  Llegaron a destino:     {correct}   ({100 * correct / spawned:.1f}%)")
    rep.print(f"  Llegaron mal:           {wrong}   ({100 * wrong / spawned:.1f}%)")
    rep.print(f"  En tránsito al cerrar:  {in_transit}   ({100 * in_transit / spawned:.1f}%)")
    rep.print(f"  Espera promedio:        {avg_wait:.1f}s")
    rep.print(f"  Viaje promedio:         {avg_travel:.1f}s")

def _histogramas_tiempos(con, out_dir):
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
    save_fig("passengers_tiempos", out_dir)
    plt.show()

def _embudo_por_estacion(con, rep: Reporter, out_dir):
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

    rep.print("\n  Embudo por estación origen:")
    rep.print(f"  {'Estación':>10}  {'Generados':>10}  {'Dest OK':>10}  {'Dest MAL':>10}  {'En tránsito':>12}")
    for _, row in df.iterrows():
        s = int(row["station"])
        sp = int(row["spawned"])
        ok = int(row["correct"])
        mal = int(row["wrong"])
        transit = sp - ok - mal
        rep.print(f"  S{s:>9}  {sp:>10}  {ok:>10}  {mal:>10}  {transit:>12}")

    # Gráfico
    stations = [f"S{int(s)}" for s in df["station"]]
    x     = list(range(len(stations)))
    w     = 0.35

    fig, ax = plt.subplots(figsize=(9, 5))
    fig.suptitle("Generados vs llegadas por estación origen", fontsize=13)

    ax.bar([i - w/2 for i in x], df["spawned"], w,
           label="generados", color="#89b4fa")
    ax.bar([i + w/2 for i in x], df["correct"], w,
           label="llegaron a destino", color="#a6e3a1")
    ax.bar([i + w/2 for i in x], df["wrong"], w,
           bottom=df["correct"],
           label="llegaron mal", color="#fab387")

    ax.set_xticks(x)
    ax.set_xticklabels(stations)
    ax.set_ylabel("pasajeros")
    ax.legend()
    ax.grid(True, axis="y")
    plt.tight_layout()
    save_fig("passengers_embudo_estaciones", out_dir)
    plt.show()

def _transit_stops(con, rep: Reporter, out_dir):
    df = con.execute("""
        SELECT passenger_id, COUNT(*) AS stops
        FROM events WHERE type = 'passenger_transit'
        GROUP BY passenger_id
    """).df()

    if df.empty:
        rep.print("  Sin eventos passenger_transit registrados.")
        return

    rep.print(f"\n  Pasajeros con tránsito intermedio: {len(df)}")
    rep.print(f"  Máx. estaciones intermedias:       {int(df['stops'].max())}")
    rep.print(f"  Promedio:                          {df['stops'].mean():.1f}")

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
    save_fig("passengers_transit", out_dir)
    plt.show()
