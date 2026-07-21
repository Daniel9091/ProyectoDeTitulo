"""
MOLDE 2.0 — Plantilla para escenarios de simulación NSim.
Copia este archivo, renómbralo (ej: escenario_2.py) y completa todos los ...

Convención de nombres:
  - El nombre del archivo = scenario_name en main.py
  - Ej: si el archivo es "hub_asimetrico.py" → scenario_name = "hub_asimetrico"
"""
import random
from objects.math3d import Vector3
from objects.modular_vehicle import ModularVehicle
from objects.passenger_id_generator import PassengerIdGenerator
from objects.station import Station
from systems.network import Network
from systems.continuous_train import ContinuousTrain
from systems.brain import Brain
from simulation.station_factory import TrackIdAllocator, create_station, connect_station_to_network
from telemetry.recorder import NullRecorder
from config.constants import TREE_DZ


# ─── PARÁMETROS ──────────────────────────────────────────────────────────────
# Edita estos valores para definir el escenario.

VM_CAPACITY = ...      # int — personas por VM (ej: 6)
DENSITY     = ...      # float 0.0–1.0 — fracción de slots ocupados al inicio (ej: 1.0 = 100%)
BELT_MARGIN = 150.0    # float — metros libres antes del primer y después del último árbol

# Coordenada Y y Z de todas las estaciones (dejar en 0.0 para red lineal estándar)
STATION_Y = 0.0
STATION_Z = 0.0
BELT_Z    = STATION_Z - TREE_DZ   # el carril siempre está TREE_DZ por debajo de las estaciones


# ── Posición X de cada estación (metros desde el origen) ─────────────────────
# Separación mínima recomendada: ~1000 m entre estaciones contiguas
X_S1 = ...   # float — estación 1 (ej: 500.0)
X_S2 = ...   # float — estación 2 (ej: 1500.0)
# Agrega X_S3, X_S4, ... según cuántas estaciones tenga el escenario

# ── Probabilidades de destino por estación ───────────────────────────────────
# dict[int, float] — claves = station_id destino, valores suman 1.0
# No incluir la propia estación como destino
DEST_FROM_1 = {2: ...}          # ej: {2: 1.0} si solo hay 2 estaciones
DEST_FROM_2 = {1: ...}          # ej: {1: 0.5, 3: 0.5} si hay 3 estaciones
# Agrega DEST_FROM_3, DEST_FROM_4, ...

# ── Tasas de generación ───────────────────────────────────────────────────────
# RATE = pasajeros/segundo que genera la estación
# VM_RATE = VMs/segundo que la estación solicita al sistema
# Regla de pulgar: VM_RATE = RATE / VM_CAPACITY (1 VM cuando se llenan los asientos)
RATE_S1    = ...              # float (ej: 0.2 → 1 pasajero cada 5 s)
VM_RATE_S1 = RATE_S1 / VM_CAPACITY

RATE_S2    = ...
VM_RATE_S2 = RATE_S2 / VM_CAPACITY
# Agrega RATE_S3, VM_RATE_S3, ...

# ─── BUILD ───────────────────────────────────────────────────────────────────

def build(seed: int = 42, recorder=None) -> tuple[Brain, dict[int, Station]]:
    """
    Construye el escenario.
    Retorna (brain, stations) listo para llamar brain.update(dt, current_time).
    """
    if recorder is None:
        recorder = NullRecorder()

    rng     = random.Random(seed)
    pid_gen = PassengerIdGenerator()
    alloc   = TrackIdAllocator(start=1)
    network = Network()
    stations: dict[int, Station] = {}

    # ── Estación 1 — descripción breve (ej: terminal izquierda, 1 andén) ─────
    s1, up1, l1, dn1, j_up_1, j_dn_1 = create_station(
        station_id=1,
        station_origin=Vector3(X_S1, STATION_Y, STATION_Z),
        num_lanes=...,               # int — cantidad de andenes (ej: 1)
        passenger_rate=RATE_S1,
        destination_probabilities=DEST_FROM_1,
        vm_request_rate=VM_RATE_S1,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up1, l1, dn1, j_up_1, j_dn_1)
    stations[1] = s1

    # ── Estación 2 — descripción breve ───────────────────────────────────────
    s2, up2, l2, dn2, j_up_2, j_dn_2 = create_station(
        station_id=2,
        station_origin=Vector3(X_S2, STATION_Y, STATION_Z),
        num_lanes=...,
        passenger_rate=RATE_S2,
        destination_probabilities=DEST_FROM_2,
        vm_request_rate=VM_RATE_S2,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
        recorder=recorder,
    )
    connect_station_to_network(network, up2, l2, dn2, j_up_2, j_dn_2)
    stations[2] = s2

    # ── Agrega más estaciones copiando el bloque anterior ────────────────────
    # Recuerda: incrementar station_id, usar X_S3/RATE_S3/etc., y agregar a stations[N]

    # ── Belt ─────────────────────────────────────────────────────────────────
    # belt_end_x: toma el máximo de todos los j_dn_N.belt_x y agrega el margen
    belt_end_x = max(j_dn_1.belt_x, j_dn_2.belt_x) + BELT_MARGIN
    # Si tienes más estaciones: max(j_dn_1.belt_x, j_dn_2.belt_x, j_dn_3.belt_x, ...) + BELT_MARGIN

    train = ContinuousTrain(
        start_pos  = Vector3(0.0, 0.0, BELT_Z),
        end_pos    = Vector3(belt_end_x, STATION_Y, BELT_Z),
        density    = DENSITY,
        vm_factory = lambda vm_id: ModularVehicle(vm_id, capacity=VM_CAPACITY),
        rng        = rng,
        junction_points = {
            1: j_up_1.belt_x,
            2: j_up_2.belt_x,
            # Agrega: N: j_up_N.belt_x  por cada estación extra
        },
        recorder=recorder,
    )

    brain = Brain(train=train, network=network, stations=stations, recorder=recorder)
    return brain, stations