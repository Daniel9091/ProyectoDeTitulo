# Librerias y archivos importados
from objects.modular_vehicles import ModularVehicle
from objects.stations import Station
from objects.station_connector import StationConnector
from objects.acceleration_tree import AccelerationTree
from objects.network import Network
from objects.brain import Brain
from objects.base import Vector3
from simulation.camera import Camera
from simulation.spawn_system import SpawnSystem
from objects.tree_selector import TreeSelector
import pygame

class Simulation:
    def __init__(self, width, height):                                                          # Inicializa la simulación / Configuracion inicial
        
        self.camera = Camera(width, height)
        self.time_scale = 1.0
        self.show_info = True
        
        # Nuevos objetos del sistema
        self.network = Network()
        self.brain = Brain(self.network)
        self.stations = []
        self.vehicles = []
        self.connectors = []
        
        self.rewinding = False
        self.rewind_duration = 0
        self.rewind_start_time = 0
        self.pre_rewind_scale = 1.0
        self.last_time_scale = 1.0
        
        self.spawn_system = SpawnSystem()
        self.init_simulation()
    
    def init_simulation(self):
        # Limpieza completa
        self.vehicles.clear()
        self.stations.clear()
        self.connectors.clear()
        self.network.tracks.clear()
        self.network.adjacency.clear()
        self.network.entry_points.clear()
        self.network.exit_points.clear()
        self.brain.vehicles.clear()
        self.brain.stations.clear()
        
        # Usar el Builder para configurar la simulación
        builder = SimulationBuilder(self)
  
        try:
            # 1. Estaciones
            builder.add_station(1, "North Station", Vector3(425, 0, 0))
            builder.add_station(2, "Central Station", Vector3(1425, 0, 0))
            builder.add_station(3, "South Station", Vector3(2425, 0, 0))
            # (Estaciones cada 1km)

            # 2. Árboles de Aceleración
            # North
            builder.add_acceleration_tree(1, 1, Vector3(0, 0, -20), Vector3(400, 0, 0), "up")       # North UP
            builder.add_acceleration_tree(2, 1, Vector3(450, 0, 0), Vector3(850, 0, -20), "down")   # North Down

            # Central
            builder.add_acceleration_tree(3, 2, Vector3(1000.15, 0, -20), Vector3(1400.15, 0, 0), "up")   # Central UP
            builder.add_acceleration_tree(4, 2, Vector3(1449.85, 0, 0), Vector3(1850, 0, -20), "down") # Central Down

            ## Nuevos arboles de Aceleracion
            builder.add_acceleration_tree(16, 2, Vector3(1000.15, 0, -20), Vector3(1400, 10, 0), "up")   # Central UP 2
            builder.add_acceleration_tree(17, 2, Vector3(1450, 10, 0), Vector3(1850, 0, -20), "down") # Central Down 2

            builder.add_acceleration_tree(18, 2, Vector3(1000.15, 0, -20), Vector3(1400, -10, 0), "up")   # Central UP 3
            builder.add_acceleration_tree(19, 2, Vector3(1450, -10, 0), Vector3(1850, 0, -20), "down") # Central Down 3

            # South
            builder.add_acceleration_tree(5, 3, Vector3(2000, 0, -20), Vector3(2400, 0, 0), "up")   # South UP
            builder.add_acceleration_tree(6, 3, Vector3(2450, 0, 0), Vector3(2850, 0, -20), "down") # South Down

            # 3. Conectores Subterráneos (Entre arboles y estaciones)
            builder.add_connector(7, Vector3(0, 0, -20), Vector3(850, 0, -20))      # Entre Arboles North
            builder.add_connector(8, Vector3(850, 0, -20), Vector3(1000.15, 0, -20))   # Entre North y Central
            builder.add_connector(9, Vector3(1000.15, 0, -20), Vector3(1850, 0, -20))  # Entre Arboles Central
            builder.add_connector(10, Vector3(1850, 0, -20), Vector3(2000, 0, -20)) # Entre Central y South
            builder.add_connector(11, Vector3(2000, 0, -20), Vector3(2850, 0, -20)) # Entre Arboles South
            # Para hacer Efecto Dona
            builder.add_connector(12, Vector3(2850, 0, -20), Vector3(2900, 0, -20)) # Fin South

            # 4. Conectores en la estacion
            builder.add_connector(13, Vector3(400, 0, 0), Vector3(450, 0, 0),1)       # En North Station
            builder.add_connector(14, Vector3(1400.15, 0, 0), Vector3(1449.85, 0, 0),1)     # En Central Station
            builder.add_connector(15, Vector3(2400, 0, 0), Vector3(2450, 0, 0),1)     # En South Station
            # Nuevos andenes en Central
            builder.add_connector(20, Vector3(1400, 10, 0), Vector3(1450, 10, 0),1)     # En Central Station 2
            builder.add_connector(21, Vector3(1400, -10, 0), Vector3(1450, -10, 0),1)     # En Central Station 3

            # 5. Conexiones de los conectores entre si
            builder.connect_tracks(7, 8)   
            builder.connect_tracks(8, 9)  
            builder.connect_tracks(9, 10)
            builder.connect_tracks(10, 11)
            # Efecto Dona
            builder.connect_tracks(11, 12)
            builder.connect_tracks(12, 7)

            # 6. Conexiones de los arboles con los conectores
            builder.connect_tracks(2, 8)   # Track North Down ->  Track Entre North y Central
            builder.connect_tracks(8, 3)   # Entre North y Central -> Track Central Up
            builder.connect_tracks(4, 10)  # Track Central Down -> Track Entre Central
            builder.connect_tracks(10, 5)  # Entre Central y South -> Track South Up
            # Arboles 2 y 3 central
            builder.connect_tracks(8,16)    # Entre North y Central -> Track Central Up 2
            builder.connect_tracks(8,18)    # Entre North y Central -> Track Central Up 3
            builder.connect_tracks(17,10)   # Track Central Down 2 -> Track Entre Central y South
            builder.connect_tracks(19,10)   # Track Central Down 3 -> Track Entre Central y South

            # Arboles del principio y final
            builder.connect_tracks(6, 12)   # Track South Down -> Fin South
            builder.connect_tracks(12,1)    # Fin South -> Track North Up

            # Conectores de las estaciones con los arboles
            builder.connect_tracks(1, 13)   # Track North Up -> En North Station
            builder.connect_tracks(13, 2)   # En North Station -> Track North Down
            builder.connect_tracks(3, 14)   # Track Central Up -> En Central Station
            builder.connect_tracks(14, 4)   # En Central Station -> Track Central Down
            builder.connect_tracks(5, 15)   # Track South Up -> En South Station
            builder.connect_tracks(15, 6)   # En South Station -> Track South Down
            # Arboles extra en Central
            builder.connect_tracks(16, 20)   # Track Central Up 2 -> En Central Station 2
            builder.connect_tracks(20, 17)   # En Central Station 2 -> Track Central Down 2
            builder.connect_tracks(18, 21)   # Track Central Up 3 -> En Central Station 3
            builder.connect_tracks(21, 19)   # En Central Station 3 -> Track Central Down 3

            
            # 6. Incorporacion de Vehiculos
            ## Creacion del Vehiculo

            # builder.add_vehicle(1, 20, 2,2)         # VM1: Estación 1 → Estación 2 (DESTINO FINAL)
            # builder.start_vehicle_on_track(1, 2)    # VM1 en árbol de salida Estación 1

            # builder.add_vehicle(2, 20, 2)           # VM2: Estación 2 → Sin destino (usará bucles)
            # builder.start_vehicle_on_track(2, 4)    # VM2 en árbol de salida Estación 3


            # # Test demoran mismo tiempo en llegar a la estacion central (Cambiar ID en caso de ser nesesario)
            # builder.add_vehicle(3, 20, 2)           
            # builder.start_vehicle_on_track(3, 3)

            # builder.add_vehicle(4, 20, 2)           
            # builder.start_vehicle_on_track(4, 16)

            # builder.add_vehicle(5, 20, 2)           
            # builder.start_vehicle_on_track(5, 18)

            # # Test demoran mismo tiempo en llegar nodo de via subterranea (Cambiar ID en caso de ser nesesario)
            # builder.add_vehicle(6, 20, 2)           
            # builder.start_vehicle_on_track(6, 4)

            # builder.add_vehicle(7, 20, 2)           
            # builder.start_vehicle_on_track(7, 17)

            # builder.add_vehicle(8, 20, 2)           
            # builder.start_vehicle_on_track(8, 19)

            # Spawn System (Opcional)
            self.spawn_system.add_spawn_point(
            spawn_id="S",
            track_id=7,  # Track Inicial (conector subterráneo)
            spawn_interval=0.6,  # Cada x segundos sale un nuevo VM (ideal 0.075)
            max_vehicles=100,     # Máximo 210 VMs 
            vehicle_capacity=2, # Capacidad de cada VM
            destination_station_id=2  # Sin destino fijo
        )
            
            # Test
            # builder.add_vehicle(6, 20, 2, 2)           
            # builder.start_vehicle_on_track(6, 4)
            
            # 7. Iniciar tree selector y asignar a red y estaciones
            tree_selector = TreeSelector()
            self.network.set_tree_selector(tree_selector)
            for station in self.stations:
                station.set_tree_selector(tree_selector)


            # Validar que las estaciones tienen árboles configurados
            for station in self.stations:
                if not station.arrival_trees:
                    print(f"ADVERTENCIA: {station.name} no tiene árboles de llegada")
                if not station.departure_trees:
                    print(f"ADVERTENCIA: {station.name} no tiene árboles de salida")
            
            print("Sistema de navegación completamente configurado")

            # 8. Validar
            builder.validate_network()

            # 9. Mostrar resumen
            summary = builder.get_summary()
            print("=== CONFIGURACIÓN COMPLETADA ===")
            print(f"Estaciones: {summary['stations']}")
            print(f"Tracks: {summary['tracks']}") 
            print(f"Vehículos: {summary['vehicles']}")
            print(f"Conexiones: {summary['connections']}")

        except (ValueError, RuntimeError) as e:
            print(f"ERROR en configuración: {e}")
            import traceback
            traceback.print_exc()
            self.vehicles.clear()
            self.stations.clear()
            self.connectors.clear()

    def update(self, dt):                                                                       # Acutaliza la simulacion basada en el tiempo real
        # Escalar delta time por la escala de tiempo
        scaled_dt = dt * self.time_scale

        # Actualizar sistema de spawn antes de Brain
        self.spawn_system.update(self, scaled_dt)
        
        # Usar Brain para actualizar todo el sistema
        if self.rewinding:
            current_time = pygame.time.get_ticks() / 1000.0
            elapsed = current_time - self.rewind_start_time
            if elapsed < self.rewind_duration:
                # Rebobinado temporal (simplificado)
                self.brain.update(-scaled_dt * 2.0)
            else:
                self.rewinding = False
                self.time_scale = self.pre_rewind_scale
        else:
            # Actualización normal usando Brain
            self.brain.update(scaled_dt)

    def handle_command(self, command):                                                          # Maneja comandos de entrada para controlar la simulación y la cámara       
        # Control de escala de tiempo
        if command == "time_scale_up":
            sign = 1 if self.time_scale >= 0 else -1
            self.time_scale = sign * min(10.0, abs(self.time_scale) * 1.5)
        
        elif command == "time_scale_down":
            sign = 1 if self.time_scale >= 0 else -1
            new_scale = abs(self.time_scale) / 1.5
            self.time_scale = sign * max(0.1, new_scale) if new_scale > 0.1 else sign * 0.0

        # Reiniciar simulación
        elif command == "reset_simulation":
            self.init_simulation()
            self.time_scale = 1.0

        # Rebobinar tiempo temporalmente
        elif command == "rewind_temporary":
            self.rewinding = True
            self.rewind_duration = 1.0
            self.rewind_start_time = pygame.time.get_ticks() / 1000.0
            self.pre_rewind_scale = self.time_scale
        
        # Pausa y reanudación del tiempo
        elif command == "time_pause":
            if self.time_scale != 0:
                self.last_time_scale = self.time_scale
                self.time_scale = 0
            else:
                self.time_scale = self.last_time_scale

        # Controles para velocidad de movimiento    
        elif command == "increase_move_speed":
            self.camera.move_speed *= 1.5
        elif command == "decrease_move_speed":
            self.camera.move_speed = max(10.0, self.camera.move_speed / 1.5)
            
        # Controles para velocidad vertical
        elif command == "increase_vertical_speed":
            self.camera.vertical_move_speed *= 1.5
        elif command == "decrease_vertical_speed":
            self.camera.vertical_move_speed = max(10.0, self.camera.vertical_move_speed / 1.5)
            
        # Controles para velocidad de rotación
        elif command == "increase_rotation_speed":
            self.camera.rotation_speed *= 1.5
        elif command == "decrease_rotation_speed":
            self.camera.rotation_speed = max(10.0, self.camera.rotation_speed / 1.5)
            
        # Controles para velocidad de zoom
        elif command == "increase_zoom_speed":
            self.camera.zoom_speed = min(1.0, self.camera.zoom_speed * 1.5)
        elif command == "decrease_zoom_speed":
            self.camera.zoom_speed = max(0.1, self.camera.zoom_speed / 1.5)

class SimulationBuilder:
    """
    CONSTRUCTOR DE SIMULACIONES - Patrón Builder
    Responsable de crear y conectar todos los componentes del sistema
    """
    
    def __init__(self, simulation):
        self.simulation = simulation
        self.stations = {}
        self.tracks = {}
        
    def add_station(self, station_id, name, position):
        """Agrega una estación al sistema"""
        station = Station(station_id, name, position)
        self.stations[station_id] = station
        self.simulation.stations.append(station)
        self.simulation.brain.add_station(station)
        return self  # Para método fluido
    
    def add_acceleration_tree(self, tree_id, station_id, start_pos, end_pos, direction):
        """Agrega un árbol de aceleración a una estación"""
        if station_id not in self.stations:
            raise ValueError(f"Estación {station_id} no existe")
            
        tree = AccelerationTree(tree_id, start_pos, end_pos, direction, station_id)
        station = self.stations[station_id]
        
        if direction == "down":
            station.add_departure_tree(tree)
        else:
            station.add_arrival_tree(tree)
            
        self.tracks[tree_id] = tree
        self.simulation.network.add_track(tree)
        return self
    
    def add_connector(self, connector_id, start_pos, end_pos, speed=20.0):
        """Agrega un conector entre puntos"""
        connector = StationConnector(connector_id, start_pos, end_pos, speed)
        self.tracks[connector_id] = connector
        self.simulation.connectors.append(connector)
        self.simulation.network.add_track(connector)
        return self
    
    def connect_tracks(self, from_track_id, to_track_id):
        """Conecta dos tracks en la red"""
        if from_track_id not in self.tracks or to_track_id not in self.tracks:
            raise ValueError("Track IDs no existen")
            
        self.simulation.network.connect_tracks(from_track_id, to_track_id)
        return self
    
    def add_vehicle(self, vehicle_id, capacity, start_station_id, destination_station_id=None):
        """Agrega un vehículo con ruta opcional"""
        if start_station_id not in self.stations:
            raise ValueError(f"Estación inicial {start_station_id} no existe")
            
        start_station = self.stations[start_station_id]
        vehicle = ModularVehicle(vehicle_id, capacity, start_station.position)
        
        # Si se especifica destino, asignar ruta
        if destination_station_id:
            if destination_station_id not in self.stations:
                raise ValueError(f"Estación destino {destination_station_id} no existe")
                
            destination_station = self.stations[destination_station_id]
            success = self.simulation.brain.assign_vehicle_to_route(vehicle, start_station, destination_station)
            if not success:
                raise RuntimeError(f"No se pudo asignar ruta al vehículo {vehicle_id}")
        
        self.simulation.brain.add_vehicle(vehicle)
        self.simulation.vehicles.append(vehicle)
        return self
    
    def start_vehicle_on_track(self, vehicle_id, track_id):
        """Posiciona un vehículo directamente en un track"""
        vehicle = None
        for v in self.simulation.vehicles:
            if v.vehicle_id == vehicle_id:
                vehicle = v
                break
                
        if not vehicle:
            raise ValueError(f"Vehículo {vehicle_id} no encontrado")
            
        if track_id not in self.tracks:
            raise ValueError(f"Track {track_id} no encontrado")
            
        track = self.tracks[track_id]
        
        # Remover de estación si está docked
        if vehicle.current_station and vehicle.state == "docked":
            station = self.stations.get(vehicle.current_station)
            if station and vehicle in station.docked_vehicles:
                station.docked_vehicles.remove(vehicle)
        
        # Agregar al track
        track.add_vehicle(vehicle)
        vehicle.current_track = track
        
        # Actualizar estado según tipo de track
        if isinstance(track, AccelerationTree):
            vehicle.state = "accelerating_down" if track.direction == "down" else "accelerating_up"
        else:
            vehicle.state = "moving"
            
        return self
    
    def validate_network(self):
        """Valida que la red esté correctamente conectada"""
        issues = []
        
        # Verificar que todos los tracks tienen conexiones de salida o son endpoints válidos
        for track_id, track in self.tracks.items():
            connections = self.simulation.network.adjacency.get(track_id, [])
            
            if not connections and not isinstance(track, AccelerationTree):
                issues.append(f"Track {track_id} no tiene conexiones de salida")
            elif not connections and isinstance(track, AccelerationTree) and track.direction == "down":
                issues.append(f"Árbol de salida {track_id} no tiene conexiones")
        
        # Verificar que las estaciones tienen árboles
        for station_id, station in self.stations.items():
            if not station.departure_trees:
                issues.append(f"Estación {station_id} no tiene árboles de salida")
            if not station.arrival_trees:
                issues.append(f"Estación {station_id} no tiene árboles de llegada")
        
        if issues:
            print("ADVERTENCIAS DE VALIDACIÓN:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("✓ Red validada correctamente")
            
        return self
    
    def get_summary(self):
        """Retorna un resumen de la configuración"""
        return {
            "stations": len(self.stations),
            "tracks": len(self.tracks),
            "vehicles": len(self.simulation.vehicles),
            "connections": sum(len(conn) for conn in self.simulation.network.adjacency.values())
        }
