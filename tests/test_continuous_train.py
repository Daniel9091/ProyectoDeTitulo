"""
Tests para ContinuousTrain.

Responsabilidades documentadas:
    - TestInit:         construcción, max_slots, density, tail_x inicial
    - TestAdvance:      tail_x, wrap-around, detección de crossings, leftover_dt exacto
    - TestVmOperations: place_vm, remove_vm y limpieza de etiquetas
    - TestSlotLabels:   set/clear de reservation, destination, demand_supply
    - TestQueries:      get_slot_belt_x, find_nearest_slot_to_belt_x, conteos
"""

import pytest
import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from systems.continuous_train import ContinuousTrain
from objects.math3d import Vector3


class FakeVehicle:
    """
    Stub minimo de ModularVehicle para test de track.
    """
    def __init__(self, vehicle_id: int = 0):
        self.vehicle_id = vehicle_id

def make_train(total_length: float = 100.0,
               junction_points: dict | None = None,
               density: float = 0.0) -> ContinuousTrain:
    """
    Tren de prueba con total_length=100, TRAIN_SPACING=2 → 50 slots.
    density=0 deja todos los slots vacíos para que cada test controle los VMs.
    """
    rng = random.Random(42)
    return ContinuousTrain(
        start_pos=Vector3(0, 0, 0),
        end_pos=Vector3(total_length, 0, 0),
        density=density,
        vm_factory=lambda vm_id: FakeVehicle(vm_id),
        rng=rng,
        junction_points=junction_points or {},
    )

# ─── INIT ─────────────────────────────────────────────────────────────────────

class TestInit:
    def test_max_slots_from_total_length(self):
        """
        max_slots = int(total_length / TRAIN_SPACING).
        100m / 2m = 50 slots — la capacidad del carril depende de la geometría.
        """
        train = make_train(total_length=100.0)
        assert train.max_slots == 50

    def test_all_slots_empty_with_zero_density(self):
        """density=0.0 → carril vacío al inicio. Estado base para todos los tests."""
        train = make_train(density=0.0)
        assert all(s['vm'] is None for s in train.slots)

    def test_all_slots_occupied_with_full_density(self):
        """density=1.0 → todos los slots tienen VM. Documenta que density es una proporción."""
        train = make_train(density=1.0)
        assert all(s['vm'] is not None for s in train.slots)

# ─── ADVANCE ──────────────────────────────────────────────────────────────────

class TestAdvance:
    def test_tail_x_advances_by_speed_times_dt(self):
        """tail_x += TRAIN_SPEED * dt = 20 * 0.1 = 2.0 m cada frame."""
        train = make_train()
        train.advance(0.1)
        assert abs(train.tail_x - 2.0) < 1e-9

    def test_tail_x_wraps_around_at_total_length(self):
        """tail_x=99, movement=2.0 → (99+2)%100 = 1.0. El carril es circular."""
        train = make_train(total_length=100.0)
        train.tail_x = 99.0
        train.advance(0.1)
        assert abs(train.tail_x - 1.0) < 1e-9

    def test_no_crossings_when_all_slots_empty(self):
        """Sin VMs en el carril no hay cruces, aunque la junction exista."""
        train = make_train(junction_points={1: 50.0})
        assert train.advance(0.1) == []

    def test_no_crossings_when_no_junction_points(self):
        """Sin junction_points registrados, nunca hay cruces."""
        train = make_train(junction_points={})
        train.slots[0]['vm'] = FakeVehicle(1)
        assert train.advance(0.1) == []

    def test_crossing_detected_with_vm_near_junction(self):
        """
        Slot 0 en belt_x=0, junction en belt_x=1.0.
        dt=0.1 → movement=2.0 ≥ d=1.0 → cruce detectado.
        Retorna (slot_idx=0, station_id=1, leftover_dt).
        """
        train = make_train(total_length=100.0, junction_points={1: 1.0})
        train.slots[0]['vm'] = FakeVehicle(42)
        crossings = train.advance(0.1)
        assert len(crossings) == 1
        slot_idx, station_id, _ = crossings[0]
        assert slot_idx == 0
        assert station_id == 1

    def test_crossing_leftover_dt_is_correct(self):
        """
        d=1.0, TRAIN_SPEED=20, dt=0.1.
        leftover = dt - d/TRAIN_SPEED = 0.1 - 1.0/20 = 0.05s.
        Brain usa este leftover para que el VM no pierda tiempo al entrar al árbol.
        """
        train = make_train(total_length=100.0, junction_points={1: 1.0})
        train.slots[0]['vm'] = FakeVehicle(42)
        _, _, leftover_dt = train.advance(0.1)[0]
        assert abs(leftover_dt - 0.05) < 1e-9

    def test_crossing_not_detected_when_slot_too_far(self):
        """
        d=1.0, dt=0.04 → movement=0.8 < d → el VM no alcanzó la junction este frame.
        """
        train = make_train(total_length=100.0, junction_points={1: 1.0})
        train.slots[0]['vm'] = FakeVehicle(42)
        assert train.advance(0.04) == []

    def test_slot_without_vm_is_ignored_at_junction(self):
        """Un slot vacío en la junction no genera cruce — solo VMs producen eventos."""
        train = make_train(total_length=100.0, junction_points={1: 1.0})
        assert train.advance(0.1) == []

    def test_leftover_is_full_dt_when_vm_exactly_at_junction(self):
        """
        VM exactamente en junction_x=0.0, slot 0 en belt_x=0.
        d=0.0 → leftover = max(0, dt - 0) = dt completo.
        El VM no consumió nada del frame para cruzar.
        """
        train = make_train(total_length=100.0, junction_points={5: 0.0})
        train.slots[0]['vm'] = FakeVehicle(1)
        _, _, leftover_dt = train.advance(0.1)[0]
        assert abs(leftover_dt - 0.1) < 1e-9

    def test_two_junctions_two_crossings_same_frame(self):
        """
        Junction A en belt_x=1.0 → cruza slot 0 (belt_x=0, d=1.0).
        Junction B en belt_x=2.5 → cruza slot 1 (belt_x=2, d=0.5).
        dt=0.1, movement=2.0. Ambas d < movement → dos cruces en el mismo frame.
        """
        train = make_train(total_length=100.0, junction_points={1: 1.0, 2: 2.5})
        train.slots[0]['vm'] = FakeVehicle(10)
        train.slots[1]['vm'] = FakeVehicle(11)
        crossings = train.advance(0.1)
        assert len(crossings) == 2
        assert {c[1] for c in crossings} == {1, 2}

    def test_crossing_station_id_matches_junction_point_key(self):
        """El station_id del cruce es exactamente la clave del junction_points dict."""
        train = make_train(total_length=100.0, junction_points={99: 1.0})
        train.slots[0]['vm'] = FakeVehicle(1)
        _, station_id, _ = train.advance(0.1)[0]
        assert station_id == 99

# ─── CONTRATOS DE SLOTS ────────────────────────────────────────────────────────

class TestSlotContracts:
    def test_place_vm_clears_reservation(self):
        """
        Cuando el VM aterriza en su slot, place_vm limpia la reserva automáticamente.
        Brain no necesita hacer clear_reservation por separado.
        """
        train = make_train()
        train.set_reservation(0, vm_id=42)
        train.place_vm(FakeVehicle(42), 0)
        assert train.slots[0]['reserved_for_vm_id'] is None

    def test_demand_supply_persists_after_place_vm(self):
        """
        Invariante (CLAUDE.md §3): demand_supply_for_station_id NO se borra al
        llegar el VM. Brain la necesita para saber a qué junction sacar al VM.
        Solo remove_vm la limpia.
        """
        train = make_train()
        train.set_demand_supply(0, station_id=7)
        train.place_vm(FakeVehicle(1), 0)
        assert train.slots[0]['demand_supply_for_station_id'] == 7

    def test_remove_vm_clears_all_routing_labels(self):
        """
        Al salir del carril, remove_vm borra destination y demand_supply.
        El slot queda limpio para el siguiente VM.
        """
        train = make_train()
        train.slots[2]['vm'] = FakeVehicle(5)
        train.slots[2]['destination_station_id'] = 7
        train.slots[2]['demand_supply_for_station_id'] = 3
        train.remove_vm(2)
        s = train.slots[2]
        assert s['vm'] is None
        assert s['destination_station_id'] is None
        assert s['demand_supply_for_station_id'] is None

    def test_free_slot_requires_no_vm_and_no_reservation(self):
        """
        'Libre' no es solo 'sin VM'. Un slot reservado ya fue comprometido
        para un VM que desciende — Brain no puede asignarlo a otro.
        get_free_slot_count() los excluye.
        """
        train = make_train(total_length=100.0)
        free_before = train.get_free_slot_count()
        train.set_reservation(0, vm_id=1)
        assert train.get_free_slot_count() == free_before - 1

    def test_destination_persists_after_place_vm(self):
        """
        Destino se escribe en el slot al hacer commit en la lane, ANTES de que el VM llegue.
        place_vm no lo borra — Brain lo necesita para saber en qué junction sacar al VM.
        Solo remove_vm lo limpia al salir del carril.
        """
        train = make_train()
        train.set_destination(0, station_id=5)
        train.place_vm(FakeVehicle(1), 0)
        assert train.slots[0]['destination_station_id'] == 5

# ─── QUERIES ──────────────────────────────────────────────────────────────────

class TestQueries:
    def test_get_slot_belt_x_slot_zero_is_at_tail_x(self):
        """Slot 0 siempre está en tail_x, sin importar cuánto avanzó el tren."""
        train = make_train()
        train.tail_x = 37.4
        assert abs(train.get_slot_belt_x(0) - 37.4) < 1e-9

    def test_get_slot_belt_x_offset_slot(self):
        """Slot N está en tail_x + N * TRAIN_SPACING. Con tail_x=0, slot 3 → 6.0m."""
        train = make_train()
        assert abs(train.get_slot_belt_x(3) - 6.0) < 1e-9

    def test_get_slot_belt_x_wraps_around(self):
        """
        tail_x=5, slot 49: (5 + 49*2) % 100 = 103 % 100 = 3.0.
        Los slots del extremo del carril hacen wrap-around.
        """
        train = make_train(total_length=100.0)
        train.tail_x = 5.0
        assert abs(train.get_slot_belt_x(49) - 3.0) < 1e-9
