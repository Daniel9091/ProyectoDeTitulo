"""
Archivo principal donde tiene comienzo la simulacion
"""
from config.constants import TRAIN_SPEED, GRAVITY, FPS
from objects.math3d import Vector3
from objects.types import *


def main():
    print("NSim Initialized")
    print(f"TRAIN_SPEED: {TRAIN_SPEED}")
    print(f"GRAVITY: {GRAVITY}")
    print(f"FPS: {FPS}")
    v = Vector3(0.0,0.0,0.0)
    print(f"Vector3: {v}, lenght ={v.length():.2f}")
    print(f" VehicleState values: {[s.value for s in VehicleState]}")
    
if __name__ == "__main__":
    main()