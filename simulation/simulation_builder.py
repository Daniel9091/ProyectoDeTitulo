# """
# simulation_builder.py — Construcción del escenario de simulación.

# Responsabilidades:
#     - Instanciar y conectar todos los objetos de la simulación
#     - Calcular posiciones geométricas derivadas de las constantes físicas
#     - Exponer build_simulation() → (brain, train, network, stations)

# Lo que NO hace:
#     - No ejecuta el loop de simulación (eso es simulation.py)
#     - No renderiza nada

# Escenario actual: 2 estaciones, 1 andén cada una.

# Constantes de escenario (sección PARÁMETROS):
#     TOTAL_BELT_LENGTH   largo del tren continuo circular (m)
#     LANE_LENGTH         largo de cada boarding lane (m)
#     INITIAL_DENSITY     fracción de slots inicialmente con VM [0.0-1.0]
#     VM_CAPACITY         pasajeros por VM
#     S*_UP_X             belt_x donde cada estación recoge VMs
#     S*_DOWN_X           se calcula automáticamente desde la física — no tocar

# Orden de construcción (invariante):
#     1. PassengerIdGenerator
#     2. ContinuousTrain
#     3. AccelerationTrees + BoardingLanes
#     4. Junctions
#     5. Network
#     6. Stations
#     7. Brain
# """





# import random
# import sys
# import os

# sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# from objects.math3d import Vector3
# from objects.types import TreeDirection
# from objects.modular_vehicle import ModularVehicle
# from objects.station import Station, StationDimensions
# from objects.passenger_id_generator import PassengerIdGenerator
# from systems.continuous_train import ContinuousTrain
# from systems.network import Network
# from systems.brain import Brain
# from tracks.acceleration_tree import AccelerationTree
# from tracks.boarding_lane import BoardingLane
# from tracks.junction import Junction
# from config.constants import (
#     TREE_ACCELERATION, BOARDING_LANE_SPEED, TRAIN_SPEED,
#     TRAIN_SPACING, MIN_VM_SEPARATION,
# )

# # ─── PARÁMETROS DE ESCENARIO ────────────────────────────────────────────────

# TOTAL_BELT_LENGTH = 600.0   # m → 300 slots (a TRAIN_SPACING=2.0)
# INITIAL_DENSITY   = 0.3     # fracción de slots inicialmente ocupados
# VM_CAPACITY       = 4       # pasajeros por VM
# LANE_LENGTH       = 20.0    # m por boarding lane

# S1_ID   = 1
# S1_UP_X = 50.0              # belt_x de UP junction de estación 1

# S2_ID   = 2
# S2_UP_X = 350.0             # belt_x de UP junction de estación 2

# # IDs únicos en toda la red  ← no deben repetirse entre estaciones
# _S1_UP_ID   = 10
# _S1_LANE_ID = 11
# _S1_DN_ID   = 12
# _S2_UP_ID   = 13
# _S2_LANE_ID = 14
# _S2_DN_ID   = 15

# _S1_JUP_ID  = 20
# _S1_JDN_ID  = 21
# _S2_JUP_ID  = 22
# _S2_JDN_ID  = 23

# # TREE_LENGTH se deriva de las constantes para que la reserva matemática sea correcta:
# #   brain.py asume T_tree = (TRAIN_SPEED - BOARDING_LANE_SPEED) / TREE_ACCELERATION
# #   El árbol debe medir exactamente la distancia que un VM recorre en ese tiempo.
# #   UP:   d = TRAIN_SPEED*T - 0.5*TREE_ACCELERATION*T^2
# #   DOWN: d = BOARDING_LANE_SPEED*T + 0.5*TREE_ACCELERATION*T^2  (igual por simetría)
# #   Con defaults: T=7.2s → TREE_LENGTH=79.2m
# _T_TREE     = (TRAIN_SPEED - BOARDING_LANE_SPEED) / TREE_ACCELERATION
# TREE_LENGTH = BOARDING_LANE_SPEED * _T_TREE + 0.5 * TREE_ACCELERATION * _T_TREE ** 2


# # ─── HELPERS ────────────────────────────────────────────────────────────────

# def _junction_down_x(up_x: float) -> float:
#     """
#     belt_x del DOWN junction para un UP junction dado.

#     Un VM tarda T_transit = T_up + T_lane + T_down en atravesar la estación.
#     Durante ese tiempo el belt avanza TRAIN_SPEED * T_transit metros.
#     El DOWN junction debe estar exactamente ahí (módulo TOTAL_BELT_LENGTH).

#     Con defaults: T_transit=24.4s, belt_advance=488m.
#     """
#     T_transit = _T_TREE + (LANE_LENGTH / BOARDING_LANE_SPEED) + _T_TREE
#     return (up_x + TRAIN_SPEED * T_transit) % TOTAL_BELT_LENGTH


# def _vm_factory(vm_id: int) -> ModularVehicle:
#     return ModularVehicle(vehicle_id=vm_id, capacity=VM_CAPACITY)


# def _build_station_tracks(station_id: int, up_x: float, down_x: float,
#                            up_id: int, lane_id: int, dn_id: int):
#     """
#     Crea los 3 tracks de una estación: UP tree → boarding lane → DOWN tree.

#     Geometría:
#         UP tree:       vertical en Z,   (up_x, 0, 0)          → (up_x, 0, TREE_LENGTH)
#         Boarding lane: horizontal en Y, (up_x, 0, TREE_LENGTH) → (up_x, LANE_LENGTH, TREE_LENGTH)
#         DOWN tree:     vertical en Z,   (down_x, 0, TREE_LENGTH) → (down_x, 0, 0)

#     Las longitudes resultantes son TREE_LENGTH, LANE_LENGTH, TREE_LENGTH.
#     UP y DOWN están en belt_x distintos — la conexión lógica es la adyacencia de Network.
#     """
#     up_tree = AccelerationTree(
#         track_id          = up_id,
#         start_pos         = Vector3(up_x,   0.0, 0.0),
#         end_pos           = Vector3(up_x,   0.0, TREE_LENGTH),
#         direction         = TreeDirection.UP,
#         base_acceleration = TREE_ACCELERATION,
#         min_vm_separation = MIN_VM_SEPARATION,
#         station_id        = None,
#     )
#     lane = BoardingLane(
#         track_id  = lane_id,
#         start_pos = Vector3(up_x, 0.0,         TREE_LENGTH),
#         end_pos   = Vector3(up_x, LANE_LENGTH,  TREE_LENGTH),
#     )
#     down_tree = AccelerationTree(
#         track_id          = dn_id,
#         start_pos         = Vector3(down_x, 0.0, TREE_LENGTH),
#         end_pos           = Vector3(down_x, 0.0, 0.0),
#         direction         = TreeDirection.DOWN,
#         base_acceleration = TREE_ACCELERATION,
#         min_vm_separation = MIN_VM_SEPARATION,  # ignorado en DOWN
#         station_id        = station_id,
#     )
#     return up_tree, lane, down_tree


# # ─── FUNCIÓN PRINCIPAL ────────────────────────────────────────────────────

# def build_simulation():
#     """
#     Construye la simulación completa.

#     Retorna:
#         brain    Brain
#         train    ContinuousTrain
#         network  Network
#         stations dict[int, Station]
#     """
#     rng     = random.Random(42)
#     pid_gen = PassengerIdGenerator()

#     s1_dn_x = _junction_down_x(S1_UP_X)   # 538.0 con los defaults
#     s2_dn_x = _junction_down_x(S2_UP_X)   # 238.0 con los defaults

#     # ── 1. ContinuousTrain ────────────────────────────────────────────────
#     # junction_points solo lleva UP junctions: son los crossings que Brain recibe
#     train = ContinuousTrain(
#         start_pos       = Vector3(0.0, 0.0, 0.0),
#         end_pos         = Vector3(TOTAL_BELT_LENGTH, 0.0, 0.0),
#         density         = INITIAL_DENSITY,
#         vm_factory      = _vm_factory,
#         rng             = rng,
#         junction_points = {S1_ID: S1_UP_X, S2_ID: S2_UP_X},
#     )

#     # ── 2. Tracks ─────────────────────────────────────────────────────────
#     up1, lane1, dn1 = _build_station_tracks(S1_ID, S1_UP_X, s1_dn_x,
#                                              _S1_UP_ID, _S1_LANE_ID, _S1_DN_ID)
#     up2, lane2, dn2 = _build_station_tracks(S2_ID, S2_UP_X, s2_dn_x,
#                                              _S2_UP_ID, _S2_LANE_ID, _S2_DN_ID)

#     # ── 3. Junctions ──────────────────────────────────────────────────────
#     j_up1  = Junction(_S1_JUP_ID,  S1_UP_X,  S1_ID, TreeDirection.UP,   [up1])
#     j_dn1  = Junction(_S1_JDN_ID,  s1_dn_x,  S1_ID, TreeDirection.DOWN, [dn1])
#     j_up2  = Junction(_S2_JUP_ID,  S2_UP_X,  S2_ID, TreeDirection.UP,   [up2])
#     j_dn2  = Junction(_S2_JDN_ID,  s2_dn_x,  S2_ID, TreeDirection.DOWN, [dn2])

#     # ── 4. Network ────────────────────────────────────────────────────────
#     network = Network()
#     for track in [up1, lane1, dn1, up2, lane2, dn2]:
#         network.add_track(track)

#     network.connect(_S1_UP_ID,   _S1_LANE_ID)   # up1 → lane1
#     network.connect(_S1_LANE_ID, _S1_DN_ID)     # lane1 → dn1  (dn1 es terminal)
#     network.connect(_S2_UP_ID,   _S2_LANE_ID)
#     network.connect(_S2_LANE_ID, _S2_DN_ID)

#     for j in [j_up1, j_dn1, j_up2, j_dn2]:
#         network.add_junction(j)

#     # ── 5. Stations ───────────────────────────────────────────────────────
#     dims = StationDimensions(
#         x_length     = 50.0,
#         y_length     = LANE_LENGTH,
#         floor_height = TREE_LENGTH,
#         num_floors   = 1,
#     )

#     station1 = Station(
#         station_id               = S1_ID,
#         origin                   = Vector3(S1_UP_X, 0.0, 0.0),
#         dimensions               = dims,
#         passenger_rate           = 0.5,
#         destination_probabilities= {S2_ID: 1.0},
#         vm_request_rate          = 0.1,
#         andenes=[{
#             'lane'            : lane1,
#             'up_tree_id'      : _S1_UP_ID,
#             'down_tree_id'    : _S1_DN_ID,
#             'extraction_point': Vector3(S1_UP_X, 0.0,        TREE_LENGTH),
#             'discharge_point' : Vector3(S1_UP_X, LANE_LENGTH, TREE_LENGTH),
#         }],
#         rng          = rng,
#         id_generator = pid_gen,
#     )

#     station2 = Station(
#         station_id               = S2_ID,
#         origin                   = Vector3(S2_UP_X, 0.0, 0.0),
#         dimensions               = dims,
#         passenger_rate           = 0.5,
#         destination_probabilities= {S1_ID: 1.0},
#         vm_request_rate          = 0.1,
#         andenes=[{
#             'lane'            : lane2,
#             'up_tree_id'      : _S2_UP_ID,
#             'down_tree_id'    : _S2_DN_ID,
#             'extraction_point': Vector3(S2_UP_X, 0.0,        TREE_LENGTH),
#             'discharge_point' : Vector3(S2_UP_X, LANE_LENGTH, TREE_LENGTH),
#         }],
#         rng          = rng,
#         id_generator = pid_gen,
#     )

#     stations = {S1_ID: station1, S2_ID: station2}

#     # ── 6. Brain ──────────────────────────────────────────────────────────
#     brain = Brain(train=train, network=network, stations=stations)

#     return brain, train, network, stations


# # ─── VERIFICACIÓN RÁPIDA ─────────────────────────────────────────────────────
# if __name__ == "__main__":
#     brain, train, network, stations = build_simulation()

#     s1_dn = _junction_down_x(S1_UP_X)
#     s2_dn = _junction_down_x(S2_UP_X)
#     print(f"TREE_LENGTH  = {TREE_LENGTH:.2f} m")
#     print(f"Belt: {train.total_length:.0f} m, {train.max_slots} slots")
#     print(f"S1: UP={S1_UP_X:.0f}m  DOWN={s1_dn:.0f}m")
#     print(f"S2: UP={S2_UP_X:.0f}m  DOWN={s2_dn:.0f}m")
#     print(f"VMs iniciales en belt: {sum(1 for s in train.slots if s['vm'] is not None)}")

#     print("\nCorriendo 300 ticks (10s a 30 FPS)...")
#     DT = 1.0 / 30.0
#     for tick in range(300):
#         brain.update(DT, tick * DT)

#     print(f"VMs en network: {network.total_vehicle_count}")
#     print(f"VMs en belt:    {sum(1 for s in train.slots if s['vm'] is not None)}")
#     print("OK — sin crashes")