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
        
        # CREAR ESTACIONES
        station1 = Station(1, "Central Station", Vector3(100, 0, 0))
        station2 = Station(2, "North Station", Vector3(400, 0, 0))
        station3 = Station(3, "South Station", Vector3(700, 0, 0))
        
        self.stations.extend([station1, station2, station3])
        
        # AGREGAR ESTACIONES AL BRAIN PRIMERO
        for station in self.stations:
            self.brain.add_station(station)
        
        # CREAR ÁRBOLES DE ACELERACIÓN/DESACELERACIÓN
        # Árboles de BAJADA (salida)
        accel_tree1 = AccelerationTree(1, Vector3(100, 0, 0), Vector3(150, 0, -20), "down", station_id=1)
        accel_tree2 = AccelerationTree(2, Vector3(400, 0, 0), Vector3(450, 0, -20), "down", station_id=2)
        accel_tree3 = AccelerationTree(3, Vector3(700, 0, 0), Vector3(750, 0, -20), "down", station_id=3)
        
        # Árboles de SUBIDA (llegada)
        decel_tree1 = AccelerationTree(4, Vector3(50, 0, -20), Vector3(100, 0, 0), "up", station_id=1)
        decel_tree2 = AccelerationTree(5, Vector3(350, 0, -20), Vector3(400, 0, 0), "up", station_id=2)
        decel_tree3 = AccelerationTree(6, Vector3(650, 0, -20), Vector3(700, 0, 0), "up", station_id=3)
        
        # ASIGNAR ÁRBOLES A ESTACIONES
        station1.add_departure_tree(accel_tree1)
        station1.add_arrival_tree(decel_tree1)
        
        station2.add_departure_tree(accel_tree2)
        station2.add_arrival_tree(decel_tree2)
        
        station3.add_departure_tree(accel_tree3)
        station3.add_arrival_tree(decel_tree3)
        
        # AGREGAR TODOS LOS ÁRBOLES A LA RED
        trees = [accel_tree1, accel_tree2, accel_tree3, decel_tree1, decel_tree2, decel_tree3]
        for tree in trees:
            self.network.add_track(tree)
        
        # CREAR STATION CONNECTORS
        connector1 = StationConnector(7, Vector3(150, 0, -20), Vector3(350, 0, -20), speed=20.0)
        connector2 = StationConnector(8, Vector3(450, 0, -20), Vector3(650, 0, -20), speed=20.0)
        
        self.connectors.extend([connector1, connector2])
        
        # AGREGAR CONNECTORS A LA RED
        for connector in self.connectors:
            self.network.add_track(connector)
        
        # CONFIGURAR RED COMPLETA DE CONEXIONES
        # Ruta: Estación 1 → Estación 2
        self.network.connect_tracks(1, 7)  # accel_tree1 -> connector1
        self.network.connect_tracks(7, 5)  # connector1 -> decel_tree2
        
        # Ruta: Estación 2 → Estación 3
        self.network.connect_tracks(2, 8)  # accel_tree2 -> connector2
        self.network.connect_tracks(8, 6)  # connector2 -> decel_tree3
        
        # CREAR Y CONFIGURAR VEHÍCULO
        vm1 = ModularVehicle(1, 20, Vector3(100, 0, 0))
        
        # ASIGNAR RUTA USANDO BRAIN
        success = self.brain.assign_vehicle_to_route(vm1, station1, station2)
        
        if success:
            self.brain.add_vehicle(vm1)
            self.vehicles.append(vm1)
            
            # CORRECCIÓN CRÍTICA: Forzar la salida inmediata del vehículo
            # En lugar de solo undock, transferir directamente al árbol de salida
            if station1.departure_trees:
                departure_tree = station1.departure_trees[0]
                
                # Remover de estación y agregar al árbol de salida
                if vm1 in station1.docked_vehicles:
                    station1.docked_vehicles.remove(vm1)
                
                # Agregar al árbol de salida con posición inicial
                departure_tree.add_vehicle(vm1)
                vm1.current_track = departure_tree
                vm1.state = "accelerating_down"
                
                # Actualizar posición inicial del vehículo
                vm1.current_position = Vector3(100, 0, 0)
                
                print(f"✓ VM {vm1.vehicle_id} posicionado en árbol de salida")
                print(f"✓ Estado: {vm1.state}")
                print(f"✓ Track actual: {vm1.current_track.track_id if vm1.current_track else 'None'}")
            
            print(f"✓ VM {vm1.vehicle_id} configurado correctamente")
            print(f"✓ Ruta: Estación 1 → Estación 2")
            
            # DEBUG: Verificar configuración
            print(f"✓ Estaciones en Brain: {list(self.brain.stations.keys())}")
            print(f"✓ Vehículos en Brain: {list(self.brain.vehicles.keys())}")
            print(f"✓ Tracks en Network: {len(self.network.tracks)}")
            print(f"✓ Conexiones en Network: {self.network.adjacency}")
        else:
            print(f"✗ ERROR: No se pudo asignar ruta al VM {vm1.vehicle_id}")
            
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