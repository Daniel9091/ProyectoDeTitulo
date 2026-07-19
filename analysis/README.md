# NSim — Pipeline de análisis

Analiza los logs JSONL generados por la simulación y produce reportes y gráficos.

## Uso rápido

```bash
# Sobre la última corrida registrada
python -m analysis

# Sobre una corrida específica
python -m analysis runs/20260718-144520.jsonl
```

Output en `analysis/output/<run_id>/` — un `.txt` + PNGs por módulo.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `_style.py` | **Todo lo visual.** Paleta, tamaños de figura, kwargs de barras/pies. Edita aquí para cambiar el aspecto de todos los gráficos. |
| `_shared.py` | **IO y DB.** Conexión DuckDB, resolución de ruta, `Reporter`, `get_event_types`. Sin lógica visual. |
| `__main__.py` | Entry point. Invoca cada módulo en orden. |
| `passengers.py` | Ciclo de vida de pasajeros (SP2+). |
| `modular_vehicles.py` | Métricas de flota de VMs (SP3+). |
| `stations.py` | Demanda y llegadas por estación. |

---

## Paleta de colores

Todos los colores viven en `_style.py`. Ningún hex literal aparece en los módulos de análisis.

| Clave | Hex | Uso semántico |
|---|---|---|
| `azul` | `#3987e5` | activo, con pasajeros, útil |
| `verde` | `#199e70` | correcto, llegó a destino |
| `naranja` | `#d95926` | vacío, sin pasajeros, incorrecto |
| `violeta` | `#9085e9` | distribuciones neutras (una serie) |

Paleta validada contra fondo `#1e1e2e` (modo oscuro): CVD ΔE ≥ 8, contraste ≥ 3:1,
banda de luminosidad OKLCH 0.48–0.67.

Si necesitas un quinto color, agrégalo en `PALETTE` de `_style.py` y úsalo por clave.
No hardcodees hex en ningún módulo.

---

## Cómo agregar una métrica a un módulo existente

1. Define una función `_mi_metrica(con, rep, out_dir)` en el módulo correspondiente.
2. Usa solo `PALETTE`, `FIG_*`, `BAR_KWARGS`/`PIE_KWARGS`, `TITLE_SIZE` de `_style`.
3. Sigue la convención de texto: sección `[ Nombre ]` + una línea explicatoria + métricas.
4. Llama `save_fig("modulo_nombre", out_dir)` al final de la función.
5. Agrega el guard en `run()`:
   ```python
   if 'event_type_requerido' in types:
       _mi_metrica(con, rep, out_dir)
   ```
6. Actualiza la sección `Charts:` del docstring del módulo.

**Convención de nombre de archivo:** `<módulo>_<función>.png`
(ej: `passengers_time_histograms.png`).

---

## Cómo agregar un módulo nuevo

1. Crea `analysis/mi_modulo.py` con el docstring estándar:

   ```python
   """
   <Descripción en una línea>.

   Questions answered:
     1. <pregunta>  → <función>

   Report:  mi_modulo.txt
   Charts:
     mi_modulo_algo.png  — descripción

   Required event types (SPx+): evento_a, evento_b

   Usage:
     python -c "from analysis.mi_modulo import run; run()"
   """
   ```

2. Implementa `run(events_path=None)` con el mismo patrón:

   ```python
   def run(events_path=None):
       if events_path is None:
           events_path = resolve_run()
       con = connect(events_path)
       out_dir = get_output_dir(events_path)
       rep = Reporter(out_dir, "mi_modulo")
       setup()
       types = get_event_types(events_path, con)
       # ... llamadas condicionales a funciones internas
       rep.save()
       con.close()
   ```

3. Agrega el módulo en `__main__.py`:

   ```python
   from analysis import mi_modulo
   mi_modulo.run(path)
   ```

---

## Notas técnicas

- **DuckDB y schema polimórfico:** los logs JSONL contienen eventos de tipos distintos con
  campos diferentes. Usar siempre `read_ndjson_auto(path, sample_size=-1)` — sin
  `sample_size=-1` DuckDB infiere el schema de las primeras N líneas y falla al leer
  campos que no aparecen en esa muestra.

- **Detección de event types:** `get_event_types()` lee el `run_manifest` de la última
  línea del archivo (O(1)) con fallback a `SELECT DISTINCT type` si el manifest no existe.
  Esto permite que cada módulo se salte funciones cuyos datos no están en la corrida.

- **Error de distancia:** `distance_carrying_passengers` tiene un error ≤ 0.036% por
  desfases de ≤ 0.67m en cada cruce belt↔árbol (overcounting al salir, undercounting al
  llegar — signos opuestos, compensación parcial). Aceptado para tesis.

- **Schema de eventos:** ver `docs/events-schema.md` para la definición completa de cada
  evento, sus campos, y qué sub-proyecto lo introdujo.
