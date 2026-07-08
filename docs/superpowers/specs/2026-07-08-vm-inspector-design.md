# Diseño: Inspector de VMs y estaciones (click-to-inspect)

Fecha: 2026-07-08

## Objetivo

Permitir hacer click en un VM (en el belt, en un árbol de aceleración o en una
boarding lane) o en una estación durante la simulación, y abrir una ventana
resumen que se actualiza en vivo con el estado del objeto seleccionado.

## Alcance

- Objetos clickeables: VMs (en cualquiera de sus 3 ubicaciones posibles) y
  estaciones.
- Fuera de alcance: junctions, slots vacíos, tracks individuales sin VM.
- No se modifica `renderer.py`, `camera.py`, `brain.py`, ni ningún archivo de
  `objects/`/`tracks`/`systems`. Toda la funcionalidad vive en un módulo nuevo.

## Arquitectura

Nuevo archivo `simulation/inspector.py`, clase `Inspector`. Sigue el patrón de
un archivo por responsabilidad ya usado en `simulation/` (`camera.py`,
`renderer.py`, `station_factory.py`).

`main.py`:
- Instancia `inspector = Inspector(font_sm, font_md)`.
- En el loop de eventos, en `MOUSEBUTTONDOWN` con `event.button == 1`, llama
  `inspector.handle_click(pygame.mouse.get_pos(), camera, train, brain._network, stations, W, H)`.
- Después de `renderer.render(...)`, llama
  `inspector.render(screen, camera, train, brain._network, stations, W, H)`.

`renderer.py` no recibe ningún parámetro nuevo ni cambia su comportamiento.
Todo el dibujo de paneles, resaltado y línea conectora ocurre en `inspector.py`,
encima de lo que ya pintó `Renderer`.

## Picking (detección de click)

`Inspector.handle_click(pos, camera, train, network, stations, W, H)`:

1. Primero verifica si `pos` cae sobre la "X" de algún panel ya abierto → si
   sí, cierra ese panel y termina (no intenta picking en el mundo 3D).
2. Reúne candidatos con su posición 3D:
   - VMs en el belt: recorre `train.slots`, para cada slot con VM usa
     `(train.get_slot_belt_x(i), train.start_pos.y, train.start_pos.z)`.
   - VMs en tránsito: recorre `network.tracks`, cada entrada de
     `track.vehicles` vía `track.position_at_progress(progress)`.
   - Estaciones: centro de la caja de la estación
     (`station.origin.x, station.origin.y, station.origin.z + floor_height/2`).
3. Proyecta cada candidato con `camera.project(...)`; descarta los `None`
   (detrás de cámara).
4. Calcula distancia en píxeles entre el punto proyectado y el click. Filtra
   los que caen dentro de un radio fijo: `PICK_RADIUS_VM = 14px`,
   `PICK_RADIUS_STATION = 30px`.
5. Entre los candidatos que pasan el filtro, elige el de menor `depth`
   (más cercano a cámara).
6. Si no hay candidatos, el click no hace nada.
7. Si el objeto elegido ya tiene un panel abierto (mismo `vm is ref` o mismo
   `station_id`), no se abre uno nuevo (no-op).
8. Si no, se agrega un panel nuevo al final de la lista de paneles abiertos.

## Modelo de datos del panel

```python
{'kind': 'vm', 'ref': vm_object}          # referencia directa al ModularVehicle
{'kind': 'station', 'station_id': 2}
```

No se guardan copias del estado — cada frame se relee del objeto real.

### Resolución de ubicación de un VM (cada frame)

```
si vm.slot_index is not None:
    ubicación = ('belt', train.slots[vm.slot_index], vm.slot_index)
si no:
    buscar en network.tracks.values() cuál track tiene vm.vehicle_id en track.vehicles
    si es AccelerationTree:
        ubicación = ('tree', track, track.vehicles[vm.vehicle_id])
    si es BoardingLane:
        ubicación = ('lane', track, track.vehicles[vm.vehicle_id])
si no se encontró en ningún lado:
    ubicación = None   # → auto-cierre del panel
```

Este lookup es barato: acceso directo por índice para el caso belt, y un
recorrido de ~15 tracks para el resto (nunca un escaneo de los ~1549 slots).

### Auto-cierre

- VM: si la resolución de ubicación no encuentra el VM en ningún lado, el
  panel se cierra ese mismo frame.
- Estación: si `stations.get(station_id)` es `None`, se cierra (caso
  defensivo — las estaciones no se destruyen hoy).
- Al cerrar un panel (por X o auto-cierre), la lista se compacta: los paneles
  siguientes se renumeran para no dejar huecos en la grilla.

## Contenido por plantilla

El VM no tiene una plantilla fija asignada al abrir el panel — cada frame se
recalcula su ubicación y se elige la plantilla correspondiente. Si el VM
cruza de un track a otro entre frames, el panel cambia de plantilla solo.

**BELT:**
```
VM #123                    [x]
Estado: MOVING
Cap: 4/6 pasajeros
Destino: S2
Slot: 842
Etiquetas: RESERVED→S2
```
`Etiquetas` lista las que están activas entre `reserved_station_id`,
`destination_station_id`, `demand_station_id` (omite las que son `None`). Si
`slot['colliding_vms']` no está vacío, se agrega una línea
`¡CHOQUE! (N VMs)`.

**TREE:**
```
VM #789                    [x]
Ubicación: Árbol UP #5 (S2)
Progreso: 34%
Cap: 6/6 pasajeros
Destino: S2
```
`Ubicación` indica dirección (`TreeDirection`) y estación asociada del árbol.

**BOARDING_LANE:**
```
VM #456                    [x]
Ubicación: BoardingLane #7 (S2)
Progreso: 62%
Cap: 3/6 pasajeros
Destino: S2
Embarcando: sí (2 pasajeros subiendo)
Pasajeros a bordo:
  S1-88 → S2
  S1-91 → S2
  S1-95 → S2
```
`Embarcando` solo aparece si `boarding_committed == False` para esa entrada
de `track.vehicles`. La lista de pasajeros usa `vm.passengers_on_board`
(acotada por `vm.capacity`, normalmente pequeño).

**STATION:**
```
Estación S2                [x]
Andenes: 3/4 activos
Demanda pendiente: 2
Caminando hacia andén: 5
Tasa pasajeros: 0.60/s
Tasa VMs: 2.00/s
Destinos: {1: 0.5, 3: 0.5}
```
Basado en `station.get_summary()` + `station.pending_demand` +
`len(station._walking)`.

## Layout de burbujas

- `PANEL_W = 220px`, `PANEL_H = 190px` (altura fija para todos los tipos,
  dimensionada para el caso más largo — VM lleno en boarding lane).
- `GAP = 8px`, `MARGIN = 8px` desde el borde de pantalla.
- Posición de la burbuja en índice `i` (orden de apertura, tras compactar):
  ```
  columnas_por_fila = max(1, (W - MARGIN) // (PANEL_W + GAP))
  fila = i // columnas_por_fila
  col  = i % columnas_por_fila
  x = MARGIN + col * (PANEL_W + GAP)
  y = MARGIN + fila * (PANEL_H + GAP)
  ```
- Sin límite de paneles abiertos — si tapan la vista, el usuario cierra los
  que no necesita con la X.
- Estilo visual: reutiliza paleta existente (`HUD_BG` semitransparente,
  `HUD_LINE`, `TEXT_BRIGHT`, `TEXT_DIM`) para consistencia con el HUD actual.
- La "X" es un cuadrado clickeable en la esquina superior derecha del panel.

## Resaltado del objeto seleccionado + línea conectora

Después de `renderer.render(...)`, en `inspector.render(...)`:

1. Para cada panel, resuelve la posición 3D actual del objeto (mismo lookup
   que para refrescar contenido) y la proyecta con `camera.project(...)`.
2. Si es visible: redibuja el wireframe del objeto (caja del VM, con las
   mismas dimensiones `VM_RENDER_WIDTH/DEPTH/HEIGHT`; o caja de la estación)
   con línea más gruesa (`width=3` vs el `1` que usa `Renderer`) y un color
   de acento fijo (`HUD_LINE`), encima de lo ya pintado por `Renderer`.
3. Dibuja una línea delgada (`width=1`, mismo color de acento) desde el borde
   o esquina de la burbuja más cercano al punto proyectado del objeto, hasta
   ese punto.
4. Si el objeto no es visible este frame (detrás de cámara o fuera de
   viewport), se omiten resaltado y línea ese frame — el panel sigue abierto
   y su contenido de texto se sigue actualizando igual.

Este dibujo de selección es responsabilidad exclusiva de `Inspector`;
`renderer.py` no sabe que existe selección alguna.

## Testing

- No existe test automatizado para `main.py`/pygame end-to-end hoy (según
  `CLAUDE.md`, se verifica corriendo). `inspector.py` sigue el mismo criterio:
  verificación manual corriendo `main.py` y clickeando VMs en cada una de sus
  3 ubicaciones y una estación.
- Las funciones puras de layout (cálculo de posición de burbuja por índice) y
  de resolución de ubicación de un VM sí son testeables sin pygame y pueden
  tener test unitario si se desea, siguiendo el patrón de
  `tests/test_<archivo>.py`.

## Fuera de alcance (explícitamente)

- Arrastrar/mover paneles con el mouse.
- Persistir qué paneles estaban abiertos entre ejecuciones.
- Clickear junctions, slots vacíos o tracks sin VM.
- Límite máximo de paneles simultáneos.
