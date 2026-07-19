"""
Tests para AccelerationTree.

Valores de referencia para make_up_tree(length=30, acceleration=5.0, separation=2.0):
    v_exit = sqrt(400 - 300) = 10.0 m/s
    dt_min = (-10 + sqrt(120)) / 5 ≈ 0.1909 s
    _min_safe_distance ≈ 3.727 m
    min_slot_gap = ceil(0.1909 * 20 / 2) = 2
"""

import math
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tracks.acceleration_tree import AccelerationTree
from objects.math3d import Vector3
from objects.types import TreeDirection, ModularVehicleState
from telemetry.recorder import NullRecorder
from config.constants import (
    TRAIN_SPEED, BOARDING_LANE_SPEED,
    ACCEL_RANGE_MIN, ACCEL_RANGE_MAX, TRAIN_SPACING, GRAVITY
)


class FakeVehicle:
    def __init__(self, vehicle_id: int):
        self.vehicle_id = vehicle_id
        self.state = ModularVehicleState.MOVING
        self.reserved_tree_acceleration = None  # accel del proximo arbol DOWN
        self.total_distance_traveled = 0.0
        self.operational_time = 0.0
        self.distance_carrying_passengers = 0.0
        self.passengers_on_board = []  

def _slanted_end_pos(length: float, target_accel: float) -> Vector3:
    """
    Punto final que, junto al origen, da un árbol de `length` metros con
    aceleración efectiva == target_accel (dado GRAVITY).
        dz = target_accel * length / GRAVITY  ;  dx = sqrt(length² - dz²)
    """
    dz = target_accel * length / GRAVITY
    dx = math.sqrt(max(0.0, length ** 2 - dz ** 2))
    return Vector3(dx, 0.0, dz)

def make_up_tree(
    length: float = 30.0,
    acceleration: float = 5.0,  # acceleracion effectiva
    separation: float = 2.0,
) -> AccelerationTree:
    return AccelerationTree(
        1, Vector3(0, 0, 0), _slanted_end_pos(length, acceleration),
        TreeDirection.UP, separation, NullRecorder(),
    )

def make_down_tree(
    length: float = 30.0,
    acceleration: float = 5.0,  # acceleracion effectiva
    separation: float = 2.0,
) -> AccelerationTree:
    end = _slanted_end_pos(length, acceleration)
    return AccelerationTree(
        2, end, Vector3(0, 0, 0),
        TreeDirection.DOWN, separation, NullRecorder(),
    )

class Test_init:
    """
    Test de la inicilaisacion de los arboles.
    """

    def test_up_tree_has_positive_min_slot_gap(self):
        """
        Un árbol UP con desaceleración debe tener slot gap positivo.
        (slots mínimos entre entradas consecutivas >= 0)
        """
        tree = make_up_tree()
        assert tree.min_slot_gap > 0

    def test_down_tree_has_zero_slot_gap(self):
        """
        Un árbol DOWN no aplica saturación; su slot gap es cero.

        (slots mínimos entre entradas consecutivas no aplica por que
        para un arbol de de bajada los VMs se separan)
        """
        tree = make_down_tree()
        assert tree.min_slot_gap == 0

    def test_down_tree_has_zero_min_safe_distance(self):
        """
        Un árbol DOWN no inicializa saturación; _min_safe_distance es cero.

        (la distancia entre el VM mas joven y el que esta a punto de entrar no
        es relevante por que los VMs se alejan con el tiempo en un arbol DOWN)
        """
        tree = make_down_tree()
        assert tree._min_safe_distance == 0.0

    def test_up_tree_slot_gap_matches_formula(self):
        """
        min_slot_gap concuerda con ceil(dt_min * TRAIN_SPEED / TRAIN_SPACING).

        """
        tree = make_up_tree(length=30.0, acceleration=5.0, separation=2.0)
        v_exit = math.sqrt(max(0.0, TRAIN_SPEED**2 - 2.0 * 5.0 * 30.0))
        dt_min = (-v_exit + math.sqrt(v_exit**2 + 2.0 * 5.0 * 2.0)) / 5.0
        expected = math.ceil(dt_min * TRAIN_SPEED / TRAIN_SPACING)
        assert tree.min_slot_gap == expected

    def test_length_computed_from_positions(self):
        """
        La longitud del árbol se calcula desde start_pos hasta end_pos.
        """
        tree = make_up_tree(length=30.0)
        assert tree.length == pytest.approx(30.0)

    def test_slot_gap_rounds_up_not_down(self):
        """
        min_slot_gap usa math.ceil, nunca floor.
        Con a=5, L=30, d_min=3:
            v_exit = sqrt(20² - 2·5·30) = sqrt(100) = 10.0 m/s
            dt_min = (-10 + sqrt(100 + 2·5·3)) / 5 = (-10 + sqrt(130)) / 5 ≈ 0.2804s
            raw    = dt_min × 20 / 2 ≈ 2.804
            floor  = 2  →  insuficiente, causaría choque (diferencia de 0.196 slots)
            ceil   = 3  →  correcto
        """
        
        tree = AccelerationTree(1, Vector3(0, 0, 0), _slanted_end_pos(30.0, 5.0),
                                TreeDirection.UP, 3.0, NullRecorder())
        v_exit = math.sqrt(max(0.0, 20.0**2 - 2.0 * 5.0 * 30.0))          # 10.0
        dt_min = (-v_exit + math.sqrt(v_exit**2 + 2.0 * 5.0 * 3.0)) / 5.0 # ≈ 0.2804
        raw = dt_min * 20.0 / 2.0                                           # ≈ 2.804

        assert raw % 1 != 0, "el valor crudo debe ser no-entero para que el test tenga sentido"
        assert tree.min_slot_gap == math.ceil(raw)   # siempre redondea hacia arriba
        assert tree.min_slot_gap > math.floor(raw)   # nunca floor

class Test_can_accept:
    """
    Testea funcion can_accept() de AccelerationTree.
    resuelve cuando se acepta un vm nuevo en el arbol
    simulando diferentes situaciones.
    """
    def test_empty_up_tree_always_accepts(self):
        """Un árbol UP sin VMs siempre acepta."""
        tree = make_up_tree()
        assert tree.can_accept() is True
    
    def test_down_tree_always_accepts_with_vehicles(self):
        """Un árbol DOWN siempre acepta, incluso con VMs adentro."""
        tree = make_down_tree()
        vm = FakeVehicle(1)
        tree.add_vehicle(vm)
        assert tree.can_accept() is True    

    def test_up_tree_rejects_when_youngest_too_close(self):
        """Rechaza si el VM más reciente no ha avanzado lo suficiente."""
        tree = make_up_tree()
        vm = FakeVehicle(1)
        tree.add_vehicle(vm)
        # distancia inicial ≈ 0, mucho menor que _min_safe_distance ≈ 3.73m
        assert tree.can_accept() is False

    def test_up_tree_accepts_when_youngest_far_enough(self):
        """Acepta si el VM más reciente superó _min_safe_distance."""
        tree = make_up_tree()
        vm = FakeVehicle(1)
        tree.add_vehicle(vm)
        tree.vehicles[vm.vehicle_id]['distance'] = tree._min_safe_distance + 1.0
        assert tree.can_accept() is True

    def test_up_tree_uses_youngest_vm_not_oldest(self):
        """El check usa el VM con menor distancia (el más reciente), no el mayor."""
        tree = make_up_tree()
        vm1 = FakeVehicle(1)
        vm2 = FakeVehicle(2)
        tree.force_add_vehicle(vm1)
        tree.force_add_vehicle(vm2)
        # vm1 lleva más tiempo, forzar distancia grande
        tree.vehicles[vm1.vehicle_id]['distance'] = tree._min_safe_distance + 5.0
        # vm2 recién entró, distancia pequeña
        tree.vehicles[vm2.vehicle_id]['distance'] = 0.1
        assert tree.can_accept() is False
    
class Test_AddVehicle:
    """
    Test de add_vehicle() de AccelerationTree.
    """

    def test_add_to_empty_tree_returns_true(self):
        """
        add_vehicle retorna True y registra el VM cuando el árbol está vacío.
        """
        tree = make_up_tree()
        vm = FakeVehicle(1)
        assert tree.add_vehicle(vm) is True
        assert vm.vehicle_id in tree.vehicles

    def test_add_rejected_returns_false_no_side_effects(self):
        """add_vehicle retorna False y no modifica nada si se rechaza por saturación."""
        tree = make_up_tree()
        vm1 = FakeVehicle(1)
        tree.add_vehicle(vm1)
        vm2 = FakeVehicle(2)
        result = tree.add_vehicle(vm2)
        assert result is False
        assert vm2.vehicle_id not in tree.vehicles
        assert vm2.state == ModularVehicleState.MOVING

    def test_add_sets_accelerating_up_state(self):
        """Un VM que entra a árbol UP recibe estado ACCELERATING_UP."""
        tree = make_up_tree()
        vm = FakeVehicle(1)
        tree.add_vehicle(vm)
        assert vm.state == ModularVehicleState.ACCELERATING_UP

    def test_add_sets_accelerating_down_state(self):
        """Un VM que entra a árbol DOWN recibe estado ACCELERATING_DOWN."""
        tree = make_down_tree()
        vm = FakeVehicle(1)
        tree.add_vehicle(vm)
        assert vm.state == ModularVehicleState.ACCELERATING_DOWN

    def test_add_uses_train_speed_as_default_for_up(self):
        """Sin entry_velocity explícita, árbol UP usa TRAIN_SPEED."""
        tree = make_up_tree()
        vm = FakeVehicle(1)
        tree.add_vehicle(vm)
        assert tree.vehicles[vm.vehicle_id]['velocity'] == pytest.approx(TRAIN_SPEED)

    def test_add_uses_boarding_lane_speed_as_default_for_down(self):
        """Sin entry_velocity explícita, árbol DOWN usa BOARDING_LANE_SPEED."""
        tree = make_down_tree()
        vm = FakeVehicle(1)
        tree.add_vehicle(vm)
        assert tree.vehicles[vm.vehicle_id]['velocity'] == pytest.approx(BOARDING_LANE_SPEED)

class Test_ForceAddVehicle:
    """
    Test de force_add_vehicle() de AccelerationTree.
    """

    def test_force_add_succeeds_when_unsafe(self):
        """force_add_vehicle agrega el VM aunque can_accept() sea False."""
        tree = make_up_tree()
        vm1 = FakeVehicle(1)
        tree.add_vehicle(vm1)
        assert not tree.can_accept()
        vm2 = FakeVehicle(2)
        tree.force_add_vehicle(vm2)
        assert vm2.vehicle_id in tree.vehicles

    def test_force_add_prints_warning_when_unsafe(self, capsys):
        """force_add_vehicle imprime advertencia cuando hay riesgo de saturación."""
        tree = make_up_tree()
        vm1 = FakeVehicle(1)
        tree.add_vehicle(vm1)
        vm2 = FakeVehicle(2)
        tree.force_add_vehicle(vm2)
        captured = capsys.readouterr()
        assert "ADVERTENCIA" in captured.out

    def test_force_add_no_warning_when_safe(self, capsys):
        """force_add_vehicle no imprime advertencia si el árbol puede aceptar."""
        tree = make_up_tree()
        vm = FakeVehicle(1)
        tree.force_add_vehicle(vm)
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_force_add_sets_correct_state(self):
        """force_add_vehicle también setea el estado del VM igual que add_vehicle."""
        tree = make_up_tree()
        vm1 = FakeVehicle(1)
        tree.add_vehicle(vm1)
        vm2 = FakeVehicle(2)
        tree.force_add_vehicle(vm2)
        assert vm2.state == ModularVehicleState.ACCELERATING_UP

class Test_Physics:
    """
    Revision de la fisica de los VMs en los arboles.
    """

    def test_up_tree_decelerates_vm(self):
        """
        Un árbol UP reduce la velocidad del VM en cada frame.

        Verifica v = v₀ + a·t con aceleración negativa (UP).
        entry_velocity=20, a=−5, dt=1 → v = 20 + (−5)·1 = 15 m/s
        """
        tree = make_up_tree(length=1000.0, acceleration=5.0)
        vm = FakeVehicle(1)
        tree.add_vehicle(vm, entry_velocity=20.0)
        tree.update(1.0)
        assert tree.vehicles[vm.vehicle_id]['velocity'] == pytest.approx(15.0)

    def test_down_tree_accelerates_vm(self):
        """
        Un árbol DOWN aumenta la velocidad del VM en cada frame.

        Verifica v = v₀ + a·t con aceleración positiva (DOWN).
        entry_velocity=2, a=+5, dt=1 → v = 2 + 5·1 = 7 m/s
        """
        tree = make_down_tree(length=1000.0, acceleration=5.0)
        vm = FakeVehicle(1)
        tree.add_vehicle(vm, entry_velocity=2.0)
        tree.update(1.0)
        assert tree.vehicles[vm.vehicle_id]['velocity'] == pytest.approx(7.0)

    def test_velocity_does_not_go_negative(self):
        """
        En árbol UP, la velocidad se clampea a 0 si la desaceleración 
        tiende a un numero negativo.

        Verifica max(0, v₀ + a·t) cuando la desaceleración agota la velocidad.
        entry_velocity=1, a=−10, dt=2 → v = max(0, 1 + (−10)·2) = max(0, −19) = 0
        """
        tree = make_up_tree(length=1000.0, acceleration=10.0)
        vm = FakeVehicle(1)
        tree.add_vehicle(vm, entry_velocity=1.0)  # se detiene en 0.1s
        tree.update(2.0)                           # dt muy superior al tiempo de parada
        assert tree.vehicles[vm.vehicle_id]['velocity'] == pytest.approx(0.0)

    def test_distance_does_not_decrease_when_stopped(self):
        """
        La distancia recorrida nunca disminuye, aunque el avance calculado fuera negativo.

        Verifica max(0.0, v₀·dt + ½·a·dt²) cuando el VM ya está detenido.
        entry_velocity=0.5, a=−10, dt=0.5 → avance = max(0, 0.25 − 1.25) = max(0, −1.0) = 0
        La distancia queda congelada en el valor anterior.
        """
        tree = make_up_tree(length=1000.0, acceleration=10.0)
        vm = FakeVehicle(1)
        tree.add_vehicle(vm, entry_velocity=0.5)
        dist_before = tree.vehicles[vm.vehicle_id]['distance']
        tree.update(0.5)
        assert tree.vehicles[vm.vehicle_id]['distance'] >= dist_before

    def test_mrua_distance_formula_down(self):
        """Verifica d = v₀t + ½at² en árbol DOWN con valores concretos."""
        tree = make_down_tree(length=1000.0, acceleration=2.0)
        vm = FakeVehicle(1)
        tree.add_vehicle(vm, entry_velocity=5.0)
        tree.update(2.0)
        # d = 5*2 + 0.5*2*4 = 10 + 4 = 14
        assert tree.vehicles[vm.vehicle_id]['distance'] == pytest.approx(14.0)

class Test_Update:
    """
    Test de update() de AccelerationTree.
    """
    def test_update_advances_vm_distance(self):
        """update() incrementa la distancia de los VMs en el árbol."""
        tree = make_down_tree(length=1000.0, acceleration=2.0)
        vm = FakeVehicle(1)
        tree.add_vehicle(vm, entry_velocity=5.0)
        tree.update(1.0)
        assert tree.vehicles[vm.vehicle_id]['distance'] > 0.0

    def test_completed_vm_is_removed(self):
        """Un VM que llega al final del track es removido de self.vehicles."""
        tree = make_down_tree(length=5.0, acceleration=2.0)
        vm = FakeVehicle(1)
        tree.add_vehicle(vm, entry_velocity=5.0)
        result = tree.update(2.0)   # d = 5*2 + 0.5*2*4 = 14 > 5
        assert vm.vehicle_id not in tree.vehicles
        assert len(result) == 1

    def test_update_returns_leftover_dt(self):
        """update() retorna leftover_dt aproximadamente correcto."""
        tree = make_down_tree(length=5.0, acceleration=2.0)
        vm = FakeVehicle(1)
        tree.add_vehicle(vm, entry_velocity=5.0)
        result = tree.update(2.0)
        # time_to_complete ≈ 5/5 = 1.0s (aprox. lineal); leftover ≈ 1.0s
        _, leftover = result[0]
        assert leftover == pytest.approx(1.146, abs=0.01)

    def test_state_restored_to_moving_on_exit(self):
        """Un VM que completa el track recupera el estado MOVING."""
        tree = make_down_tree(length=5.0, acceleration=2.0)
        vm = FakeVehicle(1)
        tree.add_vehicle(vm, entry_velocity=5.0)
        tree.update(2.0)
        assert vm.state == ModularVehicleState.MOVING

    def test_two_vms_update_independently(self):
        """Dos VMs con diferente velocidad inicial avanzan de forma independiente."""
        tree = make_down_tree(length=1000.0, acceleration=2.0)
        vm1 = FakeVehicle(1)
        vm2 = FakeVehicle(2)
        tree.add_vehicle(vm1, entry_velocity=2.0)
        tree.add_vehicle(vm2, entry_velocity=8.0)
        tree.update(1.0)
        d1 = tree.vehicles[vm1.vehicle_id]['distance']
        d2 = tree.vehicles[vm2.vehicle_id]['distance']
        assert d2 > d1

class Test_BrainInterface:

    def test_set_vehicle_acceleration_updates_value(self):
        """set_vehicle_acceleration actualiza target_acceleration del VM."""
        tree = make_up_tree()
        vm = FakeVehicle(1)
        tree.add_vehicle(vm)
        tree.set_vehicle_acceleration(vm.vehicle_id, 1.0)
        assert tree.vehicles[vm.vehicle_id]['target_acceleration'] == pytest.approx(1.0)

    def test_set_vehicle_acceleration_stores_exact_value_below_range(self):
        """
        Caso donde sobrepasa el minimo.
        Revisa que se exponga el valor real aunque este fuera del rango
        AccelerationTree solo avisa que se salio del rango, Brian se procupa
        de no salirse.
        """
        tree = make_up_tree()
        vm = FakeVehicle(1)
        tree.add_vehicle(vm)
        tree.set_vehicle_acceleration(vm.vehicle_id, 0.0)
        assert tree.vehicles[vm.vehicle_id]['target_acceleration'] == pytest.approx(0.0)

    def test_set_vehicle_acceleration_stores_exact_value_above_range(self):
        """
        Caso en el que sobrepasa el maximo
        Revisa que se exponga el valor real aunque este fuera del rango
        AccelerationTree solo avisa que se salio del rango, Brian se procupa
        de no salirse.
        """
        tree = make_up_tree()
        vm = FakeVehicle(1)
        tree.add_vehicle(vm)
        tree.set_vehicle_acceleration(vm.vehicle_id, 99.0)
        assert tree.vehicles[vm.vehicle_id]['target_acceleration'] == pytest.approx(99.0)

    def test_two_vms_have_independent_accelerations(self):
        """Dos VMs en el mismo árbol DOWN pueden tener aceleraciones distintas."""
        tree = make_down_tree(length=1000.0)
        vm1 = FakeVehicle(1)
        vm2 = FakeVehicle(2)
        tree.add_vehicle(vm1)
        tree.add_vehicle(vm2)
        tree.set_vehicle_acceleration(vm1.vehicle_id, 0.5)
        tree.set_vehicle_acceleration(vm2.vehicle_id, 1.2)
        assert tree.vehicles[vm1.vehicle_id]['target_acceleration'] == pytest.approx(0.5)
        assert tree.vehicles[vm2.vehicle_id]['target_acceleration'] == pytest.approx(1.2)

    def test_set_acceleration_warns_when_out_of_range(self, capsys):
        """Imprime advertencia si la aceleración solicitada está fuera del rango permitido."""
        tree = make_up_tree()
        vm = FakeVehicle(1)
        tree.add_vehicle(vm)
        tree.set_vehicle_acceleration(vm.vehicle_id, 99.0)
        captured = capsys.readouterr()
        assert "ADVERTENCIA" in captured.out



