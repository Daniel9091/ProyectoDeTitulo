"""
SELECTOR DE ÁRBOLES DE ACELERACIÓN - GESTOR CENTRALIZADO DE ESTRATEGIAS

Responsabilidades PRINCIPALES:
- Aplicar diferentes estrategias para seleccionar árboles de aceleración
- Gestionar la saturación progresiva de andenes
- Proporcionar información de estado para monitoreo

Responsabilidades NO incluidas:
- Movimiento de vehículos (lo hace AccelerationTree)
- Navegación entre tracks (lo hace Network) 
- Gestión de estaciones (lo hace Station)
- Coordinación general (lo hace Brain)
"""

class TreeSelector:
    """
    GESTOR CENTRALIZADO DE SELECCIÓN DE ÁRBOLES
    Implementa el patrón Strategy para diferentes algoritmos de selección
    """
    
    def __init__(self, brain=None):
        # Configuración de estrategias disponibles
        self.strategies = {
            'progressive_saturation': self._progressive_saturation_strategy,
            'emergency_flow': self._emergency_flow_strategy,
            'round_robin': self._round_robin_strategy
        }
        self.brain = brain # Referencia al Brain
        
        # Estado interno para estrategias que requieren memoria
        self._last_used_trees = {}  # station_id -> último árbol usado
        
        print("✅ TreeSelector inicializado con estrategias:", list(self.strategies.keys()))
    
    def select_best_tree(self, trees, vehicle, strategy='progressive_saturation', station_id=None):
        """
        Selecciona el mejor árbol disponible según la estrategia especificada
        
        Args:
            trees: Lista de AccelerationTree disponibles
            vehicle: Vehículo que necesita un árbol
            strategy: Nombre de la estrategia a usar
            station_id: ID de la estación (opcional, para estrategias con estado)
            
        Returns:
            AccelerationTree: El árbol seleccionado, o None si no hay disponibles
        """
        if not trees:
            print("ERROR: TreeSelector: No hay árboles disponibles para seleccionar")
            return None
        
        # Validar que todos los árboles son de subida
        up_trees = [tree for tree in trees if tree.direction == "up"]
        if not up_trees:
            print("ERROR: TreeSelector: No hay árboles de subida en la lista")
            return None
        
        # Obtener la función de estrategia
        strategy_func = self.strategies.get(strategy)
        if not strategy_func:
            print(f"ADVERTENCIA  TreeSelector: Estrategia '{strategy}' no encontrada, usando 'progressive_saturation'")
            strategy_func = self._progressive_saturation_strategy
        
        # Aplicar la estrategia
        selected_tree = strategy_func(up_trees, vehicle, station_id)
        
        # Log del resultado
        if not selected_tree:
            print(f"ERROR: TreeSelector No se pudo seleccionar árbol con estrategia '{strategy}'")
            
        return selected_tree
    
    def _progressive_saturation_strategy(self, trees, vehicle, station_id=None):
        """
        ESTRATEGIA: Saturación progresiva - minimiza andenes abiertos
        
        Lógica:
        1. Ordenar árboles por uso (más usado primero)
        2. Intentar usar el más saturado primero
        3. Solo pasar al siguiente cuando el actual esté lleno
        
        Args:
            trees: Lista de árboles de subida
            vehicle: Vehículo a asignar
            station_id: ID de estación para tracking
            
        Returns:
            AccelerationTree: El árbol más saturado que pueda aceptar el vehículo
        """
        # Ordenar por cantidad de vehículos (más usado primero)
        sorted_trees = sorted(trees, 
                            key=lambda tree: len(tree.vehicles), 
                            reverse=True)
        
        # print(f"   🎯 Estrategia progresiva: Evaluando {len(sorted_trees)} árboles")
        
        # Intentar con el más usado primero (para saturar progresivamente)
        for tree in sorted_trees:
            if tree.can_accept_vehicle(vehicle):
                print(f"Árbol {tree.track_id} seleccionado (ocupación: {len(tree.vehicles)}/{tree.max_concurrent_vehicles})")
                return tree
            else:
                occupancy = tree.get_occupancy_info()
                print(f"ERROR: Árbol {tree.track_id} rechazado (ocupación: {occupancy['vehicle_count']}/{occupancy['max_vehicles']})")
                
        return None
    
    def _emergency_flow_strategy(self, trees, vehicle, station_id=None):
        """
        ESTRATEGIA: Flujo de emergencia - evita bloqueos
        
        Lógica:
        1. Cualquier árbol disponible es aceptable
        2. Prioriza mantener el flujo sobre la eficiencia
        3. Útil cuando los árboles están cerca de la saturación
        
        Args:
            trees: Lista de árboles de subida
            vehicle: Vehículo a asignar
            
        Returns:
            AccelerationTree: El primer árbol disponible
        """
        print(f"   🚨 Estrategia emergencia: Buscando cualquier árbol disponible")
        
        for tree in trees:
            if tree.can_accept_vehicle(vehicle):
                print(f"Árbol {tree.track_id} aceptado en modo emergencia")
                return tree
                
        return None
    
    def _round_robin_strategy(self, trees, vehicle, station_id=None):
        """
        ESTRATEGIA: Round Robin - distribución balanceada
        
        Lógica:
        1. Rotar entre árboles para distribución equitativa
        2. Usa memoria por estación para recordar último usado
        3. Útil cuando se quiere evitar saturación de un solo árbol
        
        Args:
            trees: Lista de árboles de subida
            vehicle: Vehículo a asignar
            station_id: ID de estación para tracking
            
        Returns:
            AccelerationTree: Siguiente árbol en la rotación
        """
        if not station_id:
            # Sin station_id, fallback a estrategia de emergencia
            return self._emergency_flow_strategy(trees, vehicle)
        
        print(f"Estrategia round-robin para estación {station_id}")
        
        # Ordenar árboles por ID para consistencia
        sorted_trees = sorted(trees, key=lambda tree: tree.track_id)
        
        # Encontrar el último árbol usado para esta estación
        last_used_index = self._last_used_trees.get(station_id, -1)
        
        # Buscar siguiente árbol disponible en la rotación
        for offset in range(len(sorted_trees)):
            next_index = (last_used_index + offset + 1) % len(sorted_trees)
            tree = sorted_trees[next_index]
            
            if tree.can_accept_vehicle(vehicle):
                self._last_used_trees[station_id] = next_index
                return tree
                
        return None
    
    def get_available_strategies(self):
        """
        Retorna lista de estrategias disponibles
        
        Returns:
            list: Nombres de las estrategias configuradas
        """
        return list(self.strategies.keys())
    
    def get_trees_status(self, trees):
        """
        Proporciona reporte unificado del estado de todos los árboles
        
        Args:
            trees: Lista de AccelerationTree a analizar
            
        Returns:
            dict: Estado consolidado de todos los árboles
        """
        status = {
            'total_trees': len(trees),
            'up_trees': len([t for t in trees if t.direction == 'up']),
            'down_trees': len([t for t in trees if t.direction == 'down']),
            'total_vehicles': 0,
            'total_capacity': 0,
            'available_trees': 0,
            'trees_detail': {}
        }
        
        for tree in trees:
            tree_info = tree.get_occupancy_info()
            status['total_vehicles'] += tree_info['vehicle_count']
            status['total_capacity'] += tree_info['max_vehicles']
            
            if tree.direction == 'up' and tree_info['available']:
                status['available_trees'] += 1
                
            status['trees_detail'][tree.track_id] = {
                'direction': tree.direction,
                'station_id': tree.station_id,
                'occupancy': tree_info
            }
        
        # Calcular tasa de ocupación general
        if status['total_capacity'] > 0:
            status['overall_occupancy_rate'] = status['total_vehicles'] / status['total_capacity']
        else:
            status['overall_occupancy_rate'] = 0.0
            
        return status
    
    def validate_tree_selection(self, trees, vehicle, strategy='progressive_saturation'):
        """
        Valida si es posible seleccionar un árbol sin realmente seleccionarlo
        
        Útil para pre-chequeos antes de asignar rutas
        
        Args:
            trees: Lista de árboles
            vehicle: Vehículo a verificar
            strategy: Estrategia a usar
            
        Returns:
            bool: True si hay al menos un árbol disponible
        """
        if not trees:
            return False
            
        # Usar la estrategia de emergencia para verificación rápida
        available_trees = [tree for tree in trees 
                          if tree.direction == "up" and tree.can_accept_vehicle(vehicle)]
        
        return len(available_trees) > 0
    
    def get_strategy_recommendation(self, trees, station_id=None):
        """
        Recomienda la mejor estrategia basada en el estado actual
        
        Args:
            trees: Lista de árboles a analizar
            station_id: ID de estación (opcional)
            
        Returns:
            str: Nombre de la estrategia recomendada
        """
        status = self.get_trees_status(trees)
        
        # Si hay pocos árboles disponibles, usar emergencia
        if status['available_trees'] == 0:
            return 'emergency_flow'
        
        # Si la ocupación general es alta, usar round-robin para distribuir
        if status['overall_occupancy_rate'] > 0.7:
            return 'round_robin'
        
        # Por defecto, usar saturación progresiva para eficiencia
        return 'progressive_saturation'