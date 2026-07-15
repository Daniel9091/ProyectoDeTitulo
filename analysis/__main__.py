"""
Punto de entrada del paquete: python -m analysis [run_id]
"""
import sys
from analysis._shared import resolve_run
from analysis import passengers, modular_vehicles, stations


def main():
    run_arg    = sys.argv[1] if len(sys.argv) > 1 else None
    events_path = resolve_run(run_arg)
    print(f"Analizando: {events_path}")

    passengers.run(events_path)
    modular_vehicles.run(events_path)
    stations.run(events_path)
    print("\nAnálisis completo.")


if __name__ == "__main__":
    main()
