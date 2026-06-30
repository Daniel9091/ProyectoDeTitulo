# NSim/simulation_builder/escenario_base.py
"""
Escenario base: 3 estaciones lineales, estación central como hub principal.
Estudia: comportamiento del sistema con demanda asimétrica y múltiples andenes en el hub.
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

VM_CAPACITY    = 6        # VMs pequeños tipo pod de 6 personas
JUNCTION_DEPTH = 3.0      # belt 3m bajo el piso de la estación
DENSITY        = 1.0      # 100% de slots ocupados al iniciar
BELT_MARGIN    = 150.0

DIMS = StationDimensions(
    x_length   = 100.0,   # 100m de largo (ancho en X del hall)
    y_length   = 30.0,    # 30m de ancho (permite 3 andenes cómodos)
    floor_height = 5.0,   # 5m de altura de planta baja
    num_floors = 1,
)

# Estaciones en línea recta, separadas 1 km entre sí
X_S1 = 500.0
X_S2 = 1500.0
X_S3 = 2500.0

# Probabilidades de destino — justificación:
#   S1 y S3 son terminales laterales: la mayoría de sus usuarios van al hub central (S2)
#   S2 es el hub central: flujo equidistante hacia ambos lados
DEST_FROM_1 = {2: 0.7, 3: 0.3}   # 70% al hub, 30% al extremo opuesto
DEST_FROM_2 = {1: 0.5, 3: 0.5}   # 50/50, es equidistante a ambos
DEST_FROM_3 = {1: 0.3, 2: 0.7}   # simétrico a S1

# Tasas de pasajeros — S2 tiene 3 andenes así que puede procesar 3x más
RATE_S1 = 0.2          # 1 pasajero cada 5 s
RATE_S2 = 0.6          # 3 andenes × 0.2 = 0.6 pasajeros/s
RATE_S3 = 0.2

VM_RATE_S1 = RATE_S1 / VM_CAPACITY   # ~1 VM cada 30 s
VM_RATE_S2 = RATE_S2 / VM_CAPACITY
VM_RATE_S3 = RATE_S3 / VM_CAPACITY


def build(seed: int = 42) -> tuple[Brain, dict[int, Station]]:
    """
    Construye el escenario base.
    Retorna (brain, stations) listo para llamar brain.update(dt, current_time).
    """
    rng     = random.Random(seed)
    pid_gen = PassengerIdGenerator()
    alloc   = TrackIdAllocator(start=1)
    network = Network()
    stations: dict[int, Station] = {}

    # ── Estación 1 — terminal izquierda, 1 andén ─────────────────────────────
    s1, up1, l1, dn1, j_up_1, j_dn_1 = create_station(
        station_id=1,
        station_origin=Vector3(X_S1, 0.0, 0.0),
        junction_depth=JUNCTION_DEPTH,
        num_lanes=1,
        dims=DIMS,
        passenger_rate=RATE_S1,
        destination_probabilities=DEST_FROM_1,
        vm_request_rate=VM_RATE_S1,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
    )
    connect_station_to_network(network, up1, l1, dn1, j_up_1, j_dn_1)
    stations[1] = s1

    # ── Estación 2 — hub central, 3 andenes ──────────────────────────────────
    s2, up2, l2, dn2, j_up_2, j_dn_2 = create_station(
        station_id=2,
        station_origin=Vector3(X_S2, 0.0, 0.0),
        junction_depth=JUNCTION_DEPTH,
        num_lanes=3,
        dims=DIMS,
        passenger_rate=RATE_S2,
        destination_probabilities=DEST_FROM_2,
        vm_request_rate=VM_RATE_S2,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
    )
    connect_station_to_network(network, up2, l2, dn2, j_up_2, j_dn_2)
    stations[2] = s2

    # ── Estación 3 — terminal derecha, 1 andén ───────────────────────────────
    s3, up3, l3, dn3, j_up_3, j_dn_3 = create_station(
        station_id=3,
        station_origin=Vector3(X_S3, 0.0, 0.0),
        junction_depth=JUNCTION_DEPTH,
        num_lanes=1,
        dims=DIMS,
        passenger_rate=RATE_S3,
        destination_probabilities=DEST_FROM_3,
        vm_request_rate=VM_RATE_S3,
        rng=rng, id_generator=pid_gen, id_alloc=alloc,
    )
    connect_station_to_network(network, up3, l3, dn3, j_up_3, j_dn_3)
    stations[3] = s3

    # ── Belt ─────────────────────────────────────────────────────────────────
    # El tamaño del belt se determina aquí, después de conocer los belt_x calculados
    belt_end_x = max(j_dn_1.belt_x, j_dn_2.belt_x, j_dn_3.belt_x) + BELT_MARGIN
    train = ContinuousTrain(
        start_pos       = Vector3(0.0, 0.0, JUNCTION_DEPTH),
        end_pos         = Vector3(belt_end_x, 0.0, JUNCTION_DEPTH),
        density         = DENSITY,
        vm_factory      = lambda vm_id: ModularVehicle(vm_id, capacity=VM_CAPACITY),
        rng             = rng,
        junction_points = {
            1: j_up_1.belt_x,
            2: j_up_2.belt_x,
            3: j_up_3.belt_x,
        },
    )

    brain = Brain(train=train, network=network, stations=stations)
    return brain, stations
