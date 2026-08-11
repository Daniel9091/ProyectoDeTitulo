# NSim — Índice de Memoria

> **Leer este archivo al inicio de cualquier sesión sobre NSim**, antes de responder
> cualquier pregunta. CLAUDE.md ya está en contexto (arquitectura e invariantes).
> Este archivo cubre navegación, estado actual y reglas de colaboración.

---

## Reglas de mantenimiento de memoria (siempre activas)

### Dónde vive la memoria
**Toda la memoria del proyecto vive en `docs/memory/` del repo.** Nunca en `~/.claude/` excepto `user_profile.md` (personal, no va al repo). Esto garantiza que sea portable entre máquinas y versionada por git.

### Fecha en cada archivo
Cada archivo de memoria tiene una línea `> Última actualización: YYYY-MM-DD` justo debajo del título. Actualizar esa línea cada vez que se edite el archivo. Si al leer un archivo la fecha tiene más de 30 días, asumir que puede estar stale y verificar contra el código antes de usarlo.

### Reglas basadas en eventos (no en recordar)

**Al INICIAR una sesión:**
Leer `INDEX.md` → inferir qué archivos de `docs/memory/` son relevantes para la tarea → leerlos antes de escribir cualquier código o propuesta.

**Al ENCONTRAR una discrepancia entre memoria y código:**
STOP. Corregir la memoria antes de continuar. Nunca actuar sobre información que contradice el código — el código es la fuente de verdad, pero la memoria desactualizada es un riesgo activo.

**Al TERMINAR de modificar AccelerationTree, Junction, Network, ContinuousTrain o Station:**
Actualizar `design.md` inmediatamente, en la misma sesión. No diferir.

**Al CERRAR un bug o regresión:**
Agregar entrada a `history.md` antes de terminar la sesión.

**Al CAMBIAR el estado de implementación:**
Actualizar `state.md` (tests, qué está completo) y `backlog.md` (qué se abrió o cerró).

**Cuando Daniel dice "actualiza en memoria":**
1. Leer `INDEX.md` completo
2. Leer todos los archivos de `docs/memory/` relacionados con el tema
3. Actualizar cada archivo donde la información cambió
4. Actualizar la fecha de cada archivo que se edite
5. Si el cambio no encaja en ningún archivo existente → proponer dónde añadirlo

### Memoria temporal para tareas largas

Para tareas que duran múltiples sesiones o tienen muchos sub-pasos (ej: escribir el informe de tesis, implementar un SP nuevo), crear un archivo temporal:

**Ubicación:** `docs/memory/wip/wip_<descripcion>.md`
**Formato del nombre:** `wip_` + descripción corta en snake_case (ej: `wip_thesis_chapter2.md`, `wip_sp7_implementation.md`)

**Ciclo de vida:**
1. Se crea al inicio de la tarea larga con el objetivo y los sub-pasos
2. Se actualiza durante el trabajo (decisiones tomadas, hallazgos, referencias)
3. Al terminar la tarea: los hallazgos que merecen documentación permanente se promueven al archivo correcto (`design.md`, `history.md`, `backlog.md`, etc.)
4. El archivo `wip_` se elimina una vez promovido todo lo relevante

**Qué va en un wip:** progreso paso a paso, decisiones intermedias, referencias consultadas, cosas a no olvidar entre sesiones, dudas resueltas.
**Qué NO va en un wip:** decisiones finales confirmadas (esas van directo a la memoria permanente).

### Estructura obligatoria en todos los archivos de memoria
- `# Título` con descripción de qué responde el archivo
- `> Última actualización: YYYY-MM-DD` en la segunda línea
- Secciones con `##`, subsecciones con `###`
- Tablas para comparaciones y campos
- Bloques de código con ``` para fragmentos técnicos
- El razonamiento del POR QUÉ, no solo el qué (el qué está en el código)

### Lo que NO va en memoria permanente
- Contenido deducible leyendo código + docstrings (no duplicar)
- Historial de corridas específicas (va en `analysis/output/`)
- Logs de trabajo o changelogs de sesión (va en `git log`)
- Código completo de funciones (memoria guarda el RAZONAMIENTO y los contratos)

---

---

## Reglas de colaboración (siempre activas)

### Daniel escribe todo el código
Nunca usar `Edit` ni `Write` en archivos del proyecto.
**Excepción aprobada permanente:** archivos en `docs/memory/` son de Claude — sí se pueden editar.
**Excepción puntual:** solo si Daniel lo autoriza explícitamente en el chat para una sesión concreta.

### Formato para propuestas de cambio
Por cada corrección o cambio de código, entregar exactamente esto (en este orden):
1. **Archivo** — path relativo + líneas involucradas (`systems/brain.py:184-190`)
2. **Qué cambiar y por qué** — una oración
3. **Fragmento actual** — solo las líneas afectadas, nunca el archivo completo
4. **Fragmento nuevo** — solo las líneas que reemplazan o se agregan
5. **Dónde va** — si es inserción: "antes de la línea X" o "después del cierre de Y"
6. **Cómo probar** — comando exacto + qué debe dar

Si son múltiples cambios: numerarlos (Paso 1, Paso 2, …). Un bloque por archivo.

### Estilo mentor
Describir qué escribir y cómo, no escribirlo directamente. Explicar el porqué.
Responder siempre en español. Código e identificadores en inglés como de costumbre.

### Antes de proponer cualquier cambio de código
Leer el archivo actual antes de proponer — nunca asumir el estado de una línea desde memoria.
Los docstrings del código son la fuente de verdad para el comportamiento de cada función.

---

## Navegación — pregunta → archivo

| Si te preguntan sobre… | Leer |
|---|---|
| Arquitectura, glosario, contratos entre sistemas | `CLAUDE.md` |
| El loop de 8 pasos de Brain | `CLAUDE.md` §Brain — Diseño Verificado |
| Invariantes de diseño (por qué está así) | `CLAUDE.md` §Invariantes de diseño |
| Sistema de etiquetas de slot (comportamiento) | `CLAUDE.md` §Sistema de Etiquetas de Slots |
| Matemáticas de reserva / búsqueda en rango | `CLAUDE.md` §Sistema de reserva |
| Decisiones de implementación no obvias (cómo está hecho por dentro) | `docs/memory/design.md` |
| AccelerationTree, Junction, slot dict, acoplamiento | `docs/memory/design.md` |
| Qué está implementado, cuántos tests | `docs/memory/state.md` |
| Qué está pendiente / diferido | `docs/memory/backlog.md` |
| Cuánto cuesta tocar un subsistema | `docs/memory/cognitive_load.md` |
| Informe de tesis — cómo escribirlo, qué datos hay | `docs/memory/thesis.md` |
| Telemetría SP1-7, cómo usar analysis.py | `docs/memory/telemetry.md` |
| Un bug o regresión histórica resuelta | `docs/memory/history.md` |
| Cómo trabajamos juntos (reglas de colaboración) | `docs/memory/collaboration.md` |

---

## Estado rápido del proyecto (actualizar al cierre de cada sesión)

| Dimensión | Estado | Fecha |
|---|---|---|
| Tests | **353 / 353 verdes** | agosto 2026 |
| Código (`objects/`, `tracks/`, `systems/`, `simulation/station_factory.py`) | ✅ Completo con tests | agosto 2026 |
| Visualización (`main.py`, `camera.py`, `renderer.py`, `inspector.py`) | ✅ Completo, verificado corriendo | agosto 2026 |
| Análisis (`analysis/`) | ✅ Pipeline completo | agosto 2026 |
| Telemetría SP1–SP6 | ✅ Completo | agosto 2026 |
| Telemetría SP7 (KPIs agregados) | ✅ Completo (via analysis.py) | agosto 2026 |
| Informe de tesis | 🔴 Por escribir (~30 p.) | — |
| Mejoras de cámara | 🟡 Diferido por decisión de Daniel | — |
| Docstrings revisados | ✅ Todos revisados (253 correcciones) | agosto 2026 |
| Bugs conocidos | ✅ Todos resueltos post-auditoría | agosto 2026 |

**Próximo paso activo:** escribir el informe de tesis. Ver `docs/memory/thesis.md`.

---

## Dónde buscar en el código

| Pregunta | Dónde |
|---|---|
| ¿Qué hace este módulo / archivo? | Docstring en la primera línea del archivo |
| ¿Qué hace esta función? ¿qué contrato tiene? | Docstring de la función |
| ¿Cuáles son todas las constantes? | `config/constants.py` |
| ¿Cómo se construye un escenario? | `simulation_builder/inicial.py` (ejemplo de 3 estaciones) |
| ¿Cómo se corre con visualización? | `main.py` |
| ¿Cómo se corre sin visualización? | `simulation/simulation.py` — `run_headless(n_seconds)` |
| ¿Cómo se analiza una corrida? | `docs/memory/telemetry.md` → `python analysis.py` |
| ¿Dónde están los resultados de análisis? | `analysis/output/<run_id>/` |
| ¿Cómo se encuentra un símbolo? | `grep -r "nombre" NSim/` — nunca asumir ubicación |

---

## Filosofía de tests (aplicar siempre al escribir o revisar tests)

- **Tests de cálculos/física**: hardcodear los valores numéricos explícitos, NO importar constantes del proyecto. Si la constante cambia, el test debe fallar — importarla haría que pasara igual aunque el resultado sea incorrecto.
- **Tests de comportamiento y contratos**: sí pueden importar constantes (BOARDING_COMMIT_PROGRESS, TRAIN_SPEED, etc.)
- **Cada clase de test** documenta UNA responsabilidad del objeto; cada método documenta UN comportamiento dentro de esa responsabilidad
- **Qué NO testear**: `__repr__`, propiedades triviales sin lógica, comportamientos que solo fallan si se rompe el lenguaje
- **Objetivo**: no exhaustividad — cubrir los casos donde el programa se rompe de forma silenciosa

---

## Referencia rápida — campos del slot dict (ContinuousTrain)

Cada slot es un dict con 5 campos **independientes** — todos pueden estar activos a la vez:

| Campo | Tipo | Sistema |
|---|---|---|
| `vm` | `ModularVehicle \| None` | presencia física |
| `reserved_station_id` | `int \| None` | anticolicisón — guarda station_id, NO vm_id |
| `reserved_vm_id` | `int \| None` | qué VM viene (Brain mantiene `_reserved_slots: dict[vm_id→slot_idx]` aparte) |
| `destination_station_id` | `int \| None` | routing — dónde debe salir el VM |
| `demand_station_id` | `int \| None` | taza — slot comprometido para suplir demanda |

`place_vm` limpia `reserved_station_id` y `reserved_vm_id`. `remove_vm` limpia `destination_station_id` y `demand_station_id`. Ver CLAUDE.md §Sistema de Etiquetas de Slots para el comportamiento completo.

---

## Instalación en nueva máquina

Al clonar el repo, toda la memoria del proyecto está disponible en `docs/memory/` — no se requiere instalación adicional.