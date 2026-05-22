"""
Tests para Junction.

Responsabilidades documentadas:
    - TestInit:          construcción y propiedades de estado
    - TestBurstCapacity: exposición de parámetros para el sistema de reserva
    - TestCanAccept:     delegación a árboles según dirección
    - TestAddVm:         routing por carga mínima, retorno bool, distribución
    - TestForceAddVm:    selección del árbol menos saturado para entrada forzada
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


from tracks.junction import Junction
from tracks.acceleration_tree import AccelerationTree
from objects.math3d import Vector3
from objects.types import TreeDirection, ModularVehicleState

class FakeVehicle:
    def __init__(self, vehicle_id: int):
        self.vehicle_id = vehicle_id
        self.state = ModularVehicleState.MOVING
        self.reserved_tree_acceleration = None

def make_up_tree(track_id: int = 1) -> AccelerationTree:
    return AccelerationTree(track_id, Vector3(0, 0, 0), Vector3(0, 0, 30.0),
                            TreeDirection.UP, 5.0, 2.0)

def make_down_tree(track_id: int = 10) -> AccelerationTree:
    return AccelerationTree(track_id, Vector3(0, 0, 30.0), Vector3(0, 0, 0),
                            TreeDirection.DOWN, 5.0, 2.0)

def make_up_junction(trees=None) -> Junction:
    if trees is None:
        trees = [make_up_tree(1), make_up_tree(2), make_up_tree(3)]
    return Junction(100, belt_x=50.0, station_id=1, direction=TreeDirection.UP, trees=trees)

def make_down_junction(trees=None) -> Junction:
    if trees is None:
        trees = [make_down_tree(10), make_down_tree(11)]
    return Junction(200, belt_x=60.0, station_id=1, direction=TreeDirection.DOWN, trees=trees)

class TestInit:
    def test_stores_all_fields(self):
        """
        Revisa los que los parametros basicos esten en el constructor
        """
        tree = make_up_tree()
        j = Junction(7, 50.0, station_id=3, direction=TreeDirection.UP, trees=[tree])
        assert j.junction_id == 7
        assert j.belt_x == 50.0
        assert j.station_id == 3
        assert j.direction == TreeDirection.UP
        assert j.trees == [tree]

    def test_vehicle_count_empty_is_zero(self):
        """
        La cantidad de VMs en una junction vacia es cero
        """
        assert make_up_junction().vehicle_count == 0

    def test_vehicle_count_sums_all_trees(self):
        """
        Conteo de cada uno de los Vms en cada arbol aporta
        a la suma total de VM en la junction
        """
        j = make_up_junction()
        j.trees[0].add_vehicle(FakeVehicle(1))
        j.trees[1].add_vehicle(FakeVehicle(2))
        assert j.vehicle_count == 2

class TestBurstCapacity:
    def test_burst_capacity_equals_number_of_trees(self):
        """burst_capacity documenta cuántos VMs puede absorber de corrido."""
        j = make_up_junction(trees=[make_up_tree(1), make_up_tree(2), make_up_tree(3)])
        assert j.burst_capacity == 3

    def test_burst_window_up_equals_min_slot_gap(self):
        """burst_window refleja min_slot_gap del árbol, ya con math.ceil aplicado."""
        tree = make_up_tree()
        j = Junction(1, 50.0, 1, TreeDirection.UP, [tree])
        assert j.burst_window == tree.min_slot_gap
        assert j.burst_window > 0

    def test_burst_window_down_is_zero(self):
        """DOWN trees no saturan — burst_window = 0 documenta que no hay límite."""
        assert make_down_junction().burst_window == 0

class TestCanAccept:
    def test_up_junction_true_when_tree_is_empty(self):
        """Cuando un arbol esta vacio simpre acepta VMs"""
        assert make_up_junction(trees=[make_up_tree(1)]).can_accept() is True

    def test_up_junction_false_when_all_trees_saturated(self):
        """can_accept() delega físicamente a cada árbol; False si todos rechazan."""
        tree = make_up_tree()
        tree.add_vehicle(FakeVehicle(1))
        # youngest_distance = 0 < _min_safe_distance → árbol saturado
        j = Junction(1, 50.0, 1, TreeDirection.UP, [tree])
        assert j.can_accept() is False

    def test_up_junction_true_when_at_least_one_tree_free(self):
        """can_accept() delega físicamente a cada árbol; True si al menos uno acepta."""
        tree_sat = make_up_tree(1)
        tree_free = make_up_tree(2)
        tree_sat.add_vehicle(FakeVehicle(1))
        j = Junction(1, 50.0, 1, TreeDirection.UP, [tree_sat, tree_free])
        assert j.can_accept() is True

    def test_down_junction_always_true(self):
        """DOWN trees nunca saturan — can_accept() siempre True sin importar cuántos VMs hay."""
        j = make_down_junction()
        for i in range(5):
            j.trees[0].add_vehicle(FakeVehicle(i))
        assert j.can_accept() is True

class TestAddVm:
    def test_returns_true_and_adds_vehicle_when_available(self):
        """ 
        Revisa que funcion add_vm retorne True al agregar un VM
        Revisa que este VM sea considerado en el conteo de Vms de
        la junction
        """
        j = make_up_junction()
        assert j.add_vm(FakeVehicle(1)) is True
        assert j.vehicle_count == 1

    def test_returns_false_when_all_up_trees_saturated(self):
        """Retorna False sin modificar estado si todos los árboles rechazan."""
        tree = make_up_tree()
        tree.add_vehicle(FakeVehicle(1))
        j = Junction(1, 50.0, 1, TreeDirection.UP, [tree])

        result = j.add_vm(FakeVehicle(99))
        assert result is False
        assert j.vehicle_count == 1

    def test_down_junction_always_returns_true(self):
        """
        DOWN trees nunca saturan — add_vm siempre retorna True.
        Por que no se saturan.
        """
        assert make_down_junction().add_vm(FakeVehicle(1)) is True

    def test_routes_to_least_loaded_tree(self):
        """Distribuye por carga mínima — el VM nuevo va al árbol con menos vehículos."""
        tree_a = make_up_tree(1)
        tree_b = make_up_tree(2)
        tree_a.add_vehicle(FakeVehicle(99))  # tree_a ya tiene 1 VM

        j = Junction(1, 50.0, 1, TreeDirection.UP, [tree_a, tree_b])
        j.add_vm(FakeVehicle(1))

        assert tree_b.vehicle_count == 1
        assert tree_a.vehicle_count == 1

    def test_vm_state_becomes_accelerating_up(self):
        """El VM queda en ACCELERATING_UP al entrar a una junction UP."""
        j = make_up_junction(trees=[make_up_tree(1)])
        vm = FakeVehicle(1)
        j.add_vm(vm)
        assert vm.state == ModularVehicleState.ACCELERATING_UP

    def test_vm_state_becomes_accelerating_down(self):
        """El VM queda en ACCELERATING_DOWN al entrar a una junction DOWNN."""
        j = make_down_junction(trees=[make_down_tree(1)])
        vm = FakeVehicle(1)
        j.add_vm(vm)
        assert vm.state == ModularVehicleState.ACCELERATING_DOWN

class TestForceAddVm:
    def test_prefers_empty_tree_over_loaded(self):
        """Un árbol vacío siempre es la mejor opción para entrada forzada."""
        tree_a = make_up_tree(1)
        tree_b = make_up_tree(2)
        tree_a.add_vehicle(FakeVehicle(10))

        j = Junction(1, 50.0, 1, TreeDirection.UP, [tree_a, tree_b])
        j.force_add_vm(FakeVehicle(99))

        assert tree_b.vehicle_count == 1
        assert tree_a.vehicle_count == 1

    def test_picks_tree_with_most_advanced_youngest_vm(self):
        """
        Árbol menos saturado = youngest VM más avanzado.
        MRUA con v0=20m/s, a=-5m/s²: tras dt=1s, d = 20·1 - 0.5·5·1² = 17.5m
        tree_b tiene su VM en 17.5m, tree_a en 0m → tree_b recibe el VM forzado.
        """
        tree_a = make_up_tree(1)
        tree_b = make_up_tree(2)
        tree_a.add_vehicle(FakeVehicle(10))
        tree_b.add_vehicle(FakeVehicle(20))
        tree_b.update(1.0)

        j = Junction(1, 50.0, 1, TreeDirection.UP, [tree_a, tree_b])
        j.force_add_vm(FakeVehicle(99))

        assert tree_b.vehicle_count == 2
        assert tree_a.vehicle_count == 1

    def test_adds_vehicle_even_when_all_saturated_and_warns(self, capsys):
        """force_add_vm no lanza excepción aunque todos estén saturados."""
        tree = make_up_tree()
        tree.add_vehicle(FakeVehicle(1))
        j = Junction(1, 50.0, 1, TreeDirection.UP, [tree])

        j.force_add_vm(FakeVehicle(99))
        assert j.vehicle_count == 2
        assert "[ADVERTENCIA]" in capsys.readouterr().out


