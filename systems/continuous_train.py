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
        'reserved_station_id':          int | None              # Estación que reclamo el slot (routing en junction_UP) (sistema de reserva)
        'reserved_vm_id':               int | None              # VM esperado (verificacíon de llegada)
        'demand_station_id':            int | None              # Marcado para suplir demanda (sistema de taza)
        'destination_station_id':       int | None              # Destino del VM en este slot (VM tiene destino por que tiene pasajeros a bordo) (sistema de destino)    
    }
"""

import logging
import math
import random
from typing import Callable
from objects.math3d import Vector3
from objects.modular_vehicle import ModularVehicle
from config.constants import TRAIN_SPEED, TRAIN_SPACING

logger = logging.getLogger(__name__)

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
        junction_points     dict[int, float]    # {station_id: belt_x} puntos de conexion de arboles
    """

    def __init__(
            self,
            start_pos: Vector3,
            end_pos: Vector3,
            density: float,
            vm_factory: Callable,
            rng: random.Random,
            junction_points: dict,
            recorder,
    ):
        self.start_pos  = start_pos
        self.end_pos    = end_pos

        recorder = recorder

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

    def advance(self, dt: float) -> list[tuple[int, int, float]]:
        """
        Avanza el carril dt segundos y detecta cruces de junctions. O(junctions).

        Para cada junction, encuentra el slot más cercano a ella antes del avance
        y calcula el leftover_dt exacto (tiempo sobrante después de cruzar).

        Retorna list[(slot_idx, station_id, leftover_dt)].
        Si Brain decide NO trasferir el VM al árbol, ignora el leftover_dt:
        el VM ya avanzó el frame completo en el belt gracias al avance de tail_x.

        Limitación — máximo 1 cruce por junction por frame:
            El código identifica un único slot candidato via round(). Si en un
            frame dos slots cruzaran la misma junction, el segundo se perdería.
            Invariante requerida: TRAIN_SPEED * dt < TRAIN_SPACING
            NSim a 30 FPS: 20 × (1/30) ≈ 0.67 m < 2.0 m  ✓
            Si TRAIN_SPEED sube a 60+ m/s, aumentar TRAIN_SPACING o FPS.
        """

        old_tail_x =self.tail_x
        movement = TRAIN_SPEED * dt
        self.tail_x = (self.tail_x + movement)% self.total_length

        crossings = []
        for station_id, junction_x in self.junction_points.items():
            # Slot que estaba más cerca de juntion_x ANTES del avance
            relative = (junction_x - old_tail_x + self.total_length) % self.total_length
            slot_idx = round( relative / TRAIN_SPACING) % self.max_slots

            if self.slots[slot_idx]['vm'] is None:
                continue
            
            # Distancia hacia adelante desde la posición del slot hasta junction_x
            belt_x_before = (old_tail_x + slot_idx * TRAIN_SPACING) % self.total_length
            d = (junction_x - belt_x_before + self.total_length) % self.total_length

            # Cruzó si esa distancia abe en el movimiento del frame
            if d <= movement:
                leftover_dt = max(0.0, dt -d/TRAIN_SPEED)
                crossings.append((slot_idx,station_id,leftover_dt))

        return crossings

    # ─── POSICIONES ──────────────────────────────────────────────────────
    
    def get_slot_belt_x(self, slot_idx: int) -> float:
        """
        Coordenada 1D de carril del slot indicado.
        Posicion de slot i = (tail_x + slot_idx * TRAIN_SPACING) % total_length
        
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

        Si el slot YA tiene un VM — nunca debería pasar en operación correcta, indica
        que la reserva falló o llegó tarde — el VM entrante NO sobreescribe al que ya
        está: se agrega a 'colliding_vms' para que el choque quede visible y
        diagnosticable en vez de perder un VM en silencio.
        """
        slot = self.slots[slot_idx]
        slot['reserved_station_id'] = None
        slot['reserved_vm_id'] = None
        if slot['vm'] is not None:
            slot['colliding_vms'].append(vm)
            logger.critical(
                f"CHOQUE: VM {vm.vehicle_id} llegó al slot {slot_idx}, ya ocupado por "
                f"VM {slot['vm'].vehicle_id} — reserva falló o llegó tarde"
            )
        else:
            slot['vm'] = vm

    def remove_vm(self, slot_idx: int) -> ModularVehicle:
        """
        Extrae el VM del slot y lo retorna.
        Brain llama esto cuando  un VM sale del carril hacia un arbol de subida.
        No se limpia la etiqueta de reserva, por que se debe conservar hasta
        el arbol de bajada.
        """
        vm = self.slots[slot_idx]['vm']
        self.slots[slot_idx]['vm'] = None
        self.slots[slot_idx]['destination_station_id'] = None
        self.slots[slot_idx]['demand_station_id'] = None

        return vm

    # ─── ETIQUETAS DE SLOT ────────────────────────────────────────────────

    def set_reservation(self, slot_idx: int, vm_id: int, station_id: int) -> None:
        """
        Reserva el slot: station_id para routing en junction_UP, vm_id para verificar llegada.
        """
        self.slots[slot_idx]['reserved_station_id'] = station_id
        self.slots[slot_idx]['reserved_vm_id'] = vm_id

    def clear_reservation(self, slot_idx: int) -> None:
        """
        Limpia reserved_station_id y reserved_vm_id del slot.
        """
        self.slots[slot_idx]['reserved_station_id'] = None
        self.slots[slot_idx]['reserved_vm_id'] = None

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
        self.slots[slot_idx]['demand_station_id'] = station_id

    def clear_demand_supply(self, slot_idx: int) -> None:
        """
        Limpia slots[slot_idx]['demand_supply_for_station_id']
        """
        self.slots[slot_idx]['demand_station_id'] = None

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
            if s['vm'] is None and s['reserved_station_id'] is None
        )

    def get_colliding_vm_count(self) -> int:
        """
        Cantidad total de VMs actualmente en choque (el ocupante original +
        todos los que cayeron encima). Cada slot en choque aporta 1 + len(colliding_vms).
        """
        return sum(
            1 + len(s['colliding_vms'])
            for s in self.slots
            if s['colliding_vms']
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
                'vm':                     None,
                'reserved_station_id':    None,
                'reserved_vm_id':         None,
                'destination_station_id': None,
                'demand_station_id':      None,
                'colliding_vms':          [],
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

