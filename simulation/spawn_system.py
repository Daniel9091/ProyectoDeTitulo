import pygame
from objects.modular_vehicles import ModularVehicle
from objects.base import Vector3

class SpawnPoint:
    def __init__(self, spawn_id, track_id, spawn_interval=5.0, max_vehicles=10, vehicle_capacity=4, destination_station_id=None):
        self.spawn_id = spawn_id
        self.track_id = track_id
        self.spawn_interval = spawn_interval  # segundos entre spawns
        self.max_vehicles = max_vehicles
        self.vehicle_capacity = vehicle_capacity
        self.destination_station_id = destination_station_id
        
        self.last_spawn_time = 0
        self.spawned_count = 0
        self.active = True
        self.time_since_last_spawn = 0
        
    def update(self, simulation, dt):
        """Actualiza el spawn point y genera vehículos si es tiempo"""
        if not self.active or self.spawned_count >= self.max_vehicles:
            return None
        
        # ✅ CORRECCIÓN: Acumular tiempo desde último spawn
        self.time_since_last_spawn += dt
        
        if self.time_since_last_spawn >= self.spawn_interval:
            vehicle = self.spawn_vehicle(simulation)
            self.time_since_last_spawn = 0  # Resetear contador
            return vehicle
        return None
    
    def spawn_vehicle(self, simulation):
        """Genera un nuevo vehículo en el track asignado"""
        # Verificar que el track existe
        if self.track_id not in simulation.network.tracks:
            print(f"ERROR: Track {self.track_id} no existe para spawn")
            return None
            
        track = simulation.network.tracks[self.track_id]
        
        # Crear nuevo vehículo con ID único
        vehicle_id = f"_{self.spawn_id}_{self.spawned_count + 1}"
        new_vehicle = ModularVehicle(vehicle_id, self.vehicle_capacity, track.start_pos)
        
        # Configurar destino si se especificó
        if self.destination_station_id:
            new_vehicle.destination_station = self.destination_station_id
        
        # Incorporar a todos los sistemas
        simulation.vehicles.append(new_vehicle)
        simulation.brain.add_vehicle(new_vehicle)
        
        # Agregar al track (DEJAR que el track asigne el estado automáticamente)
        entry_velocity = 20.0  # Velocidad inicial para StationConnectors
        track.add_vehicle(new_vehicle, entry_velocity)
        new_vehicle.current_track = track
        
        # Actualizar contadores
        self.spawned_count += 1
        
        print(f"✅ SPAWN: Vehículo {vehicle_id} generado en track {self.track_id}")
        print(f"   - Estado: {new_vehicle.state}, Tiempo acumulado: {self.time_since_last_spawn:.2f}s")
        return new_vehicle

class SpawnSystem:
    def __init__(self):
        self.spawn_points = {}
        
    def add_spawn_point(self, spawn_id, track_id, **kwargs):
        """Agrega un nuevo spawn point"""
        self.spawn_points[spawn_id] = SpawnPoint(spawn_id, track_id, **kwargs)
        print(f"➕ Spawn Point {spawn_id} agregado en track {track_id}")
        
    def update(self, simulation, dt):
        """Actualiza todos los spawn points con el delta time"""
        spawned_vehicles = []
        for spawn_point in self.spawn_points.values():
            vehicle = spawn_point.update(simulation, dt)
            if vehicle:
                spawned_vehicles.append(vehicle)
                
        return spawned_vehicles
    
    def get_status(self):
        """Retorna estado del sistema de spawn"""
        status = {
            "total_spawn_points": len(self.spawn_points),
            "active_spawn_points": sum(1 for sp in self.spawn_points.values() if sp.active),
            "total_spawned": sum(sp.spawned_count for sp in self.spawn_points.values()),
            "spawn_points": {}
        }
        
        for sp_id, sp in self.spawn_points.items():
            status["spawn_points"][sp_id] = {
                "track": sp.track_id,
                "spawned": sp.spawned_count,
                "max": sp.max_vehicles,
                "active": sp.active,
                "time_since_last_spawn": sp.time_since_last_spawn,
                "spawn_interval": sp.spawn_interval,
                "next_spawn_in": max(0, sp.spawn_interval - sp.time_since_last_spawn)
            }
            
        return status