### Comando para correr la simulacion:
```bash
python3 -m simulation.main
```

### Cosas Por Hacer:

#### Urgentes
- Personas y andenes que incorporan personas
- Manejo de que se hace cuando un vm ya llego a la estacion
- Manejo de eleccion de arbol de aceleracion
- ~~problema desface optimo andenes de la misma estacion~~
- ~~Agregar mas vm (en tiempo de simulacion)~~
#### No tan Urgentes
- Matriz, estacion de origen, estacion de destino (Mostrar, Editar, Cumplir)
- Revisar por qeu se descordina la simulacion cuando aumento o disminuyo el tiempo de la simulacion


#### Problema de desface optimo
El problema es que la estacion tiene varios arboles de aceleracion de subida que tienen los mismos desplasamientos en "x" e "y" y diferente desplasamiento en z, a pesar de eso el profesor quiere que los vm llegen al mismo tiempo a la estacion arriba si es que parten al mismo tiempo en cada uno de los arboles. El problema se repite en la bajada, con la diferencia de que ya no parten en el mismo punto como en la subida si no que deben terminar en el mismo punto, considerando que si los vm se tiran de los arboles de aceleracion al mismo tiempo deben llegar al punto final en el mismo tiempo esto quiere decir que me pone como restriccion que todos los arboles deben tener la misma longitud (400.5 metros) a pesar del desplasamiento, y todo debe cuadrar bien.

#### Opciones
- Podemos regular el largo del trak que conecta los arboles arriba de la estacion
- Podemos regular la velocidad del trak que esta en la estacion para que valla mas rapido o mas lento
- No quiero que los vm no conisderen el desplasamiento en z por que despues se que lo voy a tener que cambiar
- si hacemos que los arboles se conecten con el trak de abajo en distintos puntos
    - este punto tiene la desventaja de que dificulta enrmemente la eleccion de arbol cuando un vm  debe decidir entre continuar por la ruta o subir por algun arbol (a lo mejor solo lo puedo hacer para los arboles de bajada para evitar ese problema, pero tendria que hacer muchos station connector por que son muchos nodos)
    - no me gusta mucho esta alnativa por las dificultades
- Puedo agregar roce o aceleracion de manera artificial en los arboles con caminos mas largos


#### Conclucion del problema
##### supuestos
- Arboles de subida parten del mismo nodo, terminan en la estacion y = 0, z = variable (andenes)
- Arboles de bajada parten de distintos puntos (andenes distinto z), llegan al mismo nodo al terminar
- Arboles tienen mismo largo, misma mi aceleracion
- Se considera que cuando un vm termina un arbol de subida llego a la estacion
- cuando un vm comienza un arbol de bajada salio de la estacion
##### Ajustes
- Los station connector en las estaciones (conectan arbol de bajada y de subida) y = 0 van a tener
    - Distintos largos ya que algunos arboles de aceleracion van a terminar o empezar antes o despues (para respetar el largo de cada uno)
    - Van a tener diferentes velocidades para asegurar que todo vm que suba a las estaciones por distintos arboles, llege a la parte de arriba al mismo tiempo y baje por su arbol correspondiente al mismo tiempo
##### Calculos
- Se debe calcular cual es la velocidad variable que debe tener el station conector para asegurar que los vm llegen al mismo tiempo al arbol de bajada
- Cual es el largo que debe tener para permitir que un arbol de subida y de bajada pueda partir antes o despues
##### Evaluar
- La velocidad variante de los station connector en la estacion no puede ser muy diferente a 0.5 metros/segundo para que la gente sea capaz de subir y no alterar la capacidad de la estacion calculada

- No fueron mas de 15 centimetros los modificados

## Resumen de nueva funcionalidad

- mejorar estations
- agregar lane
- agregar passanger
- prioridades para elegir arbol de aceleracion
    - Por defecto elige station connector siguiente
    - En caso de que su destino sea la estacion elige un arbol de aceleracion
            - Por defecto elige el primer arbol
            - Si es pedido por un arbol sube ese (para cuando una persna desde la estacion lo llama)
            - Restriccion de espaciamiento (definir cual es el espaciamiento querido en init)
            esta resticcion consiste en revisar si en el arbol que se quiere subir hay otro vm adelante, para que pueda subir el vm debe de considerar cierta distancia on el vm de adelante (esta resticcion es nesesaria por que cuando reduscan la velocidad al desacelerar podrian chocar arriba)
            - si no  puede cumplir esta codicion deja que el vm pase y le hace la misma consulta al siguiente

        Puedo hacer que un arbol pida un vm?
        discucion, va a existir la funiconalidad de que un pasagero a traves de la estacion pueda solicitar la llegada de un vm a la estacion para que el pueda subirse.
        sera mejor que la persona elija primero el anden y desde el anden llame a un vm (esto implica que los vm son llamados por arboles espesificos de la estacion) o que al solicitar un vm el vm sea distriuido en el arbol que cumpla con el espaciamiento y luego se le indiqe a la persona a que anden debe irse para abordar el vm


- passenger solicita vm


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




otra duda importante, debo aclarar que un vm no se estaciona en la estacion, luego de que sube por algun arbol de aceleracion, el vm se pasa al siguiete track, en la estacion que es un station connector, que va a baja velocidad y una persona se sube mientras esta en movimiento, me puedes aclarar si se puede hacer esto ocn el codigo que me proporcionas, dime si las fucniones son compatibles con este comportamiento y es el que estan esperando, si no dime como corregirlo















