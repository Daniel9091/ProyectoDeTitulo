"""
AccelerationTree - Árbol de aceleración/desaceleración gravitacional

Responsabilidades:
    - Mover VMs con física MRUA (d = v₀t + ½at²)
    - UP:   VM sube desacelerando contra la gravedad (TRAIN_SPEED → BOARDING_LANE_SPEED)
    - DOWN: VM baja acelerando con la gravedad     (BOARDING_LANE_SPEED → TRAIN_SPEED)
    - Controlar saturación en árboles UP: garantizar separación mínima entre VMs en la cima
    - Exponer target_acceleration por VM para que el VM ajuste su aceleración y llegue
      exactamente al slot reservado (DOWN: señal del sistema de reserva vía Brain;
      UP: ajuste fino de Brain para evitar colisiones dentro del árbol)

Lo que NO hace:
    - La decisión final de a qué árbol va un VM la toma Brain. El árbol SÍ puede rechazar
      la entrada si está saturado (can_accept() → False). Brain pregunta a todos los árboles
      del junction; si todos rechazan a un VM con reserva, Brain fuerza la entrada al árbol
      con menor saturación (force_add_vehicle()).
    - No conoce ContinuousTrain ni Station directamente
    - No resuelve colisiones (las detecta vía can_accept, pero no las corrige)
"""

import math

from tracks.base import BaseTrack
from objects.math3d import Vector3
from objects.types import TreeDirection, ModularVehicleState
from config.constants import (
    TRAIN_SPEED, BOARDING_LANE_SPEED, TRAIN_SPACING,
    ACCEL_RANGE_MIN, ACCEL_RANGE_MAX, GRAVITY
)

class AccelerationTree(BaseTrack):
    """
    Track de aceleración/desaceleración que conecta el ContinuousTrain con las estaciones.

    Física:
        UP:     entry_velocity = TRAIN_SPEED            signed_accel = -base_acceleration
        DOWN:   entry_velocity = BOARDING_LANE_SPEED    signed_accel = +base_acceleration
        MRUA: d = v₀·t + ½·a·t²,   v = v₀ + a·t

    Saturación:
        Cuando dos VMs desaceleran con la misma magnitud, su separación disminuye
        monótonamente. El punto más crítico es la cima (salida del árbol). Dado Δt entre
        entradas, la separación en la cima es:
            sep_cima = Δt · (v_salida + ½ · a · Δt)
        El Δt_min que garantiza sep_cima ≥ d_min se resuelve como ecuación cuadrática.
        El chequeo asume base_acceleration para todos los VMs; las modificaciones de Brain
        vía set_vehicle_acceleration son ajustes finos y su error de saturación es de
        segundo orden, aceptable en simulación a 30 FPS.

    Ajuste de aceleración: en DOWN (alineación con slot reservado):
        Una vez que el sistema de reserva asigna un slot a un VM que está en el DOWN tree,
        Brain llama set_vehicle_acceleration() para ajustar la tasa de aceleración de ese
        VM específico. El objetivo es que el VM salga del árbol en el momento exacto en
        que su slot reservado pasa por la junction de entrada al tren

    Estructura del dict self.vehicles (extiende BaseTrack):
    {
        vehicle_id (int): {
            'vehicle':              ModularVehicle,
            'distance':             float,              # metros recorridos desde start_pos
            'velocity':             float,              # m/s actual, siempre >= 0
            'target_acceleration':  float,              # magnitud m/s2, ajustable por Brain
            'time_in_track':        float,              # segundos acumulados en el track
        }
    }
    
    Atributos propios:
        direction           TreeDirection   UP o DOWN
        base_acceleration   float           magnitud de aceleración (m/s2), siempre > 0 (calculada, no recibida)
        min_slot_gap        int             slots mínimos entre entradas consecutivas (0 si DOWN)
        _min_safe_distance  float           umbral de distancia del VM más joven para can_accept
    """

    def __init__(
            self,
            track_id: int,
            start_pos: Vector3,
            end_pos: Vector3,
            direction: TreeDirection,
            min_vm_separation: float,
            recorder,
            station_id : int | None = None
    ):
        """
        Construye un árbol de aceleración/desaceleración gravitacional.

        Args:
            track_id: Identificador único del track.
            start_pos: Posición 3D de entrada al árbol (base).
            end_pos: Posición 3D de salida del árbol (cima).
            direction: UP (sube hacia la estación) o DOWN (baja hacia el belt).
            min_vm_separation: Distancia mínima en metros entre VMs en la cima; solo relevante para UP.
            recorder: Objeto que registra telemetría (vm_trip_completed).
            station_id: ID de la estación a la que pertenece este árbol; None si no aplica.
        """
        super().__init__(track_id, start_pos, end_pos)
        self.direction = direction
        self.base_acceleration = self._compute_effective_acceleration()
        self.station_id = station_id

        self._min_safe_distance: float = 0.0
        self.min_slot_gap: int = 0
        if direction == TreeDirection.UP:
            self._init_saturation(min_vm_separation)

        self._recorder = recorder

    def _compute_effective_acceleration(self) -> float:
        """
        Calcula la aceleración efectiva a partir de la geometría del árbol.

        La gravedad actúa solo en el eje Z. El árbol tiene largo self.length
        (distancia entre start_pos y end_pos) con componente vertical
        dz = |end_pos.z - start_pos.z|. La aceleración efectiva es la proyección
        de la gravedad sobre la dirección del árbol:
            a_eff = GRAVITY * (dz / length)

        Un árbol con dz=0 no tiene componente gravitacional — no es un
        AccelerationTree válido, es conceptualmente un track recto sin
        aceleración. Se rechaza explícitamente en vez de degradar a
        aceleración 0, que generaría VMs que nunca cambian de velocidad
        de forma silenciosa (bug invisible, no un crash visible).
        """
        dz = abs(self.end_pos.z - self.start_pos.z)
        if dz <= 0:
            raise ValueError(
                f"AccelerationTree {self.track_id}: start_pos y end_pos tienen "
                f"la misma altura Z (dz=0) — sin componente gravitacional. "
                f"Un árbol de aceleración siempre requiere diferencia de altura."
            )
        return GRAVITY * (dz / self.length)

    def _init_saturation(self, d_min: float) -> None:
        """
        Precomputa parámetros de saturación para árbol UP.
        Resuelve 0.5·a·Δt² + v_salida·Δt - d_min = 0 para obtener Δt_min,
        que garantiza sep_cima ≥ d_min entre dos VMs consecutivos.
        """
        v_entry = TRAIN_SPEED
        v_exit = math.sqrt(max(0.0, v_entry ** 2 - 2.0 * self.base_acceleration * self.length))

        dt_min = (
            (-v_exit + math.sqrt(v_exit ** 2 + 2.0 * self.base_acceleration * d_min))
            /self.base_acceleration
        )
        self._min_safe_distance = v_entry * dt_min - 0.5 * self.base_acceleration * dt_min ** 2
        self.min_slot_gap = math.ceil(dt_min * TRAIN_SPEED / TRAIN_SPACING)

    def can_accept(self) -> bool:
        """
        True si el árbol puede recibir un nuevo VM sin riesgo de colisión por saturación.

        Para UP: el VM más joven (menor distancia desde start) debe haber avanzado
        al menos _min_safe_distance. Para DOWN siempre True: los VMs se separan al acelerar.
        """
        if self.direction == TreeDirection.DOWN:
            return True
        if not self.vehicles:
            return True
        youngest_distance = min(data['distance'] for data in self.vehicles.values())
        return youngest_distance >= self._min_safe_distance

    def add_vehicle(
      self,
      vehicle,
      entry_velocity: float | None = None,
      leftover_dt: float = 0.0
    ) -> bool:
        """
        Intenta agregar un VM al árbol de forma segura.
        Retorna True si fue agregado, False si la saturación lo impide.
        No modifica ningún estado si retorna False.
        Nota: sobreescribe BaseTrack.add_vehicle() retornando bool en lugar de None.
        """
        if not self.can_accept():
            return False
        self._insert_vehicle(vehicle, entry_velocity, leftover_dt)
        return True
    
    def force_add_vehicle(
            self,
            vehicle,
            entry_velocity: float | None = None,
            leftover_dt: float = 0.0
    ) -> None:
        """
        Fuerza la entrada de un VM ignorando la comprobación de saturación.

        Registra advertencia en stdout si hay riesgo de colisión, pero no falla.
        Brain llama esto cuando todos los árboles del junction rechazaron a un VM con 
        reserva y es necesario forzar al árbol menos saturado.
        """
        if not self.can_accept():
            print(
                f"[ADVERTENCIA] AccelerationTree {self.track_id}: "
                f"VM {vehicle.vehicle_id} forzado — riesgo de colisión por saturación"
            )
        self._insert_vehicle(vehicle, entry_velocity, leftover_dt)

    def remove_vehicle(self, vehicle_id: int) -> None:
        """
        Remueve un VM del árbol y restaura su estado a MOVING.
        """
        self.vehicles[vehicle_id]['vehicle'].state = ModularVehicleState.MOVING
        del self.vehicles[vehicle_id]

    def update(self, dt: float, current_time: float = 0.0) -> list[tuple]:
        """
        Avanza todos los VMs dt segundos con física MRUA.

        La velocidad no baja de 0 (VM UP puede quedar congelado si la rampa es muy larga).
        Retorna lista de (vm, left_dt) por cada VM que completó el track en ese frame.
        """
        if not self.vehicles:
            return []
                
        completed = []
        for vid, data in list(self.vehicles.items()):
            old_distance = data['distance']
            old_velocity = data['velocity']
            accel = self._signed_acceleration(data['target_acceleration'])

            advance = max(0.0, self._compute_advance(old_velocity, dt, accel))
            data['distance'] += advance
            data['velocity'] = max(0.0, old_velocity + accel * dt)
            data['time_in_track'] += dt

            if data['distance'] >= self.length:
                remaining = self.length - old_distance
                if abs(accel) < 1e-9:
                    time_to_complete = remaining / old_velocity if old_velocity > 0 else 0.0
                else:
                    disciminant = old_velocity ** 2 + 2.0 * accel * remaining
                    time_to_complete = (-old_velocity + math.sqrt(max(0.0, disciminant))) / accel
                leftover = max(0.0, dt - time_to_complete)
                data['vehicle'].total_distance_traveled += remaining
                data['vehicle'].operational_time        += time_to_complete
                if data['vehicle'].passengers_on_board:
                    data['vehicle'].distance_carrying_passengers += remaining
                
                completed.append((data['vehicle'], leftover))
            else:
                data['vehicle'].total_distance_traveled += advance
                data['vehicle'].operational_time        += dt
                if data['vehicle'].passengers_on_board:
                    data['vehicle'].distance_carrying_passengers += advance
                
        for vm, _ in completed:
            self.remove_vehicle(vm.vehicle_id)
        
        return completed
        
    def set_vehicle_acceleration(self, vehicle_id: int, new_accel: float) -> None:
        """
        Brain ajusta la aceleración de un VM específico para que el VM llegue al slot.

        En DOWN: el sistema de reserva, a través de Brain, llama esta función para que
        el VM ajuste su aceleración y salga del árbol en el momento exacto en que su slot
        pasa por la junction.

        Avisa si se sale de rangos de aceleración.
        """
        
        if new_accel < ACCEL_RANGE_MIN or new_accel > ACCEL_RANGE_MAX:
            print(
                f"[ADVERTENCIA] AccelerationTree {self.track_id}: "
                f"aceleración de VM {vehicle_id} ({new_accel:.3f} m/s²) "
                f"fuera del rango cómodo [{ACCEL_RANGE_MIN}, {ACCEL_RANGE_MAX}]"
        )

        self.vehicles[vehicle_id]['target_acceleration'] = new_accel

    def _insert_vehicle(
            self,
            vehicle,
            entry_velocity: float | None,
            leftover_dt: float
    ) -> None:
        """
        Lógica compartida de inserción entre add_vehicle y force_add_vehicle.
        """
        if entry_velocity is None:
            entry_velocity = TRAIN_SPEED if self.direction == TreeDirection.UP else BOARDING_LANE_SPEED
        
        accel = self._signed_acceleration(self.base_acceleration)
        initial_distance = max(0.0, self._compute_advance(entry_velocity, leftover_dt, accel))       
        initial_velocity = max(0.0, entry_velocity + accel * leftover_dt)

        vehicle.total_distance_traveled += initial_distance
        vehicle.operational_time        += leftover_dt
        if vehicle.passengers_on_board:
            vehicle.distance_carrying_passengers += initial_distance

        vehicle.state = (
            ModularVehicleState.ACCELERATING_UP
            if self.direction == TreeDirection.UP
            else ModularVehicleState.ACCELERATING_DOWN
        )

        initial_accel = (
            vehicle.reserved_tree_acceleration
            if vehicle.reserved_tree_acceleration is not None
            else self.base_acceleration
        )
        vehicle.reserved_tree_acceleration = None

        self.vehicles[vehicle.vehicle_id] = {
            'vehicle':             vehicle,
            'distance':            initial_distance,
            'velocity':            initial_velocity,
            'target_acceleration': initial_accel,
            'time_in_track':       leftover_dt,
        }

    def _compute_advance(self, velocity: float, dt: float, acceleration: float) -> float:
        """
        d = v₀·t + ½·a·t² (MRUA). acceleration ya es con signo.
        """
        return velocity * dt + 0.5 * acceleration * dt * dt

    def _signed_acceleration(self, magnitude: float) -> float:
        """
        Convierte magnitud a aceleración con signo según dirección del árbol.
        """
        return -magnitude if self.direction == TreeDirection.UP else magnitude

    def __repr__(self) -> str:
        return (
            f"AccelerationTree("
            f"id={self.track_id}, "
            f"dir={self.direction.value}, "
            f"station={self.station_id}, "
            f"len={self.length:.1f}m, "
            f"vms={self.vehicle_count}, "
            f"slot_gap={self.min_slot_gap})"
        )
    