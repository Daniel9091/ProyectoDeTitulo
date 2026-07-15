"""
Station - Estacion del sistema de transporte NSim.

Responsabilidades:
    - Generar pasajeros con tasa de produccion configurable (acumulador decimal)
    - Asignar destionos según distribucion de probabilidades configurada por estación
    - Mover pasajeros desde el origen hasta el inico de la boarding lane asignada
    - Gestionar plataformas activas/inactivas con asignacion en rotación
    - Acumula demanda de VMs y exponerla a Brain (puede ser negativa)

Lo que NO hace:
    - No seleciona que arbol usa cada VM (Brain/Network lo deciden con los tree_ids)
    - No gestiona fisica de los AccelerationTree ni el tren continuo
    - No contruye su propio layout geometrico (responsabilidad de station_factory)
    - No escribe en terminal (Simulacion lo hace con get_summary())

Estructura interna por plataforma (un dict en self._platforms):
    {
        'lane':             BoardingLane,       # objeto, propiedad de Station
        'up_tree_id':       int,                # arbol de subida - Network lo resuelve
        'down_tree_id':     int,                # arbol de bajada - Network lo resuelve
        'extraction_point:  Vector3,            # Punto donde los VMs llegan desde el arbol de subida
        'discharge_point':  Vector3,            # Punto donde los VMs parten al arbol de bajada
        'state':            AndenState          # Estado actual de la plataforma
    }
"""
import random
from objects.math3d import Vector3
from objects.passenger import Passenger
from objects.types import AndenState
from tracks.boarding_lane import BoardingLane
from config.constants import PASSENGER_WALK_SPEED
from objects.passenger_id_generator import PassengerIdGenerator


class StationDimensions:
    """
    Dimenciones físicas de la estación.
    Usadas para calcular límites del plano y para render
    El largo exacto de cada boarding lane depende del offset de la plataforma más externa,
    calculado en station_factory.
    """
    def __init__(self, x_length: float, y_length: float, floor_height: float, num_floors: int):
        self.x_length = x_length
        self.y_length = y_length
        self.floor_height = floor_height
        self.num_floors = num_floors
    
    @property
    def total_height(self) -> float:
        return self.floor_height * self.num_floors

class Station:
    """
    Estacion del sistema de trasporte

    Parámetros de configuración:
        station_id                  int
        origin                      Vector3                 dentro del plano XY
        dimensions                  StationDimensions
        passenger_rate              float                   pasajeros/segundos
        destination_probabilities   dict[int,float]         {station_id:probabilidad (peso)} - se normaliza automáticamente
        vm_request_rate             float                   VMs/segundo solicitados
        platforms                   list[dict]              lista de dicts (ver estructura en módulo)
        rng                         random.Random           generador compartido con semilla fija
        id_generator                PassengerIdGenerator    generador de IDs para pasajeros (el mismo para todas las estaciones)
        recorder                    Recorder                Para que la estacion genere logs
    
    Estado interno:
        _passenger_accumulator      float                   acumula produccion de pasajeros
        _vm_demand_acumulator       float                   acumula demanda de VMs (puede ser negativa)
        _walking                    dict                    pasajeros caminando dentro de la estación
        _next_passenger_id          int                     contador de IDs unico por estacion
        _next_platform_idx          int                     puntero rotativo sobre plataformas activas
    """

    def __init__(
        self,
        station_id:                 int,
        origin:                     Vector3,
        dimensions:                 StationDimensions,
        passenger_rate:             float,
        destination_probabilities:  dict,
        vm_request_rate:            float,
        platforms:                  list,
        rng:                        random.Random,
        id_generator:               PassengerIdGenerator,
        recorder,
    ):
        """
        Inicialisacion de una estación.
        """
        self.station_id                 = station_id
        self.origin                     = origin
        self.dimensions                 = dimensions
        self.passenger_rate             = passenger_rate
        self.destination_probabilities  = destination_probabilities
        self.vm_request_rate            = vm_request_rate
        self._rng                       = rng
        self._id_generator              = id_generator
        self._recorder                  = recorder
        

        # Cada dict recibido se copia añadiendo 'state': ACTIVE por defecto
        self._platforms: list[dict] = [
            {
                'lane':             a['lane'],
                'up_tree_id':       a['up_tree_id'],
                'down_tree_id':     a['down_tree_id'],
                'extraction_point': a['extraction_point'],
                'discharge_point':  a['discharge_point'],
                'state':            AndenState.ACTIVE,
            }
            for a in platforms
        ]

        self._passenger_accumulator:    float  = 0.0
        self._vm_demand_accumulator:    float  = 0.0
        self._walking:                  dict   = {}
        self._next_platform_idx:           int    = 0

    # ─── ACTUALIZACIÓN PRINCIPAL ──────────────────────────────────────────

    def update(self, dt: float, current_time: float) -> None:
        """
        Avanza un frame: mueve caminantes, genera pasajeros acumula demanda de VMs.
        El oden importa: avanzar caminantes antes de generar nuevos.
        """
        self._advance_walking_passengers(dt)
        self._accumulate_passengers(dt, current_time)
        self._accumulate_vm_demand(dt)

    # ─── INTERFAZ CON BRAIN ───────────────────────────────────────────────

    @property
    def pending_demand(self):
        """
        Balance de demanda de VMs (parte entera del acumulador):

            - Positivo: la estación necesita más VMs.
            - Cero: equilibrio.
            - Negativo: exceso de VMs llegando, Brain no debe solicitar más.
        
        Brain lee esto cada frame para decidir si debe marcar un slot.
        Solo lectura - Brain controla cuando se descuenta.
        """
        return int(self._vm_demand_accumulator)
    
    def on_vm_committed(self) -> None:
        """
        Brain comprometio exjitosamente un slot para esta estación.
        Se llama al confirmar la marca - garantiza qeu el VM va a llegar
        """
        self._vm_demand_accumulator -= 1.0

    def on_commitment_broken(self):
        """
        El VM comprometido fue rechazado por todos los arboles de esta estacion.
        Brain lo detecta al agotarse las opciones del arbol. Se restaura la demanda.
        """
        self._vm_demand_accumulator += 1.0

    def on_unplanned_vm_at_tree(self) -> None:
        """
        Un VM no marcado para demanda fue aceptado por un arbol de esta estacion
        Aplica cuando el VM sube por pasajeros, reserva o redirecionamiento forzado.
        Brain lo detecta en el momento de aceptacion del arbol y llama esto.
        Puede dejar el acumulator negativo - se autorregula con el tiempo.
        """
        self._vm_demand_accumulator -= 1.0
      
    # ─── GESTIÓN DE PLATFORMS ───────────────────────────────────────────────

    def activate_platform(self, platform_idx: int) -> None:
        """
        Activa la plataforma en la posicion platform_idx de self._platforms.
        """
        self._platforms[platform_idx]['state'] = AndenState.ACTIVE

    def deactivate_platform(self, platform_idx: int) -> None:
        """
        Desactiva la plataforma en la posicion platform_idx de self._platforms.

        Los pasajeros en caminata hacia esta plataforma son redirigidos.
        VMs que ya están en la lane o en los árboles continúan hasta completar su trayecto.
        Brain dejará de enrutar nuevos VMs por los árboles de esta plataforma (via active_down_tree_ids).
        """
        self._platforms[platform_idx]['state'] = AndenState.INACTIVE
        self._redirect_walking_passengers_from(platform_idx)

    def _redirect_walking_passengers_from(self, closed_platform_idx: int) -> None:
        """
        Redirige a los pasajeros en caminata que iban a la plataforma cerrada.
        Si no hay plataformas activas, los pasajeros conservan su plataforma original.
        """
        active = self.get_active_platforms()
        if not active:
            return
        closed_lane = self._platforms[closed_platform_idx]['lane']
        for data in self._walking.values():
            if data['target_lane'] is closed_lane:
                new_platform = self._select_platform(active)
                new_lane     = new_platform['lane']
                data['target_lane']   = new_lane
                data['walk_distance'] = self._walk_distance_to(new_lane)

    def get_active_platforms(self) -> list[dict]:
        """
        Retorna lista de plataformas activas.
        """
        return [a for a in self._platforms if a['state'] == AndenState.ACTIVE]

    # ─── INFORMACIÓN PARA BRAIN/NETWORK ───────────────────────────────────

    @property
    def active_down_tree_ids(self) -> list[int]:
        """ IDs de arboles de bajada de plataformas activas. Brain los usa para enviar VMs. """
        return [a['down_tree_id'] for a in self.get_active_platforms()]

    @property
    def active_up_tree_ids(self) -> list[int]:
        """ IDs de arboles de subida de plataformas activas. Brain los usa para enviar VMs. """
        return [a['up_tree_id'] for a in self.get_active_platforms()]
    
    @property
    def boarding_lanes(self) -> list[BoardingLane]:
        """ Todas las boarding lanes de la estacion, en orden de creacion. """
        return [a['lane'] for a in self._platforms]
    
    @property
    def x_bounds(self) -> tuple[float,float]:
        half = self.dimensions.x_length / 2
        return (self.origin.x - half, self.origin.x + half)
    
    @property
    def y_bounds(self) -> tuple[float,float]:
        half = self.dimensions.y_length / 2
        return (self.origin.y - half, self.origin.y + half)

    # ─── LÓGICA INTERNA ───────────────────────────────────────────────────

    def _accumulate_passengers(self,dt: float, current_time: float) -> None:
        """
        Acumula la producion de pasajeros
        El while maneja dt grandes: si se acumula 2.7 genera 2 pasajeros
        """
        self._passenger_accumulator += self.passenger_rate * dt
        while self._passenger_accumulator >= 1.0:
            self._passenger_accumulator -= 1.0
            self.spawn_pasenger(current_time)

    def spawn_pasenger(self, current_time: float) -> None:
        """
        Genera un pasajero y lo pone a caminar hacia la siguiente plataforma activa en rotación.
        Si no hay plataformas activas, el pasajero se descarta silenciosamente.
        """
        active = self.get_active_platforms()
        if not active:
            return

        destination = self._choose_destination()
        passenger = Passenger(
            passenger_id =              self._id_generator.next_id(),
            origin_station_id =         self.station_id,
            destination_station_id =    destination,
            spawn_time =                current_time,
        )
        # Logs de recorder
        self._recorder.passenger_spawned(
            t=current_time,
            passenger_id=passenger.passenger_id,
            origin_station_id=self.station_id,
            destination_station_id=destination,
        )
        

        passenger.start_moving_to_lane()

        target_platform = self._select_platform(active)
        lane = target_platform['lane']
        
        self._walking[passenger.passenger_id] = {
            'passenger':        passenger,
            'target_lane':      lane,
            'distance':         0.0,
            'walk_distance':    self._walk_distance_to(lane),
        }

    def _advance_walking_passengers(self,dt: float) -> None:
        """
        Avanza dt segundos a los pasajeros caminando.
        Al llegar al inicio del boarding lane, los encola en la lane correspondiente.
        """
        arrived = []
        for pid, data in self._walking.items():
            data['distance'] += PASSENGER_WALK_SPEED * dt
            if data['distance'] >= data['walk_distance']:
                arrived.append(pid)

        for pid in arrived:
            data = self._walking.pop(pid)
            data["target_lane"].enqueue_passenger(data["passenger"])       

    def _accumulate_vm_demand(self, dt: float) -> None:
        """
        Acumula demanda de VMs.
        """
        self._vm_demand_accumulator += self.vm_request_rate * dt
    
    def _select_platform(self, active_platforms: list) -> dict:
        """
        Round-robin sobre las plataformas activas.
        El modulo garantiza que el indice no salga del rango si cambia la cantidad de activos
        """
        idx = self._next_platform_idx % len(active_platforms)
        self._next_platform_idx +=1
        return active_platforms[idx]

    def _choose_destination(self) -> int:
        """
        Elige destiono segun los pesos de destination_probabilities.
        random.choices normaliza automaticamente - los pesos no necesitan sumar 1.
        """
        destinations = list(self.destination_probabilities.keys())
        weights = list(self.destination_probabilities.values())
        return self._rng.choices(destinations, weights=weights, k=1)[0]

    def _walk_distance_to(self, lane: BoardingLane) -> float:
        """
        Distancia euclidiand desde el origen de la estacion al inicio de la boarding lane.
        """
        s = lane.start_pos
        return ((s.x - self.origin.x)**2 +
                (s.y - self.origin.y)**2 + 
                (s.z - self.origin.z)**2) ** 0.5

    # ─── DEBUG ────────────────────────────────────────────────────────────

    def get_summary(self) -> dict:
        """
        Resumen del estado para mostrar al iniciar la simulación.
        Simulation/Brain imprime esto — Station no escribe en terminal directamente.
        """
        return {
            'station_id':           self.station_id,
            'origin':               self.origin,
            'platforms':            len(self._platforms),
            'active_platforms':     len(self.get_active_platforms()),
            'passenger_rate':       self.passenger_rate,
            'vm_request_rate':      self.vm_request_rate,
            'destinations':         self.destination_probabilities,
        }
    
    def __repr__(self) -> str:
        active = len(self.get_active_platforms())
        return (
            f"Station(id={self.station_id}, "
            f"platforms={len(self._platforms)} ({active} activos), "
            f"walking={len(self._walking)}, "
            f"vm_demand={self._vm_demand_accumulator:.2f})"
        )



