import math
from objects.base import Vector3

class AccelerationTree:
    def __init__(self, id: int, tree_type: str, slope: float, length: float, position: Vector3):
        self.id = id
        self.type = tree_type  # "acceleration", "deceleration", or "constant"
        self.slope = slope  # degrees
        self.length = length  # meters
        self.position = position
    
    def calculate_trajectory(self, vehicle, initial_velocity=0):
        """Calculate trajectory based on gravity and slope"""
        g = 9.81  # gravity m/s²
        
        if self.type == "constant":
            acceleration = 0
            final_velocity = initial_velocity
            time = self.length / initial_velocity if initial_velocity != 0 else 0
        else:
            slope_rad = math.radians(self.slope)
            # Acceleration due to gravity on slope
            acceleration = g * math.sin(slope_rad)
            
            if self.type == "deceleration":
                acceleration = -acceleration
            
            # Final velocity (v² = u² + 2as)
            final_velocity = math.sqrt(initial_velocity**2 + 2 * acceleration * self.length)
            
            # Time to traverse (t = (v - u)/a)
            time = (final_velocity - initial_velocity) / acceleration if acceleration != 0 else 0
        
        return acceleration, final_velocity, time
    
    def execute_movement(self, vehicle, dt):
        """Execute movement along the acceleration tree"""
        if vehicle.distance_traveled_on_tree >= self.length:
            return True  # Tree completed
        
        if self.type == "constant":
            # Movement at constant velocity
            distance = vehicle.velocity * dt
            vehicle.distance_traveled_on_tree += distance
            
            # Calculate 3D position along the tree
            progress_ratio = vehicle.distance_traveled_on_tree / self.length
            vehicle.position.x = self.position.x + progress_ratio * self.length
        else:
            slope_rad = math.radians(self.slope)
            g = 9.81
            
            # Calculate acceleration based on slope
            acceleration = g * math.sin(slope_rad)
            if self.type == "deceleration":
                acceleration = -acceleration
            
            # Update velocity
            vehicle.velocity += acceleration * dt
            
            # Update position along the slope
            distance = vehicle.velocity * dt
            vehicle.distance_traveled_on_tree += distance
            
            # Calculate 3D position along the tree
            progress_ratio = vehicle.distance_traveled_on_tree / self.length
            height_change = self.length * math.sin(slope_rad) * progress_ratio
            
            vehicle.position.x = self.position.x + progress_ratio * self.length * math.cos(slope_rad)
            vehicle.position.z = self.position.z + height_change
        
        return vehicle.distance_traveled_on_tree >= self.length