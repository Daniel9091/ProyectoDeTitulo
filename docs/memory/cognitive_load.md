# NSim — Carga cognitiva

> Última actualización: 2026-08-11 (tabla histórica agregada)
> Responde a: "¿Cuánto cuesta tocar X? ¿qué tengo que releer antes de hacer un cambio?"
> Actualizar si cambia significativamente la complejidad de un subsistema.

---

## Qué mide el porcentaje

Dado un task bien especificado, el porcentaje es la **probabilidad de introducir un bug
o requerir una ronda extra de aclaraciones** porque el contexto existente no era suficiente.

Se miden tres cosas:
1. **Contratos entre sistemas** — si al modificar X necesito saber qué espera Y, ¿está documentado y verificado con tests?
2. **Invariantes no obvios** — ¿cuántas reglas silenciosas existen que si se violan no dan error inmediato pero dan resultados incorrectos?
3. **Brechas de contexto** — ¿cuántos archivos están vacíos, mal documentados o contradicen la documentación?

**Escala de referencia:**
- 1-5%: casi seguro de hacerlo bien a la primera
- 10-15%: probablemente una ronda de corrección
- 30-40%: múltiples rondas, riesgo de romper invariantes silenciosos
- 65-85%: alta probabilidad de bugs, requiere leer código extensamente antes de cualquier cambio

**Tipos de cambio:**
- **Pequeño** — agregar un test, cambiar una constante, corregir un docstring, añadir un método sin efectos en otros sistemas
- **Mediano** — modificar un método existente con efectos secundarios, añadir funcionalidad a un sistema que ya existe, conectar dos sistemas existentes
- **Grande** — implementar un sistema nuevo que coordina múltiples componentes, refactorizar la arquitectura, cambiar el loop principal

---

## Números actuales (post-auditoría agosto 2026)

| Tipo | Promedio proyecto |
|---|---|
| **Pequeño** | **1.0%** |
| **Mediano** | **1.5%** |
| **Grande** | **3.0%** |

Estos son promedios. La carga varía mucho según el subsistema:

| Subsistema | Pequeño | Mediano | Grande |
|---|---|---|---|
| `simulation/` — UI/render, sin invariantes de simulación | ~0.5% | ~1% | ~2% |
| `objects/`, `tracks/` — estructuras de datos y física básica | ~1% | ~1.5% | ~2.5% |
| `systems/network`, `continuous_train` — coordinación moderada | ~1% | ~2% | ~4% |
| `systems/brain` — coordinador central | ~1% | **~3-5%** | **~6-8%** |

---

## Por qué brain.py es más difícil

Incluso con docstrings perfectos, tiene invariantes que requieren releer el código antes de cambios medianos o grandes:

1. **Math de reserva** — `T_target = T_total - raw_offset * (...)`. El signo negativo es contraintuitivo: un slot adelante del target llega antes → el VM debe apurarse → T_target debe ser menor. Bug real con el signo `+` (jul 2026).
2. **Sistema 3 etiquetas** — `reserved_station_id`, `destination_station_id`, `demand_station_id` son independientes. Las interacciones al cruzar junctions tienen múltiples combinaciones por etiqueta.
3. **Orden del loop de 8 pasos** — el invariante "tracks ANTES que junction routing" previene un doble advance. Fácil de romper al agregar lógica entre pasos.
4. **`count > N` vs `count >= N`** en `_would_saturate` — el `>=` bloqueaba el primer VM en estaciones de 1 andén. Bug real (jul 2026).

---

## Evolución histórica de la carga cognitiva

La tabla muestra cómo bajó la probabilidad de introducir un bug a medida que NSim maduró.
Útil para la tesis: demuestra que el rebuild y las prácticas de ingeniería tuvieron impacto medible.

| Tipo | Sim | NSim inicial | Brain vacío | Brain completo | 329 tests (jun) | Post-audit (ago 2026) |
|---|---|---|---|---|---|---|
| **Pequeño** | 40% | 15% | 3% | 2% | 2% | **1%** |
| **Mediano** | 65% | 30% | 7% | 5% | 3% | **1.5%** |
| **Grande** | 85% | 45% | 14% | 10% | 4% | **3%** |

**Qué explica cada salto:**
- **Sim → NSim inicial**: separación de responsabilidades, jerarquía de imports sin circulares
- **NSim → Brain vacío**: tests en objects/ y tracks/ eliminaron ambigüedad en contratos base
- **Brain vacío → completo**: los 74 tests de brain documentan todos los invariantes del coordinador central
- **329 tests → post-audit**: corrección de 12 bugs silenciosos + revisión exhaustiva de docstrings en todos los módulos

---

## Qué es seguro tocar sin releer extensamente

- Cualquier cosa en `simulation/` (camera, renderer, inspector, palette) — sin invariantes de simulación
- Constantes en `config/constants.py` — cuidado si la constante es física (puede propagarse a brain.py)
- Agregar tests — siempre seguro
- Geometría de `station_factory.py` — verificar con los ejemplos de `_lane_y_offsets`

## Señal de alerta — releer brain.py antes de empezar si el cambio toca

- `systems/brain.py` directamente
- `systems/continuous_train.py` — los slots y sus etiquetas
- `tracks/junction.py` — burst_capacity / burst_window
- `tracks/acceleration_tree.py` — base_acceleration y MRUA