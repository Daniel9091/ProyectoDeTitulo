"""
Registro estructurado de eventos de una corrida de NSim.

Responsabilidades:
    - Serializar eventos a JSONL con campos base consistentes
      (schema_version, seq, t, type)
    - Bufferizar en memoria y volcar a disco cada N eventos y al cerrar

Lo que NO hace:
    - No sabe qué eventos existen a nivel de dominio (pasajero, VM, choque,
      etc.) — esos se agregan como métodos nuevos en sub-proyectos futuros
    - No decide si la telemetría está activa — main.py elige entre Recorder
      y NullRecorder según config/constants.py:TELEMETRY_ENABLED
"""
import json
from enum import Enum
from pathlib import Path

SCHEMA_VERSION = 1

def _json_default(obj):
    """
    Encoder de respaldo para json.dumps.
    Convierte cualquier Enum a su .value (ej. ModularVehicleState.MOVING → "MOVING").
    Lanza TypeError si el objeto no es serializable — falla ruidoso en vez de silencioso.
    """
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Objeto no serializable: {obj}")

class Recorder:
    """
    Escribe eventos estructurados a runs/<run_id>/events.jsonl.

    Cada evento tiene siempre estos campos base:
        schema_version  — versión del esquema (empieza en 1)
        seq             — contador monotónico; permite ordenar eventos del mismo tick
        t               — tiempo simulado en segundos
        type            — nombre del evento (ej. "run_started")

    El archivo se abre al construir el Recorder y se cierra con close().
    close() es seguro llamarlo más de una vez.
    """

    def __init__(self, run_dir: Path, run_id: str, flush_every: int = 100):
        """
        run_dir     — directorio donde se crea events.jsonl (se crea si no existe)
        run_id      — identificador de la corrida; solo se usa para referencia interna
        flush_every — cuántos eventos acumular antes de escribir a disco
                      (100 por defecto; usar valores bajos solo en tests)
        """
        self._run_dir = Path(run_dir)
        self._run_id = run_id
        self._flush_every = flush_every
        self._buffer: list[dict] = []
        self._seq = 0
        self._closed = False

        self._run_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = self._run_dir / "events.jsonl"
        self._file = open(self._events_path, "a", encoding="utf-8")

    def run_started(self, t: float, config: dict) -> None:
        """
        Emite el primer evento de la corrida. Debe llamarse una sola vez, justo
        después de construir el escenario. config debe incluir seed, scenario_name
        y todas las constantes relevantes para poder reproducir la corrida.
        """
        self._emit("run_started", t, {"config": config})

    def run_ended(self, t: float, summary: dict) -> None:
        """
        Emite el último evento de la corrida. Debe llamarse desde el bloque finally
        de main.py para que se ejecute aunque la simulación haya terminado con error.
        summary contiene las métricas agregadas (KPIs) de la corrida.
        """
        self._emit("run_ended", t, {"summary": summary})

    def close(self) -> None:
        """
        Vuelca el buffer pendiente a disco y cierra el archivo.
        Seguro llamarlo más de una vez — las llamadas extra no hacen nada.
        """
        if self._closed:
            return
        self._flush()
        self._file.close()
        self._closed = True

    # ── internos ─────────────────────────────────────────────────────────

    def _emit(self, event_type: str, t: float, fields: dict) -> None:
        """
        Construye el dict del evento con los campos base más los específicos,
        lo agrega al buffer e incrementa seq. Si el buffer llega a flush_every,
        lo vuelca a disco automáticamente.
        """
        event = {
            "schema_version": SCHEMA_VERSION,
            "seq": self._seq,
            "t": t,
            "type": event_type,
            **fields,
        }
        self._seq += 1
        self._buffer.append(event)
        if len(self._buffer) >= self._flush_every:
            self._flush()

    def _flush(self) -> None:
        """
        Escribe todos los eventos del buffer al archivo (una línea JSON por evento),
        fuerza el flush del SO y vacía el buffer en memoria.
        No hace nada si el buffer ya está vacío.
        """
        if not self._buffer:
            return
        for event in self._buffer:
            self._file.write(json.dumps(event, default=_json_default) + "\n")
        self._file.flush()
        self._buffer.clear()

class NullRecorder:
    """
    Versión sin efecto de Recorder. Misma interfaz pública, todos los métodos
    son no-op. Se usa cuando TELEMETRY_ENABLED es False para evitar ramas
    `if recorder:` en el dominio — el código llama igual a los métodos y
    simplemente no pasa nada.
    """

    def run_started(self, t: float, config: dict) -> None:
        pass

    def run_ended(self, t: float, summary: dict) -> None:
        pass

    def close(self) -> None:
        pass


