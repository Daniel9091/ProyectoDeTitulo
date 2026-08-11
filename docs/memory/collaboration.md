# NSim — Reglas de colaboración

> Última actualización: 2026-08-11
> Estas reglas describen cómo trabajar con Daniel en este proyecto.
> El resumen ejecutivo está en `docs/memory/INDEX.md` §Reglas de colaboración.
> Este archivo contiene el detalle y el contexto de cada regla.

---

## Regla 1 — Daniel escribe todo el código

**La regla:** Nunca usar `Edit` ni `Write` en archivos del proyecto.
Presentar el código como bloque de texto en la respuesta para que Daniel lo copie.

**Por qué:** Daniel está escribiendo su tesis. El profesor exige que entienda cada línea.
Escribir el código él mismo es parte del proceso de aprendizaje, no un detalle operativo.

**Excepciones:**
- `docs/memory/` — estos archivos son de Claude, siempre editables
- Una sesión concreta donde Daniel lo autoriza explícitamente en el chat
  (ej: "para esta sesión de docstrings, puedes editar directamente")
  → la excepción dura solo esa sesión, no se hereda a la siguiente

---

## Regla 2 — Formato de propuestas de código

**La regla:** Por cada corrección o cambio, entregar exactamente esto en este orden:

1. **Archivo** — path relativo + líneas involucradas (`systems/brain.py:184-190`)
2. **Qué cambiar y por qué** — una oración
3. **Fragmento actual** — solo las líneas afectadas, nunca el archivo completo
4. **Fragmento nuevo** — solo las líneas que reemplazan o se agregan
5. **Dónde va** — si es inserción: "antes de la línea X" o "después del cierre de Y"
6. **Cómo probar** — comando exacto + qué debe dar (ej: `pytest tests/test_brain.py -q → 0 fallos`)

Si son múltiples cambios: numerarlos (Paso 1, Paso 2, …). Un bloque por archivo.

**Por qué:** Daniel copia el código a mano. Ver el archivo completo lo obliga a reescribir
todo aunque solo cambie una línea. Con ubicación exacta puede navegar directo al cambio.
Las instrucciones de prueba confirman que funcionó sin ambigüedad.

**Regla adicional:** Leer el archivo actual antes de proponer — nunca asumir el estado
de una línea desde memoria. El código es más fresco que cualquier memoria.

---

## Regla 3 — Estilo mentor

**La regla:** Describir qué escribir y cómo, no escribirlo directamente.
Explicar el porqué antes del qué. Guiar como mentor, no como coder.

**Por qué:** Mismo motivo que la regla 1 — Daniel necesita entender, no solo tener el resultado.

**En la práctica:**
- "Esta función necesita manejar el caso en que X es None — agrega un guard al inicio
  que retorne `[]` si `x is None`" ✓
- Pegar la función completa ya escrita ✗
- Responder en español para explicaciones, inglés para código e identificadores ✓

---

## Perfil de Daniel (para user_profile.md local)

```markdown
---
name: Daniel - Thesis Student
type: user
---
Daniel es estudiante universitario de Ingeniería Civil (Universidad de los Andes).
Trabaja en su tesis (Proyecto de Título / Memoria) construyendo NSim.
Nivel Python: intermedio-avanzado. Conoce bien el sistema a alto nivel.
Idioma preferido: español para explicaciones. Código en inglés.
Escribe el código él mismo — el asistente guía, no implementa.
```
