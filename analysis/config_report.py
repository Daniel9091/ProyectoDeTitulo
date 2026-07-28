"""
Config report — condiciones iniciales completas de la corrida.

Lee run_started (config) y run_ended (summary).
Report: config_report.txt
"""
from analysis._shared import resolve_run, connect, get_output_dir, Reporter, get_event_types


def run(events_path=None):
    if events_path is None:
        events_path = resolve_run()
    con = connect(events_path)
    out_dir = get_output_dir(events_path)
    rep = Reporter(out_dir, "config_report")

    types = get_event_types(events_path, con)

    if 'run_started' not in types:
        rep.print("[sin run_started — config no disponible]")
        rep.save()
        con.close()
        return

    config = con.execute(
        "SELECT config FROM events WHERE type = 'run_started' LIMIT 1"
    ).fetchone()[0]

    summary = None
    if 'run_ended' in types:
        row = con.execute(
            "SELECT summary FROM events WHERE type = 'run_ended' LIMIT 1"
        ).fetchone()
        if row:
            summary = row[0]

    rep.print("=== CONDICIONES INICIALES DE LA CORRIDA ===\n")
    rep.print(f"  run_id:         {config.get('run_id', 'N/A')}")
    rep.print(f"  seed:           {config.get('seed', 'N/A')}")
    rep.print(f"  scenario_name:  {config.get('scenario_name', 'N/A')}")

    if summary:
        rep.print(f"\n  Tiempo simulado:  {summary.get('simulated_seconds', '?'):.1f} s")
        rep.print(f"  Tiempo real:      {summary.get('wall_clock_seconds', '?')} s")
        rep.print(f"  Vueltas del belt: {summary.get('train_laps', '?'):.3f}")

    belt = config.get("belt", {})
    if belt:
        rep.print("\n--- Belt ---")
        rep.print(f"  largo total:    {belt.get('total_length_m')} m")
        rep.print(f"  slots totales:  {belt.get('max_slots')}")
        rep.print(f"  densidad init:  {belt.get('density')}")
        rep.print(f"  capacidad VM:   {belt.get('vm_capacity')} pax")
        rep.print(f"  junctions:")
        for sid, bx in sorted((belt.get("junction_points") or {}).items(), key=lambda x: int(x[0])):
            rep.print(f"    Estación {sid}: belt_x = {bx} m")

    station_list = config.get("stations", [])
    if station_list:
        rep.print("\n--- Estaciones ---")
        for st in station_list:
            dest = st.get("destination_probabilities", {})
            dest_str = ", ".join(
                f"S{k}={float(v):.0%}"
                for k, v in sorted(dest.items(), key=lambda x: int(x[0]))
                if v is not None
            )

            rep.print(f"\n  Estación {st['station_id']}:")
            rep.print(f"    posición:        ({st['x']}, {st['y']}, {st['z']}) m")
            rep.print(f"    andenes:         {st['num_andenes']}")
            rep.print(f"    tasa pasajeros:  {st['passenger_rate']:.4g} pax/s")
            rep.print(f"    tasa VMs:        {st['vm_request_rate']:.4g} VM/s")
            rep.print(f"    destinos:        {dest_str}")

    constants = config.get("constants", {})
    if constants:
        rep.print("\n--- Constantes de simulación ---")
        for key, val in constants.items():
            if isinstance(val, float):
                rep.print(f"  {key:<35} {val:.6g}")
            else:
                rep.print(f"  {key:<35} {val}")

    rep.save()
    con.close()
