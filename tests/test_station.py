"""
Tests para Station

Station es responsable de:
    - Generar pasajeros según tasa de producción (acumulador decimal)
    - Mover pasajeros caminando desde el origen de la estacion hasta la cola del boarding lane
    - Gestionar plataformas activas/inactivas con asignacion round-robin
    - Acumular y exponer demanda de VMs a Brain (La taza puede ser negativa)

Se usa FakeBoardingLane para evitar instanciar el sistema completo. 
"""

import pytest
import sys
import os
import random

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from objects.station import Station, StationDimensions
from objects.passenger_id_generator import PassengerIdGenerator
from objects.math3d import Vector3
from objects.types import AndenState, PassengerState
from telemetry.recorder import NullRecorder
from config.constants import PASSENGER_WALK_SPEED

# ─── STUBS ────────────────────────────────────────────────────────────────

class FakeBoardingLane:
    """
    Stub mínimo de BoardingLane — registra lo que se encola.
    """
    def __init__(self, start_pos: Vector3):
        self.start_pos = start_pos
        self.enqueued: list = []

    def enqueue_passenger(self, passenger):
        """
        Encola pasajeros
        """
        self.enqueued.append(passenger)

def make_platform(lane: FakeBoardingLane, up_tree_id: int = 1, down_tree_id: int = 2) -> dict:
    """
    Stub mínimo de plataforma (dict) para construir una Station en tests.
    La lane que recibe es un FakeBoardingLane; los tree_ids son valores por defecto.
    """
    return {
        'lane':             lane,
        'up_tree_id':       up_tree_id,
        'down_tree_id':     down_tree_id,
        'extraction_point': Vector3(0, 0, 10),
        'discharge_point':  Vector3(0, 0, 10),
    }

def make_station(
    num_platforms: int = 1,
    passenger_rate: float = 0.0,
    vm_request_rate: float = 0.0,
    lane_y_offset: float = 5.0,
    id_generator: PassengerIdGenerator = None,
    recorder = NullRecorder(),
) -> Station:
    """
    Crea una Station con origen en (0,0,0).
    Las boarding lanes están en (0, lane_y_offset, 0).
    passenger_rate=0.0 por defecto para que los tests controlen la generación manualmente.
    """
    # Para test que solo tengan una estacion
    if id_generator is None:
        id_generator = PassengerIdGenerator()
    
    rng = random.Random(42)
    platforms = [
        make_platform(
            FakeBoardingLane(Vector3(0, lane_y_offset, 0)),
            up_tree_id=i * 2 + 1,
            down_tree_id=i * 2 + 2,
        )
        for i in range(num_platforms)
    ]
    return Station(
        station_id=1,
        origin=Vector3(0, 0, 0),
        dimensions=StationDimensions(x_length=20.0, y_length=10.0, floor_height=4.0, num_floors=3),
        passenger_rate =                passenger_rate,
        destination_probabilities =     {2: 1.0},
        vm_request_rate =               vm_request_rate,
        platforms =                     platforms,
        rng =                           rng,
        id_generator =                  id_generator,
        recorder =                      recorder,

    )

# ─── TESTS ────────────────────────────────────────────────────────────────

class Test_Init:
    """
    Test de condiciones iniciales de Station. Creacion de Station, plataformas y dimensiones.
    """
    def test_initial_state(self):
        """
        Station inicia sin pasajeros caminando y todas las plataformas activas.
        """
        station = make_station(num_platforms=2)
        assert len(station._walking) == 0
        assert len(station.get_active_platforms()) == 2

        for a in station._platforms:
            assert a['state'] == AndenState.ACTIVE

    def test_x_e_y_bounds(self):
        """
        Los limites fisicos se calculan correctamente desde el origen.
        Los limites de la estacion fueron definidos con StationDimensions.
        """
        station = make_station()
        assert station.x_bounds == pytest.approx((-10.0, 10.0))
        assert station.y_bounds == pytest.approx((-5.0, 5.0))

class Test_PassengersGeneration:
    """
    Verifica que el acumulador decimal produsca pasajeros correctamente.
    """
    def test_accumulator_spawns_one_passenger(self):
        """
        Con rate=1.0 y dt= 1.0 debe aparecer 1 pasajero en _walking.
        """
        station = make_station(passenger_rate=1.0)
        station.update(dt=1.0, current_time=0.0)
        assert len(station._walking) == 1

    def test_spawned_passenger_state_is_moving_to_lane(self):
        """
        Los pasajeros deben nacer con estado MOVING_TO_LANE.
        """
        station = make_station(passenger_rate=1.0)
        station.update(dt=1.0, current_time=0.0)
        pid = list(station._walking.keys())[0]
        assert station._walking[pid]['passenger'].state == PassengerState.MOVING_TO_LANE

    def test_large_dt_spawns_multiple_passengers(self):
        """
        Un dt de 3.0 con rate=1.0 produce 3 pasajeros en el mismo frame.
        """
        station = make_station(passenger_rate=1.0)
        station.update(dt=3.0, current_time=0.0)
        assert len(station._walking) == 3

    def test_no_spawn_without_active_platforms(self):
        """
        Si no hay plataformas activas, los pasajeros no se generan.
        """
        station = make_station(num_platforms=1, passenger_rate=5.0)
        station.deactivate_platform(0)
        station.update(dt=5.0, current_time=0.0)
        assert len(station._walking) == 0

    def test_passenger_ids_are_unique(self):
        """
        Dos pasageros que se crean simultaneamente no pueden tener el mismo ID.
        """
        station = make_station(passenger_rate=2.0)
        station.update(dt=1.0, current_time=0.0)
        pids = list(station._walking.keys())
        assert pids[0] != pids[1]

    def test_shared_generator_ensures_unique_ids_across_stations(self):
        """
        Si se tienen dos estaciones que producen cada una en el mismo frame un pasajero
        no peuden tener el mimso id
        """
        shared_gen = PassengerIdGenerator()
        station1 = make_station(passenger_rate=1.0, id_generator=shared_gen)
        station2 = make_station(passenger_rate=1.0, id_generator=shared_gen)
        station1.update(dt=1.0, current_time=0.0)
        station2.update(dt=1.0, current_time=0.0)
        pids1 = list(station1._walking.keys())
        pids2 = list(station2._walking.keys())
        assert pids1[0] == 0
        assert pids2[0] == 1

class Test_WalkingPassengers:
    """
    Verifia el movimiento de los pasajeros caminando dentro de la estacion.
    """
    def test_passenger_does_not_arrive_early(self):
        """ 
        En la mitad del tiempo de caminata requerido el pasajero debe continuar camindo.
        """
        station = make_station(lane_y_offset=5.0)
        station.spawn_passenger(current_time=0.0)
        half_time = (5.0 / PASSENGER_WALK_SPEED) / 2.0
        station._advance_walking_passengers(dt=half_time)
        assert len(station._walking) == 1

    def test_passenger_enqueued_after_full_walk(self):
        """
        Despues de que el pasajero camino la distancia total, debe estar encolado en la lane.
        """
        station = make_station(lane_y_offset=5.0)
        station.spawn_passenger(current_time=0.0)
        full_time = 5.0 / PASSENGER_WALK_SPEED + 0.1
        station._advance_walking_passengers(dt=full_time)
        
        lane = station._platforms[0]['lane']
        assert len(lane.enqueued) == 1
        assert len(station._walking) == 0

    def test_passenger_reaches_assigned_lane(self):
        """
        El pasajero se dirige y llega a la estacion que se le asigno.
        """
        station = make_station(num_platforms=2, lane_y_offset=0.0)
        station.spawn_passenger(current_time=0.0)
        station._advance_walking_passengers(dt=1.0)

        assert len(station._platforms[0]['lane'].enqueued) == 1
        assert len(station._platforms[1]['lane'].enqueued) == 0    

class Test_PlatformManagement:
    """
    Verifica acrivacion y desactivacion de plataformas, con round-robin.
    """
    def test_deactivate_reduces_active_count(self):
        """
        Cuando una plataforma es desactivada, ya no aparece en las plataformas activas.
        """
        station = make_station(num_platforms=2)
        station.deactivate_platform(0)
        assert len(station.get_active_platforms()) == 1

    def test_activate_restores_active_count(self):
        """
        Cuando una plataforma se vuelve a activar vuelve a aparecer en las plataformas activas.
        """
        station = make_station(num_platforms=2)
        station.deactivate_platform(0)
        station.activate_platform(0)
        assert len(station.get_active_platforms()) == 2

    def test_deactivate_redirects_walking_passengers(self):
        """
        Pasajeros caminando hacia una plataforma desactivada son redirigidos a la plataforma activa restante.
        """
        station = make_station(num_platforms=2, lane_y_offset=5.0)
        station.spawn_passenger(current_time=0.0)  # round-robin → plataforma 0
        lane_1 = station._platforms[1]['lane']
        station.deactivate_platform(0)
        pid = list(station._walking.keys())[0]
        assert station._walking[pid]['target_lane'] is lane_1

    def test_deactivate_no_redirect_if_no_active_platforms(self):
        """
        Si al desactivar no quedan plataformas activas, los pasajeros conservan su lane original.
        """
        station = make_station(num_platforms=1, lane_y_offset=5.0)
        station.spawn_passenger(current_time=0.0)
        pid = list(station._walking.keys())[0]
        original_lane = station._walking[pid]['target_lane']
        station.deactivate_platform(0)
        assert station._walking[pid]['target_lane'] is original_lane

    def test_redirect_does_not_affect_other_walking_passengers(self):
        """
        Solo se redirigen los pasajeros cuya lane pertenecía a la plataforma cerrada; los demás no se modifican.
        """
        station = make_station(num_platforms=3, lane_y_offset=5.0)
        station.spawn_passenger(current_time=0.0)  # → plataforma 0
        station.spawn_passenger(current_time=0.0)  # → plataforma 1
        pids = list(station._walking.keys())
        lane_1_before = station._walking[pids[1]]['target_lane']
        station.deactivate_platform(0)
        assert station._walking[pids[1]]['target_lane'] is lane_1_before

    def test_round_robin_distributes_evenly(self):
        """
        Dos pasajeros con dos plataformas activas se distribuyen la carga.
        """
        station = make_station(num_platforms=2, lane_y_offset=0.0)
        station.spawn_passenger(current_time=0.0)
        station.spawn_passenger(current_time=0.0)
        station._advance_walking_passengers(dt=1.0)
        assert len(station._platforms[0]['lane'].enqueued) == 1
        assert len(station._platforms[1]['lane'].enqueued) == 1

    def test_active_down_tree_ids_excludes_inactive(self):

        """
        active_down_tree_ids solo incluye árboles de bajada de plataformas activas.
        """
        station = make_station(num_platforms=2)
        station.deactivate_platform(0)
        ids = station.active_down_tree_ids
        assert len(ids) == 1
        assert ids[0] == station._platforms[1]['down_tree_id']

class Test_VmDemand:
    """
    Verifica que el acumulador de demanda y las llamadas a la interfaz de brain
    """
    def test_demand_accumulates_over_time(self):
        """
        rate=1.0 y dt=2.5 deberia generar una taza de 2.
        """
        station = make_station(vm_request_rate=1.0)
        station._accumulate_vm_demand(dt=2.5)
        assert station.pending_demand == 2

    def test_on_commitment_broken_restores(self):
        """
        Un compromiso incumplido debe incrementar nuevamente el acumulador.
        """
        station = make_station(vm_request_rate=1.0)
        station._accumulate_vm_demand(dt=1.0)
        station.on_vm_committed()
        station.on_commitment_broken()
        assert station.pending_demand == 1

    def test_unplanned_vm_can_make_demand_negative(self):
        """
        Un VM que no estaba planeado que llegara a la estacion produce
        taza negativa si no hay acumulado nada en el contador
        """
        station = make_station(vm_request_rate=0.0)
        station.on_unplanned_vm_at_tree()
        assert station._vm_demand_accumulator == pytest.approx(-1.0)
        assert station.pending_demand == -1

