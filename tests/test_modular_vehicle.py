"""
Test de las funciones mas importantes del archivo objects/modular_vehicles.py
"""

import pytest
from objects.modular_vehicle import ModularVehicle
from objects.types import ModularVehicleState
from objects.math3d import Vector3

class FakePassenger():
    """
    Clase minima falsa de passenger para poder porbar la funcionalidad
    de los VMs
    """
    def __init__(self, destination_station_id: int):
        self.destination_station_id = destination_station_id

class Test_initial_state():
    """
    Test de la funcion __init__()
    """
    def test_initial_state(self):
        vm = ModularVehicle(vehicle_id=1, capacity=4)
        assert vm.vehicle_id == 1
        assert vm.capacity == 4
        assert vm.state == ModularVehicleState.MOVING
        assert vm.passenger_count == 0
        assert not vm.is_full
        assert not vm.has_destination
        assert vm.slot_index is None
        assert vm.destination_station_id is None
        assert vm.position == Vector3(0.0, 0.0, 0.0)
        assert vm.operational_time == 0.0
        assert vm.total_distance_traveled == 0.0

class Test_board():
    """
    Test de la funcion board()
    """
    def test_bard_single_passenger(self):
        """"
        Test del embarque de un solo pasagero
        """
        vm = ModularVehicle(vehicle_id=1, capacity=4)
        passenger = FakePassenger(destination_station_id=3)
        assert vm.board(passenger) is True
        assert vm.passenger_count == 1

    def test_board_returns_false_when_full(self):
        """
        Test del embarque de un pasagero cuando el vm esta lleno
        """
        vm = ModularVehicle(vehicle_id=1, capacity=1)
        p1 = FakePassenger(destination_station_id=3)
        p2 = FakePassenger(destination_station_id=3)
        vm.board(p1)
        assert vm.is_full
        assert vm.board(p2) is False
        assert vm.passenger_count == 1

    def test_board_up_to_capacity(self):
        vm = ModularVehicle(vehicle_id=1, capacity=2)
        for i in range(2):
            assert vm.board(FakePassenger(destination_station_id=3)) is True
        assert vm.board(FakePassenger(destination_station_id=3)) is False

class Test_disembark():
    """
    Test de la funcion disembark()
    """
    def test_disembark_matching_passengers(self):
        """
        Test de desembarque de pasajeros con el destino correcto
        """
        vm = ModularVehicle(vehicle_id=1, capacity=4)
        p1_dest10 = FakePassenger(destination_station_id=10)
        p2_dest20 = FakePassenger(destination_station_id=20)
        p3_dest10 = FakePassenger(destination_station_id=10)
        
        vm.board(p1_dest10)
        vm.board(p2_dest20)
        vm.board(p3_dest10)
        
        leaving = vm.disembark(station_id=10)
        
        assert len(leaving) == 2
        assert p1_dest10 in leaving
        assert p3_dest10 in leaving
        assert vm.passenger_count == 1
        assert vm.passengers_on_board[0] == p2_dest20

    def test_disembark_no_one_if_wrong_station(self):
        """"
        Test de desembarque de pasajeros con el destino incorrecto
        """
        vm = ModularVehicle(vehicle_id=1, capacity=4)
        vm.board(FakePassenger(destination_station_id=7))
        left = vm.disembark(station_id=2)
        assert left == []
        assert vm.passenger_count == 1

    def test_disembark_empty_vehicle(self):
        vm = ModularVehicle(vehicle_id=1, capacity=4)
        left = vm.disembark(station_id=2)
        assert left == []

class Test_destination_management():
    """
    Test de la funciones asssing_destination () y clear_destination()
    """
    def test_assign_and_clear_destination(self):
        vm = ModularVehicle(vehicle_id=1, capacity=4)
        vm.assign_destination(5)
        assert vm.destination_station_id == 5
        assert vm
        
        vm.clear_destination()
        assert not vm.has_destination
        assert vm.destination_station_id is None

class Test_update():
    """
    Test de la funcion update()
    VM no se mueve a si mismo, la posicion no cambia
    """
    def test_update(self):
        vm = ModularVehicle(vehicle_id=1, capacity=4)
        dt = 0.1
        vm.update(dt)
        assert vm.operational_time == dt
        assert vm.total_distance_traveled == 0.0
