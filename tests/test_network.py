"""
Tests para Network.

Estrategia:
    - FakeTrack para aislar Network de la física de AccelerationTree/BoardingLane.
    - AccelerationTree real para el caso belt_placement (process_transitions
      usa isinstance(source_track, AccelerationTree) para extraer station_id).
    - Junction real para add_junction (requiere AccelerationTree en trees).
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from systems.network import Network
from tracks.base import BaseTrack
from tracks.acceleration_tree import AccelerationTree
from tracks.junction import Junction
from objects.math3d import Vector3
from objects.types import TreeDirection


class FakeVehicle:
    """VM minimo para hacer los tests."""
    def __init__(self, vehicle_id: int):
        self.vehicle_id = vehicle_id

class FakeTrack(BaseTrack):
    """Track mínimo para tests de Network. Devuelve completions predefinidas."""
    def __init__(self, track_id: int, completions: list | None = None):
        super().__init__(track_id, Vector3(), Vector3(0, 0, 1))
        self._completions = completions or []

    def add_vehicle(self, vehicle, entry_velocity=None, leftover_dt=0.0):
        self.vehicles[vehicle.vehicle_id] = {'vehicle': vehicle}

    def remove_vehicle(self, vehicle_id: int):
        self.vehicles.pop(vehicle_id, None)

    def update(self, dt: float) -> list[tuple]:
        return list(self._completions)

def make_down_tree(track_id: int = 1, station_id: int | None = None) -> AccelerationTree:
    return AccelerationTree(
        track_id=track_id,
        start_pos=Vector3(0, 0, 30),
        end_pos=Vector3(0, 0, 0),
        direction=TreeDirection.DOWN,
        base_acceleration=5.0,
        min_vm_separation=2.0,
        station_id=station_id,
    )

def make_junction(junction_id: int = 1, station_id: int = 10,
                  direction: TreeDirection = TreeDirection.UP) -> Junction:
    tree = AccelerationTree(
        track_id=100 + junction_id,
        start_pos=Vector3(0, 0, 0),
        end_pos=Vector3(0, 0, 30),
        direction=direction,
        base_acceleration=5.0,
        min_vm_separation=2.0,
    )
    return Junction(
        junction_id=junction_id,
        belt_x=50.0,
        station_id=station_id,
        direction=direction,
        trees=[tree],
    )


# ─── TOPOLOGÍA ────────────────────────────────────────────────────────────────

class Test_Topology:
    """
    Revisa que la topologia de la red, se genere de manera correcta.
    """
    def test_add_track_registers_it(self):
        """add_track registra el track en self.tracks."""
        net = Network()
        track = FakeTrack(track_id=1)
        net.add_track(track)
        assert net.get_track(1) is track

    def test_add_track_initializes_empty_adjacency(self):
        """add_track crea una lista vacía en adjacency si el track no estaba."""
        net = Network()
        net.add_track(FakeTrack(1))
        assert net.adjacency[1] == []

    def test_add_track_does_not_overwrite_existing_adjacency(self):
        """add_track no pisa la adyacencia si el track ya fue conectado antes."""
        net = Network()
        net.add_track(FakeTrack(1))
        net.add_track(FakeTrack(2))
        net.connect(1, 2)
        net.add_track(FakeTrack(1))  # re-agregar el mismo track
        assert 2 in net.adjacency[1]

    def test_connect_adds_directed_edge(self):
        """connect(1, 2) registra 2 en adjacency[1]."""
        net = Network()
        net.add_track(FakeTrack(1))
        net.add_track(FakeTrack(2))
        net.connect(1, 2)
        assert net.adjacency[1] == [2]

    def test_connect_raises_if_from_not_registered(self):
        """connect lanza ValueError si el track origen no está en self.tracks."""
        net = Network()
        net.add_track(FakeTrack(2))
        with pytest.raises(ValueError):
            net.connect(1, 2)

    def test_connect_raises_if_to_not_registered(self):
        """connect lanza ValueError si el track destino no está en self.tracks."""
        net = Network()
        net.add_track(FakeTrack(1))
        with pytest.raises(ValueError):
            net.connect(1, 2)

    def test_connect_is_idempotent(self):
        """Conectar el mismo par dos veces no duplica la arista."""
        net = Network()
        net.add_track(FakeTrack(1))
        net.add_track(FakeTrack(2))
        net.connect(1, 2)
        net.connect(1, 2)
        assert net.adjacency[1].count(2) == 1

    def test_add_junction_up_keyed_by_station_id(self):
        """add_junction UP guarda la junction bajo su station_id."""
        net = Network()
        j = make_junction(junction_id=1, station_id=10, direction=TreeDirection.UP)
        net.add_junction(j)
        assert net.get_junction_up(10) is j

    def test_add_junction_down_keyed_by_station_id(self):
        """add_junction DOWN guarda la junction bajo su station_id."""
        net = Network()
        j = make_junction(junction_id=2, station_id=10, direction=TreeDirection.DOWN)
        net.add_junction(j)
        assert net.get_junction_down(10) is j

    def test_add_junction_does_not_enter_adjacency(self):
        """Las Junctions no son tracks de tránsito: no aparecen en adjacency."""
        net = Network()
        j = make_junction(station_id=10)
        net.add_junction(j)
        assert j.junction_id not in net.adjacency
        assert j.station_id not in net.adjacency

# ─── UPDATE ALL TRACKS ────────────────────────────────────────────────────────

class Test_UpdateAllTracks:
    """
    Revisa update se este implementado bien a lo largo de Network
    """
    def test_returns_empty_when_no_completions(self):
        """Sin VMs que completen, retorna lista vacía."""
        net = Network()
        net.add_track(FakeTrack(1))
        assert net.update_all_tracks(dt=0.1) == []

    def test_collects_completion_from_track(self):
        """update_all_tracks recolecta (vm, track_id, leftover) de un track."""
        vm = FakeVehicle(1)
        track = FakeTrack(1, completions=[(vm, 0.05)])
        net = Network()
        net.add_track(track)
        result = net.update_all_tracks(dt=0.1)
        assert len(result) == 1
        got_vm, got_track_id, got_leftover = result[0]
        assert got_vm is vm
        assert got_track_id == 1
        assert got_leftover == pytest.approx(0.05)

    def test_collects_from_multiple_tracks(self):
        """Recolecta completions de todos los tracks en la red."""
        vm1 = FakeVehicle(1)
        vm2 = FakeVehicle(2)
        net = Network()
        net.add_track(FakeTrack(1, completions=[(vm1, 0.0)]))
        net.add_track(FakeTrack(2, completions=[(vm2, 0.0)]))
        result = net.update_all_tracks(dt=0.1)
        assert len(result) == 2

    def test_does_not_transfer_vms(self):
        """update_all_tracks solo recolecta — no transfiere VMs entre tracks."""
        vm = FakeVehicle(1)
        track_a = FakeTrack(1, completions=[(vm, 0.0)])
        track_b = FakeTrack(2)
        net = Network()
        net.add_track(track_a)
        net.add_track(track_b)
        net.connect(1, 2)
        net.update_all_tracks(dt=0.1)
        assert track_b.vehicle_count == 0

# ─── PROCESS TRANSITIONS ──────────────────────────────────────────────────────

class Test_ProcessTransitions:
    def test_mechanical_transition_transfers_vm(self):
        """len==1 → Network transfiere el VM al único track siguiente."""
        vm = FakeVehicle(1)
        track_a = FakeTrack(1)
        track_b = FakeTrack(2)
        net = Network()
        net.add_track(track_a)
        net.add_track(track_b)
        net.connect(1, 2)

        decisions, belt = net.process_transitions([(vm, 1, 0.0)])
        assert decisions == []
        assert belt == []
        assert vm.vehicle_id in track_b.vehicles

    def test_mechanical_transition_passes_leftover(self):
        """La transición mecánica pasa leftover_dt a add_vehicle del track destino."""
        vm = FakeVehicle(1)
        received = {}

        class TrackCapture(FakeTrack):
            def add_vehicle(self, vehicle, entry_velocity=None, leftover_dt=0.0):
                received['leftover'] = leftover_dt
                super().add_vehicle(vehicle, entry_velocity, leftover_dt)

        track_a = FakeTrack(1)
        track_b = TrackCapture(2)
        net = Network()
        net.add_track(track_a)
        net.add_track(track_b)
        net.connect(1, 2)

        net.process_transitions([(vm, 1, 0.07)])
        assert received['leftover'] == pytest.approx(0.07)

    def test_decision_case_does_not_transfer(self):
        """len>1 → VM va a decisions, no se transfiere a ningún track."""
        vm = FakeVehicle(1)
        track_a = FakeTrack(1)
        track_b = FakeTrack(2)
        track_c = FakeTrack(3)
        net = Network()
        net.add_track(track_a)
        net.add_track(track_b)
        net.add_track(track_c)
        net.connect(1, 2)
        net.connect(1, 3)

        decisions, belt = net.process_transitions([(vm, 1, 0.5)])
        assert len(decisions) == 1
        assert belt == []
        got_vm, next_ids, leftover = decisions[0]
        assert got_vm is vm
        assert set(next_ids) == {2, 3}
        assert leftover == pytest.approx(0.5)
        # No se transfirió
        assert track_b.vehicle_count == 0
        assert track_c.vehicle_count == 0

    def test_belt_placement_with_station_id(self):
        """len==0 con AccelerationTree → belt_placements incluye station_id correcto."""
        vm = FakeVehicle(1)
        down_tree = make_down_tree(track_id=1, station_id=42)
        net = Network()
        net.add_track(down_tree)  # sin connect → adjacency[1] = []

        decisions, belt = net.process_transitions([(vm, 1, 0.1)])
        assert decisions == []
        assert len(belt) == 1
        got_vm, leftover, station_id = belt[0]
        assert got_vm is vm
        assert leftover == pytest.approx(0.1)
        assert station_id == 42

    def test_belt_placement_without_station_id(self):
        """len==0 con FakeTrack (no AccelerationTree) → station_id es None."""
        vm = FakeVehicle(1)
        track = FakeTrack(1)
        net = Network()
        net.add_track(track)  # sin connect → terminal

        _, belt = net.process_transitions([(vm, 1, 0.0)])
        assert len(belt) == 1
        _, _, station_id = belt[0]
        assert station_id is None

    def test_mixed_completions_routed_correctly(self):
        """Tres VMs con distintos grados de adyacencia → tres caminos distintos."""
        vm_mech = FakeVehicle(1)
        vm_dec = FakeVehicle(2)
        vm_belt = FakeVehicle(3)

        track_a = FakeTrack(1)      # → track_b (mechanical)
        track_b = FakeTrack(2)
        track_c = FakeTrack(3)      # → track_d y track_e (decision)
        track_d = FakeTrack(4)
        track_e = FakeTrack(5)
        down_tree = make_down_tree(track_id=6, station_id=99)  # terminal

        net = Network()
        for t in [track_a, track_b, track_c, track_d, track_e, down_tree]:
            net.add_track(t)
        net.connect(1, 2)
        net.connect(3, 4)
        net.connect(3, 5)

        completions = [(vm_mech, 1, 0.0), (vm_dec, 3, 0.0), (vm_belt, 6, 0.0)]
        decisions, belt = net.process_transitions(completions)

        assert vm_mech.vehicle_id in track_b.vehicles
        assert len(decisions) == 1 and decisions[0][0] is vm_dec
        assert len(belt) == 1 and belt[0][0] is vm_belt and belt[0][2] == 99

# ─── CONSULTAS ────────────────────────────────────────────────────────────────

class Test_Queries:
    """
    Test de los puntos que expone Network hacia los demas.
    """
    def test_get_junction_up_returns_junction(self):
        net = Network()
        j = make_junction(station_id=5, direction=TreeDirection.UP)
        net.add_junction(j)
        assert net.get_junction_up(5) is j

    def test_get_junction_up_returns_none_for_unknown(self):
        net = Network()
        assert net.get_junction_up(999) is None

    def test_get_junction_down_returns_junction(self):
        net = Network()
        j = make_junction(station_id=5, direction=TreeDirection.DOWN)
        net.add_junction(j)
        assert net.get_junction_down(5) is j

    def test_get_junction_down_returns_none_for_unknown(self):
        net = Network()
        assert net.get_junction_down(999) is None

    def test_get_track_returns_track(self):
        net = Network()
        track = FakeTrack(7)
        net.add_track(track)
        assert net.get_track(7) is track

    def test_get_track_returns_none_for_unknown(self):
        net = Network()
        assert net.get_track(999) is None

    def test_get_all_station_ids_union_of_both_junctions(self):
        """Retorna union de IDs de junctions UP y DOWN registradas."""
        net = Network()
        net.add_junction(make_junction(junction_id=1, station_id=1, direction=TreeDirection.UP))
        net.add_junction(make_junction(junction_id=2, station_id=2, direction=TreeDirection.DOWN))
        net.add_junction(make_junction(junction_id=3, station_id=1, direction=TreeDirection.DOWN))
        ids = net.get_all_station_ids()
        assert set(ids) == {1, 2}

    def test_get_all_station_ids_empty_when_no_junctions(self):
        net = Network()
        assert net.get_all_station_ids() == []

    def test_total_vehicle_count_sums_all_tracks(self):
        """total_vehicle_count suma los VMs de todos los tracks."""
        vm1 = FakeVehicle(1)
        vm2 = FakeVehicle(2)
        track_a = FakeTrack(1)
        track_b = FakeTrack(2)
        net = Network()
        net.add_track(track_a)
        net.add_track(track_b)
        track_a.add_vehicle(vm1)
        track_b.add_vehicle(vm2)
        assert net.total_vehicle_count == 2

    def test_total_vehicle_count_zero_when_empty(self):
        net = Network()
        net.add_track(FakeTrack(1))
        assert net.total_vehicle_count == 0









# Preguntas de los test de network:
# Pregunta 1:
# por que no se decidio que juntion tambien tenga un typos al igual que acceleration tree, que pueda
# ser UP o DOWN, se que dependen de los arboles pero no entiendo por que se tomo la decicion de que no
# tenga typos
# 
# Pregunta 2:
# no entendi el test test_mechanical_transition_passes_leftover, puedes explicarmelo, es especialemte
# raro por que tiene una clase pequeña dentro que la verdad es que no se que hace y por que se define
# adentro
# 
# Pregunta 3:
# no entendi muy bien los test que tenian que ver con adjncy, entiendo que es un vertice entre dos traks
# pero no se como se esta implementando en verdad. feliz si podemos ahcer un repaso pero por sobre todo 
# por como se esta implementando en los tests de topologia
# 
# Pregunta 4:
# tengo una pregunta, estoy viendo en la red que se pueden conectar varios traks a uno (1 a muchos) el
# unico caso que se me ocurre que puede pasar eso (por ahora) es en uan junction, lo que no entiendo es
# como esta juntion evaluando esto si esta metido o si en realidad no, solo esta estorbando o sobrando
# lo estoy viendo en el test decision caso does not transfer
# 
# Pregunta 5:
# He notado que esta como sobre complicado todo, no se si esto es orden o es que en verdad esta complicada
# de entender network, quiero saber que opinas pero me esta costando entender los tests
# 
# Preunta 6:
# con este test puedo asumir que para Network las stationes son invisibles 
# test_get_all_station_ids_empty_when_no_junctions eso esta bien o es un error, me causa duda principalmente
# por lo que te comentaba de que me hace rudio por como se esta manejando una junciton sin junciton o no se si
# lo estoy interpretnado mal yo
# 
