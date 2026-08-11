# NSim — Backlog

> Última actualización: 2026-08-11
> Responde a: "¿Qué está pendiente? ¿qué se difirió? ¿qué viene después del informe?"
> Actualizar cuando se empiece o cierre un item.
> Para estado de lo implementado → `docs/memory/state.md`
> Para SP1-6 (completos) → `docs/memory/telemetry.md`

---

## Prioridad actual

**El informe de tesis es el único trabajo activo.** Ver `docs/memory/thesis.md`.
Todo lo demás está diferido hasta terminar el informe.

---

---

## Mejoras de cámara (4 items, diferidos)

Acordadas en sesión 2026-06-30. Listas para implementar. Todas van en `simulation/camera.py`.

### 1. Mouse confinement — MUY FÁCIL (2 líneas)
Sin esto el cursor sale de la ventana y el mouse look se rompe al mover rápido.
```python
# Al activar mouse look (right-click):
pygame.event.set_grab(True)
# Al desactivar:
pygame.event.set_grab(False)
```

### 2. Easing / momentum — FÁCIL (~10 líneas)
La cámara desliza suavemente al soltar la tecla en vez de parar al instante.
```python
self._vel = [0.0, 0.0, 0.0]   # agregar al __init__

# En update(), reemplazar movimiento directo por:
self._vel[0] = self._vel[0] * 0.80 + target_vx * 0.20
self.pos[0] += self._vel[0] * dt
```
Factor 0.80 da glide suave sin inercia exagerada.

### 3. Snap a presets — FÁCIL (teclas numéricas)
- `1` → vista aérea de todo el sistema (top-down, ve todo el belt)
- `2`, `3`, `4` → cámara mira la estación 2, 3, 4
- Implementar: lista de presets en el constructor (posición depende del escenario), teclas 1-4 llaman `set_preset(idx)`

### 4. Modo órbita — MEDIA (Alt + click izquierdo)
Orbitar alrededor de un punto de interés.
- Punto de órbita = `camera_pos + forward * orbit_radius` (calculado al activar)
- Al arrastrar: rotar yaw y pitch manteniendo distancia al punto fijo
- Alt+click activa, soltar desactiva; `[` y `]` ajustan el radio

**Descartadas (no implementar):** frustum culling completo (innecesario con ~1500 VMs en Pygame),
cuaterniones (complejidad alta, beneficio casi nulo para este proyecto).

---

## Problema Destino Terminal (diseño completo — pendiente de decisión de arquitectura)

Muchos VMs con el mismo destino X pueden saturar la junction UP de X al llegar simultáneamente.

**Solución diseñada:** al asignar destino en el sistema de reserva, verificar que el slot candidato W no incremente la densidad de VMs con destino X por encima de `burst_capacity` en ninguna ventana de `burst_window` slots.

**El check es local a W — O(burst_window):**
- Revisar solo los slots `[W-(burst_window-1), W+(burst_window-1)]`
- Para cada sub-ventana de tamaño `burst_window` que contenga a W, contar cuántos slots ya tienen `destination == X`
- Si alguna sub-ventana ya tiene ≥ `burst_capacity` → rechazar destino X para W

Ejemplo con N=3 árboles, G=9 slots (✓=puede entrar, ✗=ventana llena):
```
slots:  0  1  2  3  4  5  6  7  8  9  10  11  12 ...
puede:  ✓  ✓  ✓  ✗  ✗  ✗  ✗  ✗  ✗  ✓   ✓   ✓   ✗ ...
```
3 VMs consecutivos entran, luego 6 slots de espera, luego 3 más. BURSTY — no "1 VM cada 3 slots".

⚠️ **Decisión pendiente antes de implementar:** ¿slot-first (elegir slot y luego verificar destinos bloqueados) o destination-first (bloquear destinos y luego buscar slot libre)? Esta decisión afecta el orden de operaciones del mecanismo de reserva. **SIN ESTA DECISIÓN NO IMPLEMENTAR.**

Refs: `tracks/junction.py` → `burst_capacity`, `burst_window`; `systems/brain.py` → `_make_reservation`

---

## Arquitectura futura — dos trenes paralelos (razón de diseño de Network)

Daniel tiene previsto extender NSim a un sistema bidireccional: dos trenes continuos en sentidos opuestos compartiendo las mismas boarding lanes. Por eso `adjacency` es `1→N` y no una dataclass Andén con invariante 1 UP + 1 lane + 1 DOWN.

Topología futura:
```python
adjacency = {
    up_tree_A.id: [lane_1.id],
    up_tree_B.id: [lane_1.id],                       # misma lane, dos entradas
    lane_1.id:    [down_tree_A.id, down_tree_B.id],  # Brain elige
    down_tree_A.id: [],  # terminal → belt A
    down_tree_B.id: [],  # terminal → belt B
}
```
Features que habilita: peak hour (apagar una dirección), cambio de línea en estación (VM del tren A al DOWN tree del tren B sin que el pasajero baje), lanes de acumulación.

---

## Fórmula de dimensionamiento de andenes

Para que una estación S absorba su carga sin saturación crónica:

**N(S) ≥ ceil(2 · λ_in(S) · G · TRAIN_SPACING / TRAIN_SPEED)**

- `N(S)` = número de andenes (árboles UP) de la estación
- `λ_in(S)` = tasa de llegada de VMs (VMs/segundo)
- `G` = `burst_window` de la junction UP

Verificado empíricamente (escenario `inicial.py`): S1 (N=1) → 13.3% forced; S2 (N=4) → 0.4%; S3 (N=2) → 0.5%

---

## Ideas futuras (sin prioridad asignada)

- Scheduler greedy-online para demanda — reemplazaría el algoritmo actual de búsqueda en rango.
  Mencionado en regresión add_force (ver `docs/memory/history.md`). Sin spec aún.
- Escenarios adicionales en `simulation_builder/` — actualmente: `inicial.py` (3 estaciones) y `linea_1.py` (27 estaciones).