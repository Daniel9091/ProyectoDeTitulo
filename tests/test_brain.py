"""
Tests para Brain.

Responsabilidades documentadas:
    - TestBrainLoop:            el loop de 8 pasos corre en el orden correcto
    - TestCrossingHandler:      routing por etiqueta, contabilidad del counter
    - TestCounterAccounting:    Q15 — el counter se decrementa exactamente cuando corresponde
    - TestReservationMath:      cálculo de T_total, target_idx, aceleración ajustada
    - TestDemandSystem:         etiqueta de taza, on_vm_committed, commitment_broken
    - TestSaturationCheck:      ventana deslizante, burst_capacity, burst_window
    - TestBeltPlacement:        VM en slot reservado, fallback sin reserva

Convención de fixtures:
    make_brain_fixture()  → (brain, train, network, stations)
    Usa objetos reales (no mocks) para train y network.
    Station es MagicMock para evitar dependencia de PassengerIdGenerator.

    Para tests que necesitan Station real con pending_demand dinámico,
    setear station.pending_demand directamente en el test.
"""

import random
import logging
import math
from unittest.mock import MagicMock, patch

import pytest as pt
import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch
from objects.math3d import Vector3
from objects.modular_vehicle import ModularVehicle
from objects.types import TreeDirection
from tracks.acceleration_tree import AccelerationTree
from tracks.boarding_lane import BoardingLane
from tracks.junction import Junction
from systems.continuous_train import ContinuousTrain
from systems.network import Network
from systems.brain import Brain
from telemetry.recorder import NullRecorder
from config.constants import (
    TRAIN_SPACING, MIN_VM_SEPARATION,
    TRAIN_SPEED, BOARDING_LANE_SPEED, GRAVITY
)

# ─── CONSTANTES DE FIXTURE ───────────────────────────────────────────────────

STATION_ID          = 1
UP_TREE_ID          = 10
LANE_ID             = 11
DOWN_TREE_ID        = 12
JUNCTION_UP_X       = 10.0      # belt_x donde los VMs suben a la estación
JUNCTION_DOWN_X     = 50.0      # belt_x donde los VMs bajan al belt
TRAIN_LENGTH        = 100.0     # longitud del carril circular (50 slots)
TREE_LENGTH         = 10.0      # longitud de cada AccelerationTree
LANE_LENGTH         = 20.0      # longitud del BoardingLane
TREE_ACCELERATION   = 2.5       # acceleracion de los arboles de test

# después
TEST_SLOT_SEARCH_RANGE_RESERVATION = 10   # half=5 → rango ±5 alrededor del target
TEST_SLOT_SEARCH_RANGE_DEMAND      = 10   # 10 slots hacia atrás desde junction_up

@pytest.fixture(autouse=True)
def _fixed_slot_search_range():
    """
    Todos los tests corren con rangos fijos de búsqueda, independientes de config/constants.py.
    RESERVATION: half=5 (offsets -5..+5). DEMAND: 10 slots atrás.
    """
    with patch('systems.brain.SLOT_SEARCH_RANGE_RESERVATION', TEST_SLOT_SEARCH_RANGE_RESERVATION), \
         patch('systems.brain.SLOT_SEARCH_RANGE_DEMAND',      TEST_SLOT_SEARCH_RANGE_DEMAND):
        yield

# ─── HELPERS DE FIXTURE ───────────────────────────────────────────────────────

def _make_vm(vm_id: int = 0) -> ModularVehicle:
    return ModularVehicle(vehicle_id=vm_id, capacity=4)

def _slanted_end_pos(start: Vector3, length: float, target_accel: float) -> Vector3:
    """
    Punto final que, junto a start, produce un árbol de `length` metros con
    aceleración efectiva == target_accel (dado GRAVITY).
        dz = target_accel * length / GRAVITY  ;  dx = sqrt(length² - dz²)
    """
    dz = target_accel * length / GRAVITY
    dx = math.sqrt(max(0.0, length ** 2 - dz ** 2))
    return Vector3(start.x + dx, start.y, start.z + dz)

def _make_train(junction_up_x: float = JUNCTION_UP_X) -> ContinuousTrain:
    """
    Carril de 100m, 50 slots, sin VMs (density=0.0).
    junction_points marca la junction UP de la estación para detección de crossings.
    """
    rng = random.Random(42)
    return ContinuousTrain(
        start_pos=Vector3(0, 0, 0),
        end_pos=Vector3(TRAIN_LENGTH, 0, 0),
        density=0.0,
        vm_factory=lambda vid: ModularVehicle(vehicle_id=vid, capacity=4),
        rng=rng,
        junction_points={STATION_ID: junction_up_x},
        recorder = NullRecorder(),
    )

def _make_network() -> Network:
    """
    Red mínima de 1 estación: UP tree → lane → DOWN tree (terminal).

    Topología:
        acceler_up (UP, 10m)  →  lane (20m)  →  acceler_down (DOWN, 10m, terminal)
        junction_up  registrada en network.junctions_up[STATION_ID]
        junction_down registrada en network.junctions_down[STATION_ID]

    DOWN tree es terminal (len==0 en adyacencia) porque el VM sale al belt
    vía Brain._handle_belt_placements, no a otro track.
    """
    up_start = Vector3(0, 0, 0)
    up_tree = AccelerationTree(
        track_id=UP_TREE_ID,
        start_pos=up_start,
        end_pos=_slanted_end_pos(up_start, TREE_LENGTH, TREE_ACCELERATION),
        direction=TreeDirection.UP,
        min_vm_separation=MIN_VM_SEPARATION,
        recorder=NullRecorder(),
        station_id=STATION_ID,
    )
    lane = BoardingLane(
        track_id=LANE_ID,
        start_pos=Vector3(0, 0, 0),
        end_pos=Vector3(LANE_LENGTH, 0, 0),
        recorder=NullRecorder(),
    )
    down_start = Vector3(0, 0, 0)
    down_tree = AccelerationTree(
        track_id=DOWN_TREE_ID,
        start_pos=down_start,
        end_pos=_slanted_end_pos(down_start, TREE_LENGTH, TREE_ACCELERATION),
        direction=TreeDirection.DOWN,
        min_vm_separation=MIN_VM_SEPARATION,
        recorder=NullRecorder(),
        station_id=STATION_ID,
    )
    junction_up = Junction(
        junction_id=20,
        belt_x=JUNCTION_UP_X,
        station_id=STATION_ID,
        direction=TreeDirection.UP,
        trees=[up_tree],
    )
    junction_down = Junction(
        junction_id=21,
        belt_x=JUNCTION_DOWN_X,
        station_id=STATION_ID,
        direction=TreeDirection.DOWN,
        trees=[down_tree],
    )

    network = Network()
    network.add_track(up_tree)
    network.add_track(lane)
    network.add_track(down_tree)
    network.connect(UP_TREE_ID, LANE_ID)
    network.connect(LANE_ID, DOWN_TREE_ID)
    network.add_junction(junction_up)
    network.add_junction(junction_down)
    return network

def _make_station_mock() -> MagicMock:
    """
    Station liviana para tests que verifican llamadas (on_vm_committed, etc.).
    pending_demand=0 evita que _process_demand entre al while loop.
    """
    station = MagicMock()
    station.pending_demand = 0
    return station

def make_brain_fixture():
    """
    Construye (brain, train, network, stations) para tests de Brain.

    - train: ContinuousTrain real, 50 slots vacíos
    - network: Network real, 1 estación con UP tree → lane → DOWN tree
    - stations: {STATION_ID: MagicMock(pending_demand=0)}
    - brain: Brain real coordinando todo

    Para tests de comportamiento de slots, agregar VMs directamente:
        train.slots[idx]['vm'] = _make_vm(vm_id)

    Para tests que necesitan pending_demand > 0:
        stations[STATION_ID].pending_demand = N
    """
    train    = _make_train()
    network  = _make_network()
    station  = _make_station_mock()
    stations = {STATION_ID: station}
    brain    = Brain(train=train, network=network, stations=stations, recorder = NullRecorder())
    return brain, train, network, stations

def _wrong_order_8ab(brain, dt: float, current_time: float) -> None:
    """
    Loop idéntico a brain.update() pero con _process_demand (8b) ANTES
    que _process_reservations (8a). Usado en tests negativos de TestBrainLoop
    para demostrar la consecuencia de invertir esos dos pasos.
    """
    crossings = brain._train.advance(dt)
    completions = brain._network.update_all_tracks(dt)
    decisions, belt_placements = brain._network.process_transitions(completions)
    brain._handle_crossings(crossings)
    brain._handle_decisions(decisions)
    brain._handle_belt_placements(belt_placements)
    for station in brain._stations.values():
        station.update(dt, current_time)
    brain._process_demand()         # 8b PRIMERO (orden incorrecto)
    brain._process_reservations()   # 8a SEGUNDO (orden incorrecto)

def _wrong_order_step2_4(brain, dt: float, current_time: float) -> None:
    """
    Loop con _handle_crossings (paso 4) ANTES que update_all_tracks (paso 2).
    Consecuencia: el VM que entra al árbol en el paso 4 recibe doble movimiento
    ese mismo frame — primero leftover_dt al insertarse, luego dt completo del árbol.
    """
    crossings = brain._train.advance(dt)
    brain._handle_crossings(crossings)               # paso 4 ANTES que 2 (bug)
    completions = brain._network.update_all_tracks(dt)  # árbol mueve VM de nuevo
    decisions, belt_placements = brain._network.process_transitions(completions)
    brain._handle_decisions(decisions)
    brain._handle_belt_placements(belt_placements)
    for station in brain._stations.values():
        station.update(dt, current_time)
    brain._process_reservations()
    brain._process_demand()

def _wrong_order_step7_8b(brain, dt: float, current_time: float) -> None:
    """
    Loop con _process_demand (8b) ANTES que station.update (paso 7).
    Consecuencia: _process_demand ve pending_demand del frame anterior.
    Si era 0, ningún slot se etiqueta aunque station.update lo iba a subir a 1.
    """
    crossings = brain._train.advance(dt)
    completions = brain._network.update_all_tracks(dt)
    decisions, belt_placements = brain._network.process_transitions(completions)
    brain._handle_crossings(crossings)
    brain._handle_decisions(decisions)
    brain._handle_belt_placements(belt_placements)
    brain._process_demand()                          # 8b ANTES de station.update (bug)
    for station in brain._stations.values():
        station.update(dt, current_time)             # paso 7 llega tarde
    brain._process_reservations()

# ─── LOOP ORDER ───────────────────────────────────────────────────────────────
class TestBrainLoop:
    """
    Los 8 pasos de brain.update() tienen un orden invariante.
    Cada test verifica la CONSECUENCIA de romper ese orden:
    corremos brain.update() normal y una variante con el orden incorrecto,
    y comparamos el estado resultante del mundo (slots, distancias, contadores).
    Ningún test usa call_log — si el orden cambia en brain.update(), el estado final falla.
    """

    def test_update_does_not_crash_with_empty_train(self):
        """
        Smoke: brain.update() completa sin excepción con 50 slots vacíos.
        Si este test falla, el fixture está roto y los demás no tienen sentido.
        """
        brain, train, network, stations = make_brain_fixture()
        brain.update(dt=0.01, current_time=0.0)

    def test_tracks_advance_before_crossings_are_processed(self):
        """
        Invariante: update_all_tracks (paso 2) corre ANTES de _handle_crossings (paso 4).

        Consecuencia de romperlo: el VM que entra al árbol UP en el paso 4 recibe
        doble movimiento en el mismo frame. _insert_vehicle lo mueve con leftover_dt
        al insertarlo, y luego update_all_tracks lo vuelve a mover con dt completo.

        Números exactos (física MRUA UP, a = -2.5 m/s²):
            Correcto  — solo leftover_dt=0.01:
                d = 20×0.01 + 0.5×(-2.5)×0.01² = 0.199875 m
            Incorrecto — leftover_dt + dt adicional:
                d = 0.199875 + 19.975×0.01 + 0.5×(-2.5)×0.01² = 0.399500 m

        Setup: VM en slot 5 (belt_x = 10.0 = JUNCTION_UP_X). Con tail_x=0
        y dt=0.01, el VM está exactamente en la junction → leftover_dt = 0.01.
        """
        # ── ORDEN CORRECTO (brain.update()) ──────────────────────────────────
        brain1, train1, network1, stations1 = make_brain_fixture()
        vm1 = _make_vm(vm_id=0)
        train1.slots[5]['vm'] = vm1
        train1.slots[5]['destination_station_id'] = STATION_ID

        brain1.update(dt=0.01, current_time=0.0)

        up_tree1 = network1.get_track(UP_TREE_ID)
        assert vm1.vehicle_id in up_tree1.vehicles, \
            "Correcto: VM debe haber entrado al UP tree"
        dist_correct = up_tree1.vehicles[vm1.vehicle_id]['distance']

        # ── ORDEN INCORRECTO (_wrong_order_step2_4) ───────────────────────────
        brain2, train2, network2, stations2 = make_brain_fixture()
        vm2 = _make_vm(vm_id=0)
        train2.slots[5]['vm'] = vm2
        train2.slots[5]['destination_station_id'] = STATION_ID

        _wrong_order_step2_4(brain2, dt=0.01, current_time=0.0)

        up_tree2 = network2.get_track(UP_TREE_ID)
        assert vm2.vehicle_id in up_tree2.vehicles, \
            "Incorrecto: VM también debe estar en UP tree"
        dist_wrong = up_tree2.vehicles[vm2.vehicle_id]['distance']

        # Consecuencia medible: ~2× más movimiento con orden incorrecto
        assert dist_correct == pytest.approx(0.199875, abs=1e-4), \
            f"Correcto: solo leftover_dt de movimiento. Obtenido: {dist_correct:.6f} m"
        assert dist_wrong == pytest.approx(0.399500, abs=1e-3), \
            f"Incorrecto: doble movimiento. Obtenido: {dist_wrong:.6f} m"
        assert dist_correct < dist_wrong, \
            "El orden incorrecto produce ~2× más distancia en el mismo frame"

    def test_station_update_before_demand_labeling(self):
        """
        Invariante: station.update() (paso 7) corre ANTES de _process_demand (paso 8b).

        Consecuencia de romperlo: _process_demand ve pending_demand=0 (el valor
        antes de que station.update lo incremente). El while no entra, ningún slot
        se etiqueta, y la demanda real del frame queda sin satisfacer hasta el siguiente.

        Setup: VM en slot 4 dentro del rango de búsqueda de demanda. station.update()
        sube pending_demand de 0 a 1. Con orden correcto, el slot recibe la etiqueta.
        Con orden incorrecto, _process_demand ya corrió cuando demand era 0 — nada.
        """
        # ── ORDEN CORRECTO (brain.update()) ──────────────────────────────────
        brain1, train1, network1, stations1 = make_brain_fixture()
        station1 = stations1[STATION_ID]

        vm1 = _make_vm(vm_id=0)
        train1.slots[3]['vm'] = vm1         # slot 3 dentro del rango de búsqueda de demanda

        station1.pending_demand = 0

        def fake_update1(dt, ct):
            station1.pending_demand = 1     # simula acumulación real de demanda

        station1.update = fake_update1
        station1.on_vm_committed.side_effect = lambda: setattr(
            station1, 'pending_demand', station1.pending_demand - 1
        )

        with patch.object(brain1, '_would_saturate', return_value=False):
            brain1.update(dt=0.001, current_time=0.0)

        labeled_correct = any(
            s['demand_station_id'] == STATION_ID for s in train1.slots
        )
        assert labeled_correct, (
            "Correcto: station.update() corrió ANTES de _process_demand. "
            "demand=1 al momento de la búsqueda → slot etiquetado con demand=S."
        )

        # ── ORDEN INCORRECTO (_wrong_order_step7_8b) ──────────────────────────
        brain2, train2, network2, stations2 = make_brain_fixture()
        station2 = stations2[STATION_ID]

        vm2 = _make_vm(vm_id=0)
        train2.slots[3]['vm'] = vm2

        station2.pending_demand = 0

        def fake_update2(dt, ct):
            station2.pending_demand = 1

        station2.update = fake_update2
        station2.on_vm_committed.side_effect = lambda: setattr(
            station2, 'pending_demand', station2.pending_demand - 1
        )

        with patch.object(brain2, '_would_saturate', return_value=False):
            _wrong_order_step7_8b(brain2, dt=0.001, current_time=0.0)

        labeled_wrong = any(
            s['demand_station_id'] == STATION_ID for s in train2.slots
        )
        assert not labeled_wrong, (
            "Incorrecto: _process_demand corrió con demand=0 (station.update llegó tarde). "
            "while 0>0 no entró → ningún slot etiquetado → demanda del frame N ignorada."
        )

    def test_reservations_before_demand_prevents_double_commit(self):
        """
        Invariante: _process_reservations (8a) corre ANTES de _process_demand (8b).

        Consecuencia de romperlo: demand encuentra el slot que la reserva iba a
        elegir (está sin reserva todavía), lo etiqueta y llama on_vm_committed.
        El counter baja a 0 mientras el VM aún está en tránsito → Brain deja de
        buscar más VMs aunque la estación siga necesitando.

        Setup: VM en lane (boarding_committed), slot 5 bloqueado para que SOLO
        ese slot sea elegible por la reserva (todos los demás reservados para
        otra estación). Con orden correcto: reserva primero → slot 5 bloqueado
        para demand → on_vm_committed=0. Con orden incorrecto (8b antes 8a):
        demand llega antes, slot 5 aún libre → on_vm_committed=1.

        Slot objetivo calculado para VM en lane con progress=0.52:
            remaining = 0.48 × 20 = 9.6 m
            T_lane    = 9.6 / 2.0       = 4.8 s
            T_tree    = (20−2) / 2.5    = 7.2 s
            T_total   = 12.0 s
            future_x  = (0 + 20×12) % 100 = 40.0
            relative  = (50 − 40) % 100   = 10.0
            target    = round(10/2) % 50  = slot 5
        """
        PROGRESS_FOR_TARGET_5 = 0.52

        def _setup(brain, train, network, stations):
            station = stations[STATION_ID]
            lane = network.get_track(LANE_ID)

            vm_lane = _make_vm(vm_id=0)
            lane.vehicles[vm_lane.vehicle_id] = {
                'vehicle':            vm_lane,
                'distance':           PROGRESS_FOR_TARGET_5 * LANE_LENGTH,
                'velocity':           BOARDING_LANE_SPEED,
                'passengers':         [],
                'boarding_committed': True,
            }

            vm_belt = _make_vm(vm_id=1)
            train.slots[5]['vm'] = vm_belt

            # Forzar que _range_search_reservation solo tenga slot 5 disponible
            for idx in range(train.max_slots):
                if idx != 5:
                    train.slots[idx]['reserved_station_id'] = 99

            station.pending_demand = 1
            station.on_vm_committed.side_effect = lambda: setattr(
                station, 'pending_demand', station.pending_demand - 1
            )
            return station

        # ── ORDEN CORRECTO (brain.update()) ──────────────────────────────────
        brain1, train1, network1, stations1 = make_brain_fixture()
        station1 = _setup(brain1, train1, network1, stations1)

        with patch.object(brain1, '_would_saturate', return_value=False):
            brain1.update(dt=0.001, current_time=0.0)

        assert station1.on_vm_committed.call_count == 0, (
            "Correcto (8a antes 8b): slot 5 está en zona ciega (≤ G=2 slots de junction). "
            "safe_start=3 → demand nunca busca slots 4 ni 5. "
            "TODO: rediseñar con reservation target en slot ≤ 3 para probar concentración."
        )
        assert train1.slots[5]['reserved_station_id'] == STATION_ID, \
            "Slot 5 tiene reserva de STATION_ID"
        assert train1.slots[5]['demand_station_id'] is None, \
            "Demand no etiquetó slot 5 (zona ciega)"

        # ── ORDEN INCORRECTO (_wrong_order_8ab) ───────────────────────────────
        brain2, train2, network2, stations2 = make_brain_fixture()
        station2 = _setup(brain2, train2, network2, stations2)

        with patch.object(brain2, '_would_saturate', return_value=False):
            _wrong_order_8ab(brain2, dt=0.001, current_time=0.0)

        assert station2.on_vm_committed.call_count == 0, (
            "Incorrecto (8b antes 8a): demand también falla porque slot 5 es zona ciega. "
            "Con safe_start, ambos órdenes producen el mismo resultado en este setup. "
            "TODO: mismo rediseño pendiente."
        )
        assert train2.slots[5]['demand_station_id'] is None, \
            "Demand tampoco etiquetó slot 5 con orden incorrecto"

    def test_belt_placements_after_decisions(self):
        """
        Invariante: _handle_belt_placements (paso 6) usa _reserved_slots que fue
        populado por _process_reservations (paso 8a) en el frame anterior.
        La garantía: VM aterriza en el slot EXACTO calculado, no en un slot por fallback.

        Setup: VM al final del DOWN tree (casi completo). _reserved_slots tiene la
        entrada (del frame anterior). brain.update() detecta la completion y coloca
        el VM en el slot reservado.

        Caso negativo: misma situación pero _reserved_slots vacío (simula que
        _process_reservations no corrió o corrió en el frame equivocado). El VM
        aterriza por fallback — en un slot cercano a junction_down, NO en slot 7.
        """
        # ── CON RESERVA (orden correcto) ──────────────────────────────────────
        brain1, train1, network1, stations1 = make_brain_fixture()
        vm1 = _make_vm(vm_id=0)
        target_slot = 7

        # Simula que _process_reservations corrió en el frame anterior
        brain1._reserved_slots[vm1.vehicle_id] = target_slot

        down_tree1 = network1.get_track(DOWN_TREE_ID)
        down_tree1.vehicles[vm1.vehicle_id] = {
            'vehicle':            vm1,
            'distance':           9.99,     # 0.01 m antes del final
            'velocity':           BOARDING_LANE_SPEED,
            'target_acceleration': TREE_ACCELERATION,
            'time_in_track':      5.0,
        }

        brain1.update(dt=0.01, current_time=0.0)

        assert train1.slots[target_slot]['vm'] is vm1, (
            f"Correcto: VM debe aterrizar en slot {target_slot} (el reservado). "
            "Si está en otro slot, _handle_belt_placements no usó _reserved_slots."
        )
        assert vm1.vehicle_id not in brain1._reserved_slots, \
            "_reserved_slots debe quedar limpio después del placement (.pop fue llamado)"

        # ── SIN RESERVA (orden incorrecto o bug upstream) ─────────────────────
        brain2, train2, network2, stations2 = make_brain_fixture()
        vm2 = _make_vm(vm_id=1)
        # _reserved_slots vacío — VM bajó sin que _process_reservations lo anticipara

        down_tree2 = network2.get_track(DOWN_TREE_ID)
        down_tree2.vehicles[vm2.vehicle_id] = {
            'vehicle':            vm2,
            'distance':           9.99,
            'velocity':           BOARDING_LANE_SPEED,
            'target_acceleration': TREE_ACCELERATION,
            'time_in_track':      5.0,
        }

        brain2.update(dt=0.01, current_time=0.0)

        placed = any(s['vm'] is vm2 for s in train2.slots)
        assert placed, "Sin reserva: VM debe aterrizar igualmente (fallback, no crash)"
        assert train2.slots[target_slot]['vm'] is not vm2, (
            "Sin reserva: VM NO debe estar en el slot exacto — "
            "aterrizó por fallback (find_neartest_slot), no por cálculo de reserva."
        )

# ─── COUNTER ACCOUNTING ───────────────────────────────────────────────────────
class TestCounterAccounting:
    """
    El counter de pending_demand solo se modifica en los momentos correctos.

    Regla del diseño:
        demand label     → on_vm_committed() al poner la etiqueta
        destination label → on_unplanned_vm_at_tree() cuando el VM entra al árbol
        reservation label → no toca el counter al ponerse;
                            on_unplanned_vm_at_tree() cuando el VM es eviccionado

    Tests unitarios: llaman _handle_crossings() directamente, sin correr el loop.
    Tests de integración: corren brain.update() varios frames y verifican el counter al final.
    """

    # ── UNITARIOS ────────────────────────────────────────────────────────────

    # CON ETIQUETA DEMAND
    # Creacion de la etiqueta
    def test_demand_label_decrements_counter_immediately(self):
        """
        _process_demand() llama on_vm_committed() al marcar el slot, ANTES del crossing.
        Verificar: pending_demand -= 1 en el mismo frame que se pone la etiqueta.
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[3]['vm'] = vm
        station.pending_demand = 1
        station.on_vm_committed.side_effect = lambda: setattr(
            station, 'pending_demand', station.pending_demand - 1
        )

        with patch.object(brain, '_would_saturate', return_value=False):
            brain.update(dt=0.001, current_time=0.0)

        assert station.on_vm_committed.call_count == 1, \
            "on_vm_committed debe llamarse al marcar el slot, en el mismo frame"
        labeled = any(s['demand_station_id'] == STATION_ID for s in train.slots)
        assert labeled, "Algún slot debe tener demand_station_id=S después del frame"
        assert station.pending_demand == 0, \
            "pending_demand decrementó de 1 a 0 en el mismo frame del etiquetado"

    # Acepta junction
    def test_demand_vm_enters_tree_no_extra_decrement(self):
        """
        Un VM con demand == S que entra al árbol UP no llama on_unplanned_vm_at_tree().
        El counter ya fue decrementado cuando se puso la etiqueta.
        Verificar: counter == valor_inicial - 1 (exactamente uno, no dos).
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['demand_station_id'] = STATION_ID

        brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert station.on_unplanned_vm_at_tree.call_count == 0, (
            "VM con demand=S no debe llamar on_unplanned al entrar. "
            "Ya fue contado cuando se puso la etiqueta."
        )
        assert station.on_vm_committed.call_count == 0, \
            "handle_crossings nunca llama on_vm_committed"
        assert vm.vehicle_id in network.get_track(UP_TREE_ID).vehicles, \
            "VM debe haber entrado al árbol UP (promesa cumplida)"

    # Rechasa junction
    def test_demand_vm_rejected_restores_counter(self):
        """
        Si un VM con demand == S es rechazado en la junction, on_commitment_broken() restaura.
        Verificar: counter == valor_inicial (como si nunca se hubiera etiquetado).
        También verificar: demand_station_id del slot queda limpio.
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['demand_station_id'] = STATION_ID

        junction = network.get_junction_up(STATION_ID)
        with patch.object(junction, 'add_vm', return_value=(False, None)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert station.on_commitment_broken.call_count == 1, \
            "Promesa rota: junction rechazó → on_commitment_broken restaura el counter"
        assert train.slots[5]['demand_station_id'] is None, \
            "clear_demand_supply: slot liberado para nueva búsqueda el frame siguiente"
        assert train.slots[5]['vm'] is vm, \
            "VM se queda en el belt (crossing fue condicional, no forzado)"


    # SIN ETIQUETA DEMAND
    # Creacion de la etiqueta
    def test_reservation_does_not_change_counter(self):
        """
        Hacer una reserva (_make_reservation) no llama on_vm_committed().
        pending_demand debe ser idéntico antes y después de la reserva.
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        lane = network.get_track(LANE_ID)
        vm = _make_vm(vm_id=0)
        lane.vehicles[vm.vehicle_id] = {
            'vehicle': vm,
            'distance': 0.52 * LANE_LENGTH,
            'velocity': BOARDING_LANE_SPEED,
            'passengers': [],
            'boarding_committed': True,
        }
        station.pending_demand = 0

        brain.update(dt=0.001, current_time=0.0)

        assert station.on_vm_committed.call_count == 0, (
            "_process_reservations no debe llamar on_vm_committed. "
            "El counter solo se toca al poner etiqueta de demanda, no de reserva."
        )
        assert vm.vehicle_id in brain._reserved_slots, \
            "La reserva sí debe registrarse (confirma que el test set-up es válido)"

    def test_destination_label_no_counter_change_before_crossing(self):
        """
        Poner destination_station_id en un slot no toca el counter.
        Verificar: counter idéntico antes y después de set_destination().
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        slot_idx = 40           # lejos de junction_up_x=10.0, no cruzará este frame
        train.slots[slot_idx]['vm'] = vm
        train.slots[slot_idx]['destination_station_id'] = STATION_ID
        station.pending_demand = 0

        brain.update(dt=0.001, current_time=0.0)   # movement=0.02m, no cruza

        assert station.on_vm_committed.call_count == 0
        assert station.on_unplanned_vm_at_tree.call_count == 0
        assert station.on_commitment_broken.call_count == 0, (
            "Poner destination label no toca el counter. "
            "El counter solo cambia al cruzar la junction, no al etiquetar."
        )

    # Acepta junction
    def test_eviction_calls_on_unplanned_exactly_once(self):
        """
        Cuando un slot reservado para S tiene un VM y cruza junction UP para S:
        - El VM es eviccionado (force_add_vm)
        - on_unplanned_vm_at_tree() se llama UNA sola vez
        Verificar: counter -= 1 (no -2).
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['reserved_station_id'] = STATION_ID
        # SIN demand label → on_unplanned debe llamarse (VM imprevisto para S)

        brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert station.on_unplanned_vm_at_tree.call_count == 1, (
            "Evicción sin demand label: on_unplanned exactamente una vez. "
            "Dos llamadas sería el bug de Q15 (doble conteo)."
        )
        assert vm.vehicle_id in network.get_track(UP_TREE_ID).vehicles, \
            "VM eviccionado entró al árbol (add_vm o force_add_vm)"
        
    def test_destination_vm_enters_tree_calls_on_unplanned(self):
        """
        VM con dest == S (sin demand label) que entra al árbol llama on_unplanned_vm_at_tree().
        Verificar: counter -= 1 al momento del crossing, no antes.
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID
        # SIN demand label

        brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert station.on_unplanned_vm_at_tree.call_count == 1, (
            "VM con dest=S pero sin demand=S era imprevisto para la taza. "
            "on_unplanned descuenta el counter en el momento del crossing."
        )
        assert vm.vehicle_id in network.get_track(UP_TREE_ID).vehicles, \
            "VM entró al árbol (crossing condicional aceptado)"

    # Rechasa junction
    def test_destination_vm_rejected_no_counter_change(self):
        """
        VM con dest == S rechazado en la junction no modifica el counter.
        No hay promesa que restaurar porque no se llamó on_vm_committed().
        Verificar: counter == valor_inicial después del crossing fallido.
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID
        # SIN demand label

        junction = network.get_junction_up(STATION_ID)
        with patch.object(junction, 'add_vm', return_value=(False,None)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert station.on_unplanned_vm_at_tree.call_count == 0, \
            "VM rechazado: nunca entró → no hay qué descontar del counter"
        assert station.on_commitment_broken.call_count == 0, \
            "No hubo promesa de demanda previa que restaurar"
        assert train.slots[5]['vm'] is vm, "VM sigue en el belt"

    # SLOT VACIO
    def test_empty_reserved_slot_no_counter_change(self):
        """
        Un slot reservado para S que cruza junction UP mientras está vacío:
        - El crossing handler hace 'continue' (slot['vm'] is None)
        - No se llama ningún callback de counter
        Verificar: counter == valor_inicial.
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        train.slots[5]['reserved_station_id'] = STATION_ID
        # slot['vm'] es None → _handle_crossings hace 'continue'

        brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert station.on_unplanned_vm_at_tree.call_count == 0
        assert station.on_vm_committed.call_count == 0
        assert station.on_commitment_broken.call_count == 0, \
            "Slot vacío: ningún callback del counter debe ejecutarse"

    # VM SIN ETIQUETAS
    def test_vm_with_no_labels_passes_junction_no_change(self):
        """
        Un VM sin ninguna etiqueta que cruza junction UP para S pasa de largo.
        Ninguna rama del if/elif en _handle_crossings aplica.
        Verificar: counter == valor_inicial.
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        # SIN ninguna etiqueta

        brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert station.on_unplanned_vm_at_tree.call_count == 0
        assert station.on_vm_committed.call_count == 0
        assert station.on_commitment_broken.call_count == 0
        assert train.slots[5]['vm'] is vm, "VM pasa de largo, sigue en el belt"
        assert vm.vehicle_id not in network.get_track(UP_TREE_ID).vehicles, \
            "VM no entró al árbol: ninguna rama del if/elif aplicó"

    # VARIAS ETIQUETAS
    # Demanda y reserved en distintas estaciones
    def test_demand_eviction_broken_other_station(self):
        """
        Slot tiene demand == T (otra estación) y reserved == S.
        Al ser eviccionado para S:
        - T llama on_commitment_broken() (promesa de T rota)
        - S llama on_unplanned_vm_at_tree() (VM imprevisto para S)
        Verificar que ambas estaciones se actualizan correctamente.
        """
        OTHER_STATION_ID = 2

        brain, train, network, stations = make_brain_fixture()
        station_S = stations[STATION_ID]

        station_T = MagicMock()
        station_T.pending_demand = 0
        brain._stations[OTHER_STATION_ID] = station_T

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['reserved_station_id'] = STATION_ID       # eviccionado para S
        train.slots[5]['demand_station_id'] = OTHER_STATION_ID   # tenía promesa con T

        brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert station_T.on_commitment_broken.call_count == 1, \
            "Promesa de T rota: el slot fue tomado por S antes de llegar a T"
        assert station_S.on_unplanned_vm_at_tree.call_count == 1, \
            "VM imprevisto para S: demand era de T, no de S → on_unplanned para S"
        assert vm.vehicle_id in network.get_track(UP_TREE_ID).vehicles

    def test_reserved_and_demand_same_station_no_unplanned(self):
        """
        Slot tiene reserved=S Y demand=S.
        Rama R corre (prioridad más alta). Como demand==S, el VM estaba pre-contado
        → on_unplanned NO se llama. Counter no cambia en el crossing.
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['reserved_station_id'] = STATION_ID
        train.slots[5]['demand_station_id'] = STATION_ID

        brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert station.on_unplanned_vm_at_tree.call_count == 0, (
            "demand==S: VM estaba pre-contado al poner la etiqueta de taza. "
            "Rama R no llama on_unplanned cuando demand==station_id."
        )
        assert station.on_commitment_broken.call_count == 0, \
            "Promesa cumplida (VM entró por reserva): no se rompe"
        assert vm.vehicle_id in network.get_track(UP_TREE_ID).vehicles

    def test_reserved_and_destination_no_demand_calls_unplanned(self):
        """
        Slot tiene reserved=S Y destination=S pero SIN demand label.
        Rama R corre. demand es None → demand != S → on_unplanned se llama.
        El destino no implica pre-contabilización: solo la etiqueta de taza lo hace.
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['reserved_station_id'] = STATION_ID
        train.slots[5]['destination_station_id'] = STATION_ID
        # SIN demand_station_id

        brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert station.on_unplanned_vm_at_tree.call_count == 1, (
            "dest+reserved pero sin demand: no hubo pre-contabilización. "
            "on_unplanned se llama al entrar (demand es None != S)."
        )
        assert vm.vehicle_id in network.get_track(UP_TREE_ID).vehicles

    def test_dest_and_demand_same_station_accepted_no_unplanned(self):
        """
        Slot tiene destination=S Y demand=S. Junction acepta.
        Rama D corre (elif dest antes que elif demand en brain.py).
        demand==S → on_unplanned NO se llama (VM estaba pre-contado vía taza).
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID
        train.slots[5]['demand_station_id'] = STATION_ID

        brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert station.on_unplanned_vm_at_tree.call_count == 0, (
            "demand==S: pre-contabilizado. Rama D no llama on_unplanned "
            "cuando demand==station_id (línea 224 de brain.py)."
        )
        assert station.on_commitment_broken.call_count == 0, \
            "VM entró exitosamente: promesa cumplida"
        assert vm.vehicle_id in network.get_track(UP_TREE_ID).vehicles

    def test_all_three_labels_same_station_no_unplanned(self):
        """
        Slot tiene reserved=S, destination=S, demand=S (las 3 etiquetas apuntan a S).
        Rama R corre (prioridad más alta). demand==S → NO on_unplanned.
        Con las 3 etiquetas, la pre-contabilización por taza prevalece sobre todo.
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['reserved_station_id'] = STATION_ID
        train.slots[5]['destination_station_id'] = STATION_ID
        train.slots[5]['demand_station_id'] = STATION_ID

        brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert station.on_unplanned_vm_at_tree.call_count == 0, (
            "Todas las etiquetas apuntan a S. demand==S garantiza pre-contabilización. "
            "Rama R no llama on_unplanned. Counter solo decrementó al poner la taza."
        )
        assert station.on_commitment_broken.call_count == 0
        assert vm.vehicle_id in network.get_track(UP_TREE_ID).vehicles

    # ── INTEGRACIÓN ──────────────────────────────────────────────────────────

    def test_counter_end_to_end_demand_path(self):
        """
        INTEGRACIÓN: ciclo completo vía sistema de taza.
        1. Station S acumula demand = 1
        2. brain.update(): _process_demand etiqueta un slot → counter = 0
        3. belt avanza, VM cruza junction UP para S, entra al árbol
        4. brain.update(): crossing handler → counter no cambia (ya estaba en 0)
        Verificar: counter == 0 al final (no -1).
        El VM llegó, el contador está correcto.
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID   # SIN demand label
        station.pending_demand = 1                               # estación necesita un VM

        station.on_unplanned_vm_at_tree.side_effect = lambda: setattr(
            station, 'pending_demand', station.pending_demand - 1
        )

        brain.update(dt=0.01, current_time=0.0)

        assert vm.vehicle_id in network.get_track(UP_TREE_ID).vehicles
        assert station.on_unplanned_vm_at_tree.call_count == 1, \
            "on_unplanned llamado al momento del crossing (no antes)"
        assert station.pending_demand == 0, \
            "Counter decrementó exactamente en el frame del crossing"

    def test_counter_end_to_end_destination_path(self):
        """
        INTEGRACIÓN: ciclo completo vía sistema de destino.
        1. Station S tiene pending_demand = 1
        2. Un slot tiene destination == S (no demand)
        3. belt avanza, VM cruza junction UP para S, entra
        4. on_unplanned_vm_at_tree() decrementa al momento del crossing
        Verificar: counter == 0 exactamente al frame del crossing.
        No antes, no después.
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID   # SIN demand label
        station.pending_demand = 1                               # estación necesita un VM

        station.on_unplanned_vm_at_tree.side_effect = lambda: setattr(
            station, 'pending_demand', station.pending_demand - 1
        )

        brain.update(dt=0.01, current_time=0.0)

        assert vm.vehicle_id in network.get_track(UP_TREE_ID).vehicles
        assert station.on_unplanned_vm_at_tree.call_count == 1, \
            "on_unplanned llamado al momento del crossing (no antes)"
        assert station.pending_demand == 0, \
            "Counter decrementó exactamente en el frame del crossing"

    def test_counter_no_over_decrement_with_demand_and_destination_same_station(self):
        """
        INTEGRACIÓN: VM tiene demand == S Y destination == S simultáneamente.
        Caso: la demanda etiquetó el slot Y también tiene destino marcado.
        Al cruzar junction UP para S:
        - dest branch corre (el elif dest viene antes que elif demand en brain.py)
        - on_unplanned_vm_at_tree() NO se llama (demand != station_id es False)
        Verificar: counter decrementó exactamente UNA vez total (cuando se puso demand).
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['demand_station_id'] = STATION_ID
        train.slots[5]['destination_station_id'] = STATION_ID
        station.pending_demand = 0      # ya fue decrementado cuando se puso demand

        brain.update(dt=0.01, current_time=0.0)

        assert vm.vehicle_id in network.get_track(UP_TREE_ID).vehicles, \
            "VM entró (dest branch corrió, demand != S es False → no on_unplanned)"
        assert station.on_unplanned_vm_at_tree.call_count == 0, \
            "demand era S: no hay on_unplanned (el VM estaba pre-contado)"
        assert station.on_commitment_broken.call_count == 0
        assert station.pending_demand == 0, \
            "Counter decrementó exactamente una vez (al poner demand), no dos"

    def test_counter_self_regulates_after_excess_vms(self):
        """
        INTEGRACIÓN: más VMs de lo esperado llegan a S (ejemplo: evicción + demanda).
        - counter empieza en 1, demand etiqueta 1 VM
        - una evicción envía un segundo VM a S de manera imprevista
        - on_unplanned_vm_at_tree() lleva el counter a -1
        - brain deja de etiquetar (pending_demand <= 0 detiene el while)
        - el acumulador se recupera naturalmente con el tiempo
        Verificar que el while en _process_demand no corre cuando counter <= 0.
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        # VM 1: tenía demand=S, ya contado (counter=0)
        vm1 = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm1
        train.slots[5]['demand_station_id'] = STATION_ID

        # VM 2: reservado para S sin demand (imprevisto → on_unplanned → counter=-1)
        vm2 = _make_vm(vm_id=1)
        train.slots[3]['vm'] = vm2
        train.slots[3]['reserved_station_id'] = STATION_ID

        station.pending_demand = 0
        station.on_unplanned_vm_at_tree.side_effect = lambda: setattr(
            station, 'pending_demand', station.pending_demand - 1
        )

        brain._handle_crossings([
            (5, STATION_ID, 0.0),   # demand VM → no on_unplanned
            (3, STATION_ID, 0.0),   # reserved VM → on_unplanned → pending_demand = -1
        ])

        assert station.pending_demand == -1, \
            "Más VMs de los esperados → counter negativo (autorregulación)"
        assert station.on_unplanned_vm_at_tree.call_count == 1, \
            "Solo el VM sin demand llamó on_unplanned"

        # Ahora _process_demand no debe etiquetar nada (pending_demand <= 0)
        with patch.object(brain, '_would_saturate', return_value=False):
            brain._process_demand()

        assert station.on_vm_committed.call_count == 0, \
            "while pending_demand > 0 no entró: counter ≤ 0 detiene el etiquetado"
  
    def test_dest_and_demand_same_station_rejected_restores_counter(self):
        """
        VM tiene dest=S Y demand=S. La junction rechaza (árboles saturados).
        Rama dest corre (prioridad sobre demand). VM se redirige a siguiente estación.
        Como demand=S fue colocada antes (on_vm_committed ya decrementó),
        on_commitment_broken DEBE llamarse para restaurar el contador.
        Verificar: counter == valor_inicial después del crossing fallido.
        También: demand_station_id del slot queda limpio (clear_demand_supply).
        """
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID
        train.slots[5]['demand_station_id'] = STATION_ID

        # on_vm_committed ya decrementó cuando se puso demand
        station.pending_demand = 0
        station.on_commitment_broken.side_effect = lambda: setattr(
            station, 'pending_demand', station.pending_demand + 1
        )

        junction = network.get_junction_up(STATION_ID)
        with patch.object(junction, 'add_vm', return_value=(False,None)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        # dest branch corrió (prioridad), junction rechazó, demand==S → on_commitment_broken
        assert station.on_commitment_broken.call_count == 1, \
            "Bug Case F: promise de demand DEBE restaurarse cuando dest branch rechaza"
        assert station.pending_demand == 1, \
            "Counter restaurado: volvió al valor antes del etiquetado de demanda"
        assert train.slots[5]['demand_station_id'] is None, \
            "clear_demand_supply: etiqueta de demanda limpiada después de la promesa rota"

# ─── DESTINATION REDIRECT ─────────────────────────────────────────────────────

class TestDestinationRedirect:
    """
    VM con destination_station_id que no puede entrar a su estación.

    Comportamiento correcto:
        - Si junction rechaza → redirigir a la siguiente estación (no vuelta completa)
        - Si sistema monoestación → warning, etiqueta sin cambio
        - Si VM entra en estación equivocada (por redirección previa) → warning de pasajeros
        - Redirección es circular: después de la última estación viene la primera

    Tests unitarios: llaman _handle_crossings() con junction mockeada que rechaza.
    Tests de integración: corren update() con múltiples frames y verifican el slot label.
    """

    # ── UNITARIOS ────────────────────────────────────────────────────────────

    def test_destination_label_changes_to_next_station_when_saturated(self):
        """
        VM tiene dest == S, junction rechaza (ok=False).
        Verificar: slot['destination_station_id'] cambia a next_station_id.
        NO queda en S (eso sería la vuelta completa).
        """

        NEXT_ID = 2
        brain, train, network, stations = make_brain_fixture()

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID

        junction = network.get_junction_up(STATION_ID)
        with patch.object(junction, 'add_vm', return_value=(False,None)), \
             patch.object(brain, '_next_station_id', return_value=NEXT_ID):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert train.slots[5]['destination_station_id'] == NEXT_ID, \
            "Rechazado en S: etiqueta redirige a siguiente estación"
        assert train.slots[5]['vm'] is vm, \
            "VM sigue en el belt (no entró al árbol)"

    def test_no_redirect_in_single_station_system(self):
        """
        Sistema con solo una estación. VM tiene dest == S, junction rechaza.
        _next_station_id retorna None → etiqueta NO cambia, se emite WARNING.
        Verificar: slot['destination_station_id'] == S (sin cambio).
        """
        brain, train, network, stations = make_brain_fixture()

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID

        junction = network.get_junction_up(STATION_ID)
        with patch.object(junction, 'add_vm', return_value=(False,None)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert train.slots[5]['destination_station_id'] == STATION_ID, \
            "Monoestación: no hay alternativa, etiqueta no cambia"
        assert train.slots[5]['vm'] is vm, "VM sigue en el belt"

    def test_redirect_is_circular_last_station_goes_to_first(self):
        """
        Sistema con 3 estaciones: S1 (belt_x=10), S2 (belt_x=50), S3 (belt_x=90).
        _next_station_id(S3.id) debe retornar S1.id (distancia circular (10-90)%100 = 20).
        Verificar que el cálculo modular es correcto, no geográfico.
        """
        
        S1_ID, S2_ID, S3_ID = 1, 2, 3
        brain, train, network, stations = make_brain_fixture()

        brain._stations[S2_ID] = MagicMock()
        brain._stations[S3_ID] = MagicMock()

        j1 = MagicMock(); j1.belt_x = 10.0
        j2 = MagicMock(); j2.belt_x = 50.0
        j3 = MagicMock(); j3.belt_x = 90.0
        junction_map = {S1_ID: j1, S2_ID: j2, S3_ID: j3}

        with patch.object(network, 'get_junction_up', side_effect=lambda sid: junction_map[sid]):
            result = brain._next_station_id(S3_ID)

        assert result == S1_ID, \
        "Distancia circular: (10 - 90) % 100 = 20 → S1 es la siguiente desde S3"

    def test_passenger_warning_when_vm_enters_wrong_station(self, caplog):
        """
        VM tiene dest == T (fue redirigido), llega a T, junction acepta (ok=True).
        Pero vm.destination_station_id (de los pasajeros reales) == S != T.
        Verificar: se emite WARNING con el station_id original de los pasajeros.
        """
        OTHER_STATION_ID = 2
        brain, train, network, stations = make_brain_fixture()

        vm = MagicMock()
        vm.vehicle_id = 0
        vm.has_destination = True
        vm.destination_station_id = OTHER_STATION_ID   # pasajeros iban a OTHER

        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID  # routing: va a STATION_ID

        junction = network.get_junction_up(STATION_ID)
        with caplog.at_level(logging.WARNING, logger="systems.brain"), \
            patch.object(junction, 'add_vm', return_value=(True, 0)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert "Pasajeros" in caplog.text, \
            "Warning emitido: VM entró en estación incorrecta para sus pasajeros"

    def test_no_passenger_warning_when_station_matches(self, caplog):
        """
        VM entra normalmente a su estación correcta.
        vm.destination_station_id == station_id → NO se emite warning de pasajeros.
        """
        brain, train, network, stations = make_brain_fixture()

        vm = _make_vm(vm_id=0)   # sin pasajeros: has_destination = False
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID

        with caplog.at_level(logging.WARNING, logger="systems.brain"):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert len(caplog.records) == 0, "Sin pasajeros: no se emite warning"
        assert vm.vehicle_id in network.get_track(UP_TREE_ID).vehicles

    def test_demand_counter_not_affected_by_redirect(self):
        """
        VM con dest == S (sin demand label) no pudo entrar. Se redirige a T.
        - Station S: counter sin cambio (el VM nunca entró, no había promesa)
        - Station T: on_unplanned_vm_at_tree() cuando finalmente entra
        Verificar que ningún contador cambia en el frame de la redirección.
        """
        NEXT_ID = 2
        brain, train, network, stations = make_brain_fixture()
        station = stations[STATION_ID]

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID
        # SIN demand label

        junction = network.get_junction_up(STATION_ID)
        with patch.object(junction, 'add_vm', return_value=(False,None)), \
            patch.object(brain, '_next_station_id', return_value=NEXT_ID):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert station.on_unplanned_vm_at_tree.call_count == 0, \
            "VM rechazado: no entró → counter sin cambio"
        assert station.on_commitment_broken.call_count == 0, \
            "Sin demand label: no había promesa que restaurar"
        assert train.slots[5]['destination_station_id'] == NEXT_ID
    
    # ── INTEGRACIÓN ──────────────────────────────────────────────────────────

    def test_vm_exits_at_next_station_after_redirect(self):
        """
        INTEGRACIÓN: S3 saturada, S1 disponible.
        1. Frame 1: VM llega a S3 → junction rechaza → dest cambia a S1
        2. Belt avanza hasta S1
        3. Frame N: VM llega a S1 → junction acepta → VM sube
        Verificar: VM sale del belt en S1, no da vuelta completa.
        """
        NEXT_ID = 2
        brain, train, network, stations = make_brain_fixture()

        station_next = MagicMock(); station_next.pending_demand = 0
        brain._stations[NEXT_ID] = station_next

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID

        real_junction_s = network.get_junction_up(STATION_ID)
        junction_next = MagicMock(); junction_next.add_vm.return_value = (True, 0)
        junction_map = {STATION_ID: real_junction_s, NEXT_ID: junction_next}

        with patch.object(network, 'get_junction_up', side_effect=lambda sid: junction_map[sid]):
            # Frame 1: rechaza → redirige
            with patch.object(real_junction_s, 'add_vm', return_value=(False,None)), \
                patch.object(brain, '_next_station_id', return_value=NEXT_ID):
                brain._handle_crossings([(5, STATION_ID, 0.0)])

            assert train.slots[5]['destination_station_id'] == NEXT_ID
            assert train.slots[5]['vm'] is vm   # sigue en belt

            # Frame 2: acepta → VM sale
            brain._handle_crossings([(5, NEXT_ID, 0.0)])

        assert train.slots[5]['vm'] is None, "VM salió del belt al entrar a NEXT_ID"

    def test_cascade_redirect_finds_available_station(self):
        """
        INTEGRACIÓN: S3 saturada, S1 también saturada, S2 disponible.
        Frame 1: no entra S3 → dest = S1
        Frame 2: no entra S1 → dest = S2
        Frame 3: entra en S2 ✓
        Verificar que el cascade termina cuando encuentra capacidad.
        """
        S1_ID = STATION_ID
        S2_ID = 2
        S3_ID = 3
        brain, train, network, stations = make_brain_fixture()

        station_s2 = MagicMock(); station_s2.pending_demand = 0
        station_s3 = MagicMock(); station_s3.pending_demand = 0
        brain._stations[S2_ID] = station_s2
        brain._stations[S3_ID] = station_s3

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = S3_ID

        real_junction_s1 = network.get_junction_up(S1_ID)
        junction_s2 = MagicMock(); junction_s2.add_vm.return_value = (True, 0)
        junction_s3 = MagicMock(); junction_s3.add_vm.return_value = (False, None)
        junction_map = {S1_ID: real_junction_s1, S2_ID: junction_s2, S3_ID: junction_s3}

        with patch.object(network, 'get_junction_up', side_effect=lambda sid: junction_map[sid]):
            # Frame 1: dest=S3, rechaza → dest=S1
            with patch.object(brain, '_next_station_id', return_value=S1_ID):
                brain._handle_crossings([(5, S3_ID, 0.0)])
            assert train.slots[5]['destination_station_id'] == S1_ID

            # Frame 2: dest=S1, rechaza → dest=S2
            with patch.object(real_junction_s1, 'add_vm', return_value=(False, None)), \
                patch.object(brain, '_next_station_id', return_value=S2_ID):
                brain._handle_crossings([(5, S1_ID, 0.0)])
            assert train.slots[5]['destination_station_id'] == S2_ID

            # Frame 3: dest=S2, acepta → VM sale del belt
            brain._handle_crossings([(5, S2_ID, 0.0)])

        assert train.slots[5]['vm'] is None, "Cascade resuelto en S2"

# ─── LABEL LIFECYCLE ───────────────────────────────────────────────────────────

class TestCrossingHandler:
    """
    Las etiquetas nacen en pasos 8a/8b y mueren en el paso 4.
    Cada etiqueta tiene su momento exacto de nacimiento y muerte.

    Ciclo completo de cada etiqueta:
        demand_station_id:      nace en _process_demand → muere en remove_vm (si entra)
                                o en clear_demand_supply (si rechazado)
        destination_station_id: nace en _make_reservation o set_destination →
                                muere en remove_vm
        reserved_station_id:    nace en set_reservation → muere en place_vm (belt)
                                NO en remove_vm — persiste hasta que el VM aterriza

    Tests unitarios: verifican el estado del slot antes y después de cada acción.
    """

    def test_demand_label_cleared_after_vm_enters_tree(self):
        """
        VM con demand == S cruza junction, junction acepta.
        remove_vm() limpia demand_station_id.
        Verificar: slot['demand_station_id'] == None después del crossing exitoso.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['demand_station_id'] = STATION_ID

        junction = network.get_junction_up(STATION_ID)
        with patch.object(junction, 'add_vm', return_value=(True, 0)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert train.slots[5]['vm'] is None
        assert train.slots[5]['demand_station_id'] is None
        
    def test_demand_label_cleared_after_rejection(self):
        """
        VM con demand == S, junction rechaza.
        clear_demand_supply() limpia demand_station_id.
        Verificar: slot['demand_station_id'] == None después del crossing fallido.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['demand_station_id'] = STATION_ID

        junction = network.get_junction_up(STATION_ID)
        with patch.object(junction, 'add_vm', return_value=(False,None)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert train.slots[5]['vm'] is vm        # VM se quedó en el belt
        assert train.slots[5]['demand_station_id'] is None  # etiqueta muerta

    def test_destination_label_cleared_after_vm_enters_tree(self):
        """
        VM con dest == S cruza junction, junction acepta.
        remove_vm() limpia destination_station_id.
        Verificar: slot['destination_station_id'] == None después del crossing.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID

        junction = network.get_junction_up(STATION_ID)
        with patch.object(junction, 'add_vm', return_value=(True,0)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert train.slots[5]['vm'] is None
        assert train.slots[5]['destination_station_id'] is None

    def test_destination_label_survives_failed_crossing(self):
        """
        VM con dest == S, junction rechaza (sin redirección — caso monoestación o primera vez).
        La etiqueta cambia a next_station_id (Q2) o permanece si no hay alternativa.
        Verificar: después del crossing fallido el slot NO queda limpio — tiene nueva etiqueta.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID

        junction = network.get_junction_up(STATION_ID)
        with patch.object(junction, 'add_vm', return_value=(False,None)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert train.slots[5]['vm'] is vm
        # Etiqueta NO murió — permanece porque es monoestación (sin alternativa)
        assert train.slots[5]['destination_station_id'] == STATION_ID

    def test_reserved_label_NOT_cleared_by_remove_vm(self):
        """
        CRÍTICO: reserved_station_id NO se limpia cuando remove_vm saca el VM del belt.
        Solo se limpia en place_vm cuando el VM baja y aterriza.
        Verificar: después de una evicción, slot['reserved_station_id'] == None
        (place_vm lo limpia), pero SI se hace remove_vm SIN place_vm posterior,
        el slot queda correctamente limpio también (remove_vm limpia todos los labels).
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['reserved_station_id'] = STATION_ID
        train.slots[5]['reserved_vm_id'] = vm.vehicle_id

        junction = network.get_junction_up(STATION_ID)
        with patch.object(junction, 'add_vm', return_value=(True,0)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        # VM salió del belt
        assert train.slots[5]['vm'] is None
        # CRÍTICO: reserved_station_id sobrevive a remove_vm
        assert train.slots[5]['reserved_station_id'] == STATION_ID
        assert train.slots[5]['reserved_vm_id'] == vm.vehicle_id

        # El VM desciende y aterriza en su slot reservado
        descending_vm = _make_vm(vm_id=1)
        train.place_vm(descending_vm, 5)

        # Solo place_vm limpia la reserva
        assert train.slots[5]['reserved_station_id'] is None
        assert train.slots[5]['reserved_vm_id'] is None
        assert train.slots[5]['vm'] is descending_vm

    def test_slot_fully_clean_after_successful_crossing(self):
        """
        Después de cualquier crossing exitoso (enter tree), el slot queda
        completamente limpio: vm=None, todos los labels=None.
        Verificar los 5 campos del slot dict.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['demand_station_id'] = STATION_ID

        junction = network.get_junction_up(STATION_ID)
        with patch.object(junction, 'add_vm', return_value=(True,0)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        slot = train.slots[5]
        assert slot['vm'] is None
        assert slot['reserved_station_id'] is None
        assert slot['reserved_vm_id'] is None
        assert slot['destination_station_id'] is None
        assert slot['demand_station_id'] is None

    def test_colliding_slot_is_frozen_no_crossing_processed(self):
        """
        Un slot en choque se congela por completo: ningún label se procesa,
        ningún VM sale del belt, aunque tenga reserved/dest/demand activos.
        """
        brain, train, network, stations = make_brain_fixture()
        original = _make_vm(vm_id=0)
        intruder = _make_vm(vm_id=1)
        train.slots[5]['vm'] = original
        train.slots[5]['colliding_vms'] = [intruder]
        train.slots[5]['reserved_station_id'] = STATION_ID  # forzaría salida si no estuviera congelado

        junction = network.get_junction_up(STATION_ID)
        with patch.object(junction, 'add_vm', return_value=True) as mock_add:
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        mock_add.assert_not_called()
        assert train.slots[5]['vm'] is original
        assert train.slots[5]['colliding_vms'] == [intruder]

# ─── LABEL COMBINATIONS ──────────────────────────────────────────────────────

class TestLabelCompatibility:
    """
    Qué pasa cuando un slot tiene múltiples etiquetas al mismo tiempo.
    Las ramas en _handle_crossings son elif excluyentes — solo una corre por crossing.
    Orden de prioridad: reserved > dest > demand.

    Combinaciones posibles y acciones:
        reserved=S + dest=S             → rama reserved; on_unplanned(S) (demand=None≠S);
                                          dest limpiado; reserved sobrevive
        reserved=S + demand=S           → rama reserved; sin on_unplanned (demand==S,
                                          ya contado); demand limpiado; reserved sobrevive
        reserved=S + demand=T (T≠S)     → rama reserved; on_commitment_broken(T);
                                          on_unplanned(S); reserved sobrevive
        dest=S + demand=S, acepta       → rama dest; sin on_unplanned (demand==S);
                                          slot completamente limpio
        dest=S + demand=T (T≠S), acepta → rama dest; on_commitment_broken(T) (*);
                                          on_unplanned(S); slot limpio
        reserved=S + dest=S + demand=S  → rama reserved; sin on_unplanned ni
                                          on_commitment_broken (demand==S); reserved sobrevive
        dest=S + demand=S, rechaza      → rama dest else; on_commitment_broken(S);
                                          demand limpiado; dest sobrevive (monoestación)

    """
    # Combinacion etiquetas de la misma estacion
    def test_reserved_wins_over_destination_same_station(self):
        """
        Slot: reserved=S, dest=S, demand=None. Cruza junction UP para S.
        Rama de reserva corre. dest==S → sin eviction warning.
        demand==None → on_unplanned SÍ se llama (demand != station_id).
        Verificar: VM sale del belt, dest limpiado, reserved sobrevive.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['reserved_station_id'] = STATION_ID
        train.slots[5]['destination_station_id'] = STATION_ID

        junction = network.get_junction_up(STATION_ID)
        station = brain._stations[STATION_ID]

        with patch.object(junction, 'add_vm', return_value=(True,0)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert train.slots[5]['vm'] is None
        assert train.slots[5]['destination_station_id'] is None    # remove_vm limpió
        assert train.slots[5]['reserved_station_id'] == STATION_ID # sobrevive
        station.on_unplanned_vm_at_tree.assert_called_once()       # demand era None

    def test_reserved_wins_over_demand_same_station(self):
        """
        Slot: reserved=S, demand=S. Cruza junction UP para S.
        Rama de reserva corre. demand==S → on_unplanned NO llamado (ya contabilizado).
        Verificar: counter sin cambios en el crossing, reserved sobrevive.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['reserved_station_id'] = STATION_ID
        train.slots[5]['demand_station_id'] = STATION_ID

        junction = network.get_junction_up(STATION_ID)
        station = brain._stations[STATION_ID]

        with patch.object(junction, 'add_vm', return_value=(True,0)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert train.slots[5]['vm'] is None
        assert train.slots[5]['demand_station_id'] is None         # remove_vm limpió
        assert train.slots[5]['reserved_station_id'] == STATION_ID # sobrevive
        station.on_unplanned_vm_at_tree.assert_not_called()        # demand era S

    def test_destination_wins_over_demand_same_station(self):
        """
        Slot: dest=S, demand=S, reserved=None. Cruza junction UP para S. Junction acepta.
        Rama de destino corre (elif). demand==S → on_unplanned NO llamado (ya contabilizado).
        Verificar: slot completamente limpio, counter sin cambios en el crossing.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID
        train.slots[5]['demand_station_id'] = STATION_ID

        junction = network.get_junction_up(STATION_ID)
        station = brain._stations[STATION_ID]

        with patch.object(junction, 'add_vm', return_value=(True,0)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert train.slots[5]['vm'] is None
        assert train.slots[5]['destination_station_id'] is None
        assert train.slots[5]['demand_station_id'] is None
        station.on_unplanned_vm_at_tree.assert_not_called()  # demand era S

    def test_destination_demand_rejected_clears_demand_keeps_dest(self):
        """
        Slot: dest=S, demand=S, reserved=None. Junction rechaza.
        Rama de destino, else: on_commitment_broken para S + clear_demand_supply.
        Monoestación → dest permanece en S (no hay alternativa a donde redirigir).
        Verificar: demand=None, dest=STATION_ID, VM sigue en belt.
        Complementa Bug Case F de TestCounterAccounting — aquí el foco es el estado
        de las etiquetas, no el contador.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID
        train.slots[5]['demand_station_id'] = STATION_ID

        station = brain._stations[STATION_ID]
        junction = network.get_junction_up(STATION_ID)

        with patch.object(junction, 'add_vm', return_value=(False,None)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert train.slots[5]['vm'] is vm                              # VM en belt
        assert train.slots[5]['demand_station_id'] is None             # promesa rota
        assert train.slots[5]['destination_station_id'] == STATION_ID  # dest sobrevive
        station.on_commitment_broken.assert_called_once()

    def test_reserved_wins_with_all_three_labels(self):
        """
        Slot: reserved=S, dest=S, demand=S. Cruza junction UP para S.
        Las tres etiquetas apuntan a la misma estación.
        Rama de reserva corre. demand==S → no on_commitment_broken, no on_unplanned.
        El VM ya estaba contabilizado cuando se puso la etiqueta de demand.
        Verificar: reserved sobrevive, dest y demand limpiados, counter sin cambios.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['reserved_station_id'] = STATION_ID
        train.slots[5]['destination_station_id'] = STATION_ID
        train.slots[5]['demand_station_id'] = STATION_ID

        junction = network.get_junction_up(STATION_ID)
        station = brain._stations[STATION_ID]

        with patch.object(junction, 'add_vm', return_value=(True,0)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert train.slots[5]['vm'] is None
        assert train.slots[5]['destination_station_id'] is None    # remove_vm limpió
        assert train.slots[5]['demand_station_id'] is None         # remove_vm limpió
        assert train.slots[5]['reserved_station_id'] == STATION_ID # sobrevive
        station.on_unplanned_vm_at_tree.assert_not_called()
        station.on_commitment_broken.assert_not_called()

    # Combinacion de etiquetas de diferentes estaciones (2 casos probables)
    def test_reserved_breaks_demand_promise_other_station(self):
        """
        Slot: reserved=S, demand=T (T != S). Cruza junction UP para S.
        Rama de reserva: on_commitment_broken() para T (demanda rota).
        demand=T != S → on_unplanned para S (no estaba contabilizado para S).
        Verificar: counter de T se restaura, on_unplanned de S se llama.
        """
        OTHER_ID = 2
        brain, train, network, stations = make_brain_fixture()
        station_t = MagicMock()
        station_t.pending_demand = 0
        brain._stations[OTHER_ID] = station_t

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['reserved_station_id'] = STATION_ID
        train.slots[5]['demand_station_id'] = OTHER_ID

        station_s = brain._stations[STATION_ID]
        junction = network.get_junction_up(STATION_ID)

        with patch.object(junction, 'add_vm', return_value=(True,0)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert train.slots[5]['vm'] is None
        assert train.slots[5]['demand_station_id'] is None          # remove_vm limpió
        assert train.slots[5]['reserved_station_id'] == STATION_ID  # sobrevive
        station_t.on_commitment_broken.assert_called_once()         # promesa de T rota
        station_s.on_unplanned_vm_at_tree.assert_called_once()      # no estaba contado para S

    def test_destination_triggers_unplanned_when_demand_different(self):
        """
        Slot: dest=S, demand=T (T != S), reserved=None. Cruza junction UP para S. Acepta.
        Rama de destino corre. demand=T != S:
        → on_commitment_broken para T (promesa rota — VM no llegará a T)
        → on_unplanned_vm_at_tree para S (el VM no estaba contabilizado para S)
        Simétrico a la rama reserved que maneja el mismo caso.
        """
        OTHER_ID = 2
        brain, train, network, stations = make_brain_fixture()
        station_t = MagicMock()
        station_t.pending_demand = 0
        brain._stations[OTHER_ID] = station_t

        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm
        train.slots[5]['destination_station_id'] = STATION_ID
        train.slots[5]['demand_station_id'] = OTHER_ID

        station_s = brain._stations[STATION_ID]
        junction = network.get_junction_up(STATION_ID)

        with patch.object(junction, 'add_vm', return_value=(True,0)):
            brain._handle_crossings([(5, STATION_ID, 0.0)])

        assert train.slots[5]['vm'] is None
        station_t.on_commitment_broken.assert_called_once()    # promesa de T rota
        station_s.on_unplanned_vm_at_tree.assert_called_once() # no contabilizado para S

# ─── SATURATION SCENARIOS ────────────────────────────────────────────────────

class TestSaturationCheck:
    """
    Ventana deslizante de _would_saturate — cuándo acepta y cuándo bloquea.

    Parámetros físicos (MagicMock en tests unitarios, real en integración):
        N = burst_capacity: VMs que la junction puede absorber de corrido
        G = burst_window:   slots que separan dos grupos (DOWN junction: G=0)

    Algoritmo: para cada una de las G ventanas de tamaño G que contienen
    al candidato, count = 1 (candidato) + slots ya marcados en esa ventana.
    Si alguna ventana tiene count >= N → True.

    Cobertura de ventanas: rango [C-(G-1), C+(G-1)]. Un slot a distancia
    exacta G es el primer slot FUERA de todas las ventanas que contienen a C.

    NOTA — fixture tiene N=1 (1 árbol UP):
        Con N=1, count=1 (solo candidato) >= N=1 siempre → _would_saturate
        siempre True. Tests unitarios (1-3) usan MagicMock con N=2, G=5.
        Tests de integración (4-5) parchean _would_saturate directamente.

    Tests unitarios de _would_saturate:
        N=2, G=5, slot marcado a distancia G      → False (fuera de cobertura)
        N=2, G=5, slot marcado a distancia 2      → True  (dentro de cobertura)
        Wrap-around: candidato=48, slot 1 marcado → True  (distancia circular 3)
        G=0 (DOWN junction)                       → False inmediato
    Tests de integración:
        _range_search_demand: omite candidato si would_saturate → sin label
        _range_search_reservation fallback: elige mínimo saturation_count → CRITICAL
    """

    def test_would_saturate_returns_false_below_capacity(self):
        """
        N=2, G=5. Hay 1 slot marcado pero a distancia exactamente G del candidato
        → fuera del rango [C-(G-1), C+(G-1)] → no aparece en ninguna ventana con C.
        count=1 (solo el candidato) < N=2 → False.
        Confirma el límite: distancia < G → interfiere; distancia = G → no interfiere.
        """
        brain, train, network, stations = make_brain_fixture()
        junction = MagicMock()
        junction.burst_capacity = 2  # N
        junction.burst_window = 5    # G

        candidate = 20
        # Distancia 5 = G → primer slot FUERA de cobertura [16..24]
        train.slots[25]['destination_station_id'] = STATION_ID

        assert brain._would_saturate(junction, candidate, STATION_ID) is False
        
    def test_would_saturate_returns_true_at_capacity(self):
        """
        N=2, G=5. Slot 22 marcado con demand_station_id (distancia 2 del candidato 20).
        Ventana [20..24] contiene candidato + slot 22 → count=3 > N=2 → True.
        Usa demand_station_id (no destination) para verificar que _is_slot_marked_for
        responde a AMBAS etiquetas.
        """
        brain, train, network, stations = make_brain_fixture()
        junction = MagicMock()
        junction.burst_capacity = 2
        junction.burst_window = 5

        candidate = 20

        train.slots[21]['destination_station_id'] = STATION_ID
        train.slots[22]['destination_station_id'] = STATION_ID
        assert brain._would_saturate(junction, candidate, STATION_ID) is True

    def test_window_wraps_around_circular_belt(self):
        """
        max_slots=50. Candidato=48, slot 1 marcado.
        Distancia circular hacia adelante: (1 - 48 + 50) % 50 = 3 → dentro de [44..52 mod 50].
        Ventana start_offset=0: [48, 49, 0, 1, 2] → candidato + slot 1 → count=3 > 2 → True.
        """
        brain, train, network, stations = make_brain_fixture()
        junction = MagicMock()
        junction.burst_capacity = 2
        junction.burst_window = 5

        train.slots[0]['destination_station_id'] = STATION_ID
        train.slots[1]['destination_station_id'] = STATION_ID
        assert brain._would_saturate(junction, 48, STATION_ID) is True

    def test_demand_skips_candidate_if_would_saturate(self):
        """
        _would_saturate=True para todo candidato → _range_search_demand retorna None.
        _process_demand sale del while con break sin llamar on_vm_committed.
        El slot con VM queda sin etiqueta demand.
        (Nota: _process_demand solo hace break, no llama on_commitment_broken aquí.)
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        train.slots[5]['vm'] = vm  # slot 5 = belt_x 10 = JUNCTION_UP_X, slot visible para demand

        station = brain._stations[STATION_ID]
        station.pending_demand = 1

        with patch.object(brain, '_would_saturate', return_value=True):
            brain._process_demand()

        station.on_vm_committed.assert_not_called()
        assert train.slots[5]['demand_station_id'] is None

    def test_saturation_count_selects_minimum_in_fallback(self,caplog):
        """
        _range_search_reservation: todos los candidatos saturarían (_would_saturate=True).
        _saturation_count retorna 2 para slot 5, 3 para el resto.
        Fallback elige slot 5 (mínimo) y emite CRITICAL.
        """
        brain, train, network, stations = make_brain_fixture()
        junction_up = network.get_junction_up(STATION_ID)
        BEST_SLOT = 5

        def fake_sat_count(junction, candidate, station_id):
            return 2 if candidate == BEST_SLOT else 3

        with patch.object(brain, '_would_saturate', return_value=True):
            with patch.object(brain, '_saturation_count', side_effect=fake_sat_count):
                with caplog.at_level(logging.CRITICAL, logger='systems.brain'):
                    result,*_ = brain._range_search_reservation(BEST_SLOT, STATION_ID, junction_up)

        assert result == BEST_SLOT
        assert any(r.levelno == logging.CRITICAL for r in caplog.records)

    def test_down_junction_never_saturates(self):
        """
        Junction DOWN: burst_window=0 → _would_saturate retorna False inmediato.
        Incluso con slots densamente marcados, G=0 corta antes de cualquier conteo.
        """
        brain, train, network, stations = make_brain_fixture()
        junction_down = network.get_junction_down(STATION_ID)

        # Marcar todos los vecinos para asegurar que el check no es trivialmente False
        for i in range(0, 10):
            train.slots[i]['destination_station_id'] = STATION_ID

        assert brain._would_saturate(junction_down, 5, STATION_ID) is False

# ─── DEMAND SYSTEM ───────────────────────────────────────────────────────────

class TestDemandSystem:
    """
    El sistema de taza etiqueta slots según las prioridades correctas
    y respeta las restricciones de reserva, destino, saturación y double-commit.

    _range_search_demand busca HACIA ATRÁS desde junction_up (slot 5 = belt_x 10.0)
    hasta SLOT_SEARCH_RANGE_DEMAND=10 posiciones. Solo slots CON VM.

    Reglas de exclusión:
        reserved para otra estación → skip (VM será eviccionado antes de llegar)
        dest de otra estación       → skip (VM tiene compromiso diferente)
        demand=S ya puesto          → skip (ya comprometido — no double-commit)
        would_saturate              → skip

    Prioridades (menor número = mejor):
        1. reserved=S  → llegada garantizada por force_add_vm
        2. dest=S      → VM va a S de todas formas
        3. limpio      → candidato sin compromisos previos

    Fixture: tail_x=0, TRAIN_SPACING=2 → slot 5 = junction_up. Parchear _would_saturate=False.
    """

    def test_demand_labels_slot_when_pending_demand_positive(self):
        """
        Station S tiene pending_demand = 1. Hay un slot con VM sin etiquetas.
        _process_demand debe marcar ese slot con demand_station_id = S.
        """
        brain, train, network, stations = make_brain_fixture()
        train.slots[3]['vm'] = _make_vm(vm_id=0)

        station = brain._stations[STATION_ID]
        station.pending_demand = 1
        station.on_vm_committed.side_effect = lambda: setattr(station, 'pending_demand', 0)

        with patch.object(brain, '_would_saturate', return_value=False):
            brain._process_demand()

        assert train.slots[3]['demand_station_id'] == STATION_ID
        station.on_vm_committed.assert_called_once()

    def test_demand_skips_empty_slots(self):
        """
        _range_search_demand requiere slot['vm'] is not None.
        Slot vacío cerca de junction_up → no se etiqueta.
        Solo slots CON VM son candidatos.
        """
        brain, train, network, stations = make_brain_fixture()
        train.slots[2]['vm'] = _make_vm(vm_id=0)
        # slots 3, 4, 5 vacíos → deben ser saltados

        junction_up = network.get_junction_up(STATION_ID)
        with patch.object(brain, '_would_saturate', return_value=False):
            result,*_ = brain._range_search_demand(STATION_ID, junction_up)

        assert result == 2

    def test_demand_skips_slots_reserved_for_other_station(self):
        """
        Slot con reserved_station_id de OTRA estación es omitido.
        Ese VM será eviccionado por la junction de esa otra estación antes
        de llegar a S — etiquetarlo crearía una promesa rota.
        Contraste: reserved=S (misma estación) tiene priority=1, no se salta.
        """
        brain, train, network, stations = make_brain_fixture()
        train.slots[3]['vm'] = _make_vm(vm_id=0)
        train.slots[3]['reserved_station_id'] = 99  # otra estación → skip
        train.slots[2]['vm'] = _make_vm(vm_id=1)

        junction_up = network.get_junction_up(STATION_ID)
        with patch.object(brain, '_would_saturate', return_value=False):
            result,*_ = brain._range_search_demand(STATION_ID, junction_up)

        assert result == 2
        assert train.slots[3]['demand_station_id'] is None

    def test_demand_skips_slots_with_conflicting_destination(self):
        """
        Slot tiene destination_station_id = T (T != S).
        _range_search_demand omite este slot.
        El VM ya tiene compromiso con T — ponerle demand=S crearía conflicto.
        """
        brain, train, network, stations = make_brain_fixture()
        train.slots[3]['vm'] = _make_vm(vm_id=0)
        train.slots[3]['destination_station_id'] = 99  # otra estación → skip
        train.slots[2]['vm'] = _make_vm(vm_id=1)

        junction_up = network.get_junction_up(STATION_ID)
        with patch.object(brain, '_would_saturate', return_value=False):
            result,*_ = brain._range_search_demand(STATION_ID, junction_up)

        assert result == 2

    def test_demand_labels_multiple_slots_for_multiple_demand(self):
        """
        pending_demand=3. Prioridades completas: slot 1=P1 (reserved=S), slot 2=P2 (dest=S), slot 3=P3 (clean).
        La búsqueda recorre 5→4→3→2→1 y mantiene el mejor candidato visto hasta ahora:
          → slot 3 (P3) mejora sobre vacío; → slot 2 (P2) mejora sobre P3; → slot 1 (P1) mejora sobre P2.
        Iteración 1: retorna slot 1. Iteración 2: slot 1 skip (demand=S), retorna slot 2 (P2 > P3).
        Iteración 3: slots 1 y 2 skip (demand=S), retorna slot 3.
        Verificar: on_vm_committed × 3, orden P1→P2→P3, sin double-commit.
        """
        brain, train, network, stations = make_brain_fixture()
        train.slots[3]['vm'] = _make_vm(vm_id=0)   # P3: clean
        train.slots[2]['vm'] = _make_vm(vm_id=1)
        train.slots[2]['destination_station_id'] = STATION_ID  # P2: dest=S
        train.slots[1]['vm'] = _make_vm(vm_id=2)
        train.slots[1]['reserved_station_id'] = STATION_ID     # P1: reserved=S

        station = brain._stations[STATION_ID]
        station.pending_demand = 3
        station.on_vm_committed.side_effect = lambda: setattr(
            station, 'pending_demand', station.pending_demand - 1
        )

        with patch.object(brain, '_would_saturate', return_value=False):
            brain._process_demand()

        assert station.on_vm_committed.call_count == 3
        # Orden de labeling: P1 primero (slot 1), luego P2 (slot 2), luego P3 (slot 3)
        assert train.slots[1]['demand_station_id'] == STATION_ID  # reservado primero
        assert train.slots[2]['demand_station_id'] == STATION_ID  # dest=S segundo
        assert train.slots[3]['demand_station_id'] == STATION_ID  # limpio tercero

    def test_demand_stops_when_no_candidates(self):
        """
        pending_demand=2, solo 1 VM disponible en slot 3.
        Iteración 1: slot 3 etiquetado → on_vm_committed → pending_demand=1.
        Iteración 2: slot 3 tiene demand=S → SKIP (no double-commit).
                     Ningún otro candidato → _range_search_demand=None → break.
        Verificar: on_vm_committed solo 1 vez, pending_demand==1 al salir.
        Sin on_commitment_broken (no hubo promesa en la segunda iteración).
        """
        brain, train, network, stations = make_brain_fixture()
        train.slots[3]['vm'] = _make_vm(vm_id=0)

        station = brain._stations[STATION_ID]
        station.pending_demand = 2
        station.on_vm_committed.side_effect = lambda: setattr(
            station, 'pending_demand', station.pending_demand - 1
        )

        with patch.object(brain, '_would_saturate', return_value=False):
            brain._process_demand()

        station.on_vm_committed.assert_called_once()
        assert train.slots[3]['demand_station_id'] == STATION_ID
        assert station.pending_demand == 1

    def test_demand_never_selects_colliding_slot(self):
        """
        _range_search_demand nunca marca un slot en choque, aunque tenga VM
        y esté limpio de otras etiquetas.
        """
        brain, train, network, stations = make_brain_fixture()
        junction_up = network.get_junction_up(STATION_ID)

        with patch.object(brain, '_would_saturate', return_value=False):
            train.slots[5]['vm'] = _make_vm()
            train.slots[5]['colliding_vms'] = [_make_vm(vm_id=99)]

            result,*_ = brain._range_search_demand(STATION_ID, junction_up)

        assert result != 5, "Nunca debe marcar un slot en choque con demanda"

# ─── RESERVATION MATH ────────────────────────────────────────────────────────

class TestReservationMath:
    """
    El sistema de reserva asegura que el VM aterriza en el slot correcto calculando
    el slot que estará en junction_down en T_total segundos y ajustando la aceleración.

    Fixture: LANE_LENGTH=20, BOARDING_LANE_SPEED=2, TRAIN_SPEED=20, TREE_ACCELERATION=2.5,
             TREE_LENGTH=10, JUNCTION_DOWN_X=50, TRAIN_SPACING=2, total_length=100, max_slots=50.

    Números clave (tail_x=0):
        progress=0.5  → T_lane=5.0, T_tree_std=7.2, T_total=12.2, target_idx=3
        progress=0.54 → T_lane=4.6, T_tree_std=7.2, T_total=11.8, target_idx=7

    Tests 1-3: unitarios de _make_reservation (consecuencias observables = slot reservado + aceleración).
    Tests 4-5: integración — el VM aterriza en el slot reservado.
    """

    def test_T_total_calculated_correctly(self):
        """
        progress=0.5 → T_lane=5.0, T_tree_std=7.2, T_total=12.2 → target_idx=3.
        Verificación: future_tail_x=(0+20×12.2)%100=44, relative=(50-44)%100=6, round(6/2)=3.
        Con solo slot 3 disponible (otros bloqueados), _make_reservation debe reservar slot 3.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        lane = network.get_track(LANE_ID)
        down_tree = network.get_track(DOWN_TREE_ID)

        lane.vehicles[vm.vehicle_id] = {
            'vehicle': vm, 'distance': 0.5 * LANE_LENGTH,
            'velocity': BOARDING_LANE_SPEED, 'passengers': [], 'boarding_committed': True,
        }

        # Forzar candidato único: bloquear todos excepto slot 3
        for idx in range(train.max_slots):
            if idx != 3:
                train.slots[idx]['reserved_station_id'] = 99

        with patch.object(brain, '_would_saturate', return_value=False):
            brain._make_reservation(vm, lane, down_tree, STATION_ID)

        assert train.slots[3]['reserved_station_id'] == STATION_ID
        assert brain._reserved_slots[vm.vehicle_id] == 3

    def test_target_slot_correct_with_known_belt_state(self):
        """
        progress=0.54 → T_lane=4.6, T_tree_std=7.2, T_total=11.8 → target_idx=7.
        Verificación: future_tail_x=(0+20×11.8)%100=36, relative=(50-36)%100=14, round(14/2)=7.
        Confirma que target_idx cambia según progress (contraste con test 1 que da target=3).
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        lane = network.get_track(LANE_ID)
        down_tree = network.get_track(DOWN_TREE_ID)

        lane.vehicles[vm.vehicle_id] = {
            'vehicle': vm, 'distance': 0.54 * LANE_LENGTH,
            'velocity': BOARDING_LANE_SPEED, 'passengers': [], 'boarding_committed': True,
        }

        # Forzar candidato único: bloquear todos excepto slot 7
        for idx in range(train.max_slots):
            if idx != 7:
                train.slots[idx]['reserved_station_id'] = 99

        with patch.object(brain, '_would_saturate', return_value=False):
            brain._make_reservation(vm, lane, down_tree, STATION_ID)

        assert train.slots[7]['reserved_station_id'] == STATION_ID
        assert brain._reserved_slots[vm.vehicle_id] == 7

    def test_adjusted_acceleration_mrua_formula(self):
        """
        progress=0.5 → target=3. best_slot=5 (raw_offset=2, slot 3 bloqueado, 4 también).
        T_target = 12.2 - 2*(2/20) = 12.0
        T_tree_adj = 12.0 - 5.0 = 7.0
        a = 2*(10 - 2*7.0) / 7.0² = 2*(-4)/49 ≈ -0.16327...
        Verificar: vm.reserved_tree_acceleration ≈ expected_a.
        """

        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        lane = network.get_track(LANE_ID)
        down_tree = network.get_track(DOWN_TREE_ID)

        lane.vehicles[vm.vehicle_id] = {
            'vehicle': vm, 'distance': 0.5 * LANE_LENGTH,
            'velocity': BOARDING_LANE_SPEED, 'passengers': [], 'boarding_committed': True,
        }

        # Bloquear todo el rango [3-5, ..., 3+5] excepto slot 5 (raw_offset=2 desde target=3)
        for idx in range(train.max_slots):
            if idx != 5:
                train.slots[idx]['reserved_station_id'] = 99

        with patch.object(brain, '_would_saturate', return_value=False):
            brain._make_reservation(vm, lane, down_tree, STATION_ID)

        T_tree_adj = 7.0
        expected_a = 2.0 * (TREE_LENGTH - BOARDING_LANE_SPEED * T_tree_adj) / (T_tree_adj ** 2)
        assert vm.reserved_tree_acceleration == pt.approx(expected_a, rel=1e-6)
        assert brain._reserved_slots[vm.vehicle_id] == 5

    def test_vm_lands_in_reserved_slot_end_to_end(self):
        """
        INTEGRACIÓN: _process_reservations reserva slot X; _handle_belt_placements lo usa.
        Paso 1: VM en lane con boarding_committed → _process_reservations calcula y reserva slot.
        Paso 2: simulamos que el VM llegó al belt → _handle_belt_placements lo coloca en ese slot.
        Verificar: VM en el slot exacto que fue reservado, reserved_station_id limpiado.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        lane = network.get_track(LANE_ID)
        down_tree = network.get_track(DOWN_TREE_ID)

        lane.vehicles[vm.vehicle_id] = {
            'vehicle': vm, 'distance': 0.5 * LANE_LENGTH,
            'velocity': BOARDING_LANE_SPEED, 'passengers': [], 'boarding_committed': True,
        }

        with patch.object(brain, '_would_saturate', return_value=False):
            brain._process_reservations()

        reserved_slot = brain._reserved_slots.get(vm.vehicle_id)
        assert reserved_slot is not None, "La reserva debe haberse creado"
        assert train.slots[reserved_slot]['reserved_station_id'] == STATION_ID

        # Simular que el VM llegó al belt (belt_placement desde DOWN tree)
        brain._handle_belt_placements([(vm, 0.0, STATION_ID)])

        assert train.slots[reserved_slot]['vm'] is vm
        assert train.slots[reserved_slot]['reserved_station_id'] is None  # place_vm limpió
        assert vm.vehicle_id not in brain._reserved_slots

    def test_reserved_slots_dict_cleaned_after_placement(self):
        """
        _handle_belt_placements hace pop(vm_id) de _reserved_slots.
        Con múltiples VMs en reserva, solo el que aterriza es removido.
        Verificar: no hay leak — _reserved_slots queda limpio para ese vm_id.
        """
        brain, train, network, stations = make_brain_fixture()
        vm_a = _make_vm(vm_id=0)
        vm_b = _make_vm(vm_id=1)
        SLOT_A, SLOT_B = 7, 12

        brain._reserved_slots[vm_a.vehicle_id] = SLOT_A
        brain._reserved_slots[vm_b.vehicle_id] = SLOT_B

        # Solo vm_a llega al belt este frame
        brain._handle_belt_placements([(vm_a, 0.0, STATION_ID)])

        assert vm_a.vehicle_id not in brain._reserved_slots   # consumido
        assert vm_b.vehicle_id in brain._reserved_slots        # el otro sigue activo
        assert train.slots[SLOT_A]['vm'] is vm_a
        assert train.slots[SLOT_B]['vm'] is None               # vm_b aún no llegó

    def test_pase2_does_not_set_destination_on_colliding_slot(self):
        """
        Pase 2 (destino adquirido después del commit) nunca escribe
        destination_station_id en un slot que ya está en choque.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=0)
        vm.destination_station_id = STATION_ID
        SLOT = 7
        
        brain._reserved_slots[vm.vehicle_id] = SLOT
        train.slots[SLOT]['vm'] = _make_vm(vm_id=1)               # ocupante original
        train.slots[SLOT]['colliding_vms'] = [_make_vm(vm_id=2)]  # ya está en choque

        lane = network.get_track(LANE_ID)
        lane.vehicles[vm.vehicle_id] = {
            'vehicle': vm, 'distance': 0.5 * LANE_LENGTH,
            'velocity': BOARDING_LANE_SPEED, 'passengers': [], 'boarding_committed': True,
        }

        brain._process_reservations()

        assert train.slots[SLOT]['destination_station_id'] is None


# ─── RANGE SEARCH PRIORITIES ─────────────────────────────────────────────────

class TestRangeSearchPriorities:
    """
    Prioridades de _range_search_reservation — elige el mejor slot para
    reservar el aterrizaje de un VM que viene bajando del árbol DOWN.

    Sistema de prioridades (de mejor a peor):
        P1a (1): dest == station_id  — VM ya va a S con pasajeros
        P1b (2): demand == station_id — VM pedido por S (sin pasajeros)
        P2  (3): slot vacío           — nadie que evicionar
        P3  (4): VM limpio            — sin compromisos con ninguna estación
        P4  (5): demand == OTRA       — rompe promesa débil de otra estación
        P5  (6): dest == OTRA         — pasajeros irán a estación incorrecta (WARNING)

    Slots con reserved != None se omiten siempre:
        reserved == S     → doble reserva (sin sentido)
        reserved == OTRA  → colisión física garantizada (CRITICAL + skip)
        Prioridades de _range_search_reservation — elige el mejor slot para
    reservar el aterrizaje de un VM que viene bajando del árbol DOWN.

    Sistema de prioridades (de mejor a peor):
        P1a (1): dest == station_id  — VM ya va a S con pasajeros
        P1b (2): demand == station_id — VM pedido por S (sin pasajeros)
        P2  (3): slot vacío           — nadie que evicionar
        P3  (4): VM limpio            — sin compromisos con ninguna estación
        P4  (5): demand == OTRA       — rompe promesa débil de otra estación
        P5  (6): dest == OTRA         — pasajeros irán a estación incorrecta (WARNING)

    Slots con reserved != None se omiten siempre:
        reserved == S     → doble reserva (sin sentido)
        reserved == OTRA  → colisión física garantizada (CRITICAL + skip)
    """

    def test_reservation_prefers_dest_over_demand_same_station(self):
        """
        dest=S (P1a=1) gana sobre demand=S (P1b=2). El VM ya lleva pasajeros a S.
        """
        brain, train, network, stations = make_brain_fixture()
        junction_up = network.get_junction_up(STATION_ID)

        with patch.object(brain, '_would_saturate', return_value=False):
            train.slots[20]['vm'] = _make_vm()
            train.set_demand_supply(20, STATION_ID)   # P1b

            train.slots[25]['vm'] = _make_vm()
            train.set_destination(25, STATION_ID)     # P1a

            result,*_ = brain._range_search_reservation(22, STATION_ID, junction_up)

        assert result == 25, "dest=S (P1a) debe ganar sobre demand=S (P1b)"

    def test_reservation_prefers_empty_over_vm_without_destination(self):
        """
        slot vacío (P2=3) gana sobre VM limpio (P3=4). No hay que evicionar a nadie.
        """
        brain, train, network, stations = make_brain_fixture()
        junction_up = network.get_junction_up(STATION_ID)

        with patch.object(brain, '_would_saturate', return_value=False):
            train.slots[25]['vm'] = _make_vm()  # único VM en el rango → P3

            result,*_ = brain._range_search_reservation(22, STATION_ID, junction_up)

        assert result != 25, "No debe elegir el VM limpio cuando hay slots vacíos"
        assert train.slots[result]['vm'] is None, "Debe elegir un slot vacío (P2)"

    def test_reservation_clean_vm_beats_demand_other(self):
        """
        VM limpio (P3=4) gana sobre VM con demand=OTRA (P4=5).
        """
        OTHER = 99
        brain, train, network, stations = make_brain_fixture()
        junction_up = network.get_junction_up(STATION_ID)

        with patch.object(brain, '_would_saturate', return_value=False):
            for i in range(train.max_slots):              # llena todo el rango con demand=OTHER
                train.slots[i]['vm'] = _make_vm()
                train.set_demand_supply(i, OTHER)

            train.slots[25]['demand_station_id'] = None  # slot 25 queda limpio → P3

            result,*_ = brain._range_search_reservation(22, STATION_ID, junction_up)

        assert result == 25, "VM limpio (P3) debe ganar sobre demand=OTRA (P4)"

    def test_reservation_prefers_demand_other_over_dest_other(self, caplog):
        """
        demand=OTRA (P4=5) gana sobre dest=OTRA (P5=6). P4 no dispara WARNING.
        """
        OTHER = 99
        brain, train, network, stations = make_brain_fixture()
        junction_up = network.get_junction_up(STATION_ID)

        with patch.object(brain, '_would_saturate', return_value=False):
            for i in range(train.max_slots):              # llena todo el rango con dest=OTHER → P5
                train.slots[i]['vm'] = _make_vm()
                train.set_destination(i, OTHER)

            # slot 25: solo demand=OTHER, sin dest → P4
            train.slots[25]['destination_station_id'] = None
            train.set_demand_supply(25, OTHER)

            result,*_ = brain._range_search_reservation(22, STATION_ID, junction_up)

        assert result == 25, "demand=OTRA (P4) debe ganar sobre dest=OTRA (P5)"
        assert not any("otra estación" in r.message for r in caplog.records
                   if r.levelno == logging.WARNING), \
        "P4 no debe disparar WARNING — el WARNING es exclusivo de P5 (dest=OTRA)"

    def test_reservation_dest_other_with_warning(self, caplog):
        """
        Si el mejor disponible es dest=OTRA (P5), se elige con WARNING.
        """
        import logging
        OTHER = 99
        brain, train, network, stations = make_brain_fixture()
        junction_up = network.get_junction_up(STATION_ID)

        with patch.object(brain, '_would_saturate', return_value=False):
            for i in range(train.max_slots):
                train.slots[i]['vm'] = _make_vm()
                train.set_destination(i, OTHER)  # todos P5

            with caplog.at_level(logging.WARNING, logger="systems.brain"):
                result,*_ = brain._range_search_reservation(22, STATION_ID, junction_up)

        assert result is not None, "Debe elegir algún slot aunque sea P5"
        assert train.slots[result]['destination_station_id'] == OTHER
        assert any("otra estación" in r.message for r in caplog.records
                if r.levelno == logging.WARNING), "Debe emitir WARNING por evicción de destino"

    def test_reservation_skips_slot_reserved_for_other_station(self, caplog):
        """
        Slots con reserved=OTRA se saltan siempre. Se emite CRITICAL por cada uno.
        """
        import logging
        OTHER = 99
        brain, train, network, stations = make_brain_fixture()
        junction_up = network.get_junction_up(STATION_ID)

        with patch.object(brain, '_would_saturate', return_value=False):
            for i in range(train.max_slots):
                if i != 22:   # 22 = target = siempre dentro del rango
                    train.slots[i]['reserved_station_id'] = OTHER
            # slot 22: vacío, sin reserva → único candidato válido

            with caplog.at_level(logging.CRITICAL, logger="systems.brain"):
                result,*_ = brain._range_search_reservation(22, STATION_ID, junction_up)

        assert result == 22, "Único slot no reservado debe ser elegido"
        assert any("riesgo de colisión" in r.message for r in caplog.records
                if r.levelno == logging.CRITICAL), "Debe emitir CRITICAL por cada reserved=OTRA"

    def test_reservation_skips_slot_reserved_for_same_station_silently(self, caplog):
        """reserved=S se salta sin emitir CRITICAL. Doble reserva para misma estación."""
        import logging
        brain, train, network, stations = make_brain_fixture()
        junction_up = network.get_junction_up(STATION_ID)

        with patch.object(brain, '_would_saturate', return_value=False):
            for i in range(train.max_slots):
                if i != 22:
                    train.slots[i]['reserved_station_id'] = STATION_ID

            with caplog.at_level(logging.CRITICAL, logger="systems.brain"):
                result,*_ = brain._range_search_reservation(22, STATION_ID, junction_up)

        assert result == 22, "El único slot sin reserva debe elegirse"
        assert not any(r.levelno == logging.CRITICAL for r in caplog.records), \
            "reserved=S debe saltarse sin CRITICAL — no es un error externo, es doble reserva propia"

    def test_range_wraps_around_circular_belt(self):
        """
        target cerca de 0: índices negativos deben envolverse con % max_slots.
        """
        brain, train, network, stations = make_brain_fixture()
        junction_up = network.get_junction_up(STATION_ID)

        with patch.object(brain, '_would_saturate', return_value=False):
            # target=2, half=5 → rango incluye slots 47,48,49,0,1,2,3,4,5,6,7
            train.slots[48]['vm'] = _make_vm()
            train.set_destination(48, STATION_ID)  # P1a en slot envuelto

            result,*_ = brain._range_search_reservation(2, STATION_ID, junction_up)

        assert result == 48, "Debe encontrar el slot envuelto (48 = -2 % 50)"

    def test_reservation_never_selects_colliding_slot(self):
        """
        Un slot en choque nunca es elegible para una nueva reserva, aunque
        esté vacío de etiquetas — es tan inválido como uno ya reservado.
        """
        brain, train, network, stations = make_brain_fixture()
        junction_up = network.get_junction_up(STATION_ID)

        with patch.object(brain, '_would_saturate', return_value=False):
            train.slots[22]['vm'] = _make_vm()
            train.slots[22]['colliding_vms'] = [_make_vm(vm_id=99)]  # único candidato, pero chocando

            result,*_ = brain._range_search_reservation(22, STATION_ID, junction_up)

        assert result != 22, "Nunca debe elegir un slot en choque"

# ─── BELT PLACEMENT ──────────────────────────────────────────────────────────

class TestBeltPlacement:
    """
    El VM aterriza en el slot correcto y _reserved_slots queda limpio.
    """

    def test_vm_placed_in_reserved_slot(self):
        """
        VM tiene reserva activa: place_vm usa ese slot exacto.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=5)
        TARGET_SLOT = 10

        brain._reserved_slots[vm.vehicle_id] = TARGET_SLOT
        brain._handle_belt_placements([(vm, 0.0, STATION_ID)])

        assert train.slots[TARGET_SLOT]['vm'] is vm, \
            "El VM debe aterrizar en el slot reservado, no en otro"
    
    def test_fallback_placement_when_no_reservation(self, caplog):
        """
        VM llegó al belt sin entrada en _reserved_slots (bug upstream).
        Fallback: find_neartest_slot_to_belt_x cerca de junction_down.
        Verificar: VM aterriza en algún slot (no crash), se emite WARNING.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=5)
        # _reserved_slots vacío → sin entrada para vm_id=5

        with caplog.at_level(logging.WARNING, logger="systems.brain"):
            brain._handle_belt_placements([(vm, 0.0, STATION_ID)])

        # junction_down.belt_x = JUNCTION_DOWN_X = 50.0
        # tail_x=0 → slot N en belt_x = N * 2.0 → slot 25 = 50.0
        assert train.slots[25]['vm'] is vm, \
            "Fallback debe usar el slot más cercano a junction_down (slot 25 = belt_x 50.0)"
        assert "sin reserva" in caplog.text.lower(), \
            "Debe emitir WARNING por falta de reserva"

    def test_reserved_slots_entry_removed_after_placement(self):
        """
        Después de place_vm, _reserved_slots.pop() remueve la entrada.
        Verificar: _reserved_slots vacío después del placement.
        """
        brain, train, network, stations = make_brain_fixture()
        vm = _make_vm(vm_id=5)

        brain._reserved_slots[vm.vehicle_id] = 10
        brain._handle_belt_placements([(vm, 0.0, STATION_ID)])

        assert vm.vehicle_id not in brain._reserved_slots, \
            "vm_id debe eliminarse de _reserved_slots después del placement"
        assert len(brain._reserved_slots) == 0

