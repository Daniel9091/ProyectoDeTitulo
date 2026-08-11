"""
Network - Grafo de tracks superiores del sistema de transporte.

Responsabilidades:
    - Contener la topología completa: AccelerationTrees, BoardingLanes y Junctions
    - Mover todos los tracks cada frame (update_all_tracks)
    - Ejecutar transiciones mecánicas (un solo próximo track: sin decisión)
    - Reportar a Brain las transiciones que requieren decisión (N próximos tracks)
    - Reportar a Brain completions de DOWN trees para colocación en belt
    - Consultor de Brain: lookups de junctions, conteos, IDs de estaciones

Lo que NO hace:
    - No decide si un VM sube al árbol (Brain lee etiquetas del slot y decide)
    - No gestiona pasajeros ni demanda
    - No predice colisiones
    - No orquesta el loop principal (eso es Brain)

Topología de adyacencia (uno a muchos):
    adjacency[track_id] = [next_track_id, ...]
    - len == 1 -> transición mecánica, Network la ejecuta
    - len >  1 -> decisión de Brain (ej: dos DOWN trees para dos trenes)
    - len == 0 -> track terminal -> Brain decide qué hacer (actualmente: si es
                  AccelerationTree DOWN con station_id, Brain lo coloca en el belt)

IMPORTANTE: Junction DOWN NO es un track de tránsito. Es un punto de referencia
    geográfico (belt_x). Brain usa junction_down.belt_x para calcular qué slot reservar
    y luego llama train.place_vm() directamente. Por eso los DOWN trees tienen len == 0
    en la adyacencia — no hay "siguiente track" porque el VM sale al belt, no a otro track.

    Junction UP y Junction DOWN NO están en la adyacencia. Brain llama
    junction_up.add_vm() directamente cuando decide transferir un VM al árbol.
    Network solo las almacena como referencias para que Brain las consulte.

Arquitectura futura (dos trenes paralelos, peak hour):
    Un mismo BoardingLane puede recibir de múltiples UP trees y conectar a múltiples
    DOWN trees. La adyacencia lo soporta sin cambios de diseño:
        adjacency[lane.id] = [down_tree_A.id, down_tree_B.id]  → Brain elige
    Los árboles DOWN del tren contrario también tendrán len == 0 (terminales al belt B).
"""

from tracks.base import BaseTrack
from objects.types import TreeDirection
from tracks.junction import Junction
from tracks.acceleration_tree import AccelerationTree
from objects.modular_vehicle import ModularVehicle

class Network:
    """
    Gestiona la topología de tracks superiores y ejecuta transiciones mecánicas.
    
    Brain es responsable del loop principal. Network es un subsistema que Brain
    consulta y ordena — no orquesta por su cuenta.
    """

    def __init__(self):
        self.tracks:        dict[int, BaseTrack]    = {}
        self.adjacency:     dict[int, list[int]]    = {}
        self.junctions_up:  dict[int, Junction]     = {}
        self.junctions_down:dict[int, Junction]     = {}

    # -------------------------------------------------------------------------
    # CONSTRUCCIÓN DE TOPOLOGÍA
    # -------------------------------------------------------------------------

    def add_track(self, track: BaseTrack) -> None:
        """
        Registra un track. Si no tiene adyacencia aún, se inicializa vacía
        (terminal).
        """

        self.tracks[track.track_id] = track
        if track.track_id not in self.adjacency:
            self.adjacency[track.track_id] = []
        
    def connect(self, from_id: int, to_id: int) -> None:
        """
        Agrega una arista dirigida en el grafo: from_id -> to_id.
        Ambos tracks deben estar registrados antes de conectarlos.
        """
        if from_id not in self.tracks:
            raise ValueError(f"Track {from_id} no registrado en Network")
        if to_id not in self.tracks:
            raise ValueError(f"Track {to_id} no registrado en Network")
        if to_id not in self.adjacency[from_id]:
            self.adjacency[from_id].append(to_id)
    
    def add_junction(self, junction: Junction) -> None:
        """
        Registra una Junction como punto de referencia geográfico.
        Las Junctions no entran en la adyacencia - no son tracks de tránsito.
        Brain las consulta via get_junction_up() / get_junction_down().
        """
        if junction.direction == TreeDirection.UP:
            self.junctions_up[junction.station_id] = junction
        else:
            self.junctions_down[junction.station_id] = junction

    # -------------------------------------------------------------------------
    # LOOP PRINCIPAL — llamado por Brain en orden fijo
    # -------------------------------------------------------------------------

    def update_all_tracks(self, dt: float, current_time: float = 0.0) -> list[tuple[ModularVehicle, int, float]]:
        """
        Avanza todos los tracks dt segundos y recolecta completions.

        Retorna list[(vm, track_id, leftover_dt)] - VMs que completaron su track este frame.
        No transfiere VMs al próximo track aquí. Solo recolecta.

        Debe llamarse ANTES de que Brain procese los junction crossings del ContinuousTrain
        (antes del paso de junction routing). Esto evita el bug de doble movimiento:
        un VM que Brain transfiere a un UP tree en este tick NO se mueve hasta el tick
        siguiente - su leftover_dt queda almacenado como initial_distance en add_vehicle().
        """
        completions: list[tuple[ModularVehicle, int, float]] = []
        for track_id, track in self.tracks.items():
            finished = track.update(dt, current_time)
            for vm, leftover in finished:
                completions.append((vm, track_id, leftover))
        return completions
    
    def process_transitions(
            self,
            completions: list[tuple[ModularVehicle, int, float]],
    ) -> tuple[
        list[tuple[ModularVehicle, list[int], float]],
        list[tuple[ModularVehicle, float, int | None]],
        ]:
        """
        Procesa los VMs que completaron un track y ejecuta transiciones mecánicas.

        Para cada (vm, track_id, leftover_dt):
            - len == 1 -> transicion mecánica: Network transfiere el VM directamente.
            - len >  1 -> decisión de Brain: incluido en `decisions` sin transferir.
            - len == 0 -> track terminal: incluido en `belt_placements` para Brain.
                          Brain verifica station_id antes de colocar en belt:
                          si station_id es None, Brain no intenta colocarlo.

        Retorna:
            - decisions:        list[(vm, [next_track_ids], leftover_dt)]
            - belt_placements:  list[(vm, leftover_dt, station_id)]
                                station_id proviene de AccelerationTree.station_id.
                                Puede ser None si el árbol no tiene estación asignada
                                (indicativo de error de configuración de la red)
        """
        decisions: list[tuple[ModularVehicle, list[int], float]] = []
        belt_placements: list[tuple[ModularVehicle, float, int | None]]= []

        for vm, track_id, leftover in completions:
            next_ids = self.adjacency.get(track_id, [])

            if len(next_ids) == 1:
                next_track = self.tracks[next_ids[0]]
                next_track.add_vehicle(vm, leftover_dt=leftover)
            
            elif len(next_ids) > 1:
                decisions.append((vm, list(next_ids), leftover))

            else:
                station_id: int | None = None
                source_track = self.tracks.get(track_id)
                if isinstance(source_track, AccelerationTree):
                    station_id = source_track.station_id
                belt_placements.append((vm, leftover, station_id))
        
        return decisions, belt_placements

    # -------------------------------------------------------------------------
    # CONSULTAS — usadas por Brain
    # -------------------------------------------------------------------------

    def get_junction_up(self, station_id: int) -> Junction | None:
        """
        Junction UP de la estación dada, o None si no existe.
        """
        return self.junctions_up.get(station_id)

    def get_junction_down(self, station_id: int) -> Junction | None:
        """
        Junction DOWN de la estación dada, o None si no existe.
        """
        return self.junctions_down.get(station_id)

    def get_track(self, track_id: int) -> BaseTrack | None:
        """Track por ID, o None si no existe."""
        return self.tracks.get(track_id)
    
    def get_all_station_ids(self) -> list[int]:
        """
        IDs de todas las estaciones con al menos una Junction registrada.
        """
        return list(set(self.junctions_up.keys()) | set(self.junctions_down.keys()))
    
    @property
    def total_vehicle_count(self) -> int:
        """Número total de VMs en todos los tracks del grafo."""
        return sum(track.vehicle_count for track in self.tracks.values())

    # DEBUG
    def __repr__(self) -> str:
        return (
            f"Network("
            f"tracks={len(self.tracks)}, "
            f"stations={len(self.get_all_station_ids())}, "
            f"vehicles={self.total_vehicle_count})"
        )
