"""
continuousTrain - Carril inferior circular de la simulacion

Responsabilidades:
    - Mantener una lista de slots fjijos con posición calculada desde tail_x (O(1) por frame)
    - Avanzar el carril moviendo solo tail_x - todos los slots se recalculan desde ahí
    - Mantener las etiquetas de cada slot para que brain tome decisiones
    - Exponer consultas de datos (posicion 3D, slot mas cercano a un belt_x dado)
    - Manejar el wrap-around circular con modulo

Lo que no hace:
    - No toma deciciones de routing, colisión ni demanda (Brain lo hace)
    - No conoce logica de estaciones - solo registra junction_points por station_id
    - No gestiona pasajeros

Estructura de cada slot (dict en self.slots):
    {
        'vm':                           ModularVehicle | None
        'reserved_for_id':              int | None              # Bloqueado para Vm que baje
        'destination_station_id':        int | None              # Destino del VM en este slot (VM tiene destino por que tiene pasajeros a bordo)
        'demand_supply_for_station_id'  int | None              # Marcado para suplir demanda         
    }
"""

import math
import random
from typing import Callable
from objects.math3d import Vector3
from objects.modular_vehicle import ModularVehicle
from config.constants import TRAIN_SPEED, TRAIN_SPACING


class ContinuousTrain:
    """
    Carril inferior circular del sistema de transporte.

    El carrijl es un segmento de start_pos a end_pos tratado como via circular:
    los VMs qeu superan el final reaparecen al inicio via modulo.
    Internamente se modlea como una coordenada 1D (belt_x ∈ [0, total_length)).

    Parámetros:
        start_pos           Vector3             # inicio del carril en 3D
        end_pos             Vector3             # fin del carril en 3D
        density             float               # proporcion inicial de slots ocupados [0.0 - 1.0]
        vm_factory          Callable            # vm_factory(vm_id: int) -> ModularVehicle
        rng                 random.Random       # generador compartido con semilla fija
        junction_points     dict[int, float]    # {statjion_id: belt_x} puntos de conexjion de arboles
    """

    def __init__(
            self,
            start_pos: Vector3,
            end_pos: Vector3,
            density: float,
            vm_factory: Callable,
            rng: random.Random,
            junction_points: dict,
    ):
        self.start_pos  = start_pos
        self.end_pos    = end_pos
        dx = end_pos.x - start_pos.x
        dy = end_pos.y - start_pos.y
        dz = end_pos.z - start_pos.z

        self.total_length:  float   = math.sqrt(dx ** 2 + dy ** 2 + dz ** 2)
        self.max_slots:     int     = int(self.total_length / TRAIN_SPACING)

        # {station_id: belt_x} - puntos deonde los arboles de cada estacion conectan al carril
        self.junction_points: dict[int,float] = dict(junction_points)
        
        self.tail_x:    float = 0.0
        self.slots:     list = []
        self._init_slots(density, vm_factory, rng)

    # ─── AVANCE PRINCIPAL ─────────────────────────────────────────────────

    def advance(self, dt: float) -> None:
        """
        Avanza el carril dt segundos. O(1): solo mueve tail_x.
        El modulo garantiza el wrap-round circular automaticamente.
        """
        self.tail_x = (self.tail_x + TRAIN_SPEED * dt) % self.total_length

    # ─── POSICIONES ──────────────────────────────────────────────────────
    
    def get_slot_belt_x(self, slot_idx: int) -> float:
        """
        Coordenada 1D de carril del slot indicado.
        Posicion de slot i = (tail_x + slot_idx * TRAIN_SPACING) % total_lenght
        
        """
        return (self.tail_x + slot_idx * TRAIN_SPACING) % self.total_length
    
    def get_slot_position_3d(self,slot_idx: int) -> Vector3:
        """
        Posision 3D del slot indicado
        """
        return self.belt_x_to_3d(self.get_slot_belt_x(slot_idx))
    
    def belt_x_to_3d(self, belt_x: float) -> Vector3:
        """
        Convierte coordenada de carril a posicion 3D.

        Hoy; interpolacion lineal entre start_pos y end_pos.
        Diseñada para ser externdida en versiones futruras con trayectorias curvas
        (reemplazar con tabla de segmentoes sin cambiar la interfaz)
        """
        t = belt_x / self.total_length
        return Vector3(
            self.start_pos.x + t * (self.end_pos.x - self.start_pos.x),
            self.start_pos.y + t * (self.end_pos.y - self.start_pos.y),
            self.start_pos.z + t * (self.end_pos.z - self.start_pos.z),
        )

    # ─── GESTIÓN DE VMs EN SLOTS ──────────────────────────────────────────

    def place_vm(self, vm: ModularVehicle, slot_idx: int) -> None:
        """
        Coloca un VM en el slot indicado.
        Brain llama esto cuando un VM termina de desender para un arbol y toma su slot.
        """
        self.slots[slot_idx]['reserved_for_vm_id'] = None
        self.slots[slot_idx]['vm'] = vm

    def remove_vm(self, slot_idx: int) -> ModularVehicle:
        """
        Extrae el VM del slot y lo retorna.
        Brain llama esto cuando  un VM sale del carril hacia un arbol de subida
        """
        vm = self.slots[slot_idx]['vm']
        self.slots[slot_idx]['vm'] = None
        self.slots[slot_idx]['destination_station_id'] = None
        self.slots[slot_idx]['demand_supply_for_station_id'] = None

        return vm

    # ─── ETIQUETAS DE SLOT ────────────────────────────────────────────────

    def set_reservation(self, slot_idx: int, vm_id: int) -> None:
        """
        Reserva el slot para el VM vm_id que esta desendiendo hacia el.
        """
        self.slots[slot_idx]['reserved_for_vm_id'] = vm_id

    def clear_reservation(self, slot_idx: int) -> None:
        """
        Limpia slots[slot_idx]['reserved_for_vm_id']
        """
        self.slots[slot_idx]['reserved_for_vm_id'] = None

    def set_destination(self, slot_idx: int, station_id: int) -> None:
        """
        Registra que el VM en este slot tiene destiono station_id.
        """
        self.slots[slot_idx]['destination_station_id'] = station_id

    def clear_destination(self, slot_idx: int) -> None:
        """
        Limpia slots[slot_idx]['destination_station_id']
        """
        self.slots[slot_idx]['destination_station_id'] = None

    def set_demand_supply(self, slot_idx: int, station_id: int) -> None:
        """
        Marca el slot para suplir demanda de station_id
        """
        self.slots[slot_idx]['demand_supply_for_station_id'] = station_id

    def clear_demand_supply(self, slot_idx: int) -> None:
        """
        Limpia slots[slot_idx]['demand_supply_for_station_id']
        """
        self.slots[slot_idx]['demand_supply_for_station_id'] = None

    # ─── CONSULTAS PARA BRAIN ─────────────────────────────────────────────
    
    def find_neartest_slot_to_belt_x(self, target_belt_x: float) -> tuple[int, float]:
        """
        Retorna (slot_idx, distancia) del slot cuya posicion es mas cercana a target_belt_x.
        O(1): la distribucion uniforma de slots permite calculo directo por aritmetica.
        La distancia considera el wrap-around circular.
        Brain usa esto para dientificar que slot esta en un junciton cada frame.
        """
        relative = (target_belt_x - self.tail_x) % self.total_length
        idx = round(relative / TRAIN_SPACING) %  self.max_slots
        actual_belt_x = self.get_slot_belt_x(idx)
        dist = _circular_distance(actual_belt_x, target_belt_x, self.total_length)
        return (idx, dist)
    
    def get_occupied_slot_count(self) -> int:
        """
        Cantidad de slots ocupados ['vm'] != None.
        """
        return sum(1 for s in self.slots if s['vm'] is not None)
    
    def get_free_slot_count(self) -> int:
        """
        Cantidad de slots sin VM y sin reserva - disponibilidad para ser tomados.
        """
        return sum(
            1 for s in self.slots
            if s['vm'] is None and s['reserved_for_vm_id'] is None
        )

    # ─── INICIALIZACIÓN ───────────────────────────────────────────────────

    def _init_slots(self, density: float, vm_factory: Callable, rng: random.Random) -> None:
        """
        Crea max_slots slots y ocupa aleatoriamente segun density.
        IDs de VMs inicialies: enteros secuenciales desde 0.
        vm_factory(vm_id) construye cada ModularVehicle con el ID indicado.
        """
        next_vm_id = 0
        for _ in range(self.max_slots):
            slot = {
                'vm':                           None,
                'reserved_for_vm_id':           None,
                'destination_station_id':       None,
                'demand_supply_for_station_id': None,
            }
            if rng.random() < density:
                slot['vm'] = vm_factory(next_vm_id)
                next_vm_id += 1
            self.slots.append(slot)

    # ─── DEBUG ────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        occupied = self.get_occupied_slot_count()
        return(
            f"ContinuousTrain("
            f"slots={self.max_slots},"
            f"occupied={occupied},"
            f"tail_x={self.tail_x:.2f}/{self.total_length:.1f})"

        )

def _circular_distance(a: float, b: float, lenght: float) -> float:
    """
    Distancia minima entre dos puntos en una circunferencia de longitud lenght.
    """
    diff = abs(a -b)%lenght
    return min(diff, lenght - diff)

