### Comando para correr la simulacion:
```bash
python3 -m simulation.main
```

### Cosas Por Hacer Profesor:

- matriz origen destino
- Pernas y andenes
- Arreglar bag
- Logs en sistma velocidad
- Detectar cuando hay un vm encima del otro



### Prompt

📋 Prompt para Futura Conversación: "Flujo Continuo en Estaciones"
🎯 PROBLEMA A RESOLVER:
Flujo Continuo de VMs en Estaciones - Eliminar "Docking"

🔄 Comportamiento Actual (INCORRECTO):
python
# Cuando un VM llega a una estación:
1. Sube por árbol de aceleración (up)
2. Se DETIENE y se "dockea" en la estación  
3. Pasajeros (futuro) embarcarían en parado
4. Sale por árbol de bajada (down)
🚀 Comportamiento Deseado (CORRECTO):
python
# Comportamiento objetivo:
1. VM sube por árbol de aceleración (up)
2. Se transfiere a STATION CONNECTOR dentro de la estación
3. Se mueve LENTO (5 m/s) por el connector
4. Pasajeros embarcan EN MOVIMIENTO
5. Continúa directamente al siguiente track
6. NO HAY DETENCIÓN en ningún momento
🗺️ Contexto del Sistema Actual:
✅ Refactorización basal completada (TreeSelector, Network, Station, AccelerationTree, Brain)

✅ Control de densidad en árboles de aceleración funcionando

✅ Flujo continuo cuando hay saturación

❌ Problema pendiente: VMs se detienen en estaciones (comportamiento "docked")

🛠️ Cambios Requeridos:
1. Nuevo Estado para VMs:
python
# Agregar estado "in_station" que significa:
# "Está moviéndose por station connector dentro de una estación"
# Estados válidos: "docked", "moving", "accelerating_up", "accelerating_down", "in_station"
2. Modificar Network:
python
# CORREGIR _arrive_at_station():
# - No cambiar estado a "docked"
# - Transferir directamente a station connector de la estación
# - Mantener destino del VM
3. Station Connectors Especiales:
python
# Crear StationConnector con:
# - Velocidad reducida (5 m/s)
# - Lógica de embarque durante movimiento  
# - Asociación con estación específica
4. Actualizar Simulation Builder:
python
# Conectar árboles de subida -> station connectors -> siguientes tracks
# Eliminar conexiones a "docking"















