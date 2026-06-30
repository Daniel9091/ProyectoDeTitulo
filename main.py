# NSim/main.py
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from simulation_builder import inicial
from simulation.simulation import Simulation
from config.constants import FPS


N_SECONDS = 60 * 100              # cuántos segundos simular
N_TICKS   = FPS * N_SECONDS
PROGRESS  = FPS * 10       # imprimir status cada 10 s simulados

def main():
    print("Construyendo escenario...")
    brain, stations = inicial.build(seed=42)
    sim = Simulation(brain, stations)

    print(f"Corriendo {N_TICKS} ticks ({N_SECONDS}s simulados) a {FPS} FPS...")
    for tick in range(N_TICKS):
        sim.step(1.0 / FPS)
        if (tick + 1) % PROGRESS == 0:
            vms_en_belt = sum(1 for s in brain._train.slots if s['vm'] is not None)
            print(f"  t={sim.current_time:.0f}s — VMs en belt: {vms_en_belt}/{brain._train.max_slots}")

    print(f"\nFin. Tiempo simulado: {sim.current_time:.1f}s")

if __name__ == "__main__":
    main()