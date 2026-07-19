"""
Test para boardingLane

BoardingLane es subclase concreta de BaseTrack.
Gestinona el abordaje de pasajeros agrupados por destiono a velocidad constante

Desiciones de disño verficadas
    - Velocidad siempre BOARDING_LANE_SPEED (constante, sin exepcion)
    - Cola agrupada por destination_station_id (dict de deques FIFO)
    - VM aborda el grupo con el pasajero mas antiguo (menor spawn_time)
    - VM aborda hasta vehicle.capacity pasageros del grupo ganador
    - Embarque comprometido al alcanzar BOARDING_COMMIT_PROGRESS
    - boarding_committed previene doble llamada a complete_boarding()
    - update() retorna (vm, leftover_dt) confroeme al contratoTrack
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tracks.boarding_lane import BoardingLane
from objects.math3d import Vector3
from objects.passenger import Passenger
from objects.types import PassengerState
from telemetry.recorder import NullRecorder
from config.constants import BOARDING_LANE_SPEED, BOARDING_COMMIT_PROGRESS

# HELPERS

class FakeVehicle:
    """
    Stub minimo de ModularVehicle para test de track.
    """
    def __init__(self, vehicle_id: int, capacity: int = 1):
        self.vehicle_id = vehicle_id
        self.capacity = capacity
        self.passengers_on_board = []
        self.destination_station_id = None
        self.total_distance_traveled = 0.0
        self.operational_time = 0.0
        self.distance_carrying_passengers = 0.0

    @property
    def is_full(self) -> bool:
        return len(self.passengers_on_board) >= self.capacity

    def board(self, passenger) -> bool:
        if self.is_full:
            return False
        self.passengers_on_board.append(passenger)
        return True

    def assign_destination(self, station_id: int) -> None:
        self.destination_station_id = station_id
    
def make_passenger(passenger_id: int, destination: int = 1, spawn_time: float = 0.0) -> Passenger:
    """
    Crea un pasajero listo para ser encolado (MOVING_TO_LANE)
    destination y spawn_time permiten construir esenarios de prioridad.
    """
    p = Passenger(passenger_id, origin_station_id = 0, destination_station_id = destination, spawn_time = spawn_time)
    p.start_moving_to_lane()
    return p

# TEST

class Test_init:
    """
    Verifica la inicialisacion de BoardingLane.
    """
    def test_init(self):
        """
        Track horizontal de 10 m debe heredar lenght correctamente de BaseTrack.
        El Diccionario de de grupos debe iniciar vacio
        No debe haber VMs al inicialisar
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())

        assert lane.length == pytest.approx(10.0)
        assert lane.passenger_groups == {}
        assert lane.vehicle_count == 0

class Test_EnqueuePassenger:
    """
    Verifica el agrupamiento de pasajeros pro destino al encolar.
    """
    def test_enqueue_crates_group_for_new_destination(self):
        """
        Al encolar el primer pasajero hacia un destino, se crea su grupo.
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        p = make_passenger(1,2)
        lane.enqueue_passenger(p)
        assert 2 in lane.passenger_groups
        assert len(lane.passenger_groups[2]) == 1

    def test_enqueue_adds_to_existing_group(self):
        """
        Dos pasajeros al mismo destino deben qudar en el mismo grupo.
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        p1 = make_passenger(1,3)
        p2 = make_passenger(2,3)
        lane.enqueue_passenger(p1)
        lane.enqueue_passenger(p2)
        assert len(lane.passenger_groups[3]) == 2

    def test_enqueue_creates_separate_groups_per_destination(self):
        """
        Pasajeros a distintos destinos generan grupos separados.
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        p1 = make_passenger(1,3)
        p2 = make_passenger(2,4)
        lane.enqueue_passenger(p1)
        lane.enqueue_passenger(p2)
        assert len(lane.passenger_groups) == 2
    
    def test_enqueue_transistions_passenger_state(self):
        """
        El pasajero debe quedar en WAITING_AT_LANE_QUEUE tras encolar.
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        p = make_passenger(1,2)
        lane.enqueue_passenger(p)
        assert p.state == PassengerState.WAITING_IN_LANE_QUEUE

    def test_enqueue_preserves_fifo_within_group(self):
        """
        El orden dentro de un grupo debe ser FIFO (primero encolado, primero servido).
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        p1 = make_passenger(1,1)
        p2 = make_passenger(2,1)
        lane.enqueue_passenger(p1)
        lane.enqueue_passenger(p2)
        assert lane.passenger_groups[1][0] == p1
        assert lane.passenger_groups[1][1] == p2

class Test_SelectProrityGroup:
    """
    Verifica la seleccion del grupo con mayor tiempo de espara.
    """
    def test_returns_none_when_no_groups(self):
        """
        Sin pasageros debe retornar None
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        assert lane._select_priority_group() is None
    
    def test_returns_only_destination_when_one_group(self):
        """
        Con un solo grupo debe retornar ese destination_id
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        p = make_passenger(1,7)
        lane.enqueue_passenger(p)
        assert lane._select_priority_group() == 7
    
    def test_returns_destination_with_oldest_passenger(self):
        """
        Con dos pasajeros, elige el que tiene el pasajero con menor spawn_time.

        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        # dest=2 tiene pasajero mas antiguo (spawn_time= 1.0)
        # dest=3 tiene pasajero mas reciente (spawn_time = 5.0)
        lane.enqueue_passenger(make_passenger(1,2,spawn_time=1.0))
        lane.enqueue_passenger(make_passenger(2,3,spawn_time=5.0))
        assert lane._select_priority_group() == 2

class Test_AddVehicle:
    """
    Verifica la entrada de VMs al lane y el emparejamiento con grupos de pasajeros.
    """
    def test_vehicle_enters_at_boarding_speed(self):
        """
        El VM debe entrar exactamente a BOARDING_LANE_SPEED
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        vm = FakeVehicle(1)
        lane.add_vehicle(vm)
        assert lane.vehicles[vm.vehicle_id]['velocity'] == pytest.approx(BOARDING_LANE_SPEED)

    def test_vehicle_boards_from_priority_group(self):
        """
        El VM aborda del grupo con el pasajero mas antiguo, no del primer encolado.
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        p_old = make_passenger(1,2,spawn_time=1.0) # mas antiguo
        p_new = make_passenger(2,3,spawn_time=9.0)
        lane.enqueue_passenger(p_old)
        lane.enqueue_passenger(p_new)
        vm = FakeVehicle(1,capacity=1)
        lane.add_vehicle(vm)
        boarded = lane.vehicles[vm.vehicle_id]['passengers']
        assert p_old in boarded

    def test_vehicle_respects_capacity(self):
        """
        VM con capacity=2 aborda exactamente 2 pasageros aunque hay mas.
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        for i in range(4):
            lane.enqueue_passenger(make_passenger(i, destination=1))
        vm = FakeVehicle(1,capacity=2)
        lane.add_vehicle(vm)
        assert len(lane.vehicles[vm.vehicle_id]['passengers']) == 2

    def test_exhausted_group_is_delated(self):
        """
        Si el grupo queda vacio tras el boarding, se elimina del diccionario.
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        lane.enqueue_passenger(make_passenger(1,2))
        vm = FakeVehicle(1,capacity=2)
        lane.add_vehicle(vm)
        lane.add_vehicle(vm)
        assert 2 not in lane.passenger_groups

    def test_partial_group_remains_in_dict(self):
        """
        Si quedan pasajeros en el grupo tras el boarding, el grupo persiste.
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        lane.enqueue_passenger(make_passenger(1,1))
        lane.enqueue_passenger(make_passenger(2,1))
        vm = FakeVehicle(1,capacity=1)
        lane.add_vehicle(vm)
        assert 1 in lane.passenger_groups
        assert len(lane.passenger_groups[1]) == 1

    def test_empty_queue_boards_no_passengers(self):
        """
        Sin pasajeros, el VM entra con lista vacía.
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        vm = FakeVehicle(1,capacity=1)
        lane.add_vehicle(vm)
        assert lane.vehicles[vm.vehicle_id]['passengers'] == []

    def test_boarded_passengers_transition_to_boarding(self):
        """
        Todos los pasajeros abordados deben pasar a estado BOARDING.
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        p1 = make_passenger(1,1)
        p2 = make_passenger(2,1)
        lane.enqueue_passenger(p1)
        lane.enqueue_passenger(p2)
        vm = FakeVehicle(1,capacity=2)
        lane.add_vehicle(vm)
        assert p1.state == PassengerState.BOARDING
        assert p2.state == PassengerState.BOARDING

    def test_leftover_dt_initial_distance(self):
        """
        La distancia inicial debe ser leftover_dt * BOARDING_lANE_SPEED
        """
        lane = BoardingLane(1, Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        vm = FakeVehicle(1)
        lane.add_vehicle(vm, leftover_dt=1.0)
        assert lane.vehicles[vm.vehicle_id]['distance'] == pytest.approx(1.0 * BOARDING_LANE_SPEED)

    def test_boarding_committed_starts_false(self):
        """
        El flag boarding_committed debe iniciar en False.
        """
        lane = BoardingLane(1,Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        vm = FakeVehicle(1)
        lane.add_vehicle(vm)
        assert not lane.vehicles[vm.vehicle_id]['boarding_committed']

class Test_Update:
    """
    Verifica el avance de VMs, el punto de compromiso y el contratro de retorno.
    """                      
    def test_update_advances_distance(self):
        """
        Tras update(1.0), la distancia debe aumentar en exactamente BOARDING_LANE_SPEED.
        """
        lane = BoardingLane(1, Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        vm = FakeVehicle(1)
        lane.add_vehicle(vm)
        lane.update(1.0)
        assert lane.vehicles[vm.vehicle_id]['distance'] == pytest.approx(BOARDING_LANE_SPEED * 1.0)

    def test_commit_triggers_complete_boarding(self):
        """
        Al alcanzar el 50% del recorrido, el pasajero debe pasar a IN_TRANSIT.
        """
        lane = BoardingLane(1, Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        p = make_passenger(1,1)
        lane.enqueue_passenger(p)
        vm = FakeVehicle(1)
        lane.add_vehicle(vm)
        lane.update(2.5)           # 5m a 2m/s = 2.5s para alcanzar el 50%
        assert p.state == PassengerState.IN_TRANSIT

    def test_commit_triggers_for_all_passengers(self):
        """
        Al comprometerse, todos los pasajeros del VM pasan a IN_TRANSIT.
        """
        lane = BoardingLane(1, Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        p1 = make_passenger(1, destination=1)
        p2 = make_passenger(2, destination=1)
        lane.enqueue_passenger(p1)
        lane.enqueue_passenger(p2)
        vm = FakeVehicle(1, capacity=2)
        lane.add_vehicle(vm)
        lane.update(2.5)
        assert p1.state == PassengerState.IN_TRANSIT
        assert p2.state == PassengerState.IN_TRANSIT   

    def test_commit_registers_vehicle_id_on_passengers(self):
        """
        Al comprometerse, cada pasajero registra el vehicle_id correcto.
        """
        lane = BoardingLane(1, Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        p = make_passenger(1,1)
        lane.enqueue_passenger(p)
        vm = FakeVehicle(42)
        lane.add_vehicle(vm)
        lane.update(2.5)
        assert p.vehicle_id == 42

    def test_no_double_commit_on_subsequent_frames(self):
        """
        complete_boarding no debe llamarse dos veces aunque el VM siga en el lane.
        """
        lane = BoardingLane(1, Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        p = make_passenger(1,1)
        lane.enqueue_passenger(p)
        vm = FakeVehicle(1)
        lane.add_vehicle(vm)
        lane.update(2.5)   # commit en frame 1
        lane.update(0.1)   # frame 2: no debe lanzar ValueError 

    def test_completed_vehicle_is_removed(self):
        """
        VM que termina el lane debe ser removido de self.vehicles.
        """
        lane = BoardingLane(1, Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        vm = FakeVehicle(1)
        lane.add_vehicle(vm)
        lane.update(10.0)          # 20m > 10m → completa
        assert vm.vehicle_id not in lane.vehicles

    def test_update_returns_vm_and_correct_leftover(self):
        """
        update() debe retornar (vm, leftover_dt) con el tiempo sobrante exacto.
        """
        lane = BoardingLane(1, Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        vm = FakeVehicle(1)
        lane.add_vehicle(vm)
        # 10m a 2m/s = 5s para completar; dt=7s → leftover=2s
        completed = lane.update(7.0)
        assert len(completed) == 1
        vm_ret, leftover = completed[0]
        assert vm_ret is vm
        assert leftover == pytest.approx(2.0)

    def test_vehicle_without_passengers_completes_correctly(self):
        """
        VM sin pasajeros debe completar el lane sin errores y retornar tupla.
        """
        lane = BoardingLane(1, Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        vm = FakeVehicle(1)
        lane.add_vehicle(vm)
        completed = lane.update(7.0)
        assert len(completed) == 1
        assert completed[0][0] is vm

class Test_RemoveVehicle:
    """
    Verifica la remocion de VMs del lane por vehicle_id.
    """
    def test_remove_decrements_vehicle_count(self):
        """
        Remover un VM debe reducir vehicle_count a 0
        """
        lane = BoardingLane(1, Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        vm = FakeVehicle(1)
        lane.add_vehicle(vm)
        lane.remove_vehicle(vm.vehicle_id)
        assert lane.vehicle_count == 0
    
    def test_removed_vehicle_not_in_dict(self):
        """
        El VM removido no debe aparecer en self.vehicles.
        """
        lane = BoardingLane(1, Vector3(0,0,0), Vector3(10,0,0), NullRecorder())
        vm = FakeVehicle(1)
        lane.add_vehicle(vm)
        lane.remove_vehicle(vm.vehicle_id)
        assert vm.vehicle_id not in lane.vehicles
