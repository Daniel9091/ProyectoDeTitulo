"""
BaseTrack - Clase abstracta para todos los segmentos de via lineales en Nsim

Responsabilidades de este archivo:
    -Definir la interfaz y el comportamiento COMPARTIDO entre BoardingLane y AccelerationTree.
        Ambos son segmentos rectilíneos con VMs moviéndose de un punto A a un punto B.

Lo que define:
    - Métodos abstractos que toda subclase DEBE implementar
    - Estructura estándar del dict self.vehicles (distance + velocity)
    - Cálculos geométricos: longitud, posición interpolada, vector dirección
    - get_progress() como método CONCRETO derivado de distance/length

Lo que NO define:
    - Física (constante, gravitacional) - eso es responsabilidad de la subclase
    - Lógica de pasajeros
    - Anti-colisión
    - ContinuousTrain No hereda de aquí: es circular y slot-based
    arquitectura completamente distinta (vive en systems/)
"""
from abc import ABC, abstractmethod
from objects.math3d import Vector3

class BaseTrack(ABC):
    """
    Clase base abstracta para segmentos de via lineales

    Geometria:
    Un track es un segmento recto de start_pos -> end_pos.
    Los VMs avanzan con un progreso normalizado: 0.0 -> 1.0 (fin)

    Contexto de coordenadas:
    X -> direccion principal del tren (horizontal)
    Y -> offset lateral (posición dentro de la estación)
    Z -> altura (vertical)

    Estructura estándar del dict self.vehicles:
    {
        vehicle_id (int): {
            'vehicle':  ModularVehicle,   # referencia al objeto VM
            'distance': float,            # metros recorridos desde start_pos
            'velocity': float,            # m/s actual (presente en TODAS las subclases)
        }
    }
    Cada subclase AÑADE campos propios encima de esta base:
        BoardingLane    → 'passenger', 'boarding_committed'
        AccelerationTree → 'target_acceleration', 'time_in_track'

    Métodos abstractos (cada subclase DEBE implementarlos):
        add_vehicle, remove_vehicle, update

    Métodos concretos (ya implementados, disponibles para subclases):
        get_progress, position_at_progress, direction_vector,
        vehicle_count, get_vehicles
    """

    def __init__(self, track_id, start_pos: Vector3, end_pos: Vector3):
        # IDENTIDAD
        self.track_id = track_id
        # GEOMETRIA
        self.start_pos: Vector3 = start_pos
        self.end_pos: Vector3 = end_pos
        self.length: float =  start_pos.distance_to(end_pos)
        # VEHICULOS
        # dict[vehicle_id → datos del VM en este track]
        # O(1) para lookup, inserción y eliminación por vehicle_id.
        # Brain necesita O(1) para ajustar la aceleración de un VM específico
        # en AccelerationTree — por eso dict y no lista.

        self.vehicles: dict[int, dict] = {}
        
    # INTERFAZ ABSTRACTA
    @abstractmethod
    def add_vehicle(self,vehicle,entry_velocity:float | None = None, leftover_dt: float = 0.0) -> None:
        """
        Agrega un VM al track, inicializando su entrada.

        La subclase define:
            - La velocidad inicial (entry_velocity o su propia constante)
            - Los campos adicionales del dict (passenger, target_acceleration, etc.)
            - La formula de movimiento que ocupa leftover_dt para convertirlo en distancia

        Convencion: distance=0.0 al entrar, velocity segun el tipo de track.
        """
        pass
    
    @abstractmethod
    def remove_vehicle(self, vehicle_id: int) -> None:
        """
        Remueve un VM del track y limpia su entrada de self.vehicles.
        La subclase maneja los efectos secundarios (re-encolar pasajero, etc.).
        """
        pass

    @abstractmethod
    def update(self, dt: float, current_time: float = 0.0) -> list[tuple]:
        """
        Avanza la simulación dt segundos para todos los VMs en el track.
        current_time se usa para timestamps de telemetría (passenger_boarded, vm_trip_completed).
        Es opcional (default 0.0) para mantener compatibilidad con tests que no pasan tiempo.


        La subclase aplica su física:
            BoardingLane        -> velocidad constante BOARDING_LANE_SPEED
            AccelerationTree    -> MRUA con a = +/- g * sin(teta), velocity por VM

        Retorna lista de tuplas (vm, leftover_dt) por cada VM que completó el track.
        leftover_dt = tiempo sobrante del frame después de que el VM llegó al final.
        El caller usa ese leftover_dt para llamar add_vehicle() en el siguiente track.  

        Nota sobre time_left:
            Si un VM supera el final del track en este frame, el sobrante
            es relevante para la transicion precisa al siguiente track.
            La subclase puede retornar (vm, time_left) si lo necesita,
            o simplemente [vm] si la transicion se maneja externamente
        """
        pass

    def get_progress(self, vehicle) -> float:
        """
        Retorna el progreso normalizado del VM (0.0 = start_pos, 1.0 = end_pos).
        Las subclases no necesitan sobrescribir esto.

        Retorna 0.0 si el VM no está en el track. (falla silenciosa segura).
        """
        data = self.vehicles.get(vehicle.vehicle_id)
        if data is None:
            return 0.0
        if self.length <= 0:
            return 1.0
        return data['distance'] /self.length
    
    def position_at_progress(self, progress: float) -> Vector3:
        """
        Calcula la posición 3D para un progreso dado por interpolación lineal.

        progress=0.0 -> start_pos
        progress=1.0 -> end_pos

        Funciona para ambas clases porque son rectilíneas.
        """
        direction = self.end_pos - self.start_pos
        return self.start_pos + direction * progress

    def direction_vector(self) -> Vector3:
        """
        Vector unitario de start_pos -> end_pos

        Útil para convertir speed (escalar) en velocity (vectorial):
            velocity_vec = direction_vector * speed
        """
        direction = self.end_pos - self.start_pos
        if direction.length() > 0:
            return direction.normalize()
        return Vector3()

    @property
    def vehicle_count(self) -> int:
        """
        Cantidad de VMs en el track.
        """
        return len(self.vehicles)

    def get_vehicles(self) -> list:
        """
        Lista de objetos VM actualmente en el track.
        """
        return [data['vehicle'] for data in self.vehicles.values()]

    # DEBUG
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"id={self.track_id}, "
            f"length={self.length:.1f}m, "
            f"vehicles={self.vehicle_count})"
        )

