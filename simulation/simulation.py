# Librerias y archivos importados
from objects.modular_vehicles import ModularVehicle
from objects.stations import Station
from objects.station_connector import StationConnector
from objects.acceleration_tree import AccelerationTree
from objects.network import Network
from objects.brain import Brain
from objects.base import Vector3
from simulation.camera import Camera
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
            # CONFIGURACIÓN CON DIMENSIONES REALES Y SENTIDO ÚNICO
            
            # 1. ESTACIONES 
            builder.add_station(1, "North Station", Vector3(0, 0, 0))
            builder.add_station(2, "Central Station", Vector3(1000, 0, 0))
            builder.add_station(3, "South Station", Vector3(2000, 0, 0))
            
            # 2. ÁRBOLES DE ACELERACIÓN 
            # North: solo árbol de bajada
            builder.add_acceleration_tree(1, 1, Vector3(0, 0, 0), Vector3(400, 0, -20), "down")
            # Central: árbol de subida y bajada
            builder.add_acceleration_tree(4, 2, Vector3(600, 0, -20), Vector3(1000, 0, 0), "up")
            builder.add_acceleration_tree(2, 2, Vector3(1000, 0, 0), Vector3(1400, 0, -20), "down")
            # South: solo árbol de subida
            builder.add_acceleration_tree(5, 3, Vector3(1600, 0, -20), Vector3(2000, 0, 0), "up")
            
            # 3. CONECTORES SUBTERRÁNEOS
            builder.add_connector(7, Vector3(400, 0, -20), Vector3(600, 0, -20))
            builder.add_connector(8, Vector3(1400, 0, -20), Vector3(1600, 0, -20))
            
            # 4. CONEXIONES DE LA RED
            builder.connect_tracks(1, 7)   # North down -> connector7
            builder.connect_tracks(7, 4)   # connector7 -> Central up
            builder.connect_tracks(2, 8)   # Central down -> connector8
            builder.connect_tracks(8, 5)   # connector8 -> South up
            
            # 5. VEHÍCULOS 
            builder.add_vehicle(1, 20, 1, 2)  # VM1: North -> Central
            builder.add_vehicle(2, 20, 2, 3)  # VM2: Central -> South
            
            # 6. INICIAR VEHÍCULOS EN ESTACIONES (docked)
            # No es necesario iniciarlos en tracks, porque se asignan a estaciones y luego se les da destino.
            
            # Validar configuración
            builder.validate_network()
            
            # Mostrar resumen
            summary = builder.get_summary()
            print("=== CONFIGURACIÓN CON SENTIDO ÚNICO ===")
            print(f"Estaciones: {summary['stations']}")
            print(f"Tracks: {summary['tracks']}") 
            print(f"Vehículos: {summary['vehicles']}")
            print(f"Conexiones: {summary['connections']}")
            
            # INFORMACIÓN DE FÍSICA
            print("\n=== FÍSICA DE ÁRBOLES ===")
            for track_id, track in builder.tracks.items():
                if hasattr(track, 'get_track_type') and track.get_track_type() == "AccelerationTree":
                    print(f"Árbol {track_id} ({track.direction}):")
                    print(f"  - Longitud: {track.length:.1f}m")
                    print(f"  - Ángulo: {track.get_angle_degrees():.1f}°")
                    print(f"  - Aceleración: {track.acceleration:.2f}m/s²")
                    if track.direction == "down":
                        print(f"  - Velocidad final: {track.final_velocity:.1f}m/s")
                    else:
                        print(f"  - Velocidad inicial: {track.initial_velocity:.1f}m/s")

            print("\n=== CONECTORES SUBTERRÁNEOS ===")
            for track_id, track in builder.tracks.items():
                if hasattr(track, 'get_track_type') and track.get_track_type() == "StationConnector":
                    print(f"Conector {track_id}:")
                    print(f"  - Longitud: {track.length:.1f}m")
                    print(f"  - Velocidad: {track.speed}m/s")
                    print(f"  - Dirección: {track.direction}")
            
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
