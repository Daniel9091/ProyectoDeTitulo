"""
BoardingLane - Segmento de abordaje de pasajeros

Responsabilidades:
    - Mover VMs a velocidad constante
    - Gestionar el abordaje de hasta vehicle.capacity pasajeros por VM (cola FIFO por grupo de destino)
    - Comprometer el abordaje al alcanzar BOARDING_COMMIT_PROGRESS

Lo que NO hace:
    - No conoce Brain, Station ni TreeSelector
    - No asigna destinos a los VMs
    - No gestiona posicion 3D de pasageros (Passenger no tiene Vector 3D)
"""
from collections import deque
from tracks.base import BaseTrack
from objects.math3d import Vector3
from objects.passenger import Passenger
from config.constants import BOARDING_LANE_SPEED, BOARDING_COMMIT_PROGRESS

class BoardingLane(BaseTrack):
    """
    Track de abordaje en las estaciones
    A velocidad constante

    Estructura del dict self.vehicles (extiende BaseTrack):
    {
        vehicle_id (int): {
            'vehicle':      ModularVehicle,
            'distance':     float,              # metros recorridos desde start_pos
            'velocity':     float,              # siempre BOARDING_LANE_SPEED
            'passengers':   list[Passenger],    # pasajeros asignados al VM
            'boarding_committed': bool,         # True si progress >= BOARDING_COMMIT_PROGRESS
        }
    }
    Atributos propios:
        passenger_groups: dict[int, deque[Passenger]]  # pasajeros agrupados por destino
    """
    def __init__(self,track_id: int, start_pos: Vector3, end_pos: Vector3, recorder):
        """
        Inicialización utiliza __init__ de BaseTrack.
        """
        super().__init__(track_id, start_pos, end_pos)
        self.passenger_groups: dict[int, deque[Passenger]] = {}
        self._recorder = recorder

    def enqueue_passenger(self, passenger: Passenger) -> None:
        """
        Asigna un pasajero a su grupo de destino en este lane.
        El pasajero debe estar en MOVING_TO_LANE (ya fue asignado por Station).
        """
        passenger.arrive_at_lane()
        dest = passenger.destination_station_id
        if dest not in self.passenger_groups:
            self.passenger_groups[dest] = deque()
        self.passenger_groups[dest].append(passenger)

    def add_vehicle(self, vehicle, entry_velocity = None, leftover_dt = 0.0) -> bool:
        """
        Agrega un VM al lane a velocidad constante BOARDING_LANE_SPEED.
        Aborda hasta vehicle.capacity pasajeros del grupo con mayor tiempo de espera.
        leftover_dt convierte el tiempo sobrante del frame en distancia inicial.
        Siempre retorna True — la BoardingLane no tiene saturación.
        """
        velocity = BOARDING_LANE_SPEED
        initial_distance = self._compute_advance(velocity, leftover_dt)
        if vehicle.passengers_on_board:
            vehicle.distance_carrying_passengers += initial_distance

        vehicle.total_distance_traveled += initial_distance
        vehicle.operational_time        += leftover_dt

        
        passengers = []
        priority_dest = self._select_priority_group()

        if priority_dest is not None:
            group = self.passenger_groups[priority_dest]
            while group and len(passengers) < vehicle.capacity:
                p = group.popleft()
                p.start_boarding()
                vehicle.board(p)
                passengers.append(p)
            if not group:
                del self.passenger_groups[priority_dest]
            vehicle.assign_destination(priority_dest)

        self.vehicles[vehicle.vehicle_id] = {
            'vehicle': vehicle,
            'distance': initial_distance,
            'velocity': velocity,
            'passengers': passengers,
            'boarding_committed': False,
        }
        return True

    def remove_vehicle(self, vehicle_id: int) -> None:
        """
        Remueve un VM del lane y limpia su entrada de self.vehicles.
        """
        del self.vehicles[vehicle_id]

    def update(self, dt: float, current_time: float = 0.0) -> list[tuple]:
        """
        Avanza todos los VMs dt segundos a BOARDING_LANE_SPEED.

        Al alcanzar BOARDING_COMMIT_PROGRESS, llama complete_boarding() en el pasajero.
        El flag boarding_committed evita llamadas repetidas en frames subsiguientes.

        Retorna lista de tuplas (vm, leftover_dt) para VMs que completaron el lane.
        """
        completed = []
        for vehicle_id, data in list(self.vehicles.items()):
            old_distance = data['distance']

            advance = self._compute_advance(data['velocity'], dt)
            data['distance'] += advance
            progress = data['distance'] / self.length

            if not data['boarding_committed'] and progress >= BOARDING_COMMIT_PROGRESS:
                data['boarding_committed'] = True
                for passenger in data['passengers']:
                    passenger.complete_boarding(vehicle_id)
                    self._recorder.passenger_boarded(
                        t=current_time,
                        passenger_id=passenger.passenger_id,
                        vm_id=vehicle_id,
                        spawn_time=passenger.spawn_time,
                    )

            if data['distance'] >= self.length:
                remaining = self.length - old_distance
                time_to_complete = remaining / data['velocity']
                leftover = dt - time_to_complete
                data['vehicle'].total_distance_traveled += remaining
                data['vehicle'].operational_time        += time_to_complete

                if data['vehicle'].passengers_on_board:
                    data['vehicle'].distance_carrying_passengers += remaining

                self._recorder.vm_trip_completed(
                    current_time, vehicle_id,
                    len(data['passengers']), self.length
                )
                completed.append((data['vehicle'], leftover))

            else:
                data['vehicle'].total_distance_traveled += advance
                data['vehicle'].operational_time        += dt
                if data['vehicle'].passengers_on_board:
                    data['vehicle'].distance_carrying_passengers += advance

        
        for vm, _ in completed:
            self.remove_vehicle(vm.vehicle_id)
        
        return completed

    def _select_priority_group(self) -> int | None:
        """
        Retorna el destination_id del grupo con el pasajero que lleva más tiempo esperando.
        Compara passenger_groups[dest][0].spawn_time entre todos los grupos activos.
        Retorna None si no hay grupos.
        """
        if not self.passenger_groups:
            return None
        return min(self.passenger_groups,key=lambda dest: self.passenger_groups[dest][0].spawn_time)
    
    def _compute_advance(self, velocity: float, dt:float) -> float:
        """
        Calcula la distancia que avanza el VM en dt segundos.
        En BoardingLane la velocidad es constante: d = v * dt.
        """
        return velocity * dt
        



