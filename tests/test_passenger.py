"""
Test para las funciones mas importantes del archivo objects/passenger.py
"""

import pytest
from objects.passenger import Passenger
from objects.types import PassengerState

VEHICLE_ID_STUB = 42 # ID de VM de test

class Test_initial_state:
    """"
    Test de la la funcion __init__()
    """
    def test_initial_state(self):
        """
        Test de caso normal
        """
        p = Passenger(passenger_id=1, origin_station_id=2, destination_station_id=3, spawn_time=0.0)
        assert p.passenger_id == 1
        assert p.origin_station_id == 2
        assert p.destination_station_id == 3
        assert p.state == PassengerState.WAITING_AT_ENTRANCE
        assert p.spawn_time == 0.0
        assert p.arrival_time is None
        assert p.vehicle_id is None

class Test_state_transitions:
    """
    Test para las funicones de transicion de estado
    """
    def test_full_journey(self):
        """
        Secuencia completa de estados, de principio a fin.
        """
        p = Passenger(1,2,5, spawn_time=0.0)

        # Primer paso (Spawn -> Lane)
        p.start_moving_to_lane()
        assert p.state == PassengerState.MOVING_TO_LANE
        assert not p.is_waiting

        # Segundo paso (Lane -> waiting_in_lane)
        p.arrive_at_lane()
        assert p.state == PassengerState.WAITING_IN_LANE_QUEUE
        assert p.is_waiting

        # Tercer paso (waiting_in_lane -> bording)
        p.start_boarding()
        assert p.state == PassengerState.BOARDING
        assert not p.is_waiting

        # Cuerto paso (bording -> complete bording)
        p.complete_boarding(vehicle_id=VEHICLE_ID_STUB)
        assert p.state == PassengerState.IN_TRANSIT
        assert p.vehicle_id == VEHICLE_ID_STUB
        assert not p.is_waiting

        # Quinto paso (complete bording -> complete journey)
        p.arrive(current_time=10.0)
        assert p.is_arrived
        assert p.state == PassengerState.ARRIVED
        assert p.arrival_time == 10.0
        assert p.vehicle_id is None
        
    def test_invalid_skip_to_boarding(self):
        """
        No se puede ir a BOARDING directo desde WAITING_AT_ENTRANCE
        """
        p = Passenger(1,2,5, spawn_time=0.0)
        with pytest.raises(ValueError):
            p.start_boarding()

    def test_invalid_skip_to_in_transit(self):
        """
        No se puede completar boarding sin haberlo iniciado.
        """
        p = Passenger(1,2,5, spawn_time=0.0)
        with pytest.raises(ValueError):
            p.complete_boarding(vehicle_id=VEHICLE_ID_STUB)
    
    def test_invalid_arrive_without_transit(self):
        """
        No se puede completar el viaje sin haber iniciado el viaje
        """
        p = Passenger(1,2,5, spawn_time=0.0)
        with pytest.raises(ValueError):
            p.arrive(current_time=5.0)

    def test_invalid_duplicate_trasition(self):
        """
        No se puede hacer la misma transicion dos veces.
        """
        p = Passenger(1,2,5, spawn_time=0.0)
        p.start_moving_to_lane()
        with pytest.raises(ValueError):
            p.start_moving_to_lane()

class Test_metrics:
    """
    Test de las funciones metricas
    """
    def test_total_travel_time(self):
        """
        Test de la funcion total_travel_time()
        """
        p = Passenger(1,2,5, spawn_time=2.0)
        p.start_moving_to_lane()
        p.arrive_at_lane()
        p.start_boarding()
        p.complete_boarding(VEHICLE_ID_STUB)
        p.arrive(current_time=12.0)
        assert p.total_travel_time() == pytest.approx(10.0)
    
    def test_total_travel_time_none_while_traveling(self):
        """
        Retorna None si todavia no ha completado el viaje
        """
        p = Passenger(1,2,5, spawn_time=2.0)
        assert p.total_travel_time() is None


