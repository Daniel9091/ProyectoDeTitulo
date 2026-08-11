# NSim — Historial de bugs y decisiones resueltas

> Última actualización: 2026-08-11
> Archivo de referencia. Leer cuando aparezca un síntoma similar a los descritos aquí,
> o cuando quieras entender por qué algo está implementado de una manera específica.
> Para bugs pendientes → `docs/memory/backlog.md`

---

## Regresión: VMs perdiéndose silenciosamente (jul 2026)

**Síntoma:** `forced = 0` en toda corrida. VMs desaparecían del belt sin entrar al árbol.

**Causa raíz:** Commit `8478bb4` cambió `junction.add_vm` de retornar `bool` a retornar
`tuple[bool, int | None]`, pero las 3 llamadas en `brain.py._handle_crossings` no se
actualizaron. `ok = junction.add_vm(...)` capturaba la tupla entera:
- Rama `reserved`: `if not ok` → `if not (False, None)` → `False` → `force_add_vm` nunca llamado → VM perdido
- Rama `dest` / `demand`: `if ok` → `if (False, None)` → `True` → ejecuta lógica de éxito aunque el árbol rechazó → VM perdido + logs incorrectos

**Fix:** Commit `357b546` — desempaquetar correctamente en las 3 ramas:
```python
ok, tree_idx = junction.add_vm(vm, leftover_dt)
```

**Canario para el futuro:** Si `forced = 0` en una corrida donde deberían haber forzados,
verificar primero que `junction.add_vm` esté desempaquetado correctamente en las 3 ramas.

**Limitación conocida del scheduler (no resuelta):** El scheduler de reservas es greedy-online.
Puede elegir un slot con offset grande que después quede a distancia < G de otro slot elegido.
`_would_saturate` previene conflictos con marcas actuales pero no con marcas futuras.
Ver `docs/memory/backlog.md` para la mejora propuesta.

---

## Bug: falsos negativos en crossing detection a FPS 11–19 (ago 2026)

**Síntoma:** Colisiones en la simulación visual, dependientes del FPS. Desaparecían a FPS ≥ 20
y a FPS ≤ 10, pero ocurrían en el rango 11–19.

**Causa raíz:** `continuous_train.advance()` usaba `round()` para encontrar el slot más
cercano a una junction. Cuando un slot está entre `TRAIN_SPACING/2` y `TRAIN_SPACING` metros
antes de la junction, `round()` devuelve el slot siguiente (que ya cruzó). El slot correcto
nunca se revisaba → el VM cruzaba sin que Brain lo detectara → no subía al árbol →
colisión cuando otro VM aterrizaba en ese slot.

**Fix:** `continuous_train.py` líneas 115-122 — reemplazar `round()` por `floor()` con
rango exacto de slots que cruzan en el frame:
```python
i_high = math.floor(relative / TRAIN_SPACING)
i_low  = math.floor((relative - movement) / TRAIN_SPACING) + 1
for i in range(i_high, i_low - 1, -1):
    slot_idx = i % self.max_slots
```
Matemáticamente exacto para cualquier FPS — sin aproximaciones.

---

## Corrección de gráficos para escenarios de muchas estaciones (ago 2026)

**Problema:** `analysis/` fue diseñado inicialmente para 3 estaciones. Con 27 estaciones
(`linea_1.py`), los labels del eje X se superponían y las series de tiempo compartían colores.

**Helpers creados en `_shared.py` y `_style.py`:**
- `fig_for_stations(n_stations, height=4.5)` — ancho dinámico según número de estaciones
- `station_x_ticks(ax, stations, xlabel_base)` — xticks filtrados + rotados + rango S1←→S27

**Archivos actualizados:** `slot_labels.py`, `trees.py`, `stations.py` — todos usan los helpers.
Para series de tiempo con 27 estaciones, `stations.py` usa paleta expandida (tab20 + tab20b = 40 colores)
con leyenda fuera del área (`bbox_to_anchor=(1.01, 1)`).

---

## Auditoría agosto 2026 — bugs corregidos (resumen)

12 bugs y typos corregidos en sesión 2026-08-10. Los más relevantes por categoría:

**Bugs silenciosos de runtime** (no generaban excepción, resultado incorrecto):
- `continuous_train.py`: `recorder = recorder` → `self._recorder = recorder` (recorder descartado silenciosamente)
- `renderer.py`: `VM_FREE` indefinido → `palette.active["vm_default"]` (NameError latente)
- `simulation.py`: `self._brian` → `self._brain` (typo en atributo)

**Typos en nombres de símbolos** (AttributeError al llamar):
- `spawn_pasenger` → `spawn_passenger` (station.py + test)
- `find_neartest_slot_to_belt_x` → `find_nearest_slot_to_belt_x` (continuous_train + brain)

**Bugs de lógica corregidos en sesiones anteriores** (julio 2026):
- `_would_saturate`: `count >= N` → `count > N` — con `>=`, N=1 bloqueaba siempre el primer VM
- `_make_reservation`: signo invertido en `T_target` → VMs llegaban sistemáticamente desfasados
- `acceleration_tree`: `base_acceleration` pasado como parámetro → movido a cálculo interno desde geometría
- `brain._handle_crossings`: pasajeros no bajaban cuando `reserved == dest` (BUG-T1)
- `brain._handle_crossings`: pasajeros atrapados en VM redirigido → `disembark_all` (BUG-T2)

Para la lista completa con ubicaciones exactas, ver el historial de commits (`git log`).