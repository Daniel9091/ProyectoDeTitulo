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
    
    def init_simulation(self):                                                                  # Inicializa la simulación con estaciones, conectores y vehículos
        # Limpieza de datos previos
        self.vehicles.clear()
        self.stations.clear()
        self.connectors.clear()
        self.network.connectors.clear()
        self.network.vehicles.clear()
        
        # Crear estaciones en posiciones fijas simples
        station1 = Station(1, "Central Station", Vector3(0, 0, 0))
        station2 = Station(2, "North Station", Vector3(300, 0, 0))
        station3 = Station(3, "South Station", Vector3(600, 0, 0))
        
        self.stations.extend([station1, station2, station3])
        
        # Crear conectores con árboles de aceleración simplificados
        connector1 = StationConnector(1, station1, station2, 300.0)
        connector2 = StationConnector(2, station2, station3, 300.0)
        
        # Añadir árboles de aceleración básicos
        connector1.add_acceleration_tree(AccelerationTree(1, "acceleration", 30.0, 150.0, station1.position))
        connector2.add_acceleration_tree(AccelerationTree(2, "acceleration", 30.0, 150.0, station2.position))
        
        self.connectors.append(connector1)
        self.connectors.append(connector2)
        self.network.add_connector(connector1)
        self.network.add_connector(connector2)
        
        # Crear vehículos en posiciones iniciales y asignar rutas
        for i in range(3):
            # Posicionar vehículos cerca de la primera estación
            start_pos = Vector3(i * 10, 0, 0)
            vehicle = ModularVehicle(i, 20, start_pos)
            
            # Asignar ruta al vehículo
            if i % 2 == 0:
                self.brain.assign_vehicle_to_route(vehicle, station1, station2)
            else:
                self.brain.assign_vehicle_to_route(vehicle, station2, station3)
                
            # Dar una velocidad inicial para que se muevan
            vehicle.velocity = 5.0  # m/s                                               # Por ahora esto esta raro, velocidad para que partan desde arriba (estacion)
    
            self.vehicles.append(vehicle)
            self.network.vehicles.append(vehicle)
    
    def update(self, dt):                                                                       # Acutaliza la simulacion basada en el tiempo real
        # Escalar delta time por la escala de tiempo
        scaled_dt = dt * self.time_scale
        
        # Manejar rebobinado temporal
        current_time = pygame.time.get_ticks() / 1000.0
        if self.rewinding:                                                                      # Si se esta rebobinando, mover vehiculos hacia atras   
            elapsed = current_time - self.rewind_start_time
            if elapsed < self.rewind_duration:
                self.network.update_vehicle_positions(-scaled_dt * 2.0)
            else:
                self.rewinding = False
                self.time_scale = self.pre_rewind_scale
        else:                                                                                   # Actualizar posiciones de vehiculos normalmente            
            self.network.update_vehicle_positions(scaled_dt)
    
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