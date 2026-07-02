"""
Tests para station_factory.py

- Test_LaneYOffsets: función pura — valores exactos verificados a mano
- Test_CreateStation: integración — tipos, conteos, IDs únicos, geometría invariante
- Test_ConnectStationToNetwork: registra correctamente en Network

Fixture: dz = TREE_DZ (física, ya no configurable) ≈ 20.20
    Para N=3 (y_ext=5): dx_ext=sqrt(400²-25-20.20²)≈399.46 → geometría válida.
"""

import pytest
import math
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


from objects.math3d import Vector3
from objects.station import Station
from objects.passenger_id_generator import PassengerIdGenerator
from objects.types import TreeDirection
from tracks.junction import Junction
from systems.network import Network
from simulation.station_factory import (
    TrackIdAllocator,
    create_station,
    connect_station_to_network,
    _lane_y_offsets,
)
from config.constants import TREE_LENGTH, TREE_DZ, STATION_X_LENGTH, STATION_Y_LENGTH

# ─── FIXTURES ────────────────────────────────────────────────────────────────

ORIGIN = Vector3(100.0, 0.0, 0.0)
EXPECTED_JUNCTION_DEPTH = ORIGIN.z - TREE_DZ   # junction_depth que create_station calcula internamente

def make_components(num_lanes: int = 1, station_id: int = 1):
    alloc   = TrackIdAllocator(start=1)
    rng     = random.Random(42)
    pid_gen = PassengerIdGenerator()
    return create_station(
        station_id                 = station_id,
        station_origin             = ORIGIN,
        num_lanes                  = num_lanes,
        passenger_rate             = 0.0,
        destination_probabilities  = {2: 1.0},
        vm_request_rate            = 0.0,
        rng                        = rng,
        id_generator               = pid_gen,
        id_alloc                   = alloc,
    )

# ─── TEST CLASES ─────────────────────────────────────────────────────────────

class Test_LaneYOffsets:
    """
    Logica de andenes y offsets
    """
    def test_one_lane_returns_zero(self):
        """Si hay una lane se posiciona en el centro"""
        assert _lane_y_offsets(1, 20.0) == [0.0]

    def test_raises_on_zero_lanes(self):
        """Si no hay lanes en una estacion ValueError"""
        with pytest.raises(ValueError):
            _lane_y_offsets(0, 20.0)

    def test_three_lanes_symmetric(self):
        """Verifiacion de orden de las lanes en la estacion"""
        assert _lane_y_offsets(3, 20.0) == pytest.approx([-5.0, 0.0, 5.0])

    def test_five_lanes_symmetric(self):
        """Verifiacion de orden de las lanes en la estacion"""
        assert _lane_y_offsets(5, 20.0) == pytest.approx([-20/3, -10/3, 0.0, 10/3, 20/3])

    def test_two_lanes_has_central_and_one(self):
        """Verifica que si tenemos 2 lanes en una estacion halla una central y otra al costado"""
        result = _lane_y_offsets(2, 20.0)
        assert len(result) == 2
        assert any(abs(y) < 1e-9 for y in result)   # hay lane central en 0

    def test_central_lane_always_zero(self):
        """Verificacion de varias convinaciones de lanes en estacion para vereificar el orden"""
        for n in range(1, 7):
            offsets = _lane_y_offsets(n, 20.0)
            assert any(abs(y) < 1e-9 for y in offsets), f"Sin lane central para N={n}"

    def test_lanes_never_reach_border(self):
        """
        Nunca una lane va a estar en el offest borde de la estacion
        Siempre deja un margen
        """
        for n in range(1, 8):
            offsets = _lane_y_offsets(n, 20.0)
            assert all(abs(y) < 10.0 for y in offsets), f"Lane fuera de borde para N={n}"

    def test_result_is_sorted(self):
        """Offset siempre salen ordenados de menor a mayor"""
        for n in range(1, 6):
            offsets = _lane_y_offsets(n, 20.0)
            assert offsets == sorted(offsets)

    def test_count_matches_num_lanes(self):
        """Verifica que si tenemos n andenes tenemos n offset"""
        for n in range(1, 6):
            assert len(_lane_y_offsets(n, 20.0)) == n

class Test_CreateStation:

    def test_returns_station_instance(self):
        """El primer elemento de la tupla es una instancia de Station"""
        station, *_ = make_components()
        assert isinstance(station, Station)

    def test_returns_correct_list_lengths(self):
        """
        Verifica que con N=3, los tres listados (up_trees, lanes, dn_trees)
        tienen exactamente 3 elementos cada uno.
        """
        _, up_trees, lanes, dn_trees, _, _ = make_components(num_lanes=3)
        assert len(up_trees) == 3
        assert len(lanes) == 3
        assert len(dn_trees) == 3

    def test_returns_junction_instances(self):
        """
        Verifica que el quinto y el sexto elemento de la tupla
        sean instancias de juntion
        """
        _, _, _, _, j_up, j_down = make_components()
        assert isinstance(j_up, Junction)
        assert isinstance(j_down, Junction)

    def test_all_ids_unique(self):
        """
        Verifica que ningún track comparte ID con otro track 
        ni con las junctions de la misma estación.
        """
        _, up_trees, lanes, dn_trees, j_up, j_down = make_components(num_lanes=3)
        ids = (
            [t.track_id for t in up_trees + lanes + dn_trees]
            + [j_up.junction_id, j_down.junction_id]
        )
        assert len(ids) == len(set(ids))

    def test_up_trees_have_no_station_id(self):
        """ 
        Verifica que los arboles de subida tienen station_id=None
        por que no es nesesario este atribuito para la operacion
        """
        _, up_trees, _, _, _, _ = make_components(num_lanes=2)
        for tree in up_trees:
            assert tree.station_id is None

    def test_down_trees_have_station_id(self):
        """
        Verifica quelos árboles de bajada tienen el station_id 
        de su estación porque son el destino de llegada.
        """
        _, _, _, dn_trees, _, _ = make_components(num_lanes=2, station_id=7)
        for tree in dn_trees:
            assert tree.station_id == 7

    def test_station_platform_count(self):
        """
        Station tiene tantas plataformas activas como andenes pedidos en num_lanes.
        """
        station, _, _, _, _, _ = make_components(num_lanes=3)
        assert len(station.get_active_platforms()) == 3

    def test_junction_up_is_left_of_station(self):
        """
        Verifica que la junction UP queda a la 
        izquierda del centro de la estación en el eje X.
        """
        _, _, _, _, j_up, _ = make_components()
        assert j_up.belt_x < ORIGIN.x

    def test_junction_down_is_right_of_station(self):
        """
        verifica que la junction DOWN queda a la
        derecha del centro de la estación en el eje X.
        """
        _, _, _, _, _, j_down = make_components()
        assert j_down.belt_x > ORIGIN.x

    def test_junction_directions(self):
        """
        junction_up tiene dirección UP y junction_down tiene dirección DOWN.
        """
        _, _, _, _, j_up, j_down = make_components()
        assert j_up.direction == TreeDirection.UP
        assert j_down.direction == TreeDirection.DOWN

    def test_shared_allocator_no_id_collision(self):
        """Dos estaciones con el mismo allocator no comparten IDs."""
        alloc   = TrackIdAllocator(start=1)
        rng     = random.Random(42)
        pid_gen = PassengerIdGenerator()
        kwargs  = dict(
            station_origin            = ORIGIN,
            num_lanes                 = 2,
            passenger_rate            = 0.0,
            destination_probabilities = {2: 1.0},
            vm_request_rate           = 0.0,
            rng                       = rng,
            id_generator              = pid_gen,
            id_alloc                  = alloc,
        )
        _, up1, l1, dn1, ju1, jd1 = create_station(station_id=1, **kwargs)
        _, up2, l2, dn2, ju2, jd2 = create_station(station_id=2, **kwargs)

        ids1 = {t.track_id for t in up1+l1+dn1} | {ju1.junction_id, jd1.junction_id}
        ids2 = {t.track_id for t in up2+l2+dn2} | {ju2.junction_id, jd2.junction_id}
        assert ids1.isdisjoint(ids2)

class Test_ConnectStationToNetwork:

    def test_all_tracks_registered(self):
        """
        Verifica que después de conectar, Network contiene num_lanes
        × 3 tracks (up + lane + down por andén).
        """
        _, up_trees, lanes, dn_trees, j_up, j_down = make_components(num_lanes=2)
        network = Network()
        connect_station_to_network(network, up_trees, lanes, dn_trees, j_up, j_down)
        assert len(network.tracks) == 6   # 2×(up + lane + down)

    def test_junctions_registered_by_station_id(self):
        """
        verifica que Network registra junction_up en junctions_up[station_id] 
        y junction_down en junctions_down[station_id].
        """
        _, up_trees, lanes, dn_trees, j_up, j_down = make_components(station_id=1)
        network = Network()
        connect_station_to_network(network, up_trees, lanes, dn_trees, j_up, j_down)
        assert network.junctions_up[1] is j_up
        assert network.junctions_down[1] is j_down

    def test_chain_in_adjacency(self):
        """up_tree → lane → down_tree; down_tree es terminal (adyacencia vacía)."""
        _, up_trees, lanes, dn_trees, j_up, j_down = make_components(num_lanes=2)
        network = Network()
        connect_station_to_network(network, up_trees, lanes, dn_trees, j_up, j_down)
        for up, lane, down in zip(up_trees, lanes, dn_trees):
            assert lane.track_id in network.adjacency[up.track_id]
            assert down.track_id in network.adjacency[lane.track_id]
            assert network.adjacency.get(down.track_id, []) == []

    def test_star_unpack_pattern(self):
        """Verifica que station, *rest = create_station(...) funciona con connect_station_to_network."""
        alloc   = TrackIdAllocator(start=1)
        rng     = random.Random(42)
        pid_gen = PassengerIdGenerator()
        station, *rest = create_station(
            station_id                = 1,
            station_origin            = ORIGIN,
            num_lanes                 = 1,
            passenger_rate            = 0.0,
            destination_probabilities = {2: 1.0},
            vm_request_rate           = 0.0,
            rng                       = rng,
            id_generator              = pid_gen,
            id_alloc                  = alloc,
        )
        network = Network()
        connect_station_to_network(network, *rest)
        assert len(network.tracks) == 3   # up + lane + down

class Test_Geometry:
    """Verifica posiciones 3D exactas de junctions, extracción y descarga."""

    def test_all_trees_equal_length_euclidean(self):
        """Distancia euclidiana calculada manualmente entre start y end de cada árbol = TREE_LENGTH."""
        _, up_trees, _, dn_trees, _, _ = make_components(num_lanes=3)
        for tree in up_trees + dn_trees:
            d = math.sqrt(
                (tree.end_pos.x - tree.start_pos.x) ** 2 +
                (tree.end_pos.y - tree.start_pos.y) ** 2 +
                (tree.end_pos.z - tree.start_pos.z) ** 2
            )
            assert d == pytest.approx(TREE_LENGTH, abs=1e-6)

    def test_junction_z_equals_junction_depth(self):
        """Los árboles UP parten desde la profundidad correcta del belt (eje Z)."""
        _, up_trees, _, _, _, _ = make_components(num_lanes=3)
        for tree in up_trees:
            assert tree.start_pos.z == pytest.approx(EXPECTED_JUNCTION_DEPTH)

    def test_junction_y_equals_station_origin_y(self):
        """La junction queda justo debajo del centro de la estación en Y."""
        _, up_trees, _, dn_trees, _, _ = make_components(num_lanes=3)
        for tree in up_trees:
            assert tree.start_pos.y == pytest.approx(ORIGIN.y)
        for tree in dn_trees:
            assert tree.end_pos.y == pytest.approx(ORIGIN.y)

    def test_extraction_z_is_floor_height(self):
        """Todos los puntos de extracción (fin del UP tree) están en el piso de la estación."""
        _, up_trees, _, _, _, _ = make_components(num_lanes=3)
        for tree in up_trees:
            assert tree.end_pos.z == pytest.approx(ORIGIN.z)

    def test_discharge_z_is_floor_height(self):
        """Todos los puntos de descarga (inicio del DOWN tree) están en el piso de la estación."""
        _, _, _, dn_trees, _, _ = make_components(num_lanes=3)
        for tree in dn_trees:
            assert tree.start_pos.z == pytest.approx(ORIGIN.z)

    def test_belt_x_symmetric_around_station_center(self):
        """junction_up y junction_down son equidistantes del centro X de la estación."""
        _, _, _, _, j_up, j_down = make_components(num_lanes=3)
        mid = (j_up.belt_x + j_down.belt_x) / 2.0
        assert mid == pytest.approx(ORIGIN.x)

    def test_belt_x_exact_value(self):
        """belt_x_up coincide con el valor calculado manualmente con la fórmula geométrica."""
        dz     = TREE_DZ
        y_ext  = max(abs(y) for y in _lane_y_offsets(3, STATION_Y_LENGTH))
        dx_ext = math.sqrt(TREE_LENGTH**2 - y_ext**2 - dz**2)
        expected_belt_x_up = ORIGIN.x - STATION_X_LENGTH / 2.0 - dx_ext
        _, _, _, _, j_up, _ = make_components(num_lanes=3)
        assert j_up.belt_x == pytest.approx(expected_belt_x_up)

    def test_inner_lane_extraction_x_more_interior_than_outer(self):
        """El andén central (y=0) comienza más adentro en X que el andén externo."""
        _, up_trees, _, dn_trees, _, _ = make_components(num_lanes=3)
        # up_trees ordenados por y_offset: [y=-5, y=0, y=+5]
        assert up_trees[1].end_pos.x > up_trees[0].end_pos.x     # central UP: X más interior (derecha)
        assert dn_trees[1].start_pos.x < dn_trees[0].start_pos.x  # central DOWN: X más interior (izquierda)

    def test_extraction_y_is_origin_y_plus_offset(self):
        """Con origin.y != 0, el Y de extracción es station_origin.y + y_i — no solo y_i."""
        alloc   = TrackIdAllocator(start=1)
        rng     = random.Random(42)
        pid_gen = PassengerIdGenerator()
        origin_y = 3.0
        _, up_trees, _, _, _, _ = create_station(
            station_id=1,
            station_origin=Vector3(100.0, origin_y, 0.0),
            num_lanes=3,
            passenger_rate=0.0,
            destination_probabilities={2: 1.0},
            vm_request_rate=0.0,
            rng=rng,
            id_generator=pid_gen,
            id_alloc=alloc,
        )
        for tree, y_i in zip(up_trees, _lane_y_offsets(3, STATION_Y_LENGTH)):
            assert tree.end_pos.y == pytest.approx(origin_y + y_i)

    def test_lane_endpoints_match_tree_endpoints(self):
        """El inicio de la lane coincide con el fin del UP tree; el fin de la lane con el inicio del DOWN tree."""
        _, up_trees, lanes, dn_trees, _, _ = make_components(num_lanes=3)
        for up, lane, dn in zip(up_trees, lanes, dn_trees):
            assert lane.start_pos.x == pytest.approx(up.end_pos.x)
            assert lane.start_pos.y == pytest.approx(up.end_pos.y)
            assert lane.start_pos.z == pytest.approx(up.end_pos.z)
            assert lane.end_pos.x == pytest.approx(dn.start_pos.x)
            assert lane.end_pos.y == pytest.approx(dn.start_pos.y)
            assert lane.end_pos.z == pytest.approx(dn.start_pos.z)

