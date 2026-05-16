"""
Test para BaseTrack

BaseTrack es una clase abstracta - no se puede instanciar directamente
Se usa MinimalTrack para implementacion correcta minima solo para porbar
el comportamiento de BaseTrack YA devine (geometric, get_progress, etc.).
Aca no se testean las subclases.

Descion de diseño que se verifica
    - self.vehicles guarda 'distance' (metros) NO 'progress'
    - get_progress() es concreto y deriva progress = distance / length
    - 'velocity' siempre presetne en el dict estandar
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tracks.base import BaseTrack
from objects.math3d import Vector3

# CLASES MINIMAS PARA TESTS

class MinimalTrack(BaseTrack):
    """
    Subclase minima de BaseTrack para testear su comportamiento compartido.
    Fisica trivial: Velocidad constante (por ahora). sin logica adicional
    """

    SPEED = 5.0 # m/s

    def add_vehicle(self, vehicle, entry_velocity: float |None = None, leftover_dt: float = 0.0):
        """
        Agrega un VM al track, inicialisando su entrada.
        """
        velocity = entry_velocity if entry_velocity is not None else self.SPEED
        initial_distance = velocity * leftover_dt
        self.vehicles[vehicle.vehicle_id] = {
            'vehicle': vehicle,
            'distance': initial_distance,
            'velocity': velocity,
        }

    def remove_vehicle(self, vehicle_id: int):
        del self.vehicles[vehicle_id]

    def update(self, dt):
        completed = []
        for vehicle_id, data in list(self.vehicles.items()):
            data['distance']+= data['velocity'] * dt
            if data['distance'] >= self.length:
                completed.append(data['vehicle'])
        for vm in completed:
            self.remove_vehicle(vm.vehicle_id)
        return completed

class FakeVehicle:
    """
    Stub minimo de ModularVehicle para test de track.
    """
    def __init__(self, vehicle_id: int):
        self.vehicle_id = vehicle_id

# Tests
class Test_init:
    """
    Test de la inicialisacion de los tracks
    """
    def test_horizontal_lenght(self):
        """
        Segmento horizonatl de 10 m en X.
        """
        track = MinimalTrack(track_id=1, start_pos=Vector3(0,0,0), end_pos=Vector3(10,0,0))
        assert track.length == pytest.approx(10.0)

    def test_diagonal_lenght(self):
        """
        Testeo de un segmento diagonal
        Triángulo 3-4-5: longitud debe ser 5m.
        (componentes en x e y)
        """
        track = MinimalTrack(track_id=1, start_pos=Vector3(0,0,0), end_pos=Vector3(3.0,4.0,0))
        assert track.length == pytest.approx(5.0)
    
    def test_vertical_length_acceleration_tree(self):
        """
        Segmento que sube en Z - Caso tipico de AccelerationTree.
        """
        track = MinimalTrack(track_id=1, start_pos=Vector3(5.0,0,0), end_pos=Vector3(5.0,0,20.0))
        assert track.length == pytest.approx(20.0)

    def test_vehicles_start_empty(self):
        """
        Confirma que el track inicia vacio.
        """
        track = MinimalTrack(1, Vector3(0,0,0), Vector3(10,0,0))
        assert track.vehicle_count == 0
        assert track.get_vehicles() == []

# Class comparativa con version anterior
class Test_distanceDesign:
    """
    Guarda de regresión: el dict usa 'distance' (metros), no 'progress' (normalizado).
    Esto previene acumulación de error de punto flotante por divisiones repetidas cada frame.

    Este es el cambio de diseño clave respecto a la version anterior.
    """

    def test_dict_stores_distance_not_progress(self):
        """
        El dict anterno debe tener 'distance', no 'progress'.
        """
        track = MinimalTrack(1, Vector3(0,0,0), Vector3(10,0,0))
        vm = FakeVehicle(1)
        track.add_vehicle(vm)
        
        data = track.vehicles[vm.vehicle_id]

        assert 'distance' in data
        assert 'progress' not in data # nuevo diseño

    def test_dict_time_velocity(self):
        """
        'velocity' debe estar siempre presente, incluso en tracks de velocidad constante.
        """
        track = MinimalTrack(1, Vector3(0,0,0), Vector3(10,0,0))
        vm = FakeVehicle(1)
        track.add_vehicle(vm)

        data = track.vehicles[vm.vehicle_id]
        assert 'velocity' in data

    def test_initial_distance_whithout_leftover_dt(self):
        """
        Un VM recien agregado con leftover_dt no puede ser cero
        """
        track = MinimalTrack(1, Vector3(0,0,0), Vector3(10,0,0))
        vm = FakeVehicle(1)
        track.add_vehicle(vm, entry_velocity=12.5)

        assert track.vehicles[vm.vehicle_id]['velocity'] == pytest.approx(12.5)

class Test_getProgress:
    """
    get_progress() es CONCRETO en BaseTrack
    Verifica que derive correctamtne de distance / length.
    """

    def test_progress_inicial_es_cero(self):
        """
        Verifica que tras agregar un vm este con un progress 0.0
        """
        track = MinimalTrack(1, Vector3(0,0,0), Vector3(10,0,0))
        vm = FakeVehicle(1)
        track.add_vehicle(vm)
        assert track.get_progress(vm) == pytest.approx(0.0)

    def test_progress_con_leftover_dt(self):
        """
        Verifica que al agregar un vm con leftover, entra con x metros ya recorridos
        """
        track = MinimalTrack(1,Vector3(0,0,0), Vector3(10,0,0))
        vm = FakeVehicle(1)
        track.add_vehicle(vm, leftover_dt=5.0) # Entra con 5 metros ya recorridos
        assert track.get_progress(vm) == pytest.approx(2.5)

class Test_geometria:
    """
    Test para comprobar que se entregeuen correctamente las posiciones 3D de los objetos
    Recordar que la el progreso de un track solo est utilizada para mostrar la posicion 3D
    """
    def test_psition_at_start(self):
        """
        Caso inicial, () -> start_pos
        """
        track = MinimalTrack(1, Vector3(0,0,0), Vector3(10,0,0))
        pos = track.position_at_progress(0.0)
        assert pos.x == pytest.approx(0.0)
    
    def test_position_at_end(self):
        """
        Caso final, end_pos -> end_pos
        """
        track = MinimalTrack(1, Vector3(0,0,0), Vector3(10,0,0))
        pos = track.position_at_progress(1.0)
        assert pos.x == pytest.approx(10.0)
    
    def test_psitiona_at_midponit(self):
        """
        Caso medio (debe retornar 'progress'=0.5 en el punto medio)
        """
        track = MinimalTrack(1, Vector3(0,0,0), Vector3(10,0,0))
        pos = track.position_at_progress(0.5)
        assert pos.x == pytest.approx(5.0)
    
    def test_direction_is_unit_vector(self):
        """
        Comprueba funcion direcion_vector
        como es unitario la suma de sus partes siempre debe ser secano a 1
        """
        track = MinimalTrack(1, Vector3(0,0,0), Vector3(10,0,0))
        assert track.direction_vector() == pytest.approx(Vector3(1,0,0))

    def test_direction_vector_horizontal(self):
        """
        Testeo de la funion direction_vector()
        Demuestra en que direccion se debe mover el vm
        """
        track = MinimalTrack(1, Vector3(0,0,0), Vector3(10,0,0))
        d = track.direction_vector()
        assert d.x == pytest.approx(1.0)
        assert d.y == pytest.approx(0.0)
        assert d.z == pytest.approx(0.0)


class Test_gestion_vehicles:
    """
    Verifica el ciclo de vida de VMs: agregar, remover, completar el track.
    """
    def test_remove_vehicle(self):
        """
        Test de remove_vehicle()
        """
        track = MinimalTrack(1, Vector3(0,0,0), Vector3(10,0,0))
        vm = FakeVehicle(1)
        track.add_vehicle(vm)
        track.remove_vehicle(vm.vehicle_id)
        assert track.vehicle_count == 0
        assert vm not in track.get_vehicles()

    def test_update_returns_completed_with_leftover(self):
        """
        update() debe retornar lista de tuplas (vm, leftover_dt).
        leftover_dt es el tiempo sobrante del frame que el VM debe usar en el siguiente track.
        """
        track = MinimalTrack(1, Vector3(0,0,0), Vector3(10,0,0))
        vm = FakeVehicle(1)
        track.add_vehicle(vm, entry_velocity=10.0)
        completados = track.update(2.0)                 # 20 > 10 metros -> cvompleta
        assert vm in completados                        # comprueba lista de completados
        assert vm.vehicle_id not in track.vehicles      # compruba que no continue en el track

    def test_vm_removed_after_completing(self):
        """
        VM que completa el track debe ser removido del self.vehicles automaticamente.
        """
        track = MinimalTrack(1, Vector3(0,0,0), Vector3(10,0,0))
        vm = FakeVehicle(1)
        track.add_vehicle(vm)
        track.update(2.0)
        assert vm.vehicle_id not in track.vehicles























