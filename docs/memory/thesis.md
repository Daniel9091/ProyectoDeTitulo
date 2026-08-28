# NSim — Informe de tesis

> Última actualización: 2026-08-23
> Responde a: "¿Cómo escribo el informe? ¿qué datos hay disponibles? ¿qué evalúa el corrector?"
> Actualizar cuando avance la escritura del informe.

---

## Contexto

Informe final de tesis de Daniel para titularse de Ingeniero Civil (Universidad de los Andes).
Modalidad: **Memoria** (investigación). Individual. ~30 páginas.

---

## ESTADO ACTUAL — Capítulo 4 (Desarrollo)

> Actualizado 24-08-2026, tras sesión larga de redacción. Consultar esto primero antes de
> asumir qué está escrito, qué falta, o de dónde partir.

**Redactado y aprobado por Daniel (texto final ya pegado en "Iteración 1" del doc de Drive,
fuente de verdad — no reescribir desde cero, solo iterar si hay feedback nuevo):**
- §4.1.1 Enfoque General
- §4.1.2 Proceso de Desarrollo y Control de Calidad
- §4.1.3 Reducción de la Carga Cognitiva (con Tabla X, Figura Y de evolución, Tabla Z de
  desglose por subsistema)
- §4.1.4 Diseño de las Pruebas de Carga (con Tabla W de diseño de experimentos — variables
  aún "por definir" en valores finales, ver más abajo)
- §4.2 Arquitectura General del Sistema (con Figura A: diagrama de capas Mermaid; Figura B:
  diagrama de clases Mermaid; Figura C: captura general anotada; Figura D: captura de
  detalle de estación S8 anotada — código y archivos de ambas figuras abajo)
- §4.3 Constantes del Sistema y su Justificación (Tabla W de 10 constantes con columna
  Naturaleza)
- **§4.4 Objetos Simples del Sistema — COMPLETO (24-08-2026).** Los 4 objetos (Pasajero,
  Vehículo Modular, Cinta de Abordaje, Estación) redactados y aprobados, con Figura E
  (diagrama de estados del Pasajero) y Figura F (captura del inspector interactivo sobre
  la estación S16). Ver plantilla de estilo y hallazgos técnicos en la sección nueva más
  abajo ("§4.4 — plantilla de objetos simples y hallazgos").

**En progreso:** ninguna sección activa — §4.4 se cerró completo. Siguiente paso natural:
§4.5.1 (Brain).

**No iniciado:** §4.5 (Sistemas de Gestión Complejos, 4.5.1-4.5.6), §4.6, §4.7, §4.8.

**Pendientes cruzados abiertos (no bloquean, pero revisar antes de cerrar el capítulo):**
- §5.5 (Resultados) menciona "crecimiento de filas de espera" como indicador de límite
  operacional — contradice el criterio de seguridad-primero fijado en §4.1.4. Corregir
  cuando se llegue a ese capítulo.
- Sigue sin confirmarse con el profesor si la matriz OD de Línea 1 corresponde a hora punta
  — no afirmado en ningún texto ya escrito.
- Lista final de escenarios de prueba de carga aún no decidida por Daniel (comentario propio
  en el doc: "Evaluar cuáles escenarios dejar").
- Nota propia de Daniel en el doc, sin resolver: renombrar "Sim"/"NSim" a "v1"/"v2" (NSim
  significa redundantemente "nueva simulación").
- Nota propia de Daniel: Figura D (captura de detalle) podría necesitar mejor zoom/tamaño;
  no se alcanza a mostrar una junction claramente. Revisar si vale la pena una nueva captura.

**Hallazgo útil de esta sesión:** `VM_CAPACITY = 6` y `DENSITY` (fracción de slots
ocupados al iniciar, 1=lleno/0=vacío) viven en `simulation_builder/linea_1_edit.py`, NO en
`config/constants.py`. Esto resuelve la duda anterior sobre "capacidad de los VMs".

---

## §4.4 — plantilla de objetos simples y hallazgos (24-08-2026)

**Objetos incluidos en §4.4 (simples) vs excluidos:**
- Sí llevan sección propia: `Passenger`, `ModularVehicle`, `BoardingLane`, `Station`.
- NO llevan sección propia (infraestructura genérica sin decisión de diseño propia del
  Metro Continuo): `objects/math3d.py` (Vector3), `objects/passenger_id_generator.py`,
  `objects/types.py` (los enums) y `tracks/base.py` (BaseTrack). Su CONTENIDO sí se usa,
  integrado dentro de la descripción del objeto que corresponde (ej. los estados de
  `types.py` aparecen en la Figura E de Pasajero, no como sección aparte).
- Orden de redacción usado (de menos a más dependiente, verificado por imports reales,
  confirmado por Daniel como el orden real de programación): Passenger → ModularVehicle
  → BoardingLane → Station.

**Plantilla de estilo (aplicar igual en §4.5, ajustando profundidad a sistemas complejos):**
1. Abrir con **qué ES** el objeto (una frase de naturaleza/esencia), no con qué hace.
2. **Nunca** poner nombres de funciones entre backticks ni CONSTANTES en mayúscula sueltas
   dentro de la prosa — describir en palabras. Código/identificadores exactos solo en
   pies de figura o tablas, no en el cuerpo del texto. (Iterado varías veces hasta que
   Daniel quedó conforme — la versión con backticks se sintió "poco formal".)
3. NO listar atributos/métodos como inventario plano. Cada atributo o método mencionado
   debe explicar un **por qué** (una decisión de diseño), no solo aparecer nombrado.
4. Un "por qué importa" central por objeto (ej. Pasajero: por qué solo dos timestamps;
   Vehículo Modular: por qué el mismo objeto se conserva íntegro entre tracks).
5. Referencias cruzadas explícitas cuando una decisión de diseño cruza dos objetos (ej. la
   asimetría de quién decide el embarque aparece en Pasajero Y en Vehículo Modular).
6. Etiquetas de coordinación (destino=verde, demanda=amarillo): introducirlas donde
   aparecen naturalmente (destino en BoardingLane, demanda en Station) pero con MUCHA
   cautela — sin frases tipo "la segunda de las tres etiquetas" (Daniel lo pidió sacar una
   vez ya escrito). El mecanismo completo de las 3 etiquetas recién se explica en §4.5.1.
7. Extensión objetivo: ~190-230 palabras para Pasajero/VM/BoardingLane; Estación tiene
   permiso explícito de Daniel para extenderse más (≈430 palabras) por ser "un coordinador
   menor" con más detalle interesante.

**Hallazgos técnicos verificados en el código (no asumir de memoria en §4.5):**
- **El desembarque de pasajeros es instantáneo y lo dispara Brain, NO Station.** Ocurre en
  `brain._handle_crossings`, vía `vm.disembark_all()`, en el instante en que el VM cruza
  hacia la estación. Station no participa en el instante mismo; solo se ve afectada
  indirectamente si la llegada no era demanda propia (`on_unplanned_vm_at_tree`).
- **No existe una clase "Andén".** Es un dict dentro de `Station._platforms` que agrupa:
  `lane` (BoardingLane), `up_tree_id`, `down_tree_id`, `extraction_point`,
  `discharge_point`, `state` (AndenState). Útil aclararlo explícitamente en el informe.
- **El "tercer timestamp" de Pasajero no existe como atributo.** Passenger solo guarda
  `spawn_time` y `arrival_time`. El instante de embarque comprometido se registra como
  evento de telemetría (`recorder.passenger_boarded(t, passenger_id, vm_id, spawn_time)`),
  no en el objeto de dominio — el propio código comenta "spawn_time permite calcular
  wait_time". Objeto de dominio mínimo a propósito; el historial vive en telemetría.
- **`passenger_rate` y `vm_request_rate` son dos parámetros de Station independientes,
  uno NO se deriva del otro.** El operador del escenario configura ambos por separado;
  la cantidad de pasajeros que llega no determina automáticamente cuántos VMs se piden.
  Esto permite priorizar flujo de VMs hacia ciertas estaciones deliberadamente. Aclaración
  explícita pedida por Daniel en §4.4 — podría ser relevante también como variable de
  escenario en §5.3 si en algún momento se quiere probar un descalce demanda/oferta.
- Round-robin (Station, entre andenes activos) y selección por mayor tiempo de espera +
  llenado FIFO del mismo destino (BoardingLane, dentro de un andén) son DOS mecanismos
  distintos — no mezclarlos en el texto.

**Figuras generadas en §4.2-§4.4 (próxima letra libre para §4.5: G):**
- A: diagrama de capas (Mermaid flowchart) — B: diagrama de clases (Mermaid classDiagram)
- C: captura general anotada (belt+estación a lo lejos) — D: captura de detalle S8 anotada
  (7 callouts: estación, belt, vía, pasajeros caminando, VM abordando/destino/en tránsito)
- E: diagrama de estados del Pasajero (Mermaid stateDiagram-v2, `direction LR`, transiciones
  numeradas 1-5, leyenda como `note right of ARRIVED` con líneas cortas para que no se
  ensanche — Mermaid autoajusta el ancho de la nota a su línea más larga, no hay parámetro
  de ancho fijo)
- F: captura real del inspector interactivo sobre estación S16 (subida por Daniel)

**Pendiente de Daniel para figuras D/E:** revisar si conviene una nueva captura de detalle
con mejor zoom que sí muestre una junction (nota propia de Daniel en el doc, sin resolver).

---

## Rúbrica Anexo 1 — lo que evalúa el corrector

| Indicador | Tipo | Peso | Lo que importa |
|---|---|---|---|
| Presentación y expresión escrita | A | 10% | Sin errores, formato consistente, figuras útiles |
| Resumen | A | 5% | Motivación + trabajo realizado + resultados/conclusiones |
| Introducción y motivación | B | 15% | Problema claro, motivación clara, alcance que coincide con lo hecho |
| Desarrollo | B | 20% | Tareas adecuadas para resolver el problema, bien detalladas |
| Análisis y conclusiones | B | 30% | Métodos adecuados, comparaciones, conclusiones justificadas |
| Referencias | A | 5% | Todas las aseveraciones relevantes referenciadas |
| Relevancia, alcance y novedad | B | 15% | Trabajo relevante para la especialidad, profundidad adecuada |

**Los indicadores tipo B suman el 80% de la nota.** Tipo A es presentación.

---

## Estrategia principal

Hacer la revisión fácil para el corrector: que pueda tener la pauta en la mano y señalar
exactamente en qué página se responde cada criterio.

- Definir objetivos de forma muy explícita en la introducción
- Cada sección del informe responde uno o más objetivos de forma identificable
- Los indicadores tipo B requieren que el lector evalúe pertinencia sin dificultad → claridad y estructura son clave

---

## Estado del material disponible (agosto 2026)

| Material | Estado |
|---|---|
| Código | ✅ Completo, 353 tests verdes |
| Docstrings | ✅ Todos revisados — listos para citar directamente en el informe |
| Telemetría SP1-SP6 | ✅ Completo |
| Pipeline de análisis | ✅ Funcional — genera gráficos y resúmenes de texto |
| SP7 (KPIs agregados) | 🔴 Pendiente — puede escribirse el informe sin esto |

---

## Datos y gráficos disponibles

Corrida más completa: `analysis/output/inicial_seed42_20260720-132250/`

| Archivo | Contenido |
|---|---|
| `passengers_station_funnel.png` | Flujo de pasajeros por estación |
| `passengers_time_histograms.png` | Distribución de tiempos de viaje |
| `modular_vehicles_fleet_overview.png` | Vista general de la flota |
| `modular_vehicles_trip_occupancy.png` | Ocupación por viaje |
| `slot_labels_*.png` (6 archivos) | Actividad de etiquetas de slot |
| `stations.txt` | KPIs por estación en texto |
| `passengers.txt` | Estadísticas de pasajeros |
| `modular_vehicles.txt` | Estadísticas de VMs |

Para regenerar: `python analysis.py` desde `NSim/` — ver `docs/memory/telemetry.md`.

---

## Qué puede citar el informe del código

El código está documentado para poder ser citado directamente:
- Cada módulo tiene docstring de arquitectura — útil para la sección de Desarrollo
- `CLAUDE.md` tiene el glosario, los invariantes y los contratos entre sistemas
- `config/constants.py` tiene todos los parámetros físicos con sus unidades

---

## Narrativa aprobada — Sim → NSim (para §4.1.2 / §4.1.3)

> Confirmada por Daniel (23-08-2026), a partir del relato real que dio pie al comentario
> del profesor sobre contar las dos iteraciones. Versión condensada a hechos de ingeniería,
> sin metacomentario, para usar como base al redactar 4.1.2 y 4.1.3.

**Sim (primera iteración, primeros ~4 meses) — versión final acordada:**
No reducir la causa a "la simulación creció demasiado / demasiada información" como única
explicación — eso quedó incompleto en un intento anterior. La causa real, según Daniel: tanto
él como la IA se **desconectaron** del proyecto a medida que este creció (no solo "había
mucha información", sino que efectivamente se perdió la conexión con el estado real del
sistema). Evitar también personalizar el rol del profesor como "me corregía cada semana"
— Daniel lo encuentra poco académico; sí se puede describir el proceso semanal de prueba
y corrección de forma genérica, sin atribuirlo directamente a la dinámica con el guía. El
resultado final debe capturarse como: un sistema compuesto por partes heterogéneas
desarrolladas sin visión de conjunto (metáfora de Daniel: "un Frankenstein", no usar
literalmente en el informe), difícil de mantener, con incongruencias crecientes tanto entre
la documentación/contexto asumido y la realidad del sistema, como dentro del propio
código.

**Decisión de reescritura (sugerida por el profesor):**
Reconstruir el sistema desde cero, con reglas nuevas impuestas por Daniel para forzar
comprensión propia. La regla de tipado NO aplicó a la totalidad del código por igual —
distingue núcleo de negocio de módulos de soporte:
- **Núcleo de negocio** (objetos y sistemas de gestión que implementan las reglas del Metro
  Continuo: brain, junction, acceleration_tree, continuous_train, station, etc.): tipiado
  íntegramente por Daniel, nunca escrito por la IA dentro del archivo; cobertura de tests
  exhaustiva.
- **Módulos de soporte** (construcción de escenarios, análisis, cámara, renderizado): con
  mayor participación de la IA en la escritura, sin la misma exigencia de tests — son más
  cambiantes y no forman parte de la lógica crítica del negocio.
Además: (1) se mantuvo un documento de contexto general del proyecto para no perder el
foco; (2) se documentó cada función y módulo mediante docstrings pensados para leerse
antes de entrar al detalle del código; (3) se construyó la batería de más de trescientas
pruebas automatizadas. Un punto adicional que distingue a NSim de Sim: la arquitectura
completa —clases necesarias, responsabilidad de cada una, orden de ejecución entre
sistemas— fue definida por Daniel *antes* de escribir las clases, a diferencia de Sim, donde
esa visión de conjunto se armaba recién a medida que el código ya existía.

**Efecto medido:**
La carga cognitiva (definida operacionalmente en `cognitive_load.md`) bajó de valores muy
altos en Sim (40/65/85% para cambios pequeño/mediano/grande) a valores bajos en NSim
post-auditoría (1/1.5/3%). La tabla completa con hitos intermedios (NSim inicial, Brain
vacío, Brain completo, 329 tests, post-auditoría) vive en `docs/memory/cognitive_load.md`.

**Factores adicionales de la reducción, útiles para 4.1.3:**
- Los primeros archivos de NSim estaban vacíos, lo que dificultaba que la IA infiriera cómo
  un módulo futuro se conectaría con lo ya construido — incongruencia esperable de la
  etapa temprana, no un fracaso del método.
- La documentación se escribió en español (para que Daniel y el otro memorista, Rafael,
  pudieran leerla), lo cual probablemente elevó algo la carga cognitiva de la IA respecto de
  tenerla en inglés — trade-off consciente, mencionable como limitación menor.
- Una auditoría final de consistencia entre docstrings y memoria, más una corrección
  ortográfica general, redujo aún más la carga hacia el final del proyecto.

**Nota aparte (con evidencia concreta — UBICACIÓN DECIDIDA: no en 4.1.2/4.1.3, va en §6.1):**
En §4.1.2 solo va la afirmación general (el módulo de análisis también sirvió para depurar,
no solo para reportar) con referencia cruzada "(§6.1)" — sin nombrar `junction` ni
"inserciones forzadas", porque esos términos todavía no están definidos en ese punto del
informe (se explican recién en §4.5.4 y §5.1). El ejemplo concreto y con el detalle técnico
completo va en §6.1 (Desafíos del Desarrollo), donde el lector ya tiene todo el vocabulario:
- La métrica de inserciones forzadas (`forced`) apareció consistentemente en cero en toda
  una corrida, lo cual llevó a encontrar que `junction.add_vm` había cambiado su tipo de
  retorno sin actualizar las tres llamadas que lo consumían en `brain._handle_crossings`.
- El otro caso documentado (colisiones falsas dependientes del FPS, rango 11–19) ya estaba
  reservado por el punteo original para §4.6 (Simulación en Tiempo Discreto) como "caso
  real documentado durante el desarrollo" — no duplicarlo en §6.1, con la referencia cruzada
  basta.

**Nota de precisión:** Daniel mencionó de memoria "200 y tantos tests"; el número
verificado en `state.md`/`cognitive_load.md` es **353 tests**, consistente con lo ya escrito en
el punteo ("superior a trescientas"). Usar 353 al redactar.

**Nota — ubicación de los invariantes de Brain (decidida 23-08-2026):**
En §4.1.3, al cerrar con "la carga cognitiva no es uniforme, Brain concentra más", NO usar
los ejemplos concretos de invariantes (signo contraintuitivo de `T_target`, sistema de tres
etiquetas, orden del loop de 8 pasos) — esos términos (`slots`, etiquetas de coordinación)
todavía no están definidos en ese punto del informe. En su lugar, usar la tabla real de
`cognitive_load.md` desglosada por subsistema (`simulation/`, `objects+tracks/`,
`systems/network+continuous_train`, `systems/brain`), que muestra la disparidad sin
necesitar jerga no explicada. Los invariantes concretos de Brain se desarrollan recién en
§4.5.1, con todo el vocabulario ya introducido.

**Decisiones estructurales de §4 — orden y profundidad (decididas 24-08-2026):**
1. **CORRECCIÓN (24-08-2026, sesión larga):** no existía ningún cambio de numeración
   pendiente. El punteo ORIGINAL ya tenía §4.2 = Arquitectura General y §4.3 = Constantes
   (en ese orden). La "decisión de mover Constantes después de Arquitectura" que se discutió
   en sesión fue en realidad corregir una mala lectura mía del punteo al inicio de esa
   conversación — el resultado final coincide con el orden que el punteo ya tenía. NO hay
   renumeración pendiente. Orden confirmado de §4: 4.1 Metodología (4.1.1-4.1.4) → 4.2
   Arquitectura General → 4.3 Constantes → 4.4 Objetos Simples → 4.5 Sistemas Complejos
   (4.5.1 Brain ... 4.5.6 Destino Terminal) → 4.6 Simulación en Tiempo Discreto → 4.7
   Preprocesamiento → 4.8 Orden de Ejecución.
2. **Tabla de §4.3 lleva columna "Naturaleza"** (Física / Diseño-confort / Parámetro de
   experimento / Derivada), igual que la Tabla 5.1 de Saavedra (Fija/Variable/Derivada).
   Resuelve que TRAIN_SPEED y SLOT_SEARCH_RANGE_RESERVATION son valores base
   usados en §5.2 pero variados deliberadamente en §5.3 — no son verdades fijas.
3. **§4.1.4 (Diseño de Pruebas de Carga) NO se mueve** — se queda en Metodología,
   pero se calibra su profundidad: describe el diseño experimental (escenario base, variar
   una constante a la vez, matriz OD fija, criterio de límite operacional) usando solo
   términos autoexplicativos (velocidad del tren, número de andenes) y una glosa mínima
   con referencia cruzada para lo que no lo es (rango de búsqueda de reserva → §4.5.1).
   El análisis profundo de por qué se eligió cada rango y qué pasó al variarlo se deja
   íntegramente para §5.3, donde el sistema ya está completamente explicado.

**Constantes reales verificadas en `config/constants.py` (24-08-2026), para §4.2:**
- Físicas: GRAVITY (9.8 m/s²), PASSENGER_WALK_SPEED (0.5 m/s)
- Diseño/confort: BOARDING_LANE_SPEED (2.0 m/s), TRAIN_VM_LENGTH (1.0 m),
  TRAIN_GAP (1.0 m), TREE_LENGTH (400 m), SLOT_SEARCH_RANGE_DEMAND (10),
  BURST_WINDOW_SAFETY_MARGIN (0)
- Parámetro de experimento (base en §5.2, variado en §5.3): TRAIN_SPEED (20.0 m/s),
  SLOT_SEARCH_RANGE_RESERVATION (±20 slots)
- Derivadas: TRAIN_SPACING (= VM_LENGTH + GAP = 2.0 m), TREE_DZ (profundidad del
  tren principal bajo el andén, ~19.4 m, vía cinemática §2.2), MIN_VM_SEPARATION (=
  TRAIN_SPACING)
- Excluidas de §4.2 (módulo de visualización/soporte, no núcleo de negocio): FPS,
  SCREEN_WIDTH/HEIGHT, todas las CAM_*
- **Pendiente de confirmar con Daniel:** "capacidad de los VMs" no aparece en
  `constants.py` (¿está en la clase VM? ¿es ilimitada?); "capacidad de los andenes" no es
  una constante fija — se deriva de la fórmula q=kv (§2.5) + geometría de estación, el
  cálculo real va en §5.2, no en §4.2.

**§4.1.4 — correcciones de Daniel (24-08-2026):**
1. **Densidad del tren continuo:** NO es `TRAIN_GAP` (separación física, constante fija).
   Es un parámetro de inicialización del escenario: fracción de posiciones que empiezan
   ocupadas por un VM al arrancar la simulación (1 = todas ocupadas, 0 = todas
   disponibles). Hipótesis (explícitamente exploratoria, el propio Daniel dice que el
   mecanismo aún no se entiende del todo bien): reducir esta densidad inicial → más
   posiciones disponibles → menor tasa de inserciones forzadas. Tratar con el mismo tono
   de honestidad epistémica que la carga cognitiva — no afirmar como hecho establecido.
2. **Criterio de límite operacional: es estrictamente de seguridad, NO de comodidad.**
   Se alcanza cuando hay colisiones entre VMs o aumento sostenido de inserciones
   forzadas — NO cuando crecen las filas de pasajeros. Principio: seguridad primero,
   comodidad después (mismo principio que §4.5.6 y el ítem c de trabajo futuro).
   **OJO:** el punteo original en §5.5 menciona "crecimiento sostenido de las filas de
   espera" como indicador de límite operacional junto a las inserciones forzadas — esto
   contradice el criterio corregido. Revisar §5.5 cuando lleguemos a Resultados y alinearlo
   con el criterio de seguridad-primero (las filas de espera pueden sca ser un indicador de
   comodidad/capacidad, pero no deberían definir el "límite operacional" propiamente tal).
