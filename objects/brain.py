from objects.base import Vector3

class Brain:
    def __init__(self, network):
        self.network = network
        self.vehicles = []
        self.connectors = network.connectors
        self.debug_frame = 0
    
    def add_vehicle(self, vehicle):
        self.vehicles.append(vehicle)
        self.network.vehicles.append(vehicle)
    
    def assign_vehicle_to_route(self, vehicle, origin_station, destination_station):
        connector = self.network.find_route(origin_station.id, destination_station.id)
        if not connector:
            print(f"❌ No se encontró conector de {origin_station.id} a {destination_station.id}")
            return False
        
        acceleration_tree = origin_station.get_acceleration_tree()
        deceleration_tree = destination_station.get_deceleration_tree()
        
        if not acceleration_tree:
            print(f"❌ No hay árbol de aceleración en estación {origin_station.id}")
            return False
        if not deceleration_tree:
            print(f"❌ No hay árbol de desaceleración en estación {destination_station.id}")
            return False
        
        vehicle.assign_route(connector, destination_station, acceleration_tree, deceleration_tree)
        return True
    
    def update(self, dt):
        self.debug_frame += 1
        print(f"\n=== FRAME {self.debug_frame} (dt={dt:.3f}s) ===")
        
        completed_vehicles = self.network.update_vehicle_movements(dt)
        
        # DEBUG: Estado de todos los VMs
        for vehicle in self.vehicles:
            info = vehicle.get_debug_info()
            print(f"VM{info['vm_id']}: {info['state']} | {info['segment']} | "
                  f"Pos({info['position'][0]:.1f},{info['position'][2]:.1f}) | "
                  f"Vel{info['velocity']:.1f}m/s")
        
        for vehicle in completed_vehicles:
            print(f"🔄 VM {vehicle.id} completó segmento, procesando transición...")
            self._handle_segment_completion(vehicle)
    
    def _handle_segment_completion(self, vehicle):
        current_state = vehicle.current_state
        
        if current_state == "on_acceleration_tree":
            print(f"🔄 VM {vehicle.id} terminó aceleración → pasa a conector")
            vehicle.current_state = "on_connector"
            vehicle.distance_traveled_on_tree = 0.0
            # Posicionar al inicio del conector
            vehicle.position = Vector3(vehicle.current_connector.origin_station.position.x,
                                     vehicle.current_connector.origin_station.position.y,
                                     vehicle.current_connector.origin_station.position.z)
            
        elif current_state == "on_connector":
            print(f"🔄 VM {vehicle.id} terminó conector → pasa a desaceleración")
            vehicle.current_state = "on_deceleration_tree"
            vehicle.distance_traveled_on_tree = 0.0
            # Posicionar al inicio del árbol de desaceleración
            vehicle.position = Vector3(vehicle.deceleration_tree.start_position.x,
                                     vehicle.deceleration_tree.start_position.y,
                                     vehicle.deceleration_tree.start_position.z)
            
        elif current_state == "on_deceleration_tree":
            print(f"🔄 VM {vehicle.id} terminó desaceleración → llega a estación")
            vehicle.arrive_at_station()