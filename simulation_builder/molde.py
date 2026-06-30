"""
MOLDE — Estructura base para construir escenarios de simulación.
Copia este archivo, renómbralo y rellena los ... con valores reales.
No está pensado para correr directamente.
"""
import random
from objects.math3d import Vector3
from objects.station import Station, StationDimensions
from objects.passenger_id_generator import PassengerIdGenerator
from objects.modular_vehicle import ModularVehicle
from systems.network import Network
from systems.continuous_train import ContinuousTrain
from systems.brain import Brain
from simulation.station_factory import TrackIdAllocator, create_station, connect_station_to_network

# ─── PARÁMETROS ──────────────────────────────────────────────────────────────

VM_CAPACITY:    int   = ...
JUNCTION_DEPTH: float = ...
DENSITY:        float = ...
BELT_MARGIN:    float = 150.0

DIMS = StationDimensions(
    x_length     = ...,
    y_length     = ...,
    floor_height = ...,
    num_floors   = 1,
)

X_S1: float = ...
DEST_FROM_1: dict = ...
RATE_S1:     float = ...
VM_RATE_S1:  float = ...


def build(seed: int = 42) -> tuple[Brain, dict]:
    rng     = random.Random(seed)
    pid_gen = PassengerIdGenerator()
    alloc   = TrackIdAllocator(start=1)
    network = Network()
    stations: dict[int, Station] = {}

    s1, up1, l1, dn1, j_up_1, j_dn_1 = create_station(
        station_id=1,
        station_origin=Vector3(X_S1, 0.0, 0.0),
        junction_depth=JUNCTION_DEPTH,
        num_lanes=...,
        dims=DIMS,
        passenger_rate=RATE_S1,
        destination_probabilities=DEST_FROM_1,
        vm_request_rate=VM_RATE_S1,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
    )
    connect_station_to_network(network, up1, l1, dn1, j_up_1, j_dn_1)
    stations[1] = s1

    belt_end_x: float = ...
    train = ContinuousTrain(
        start_pos       = Vector3(0.0, 0.0, JUNCTION_DEPTH),
        end_pos         = Vector3(belt_end_x, 0.0, JUNCTION_DEPTH),
        density         = DENSITY,
        vm_factory      = lambda vm_id: ModularVehicle(vm_id, capacity=VM_CAPACITY),
        rng             = rng,
        junction_points = {1: j_up_1.belt_x},
    )

    brain = Brain(train=train, network=network, stations=stations)
    return brain, stations
