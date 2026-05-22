"""
Junction - Punto de conexión entre el ContinuousTrain y un grupo de AccelerationTrees.

Responsabilidades:
    - Agrupar árboles que comparten el mismo belt_x de entrada/salida
    - UP: routing de VMs al árbol con menor carga, respetando saturación física
    - DOWN: distribución de VMs por carga mínima (DOWN trees no saturan)
    - Exponer burst_capacity y burst_window para el sistema de reserva

Lo que NO hace:
    - No implementa el sliding-window check del 'Problema Destino Terminal'
        (ese check vive en el sistema de reserva; Juction solo expone burst_capacity y burst_window)
    - No conoce ConinuousTrain ni Station
    - No tine update() - sus árboles son actalizados por Network/Brain
"""

from tracks.acceleration_tree import AccelerationTree
from objects.types import TreeDirection

class Junction:
    """
    Punto físico en el belt donde confluyen AccelerationTrees de una estación.

    Cada estación tiene dos Junctions:
        UP (belt_x_entry):  VMs salen del belt hacia la estación - gestiona saturación
        DOWN (belt_x_exit): Vms llegan al belt desde la estación - solo distribuye

    Capacidad de absorción (para 'Problema Destino Terminal):
        burst_capacity  - VMs absorbibles de corrido = len(trees)
        burst_window    - slots hasta recargar capacidad = trees[0]. min_slot_gap (UP) / 0 (DOWN)

    Atributos:
        junction_id     int                         identificador único
        belt_x          float                       posición en el carril circular (metros)
        station_id      int                         estación a la que pertence
        direction       TreeDirection               UP o DOWN
        trees           list[AccelerationTree]      árboles gestionados por esta junction
    """

    def __init__(
      self,
      junction_id: int,
      belt_x: float,
      station_id: int,
      direction: TreeDirection,
      trees: list[AccelerationTree]
    ):
        self.junction_id = junction_id
        self.belt_x = belt_x
        self.station_id = station_id
        self.direction = direction
        self.trees = trees
    
    # ── ROUTING ─────────────────────────────────────────────────────────

    def can_accept(self) -> bool:
        """
        True si al menos un árbol puede recibir un nuevo VM.
        Para DOWN siempre True (DOWN trees no saturan).
        """
        return any(tree.can_accept() for tree in self.trees)
    
    def add_vm(self, vehicle, leftover_dt:float = 0.0) -> bool:
        """
        Enruta el VM al árbol disponible con menor carga.
        Retorna False si todos los árboles UP están saturados.
        Para DOWN siempre retorna True.
        """
        for tree in sorted(self.trees, key = lambda t: t.vehicle_count):
            if tree.add_vehicle(vehicle, leftover_dt=leftover_dt):
                return True
        return False
    
    def force_add_vm(self, vehicle, leftover_dt:float = 0.0) -> None:
        """
        Fuerza la entrada del VM al árbol menos saturado, ignorando can_accept().
        Brain llama esto cuando add_vm retorno False y el VM tiene reserva.
        Delega el [ADVERTENCIA] al AccelerationTree correspondiente.
        """
        self._least_saturated_tree().force_add_vehicle(vehicle, leftover_dt=leftover_dt)

    # ── CAPACIDAD DE ABSORCIÓN ───────────────────────────────────────────

    @property
    def burst_capacity(self) -> int:
        """
        VMs que esta junction puede absorber de corrido = número de árboles
        """
        return len(self.trees)
    
    @property
    def burst_window(self) -> int:
        """
        Slots que deben transcurrir para que la capacidad se recargue por completo.
        Para UP: derivado de min_slot_gap del árbol (ya incorpora math.ceil).
        Para DOWN: 0 (sin saturación).

        IMPORTANTE:
        Asume que todos los UP trees tienen el mismo min_slot_gap.
        """
        if self.direction == TreeDirection.UP and self.trees:
            return self.trees[0].min_slot_gap
        return 0
    
    # ── ESTADO ──────────────────────────────────────────────────────────
    @property
    def vehicle_count(self) -> int:
        return sum(tree.vehicle_count for tree in self.trees)
    
    # ── PRIVADOS ─────────────────────────────────────────────────────────

    def _least_saturated_tree(self) -> AccelerationTree:
        """
        Árbol donde el VM más joven está más avanzado - el más seguro para entrada forzada.
        un árbol vacío tiene distancia inf y siempre gana.
        """
        def youngest_distance(tree: AccelerationTree) -> float:
            if not tree.vehicles:
                return float('inf')
            return min(data['distance'] for data in tree.vehicles.values())
        return max(self.trees, key=youngest_distance)

    def __repr__(self) -> str:
        return(
            f"Junction(id={self.junction_id}, "
            f"belt_x={self.belt_x:.1f}, "
            f"station={self.station_id}, "
            f"dir={self.direction.value}, "
            f"trees={len(self.trees)}, "
            f"burst={self.burst_capacity}/{self.burst_window})"
        )


