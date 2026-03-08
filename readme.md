### Comando para correr la simulacion:
```bash
python3 -m simulation.main
```

### Cosas Por Hacer Profesor:


### Notas Importantes:
- Tengo un cuello de botella en la revision de colisiones O(n2)

### Refactorisacion Trabajo de relojeria
Resumen Definitivo y Plan de Refactorización de la Simulación
Objetivo General: Aumentar la precisión y robustez de la simulación, corrigiendo errores de sincronización y mejorando la lógica de predicción de colisiones para que sea fiable bajo cualquier velocidad de simulación (dt).

1. Resumen del Flujo de Actualización (El "Cómo Funciona Ahora")
Avance del Bucle Principal: El tiempo global avanza en dt.
Movimiento Sincronizado: Todos los Tracks mueven sus vehículos internos una distancia correspondiente al dt completo.
Recopilación de "Finalizados": Se crea una lista de vehículos que completaron su Track.
Fase de Transferencia: Se procesa la lista. Se decide el siguiente Track y el vehículo se transfiere lógicamente, reseteando su progreso a 0 en el nuevo Track.
Registro de Eventos: Si el nuevo Track es un árbol de descenso, se registra un evento en el Brain para una futura comprobación de colisión.
Ejecución de Lógicas (Predicción): El Brain procesa los eventos y ejecuta la predicción de colisión.
2. Diagnóstico Completo de Problemas Identificados
P1: Colisiones en Bucles (El Problema del "Tiempo Sobrante"):

Síntoma: Vehículos en bucles simples chocan cuando la simulación se acelera (aumenta dt).
Causa: Si un vehículo termina un track en 0.4s y el dt es de 1.0s, los 0.6s restantes se pierden. El vehículo no avanza en el nuevo track hasta el siguiente ciclo, mientras que el de atrás sí se movió durante los 1.0s completos.
P2: Predicción de Colisión Imprecisa (El Problema de la "Foto Fija"):

Síntoma: La predicción de colisiones da falsos positivos y negativos.
Causa: El cálculo es estático. Predice el tiempo T que tardará el vehículo descendiente (VM1) en llegar a la unión y luego busca si otro vehículo (VM2) está actualmente en una "zona de peligro" a T segundos de distancia. No considera que VM2 también se moverá durante esos T segundos.
P3: Puntos Ciegos en la Predicción (El Problema del "Camino Único"):

Síntoma: La predicción no ve colisiones cuando un vehículo se acerca por una vía convergente no principal.
Causa: Al buscar hacia atrás la "zona de peligro", el código solo sigue la primera ruta predecesora que encuentra (preds[0]), ignorando otras vías que convergen en la misma unión.
P4: Cálculo de Descenso Impreciso (El Problema del "Inicio Falso"):

Síntoma: (Este es el que acertadamente señalaste) La predicción de colisión calcula mal el tiempo de descenso del VM1.
Causa: La función get_time_to_complete asume que el vehículo siempre empieza a descender desde el progreso = 0 del árbol. Sin embargo, una vez solucionado P1, un vehículo podría entrar al árbol y, por el "tiempo sobrante", avanzar inmediatamente a un progreso de, por ejemplo, 0.05. La predicción no tiene en cuenta esta distancia ya recorrida, resultando en un time_to_junction incorrecto.
3. Plan de Acción Definitivo: Refactorización por Pasos
Este es el orden correcto y completo para aplicar los cambios.

Paso 1: Implementar la Continuidad del Movimiento (Soluciona P1)

Este es el cimiento de todo. Sin esto, los demás arreglos no serán precisos.

Objetivo: Eliminar la pérdida de tiempo en las transferencias.
Cambios a Realizar:
El método update_vehicles de cada Track debe devolver una lista de tuplas: [(vehicle, tiempo_sobrante)].
La función _transfer_vehicle de Network debe aceptar este tiempo_sobrante.
Después de transferir el vehículo al next_track, _transfer_vehicle debe llamar inmediatamente a un método en next_track (ej: update_vehicle_progress(vehicle, tiempo_sobrante)) para que el vehículo avance la distancia correspondiente a ese tiempo.
Punto Clave a Vigilar: Este cambio es la causa directa del problema P4, por lo que el Paso 3 se vuelve obligatorio después de este.
Paso 2: Robustecer la Búsqueda de la Predicción (Soluciona P3)

Una vez que el movimiento es preciso, nos aseguramos de que la predicción mire en todos los lugares correctos.

Objetivo: Eliminar los puntos ciegos en las uniones.
Cambios a Realizar:
En _check_for_future_collision_at_junction, modificar el bucle que retrocede por los tracks.
En lugar de solo tomar preds[0], la lógica debe iterar sobre todos los predecesores (preds) de una unión, realizando la búsqueda de la "zona de peligro" para cada ruta de aproximación posible.
Punto Clave a Vigilar: La lógica de "gastar tiempo" (time_left) debe gestionarse de forma independiente para cada rama que se explora.
Paso 3: Hacer el Cálculo de la Predicción Consciente del Estado Real (Soluciona P4 y mejora P2)

Este paso refina el cálculo de la predicción, usando la información correcta que ahora tenemos gracias al Paso 1.

Objetivo: Hacer que la predicción se base en la posición y tiempo reales de los vehículos involucrados.
Cambios a Realizar:
Solucionar P4: Modificar descending_tree.get_time_to_complete() para que acepte un parámetro opcional start_progress.
Conectar todo: La función _check_for_future_collision_at_junction debe: a. Obtener el progreso actual del descending_vehicle en su árbol. b. Pasar ese start_progress a get_time_to_complete para obtener un time_to_junction exacto para VM1.
Punto Clave a Vigilar: Este paso hace que el cálculo para VM1 sea preciso. Sin embargo, es importante recordar que el cálculo para VM2 sigue siendo una "foto fija" (problema P2). Aunque la predicción será mucho más fiable, no será una simulación dinámica perfecta.







#### Problemas mitad de camino

Resumen Actualizado para Futuras Refactorizaciones
Aquí tienes el resumen consolidado, incluyendo estos nuevos hallazgos. Lo he estructurado para que podamos añadirlo a nuestro plan de acción en el readme.md.

4. Nuevos Problemas Identificados (Post-Paso 1)
Tras la implementación exitosa del "Paso 1" en StationConnector y AccelerationTree, las pruebas han revelado dos nuevos problemas de precisión.

P5: Fuga de Continuidad en Andenes (BoardingLane):

Síntoma: Aunque el bucle principal es estable, se sospecha que la precisión se pierde al pasar por las estaciones.
Causa: La clase BoardingLane no fue incluida en la refactorización del "Paso 1". No implementa la lógica de update_vehicle_progress para manejar el tiempo_sobrante. Cada vez que un vehículo transita por un andén, se pierde una fracción de segundo, reintroduciendo el error de desincronización original (P1) de forma localizada.
P6: Espaciado Inconsistente en el SpawnSystem:

Síntoma: Los vehículos generados por un SpawnPoint con un intervalo constante no mantienen una distancia inicial perfectamente uniforme. Esta inconsistencia se agrava drásticamente al cambiar el time_scale de la simulación durante el proceso de spawn.
Causa (El "Error de Overshoot"): La lógica de SpawnPoint.update descarta el tiempo excedente en cada ciclo de generación. Si el intervalo es de 1.0s y el acumulador de tiempo llega a 1.03s, se genera un vehículo y el acumulador se resetea a 0, perdiendo 0.03s. Esto causa que el tiempo real entre spawns no sea constante, provocando las variaciones de distancia observadas.
5. Plan de Acción Actualizado
El plan original sigue siendo válido, pero ahora debemos insertar la solución a estos nuevos problemas en el orden correcto para no construir sobre una base inestable.

Paso 1.5: Sellar la Fuga de Continuidad (Soluciona P5)

Prioridad: Inmediata. Debe hacerse antes de continuar con los pasos 2 y 3 del plan original.
Objetivo: Hacer que BoardingLane respete la continuidad del movimiento.
Cambios a Realizar:
Modificar la clase objects/boarding_lane.py.
Implementar el método update_vehicle_progress(self, vehicle, time_delta) de la misma forma que en StationConnector.
Asegurarse de que update_vehicles en BoardingLane también devuelva la tupla (vehicle, tiempo_sobrante).
Paso 1.7: Corregir la Precisión del SpawnSystem (Soluciona P6)

Prioridad: Alta. Afecta la consistencia inicial de la simulación.
Objetivo: Garantizar que el intervalo de spawn sea matemáticamente preciso e independiente del dt y del time_scale.
Cambios a Realizar:
Modificar la clase simulation/spawn_system.py.
En el método SpawnPoint.update, cambiar la línea self.time_since_last_spawn = 0 por self.time_since_last_spawn -= self.spawn_interval. Esto preserva el tiempo excedente ("overshoot") para el siguiente ciclo, asegurando un intervalo promedio exacto.
Una vez completados estos dos "pasos intermedios", la base de la simulación será mucho más sólida, y podremos continuar con los Pasos 2 y 3 del plan original (robustecer la predicción de colisiones) con la confianza de que el movimiento y la generación de vehículos son precisos.




####  Caso de prueba y

Caso de Prueba: "La Unión en Y" para la Predicción de Colisiones
Objetivo: Verificar que la refactorización del Paso 2 ("Robustecer la Búsqueda de la Predicción") funciona correctamente. Específicamente, este caso de prueba está diseñado para confirmar que el sistema de predicción de colisiones ya no sufre del problema del "Camino Único" (P3) y ahora es capaz de detectar vehículos en conflicto que se aproximan a una unión desde múltiples vías de entrada.

1. Cómo Preparar el Entorno de Prueba
Para ejecutar esta prueba, se debe modificar temporalmente el fichero simulation/simulation.py para crear una red simple y controlada.

Acción: En el método init_simulation de la clase SimulationBuilder dentro de simulation/simulation.py, comenta la configuración de red y vehículos existente y reemplázala con la siguiente configuración de prueba.

python
 Show full code block 
# DENTRO DE: SimulationBuilder.init_simulation() en simulation/simulation.py

try:
    # 1. Estaciones (se pueden mantener o comentar, no afectan la prueba)
    builder.add_station("1", "North Station", Vector3(425, 0, 0))
    # ... (resto de estaciones)

    # =================================================================
    # --- INICIO DE LA CONFIGURACIÓN DEL CASO DE PRUEBA ---
    # =================================================================

    # A. CREAR LA GEOMETRÍA DE LA "UNIÓN EN Y"
    # Un árbol de descenso que apunta a la unión en (1000, 0, -20)
    builder.add_acceleration_tree(100, "1", Vector3(1000, 20, 0), Vector3(1000, 0, -20), "down")
    # La vía común que sale de la unión
    builder.add_connector(101, Vector3(1000, 0, -20), Vector3(1200, 0, -20))
    # Las dos ramas que se fusionan en la unión (Ruta A y Ruta B)
    builder.add_connector(102, Vector3(800, 50, -20), Vector3(1000, 0, -20)) # Ruta A
    builder.add_connector(103, Vector3(800, -50, -20), Vector3(1000, 0, -20)) # Ruta B
    # Un track de preparación para el vehículo que va a descender
    builder.add_connector(104, Vector3(950, 20, 0), Vector3(1000, 20, 0))

    # B. CONECTAR LOS TRACKS DE LA "UNIÓN EN Y"
    builder.connect_tracks(102, 101) # Ruta A se conecta a la Vía Común
    builder.connect_tracks(103, 101) # Ruta B se conecta a la Vía Común
    builder.connect_tracks(100, 101) # El Árbol de Descenso se conecta a la Vía Común
    builder.connect_tracks(104, 100) # El track de preparación se conecta al Árbol de Descenso

    # C. COMENTAR LA CONFIGURACIÓN ORIGINAL
    # Comenta o elimina las secciones originales de "Conectores Subterráneos",
    # "Conexiones de los conectores", "Conexiones de los arboles", etc.
    # para que no interfieran con la prueba.

    # D. AÑADIR Y POSICIONAR LOS VEHÍCULOS DE PRUEBA
    # Comenta el SpawnSystem original
    # self.spawn_system.add_spawn_point(...)

    # Añadir los 3 vehículos necesarios para la prueba
    builder.add_vehicle(1, 2, "1") # VM Descendiente
    builder.add_vehicle(2, 2, "1") # VM Conflicto en Ruta A
    builder.add_vehicle(3, 2, "1") # VM Conflicto en Ruta B

    # Posicionar los vehículos en sus tracks de inicio
    builder.start_vehicle_on_track(1, 104) # VM Descendiente, listo para bajar por el árbol 100.
    builder.start_vehicle_on_track(2, 102) # VM Conflicto, en la Ruta A.
    builder.start_vehicle_on_track(3, 103) # VM Conflicto, en la Ruta B.

    # =================================================================
    # --- FIN DE LA CONFIGURACIÓN DEL CASO DE PRUEBA ---
    # =================================================================

    # 7. Iniciar tree selector y demás configuraciones finales...
    tree_selector = TreeSelector(self.brain)
    # ... (el resto del código de configuración puede permanecer)

2. Cómo Ejecutar las Pruebas
Una vez que el entorno está preparado, la prueba se realiza en tres partes para verificar cada escenario de forma aislada y luego en conjunto.

Prueba 1: Conflicto solo en Ruta A

En el código de prueba anterior, comenta la línea que posiciona al vehículo de la Ruta B: # builder.start_vehicle_on_track(3, 103)
Ejecuta la simulación: python3 -m simulation.main.
Resultado Esperado: La consola debe mostrar una alerta 🚨 ALERTA DE COLISIÓN FUTURA 🚨 que mencione al VM descendiendo: _1_1 y al VM en conflicto: _1_2 (en el track 102).
Prueba 2: Conflicto solo en Ruta B

Comenta la línea del vehículo de la Ruta A y descomenta la de la Ruta B: # builder.start_vehicle_on_track(2, 102) builder.start_vehicle_on_track(3, 103)
Ejecuta la simulación.
Resultado Esperado: La consola debe mostrar una alerta de colisión que mencione al VM descendiendo: _1_1 y al VM en conflicto: _1_3 (en el track 103).
Prueba 3: La Prueba Definitiva (Conflicto en ambas rutas)

Asegúrate de que las líneas de posicionamiento de los tres vehículos estén activas.
Ejecuta la simulación.
Resultado Esperado: La consola debe mostrar DOS alertas de colisión distintas: una para el conflicto con el vehículo 2 y otra para el conflicto con el vehículo 3.
3. Cómo Restaurar la Simulación
Una vez completadas las pruebas, simplemente elimina o comenta todo el bloque de "CONFIGURACIÓN DEL CASO DE PRUEBA" y descomenta la configuración original de la red y del SpawnSystem en simulation.py para volver al funcionamiento normal.

Con este documento, cuando decidas que es el momento, podremos realizar la prueba de forma rápida y eficiente.
