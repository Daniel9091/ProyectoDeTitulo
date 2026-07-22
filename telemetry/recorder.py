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

        self._event_types_seen: set[str] = set()
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

    # ── Passengers ───────────────────────────────────────────────────────

    def passenger_spawned(self, t: float, passenger_id: int,
                        origin_station_id: int, destination_station_id: int) -> None:
        """Pasajero creado en la estación origen."""
        self._emit("passenger_spawned", t, {
            "passenger_id":             passenger_id,
            "origin_station_id":        origin_station_id,
            "destination_station_id":   destination_station_id,
        })

    def passenger_boarded(self, t: float, passenger_id: int,
                        vm_id: int, spawn_time: float) -> None:
        """Embarque comprometido (BOARDING_COMMIT_PROGRESS alcanzado). spawn_time permite calcular wait_time."""
        self._emit("passenger_boarded", t, {
            "passenger_id": passenger_id,
            "vm_id":        vm_id,
            "spawn_time":   spawn_time,
        })

    def passenger_transit(self, t: float, passenger_id: int,
                        vm_id: int, station_id: int) -> None:
        """VM del pasajero entró a una estación intermedia; el pasajero no bajó."""
        self._emit("passenger_transit", t, {
            "passenger_id": passenger_id,
            "vm_id":        vm_id,
            "station_id":   station_id,
        })

    def passenger_arrived(self, t: float, passenger_id: int,
                        station_id: int, spawn_time: float) -> None:
        """Pasajero llegó a su destino y bajó del VM. spawn_time permite calcular travel_time."""
        self._emit("passenger_arrived", t, {
            "passenger_id": passenger_id,
            "station_id":   station_id,
            "spawn_time":   spawn_time,
        })

    def passenger_arrived_wrong(self, t: float, passenger_id: int,
                                 station_id: int, expected_station_id: int,
                                 spawn_time: float) -> None:
        """Pasajero bajó en una estación que NO era su destino (VM redirigido)."""
        self._emit("passenger_arrived_wrong", t, {
            "passenger_id":          passenger_id,
            "station_id":            station_id,
            "expected_station_id":   expected_station_id,
            "spawn_time":            spawn_time,
        })

    # ── Modular Vehicles ────────────────────────────────────────────────────

    def vm_run_summary(self, t: float, vm_id: int,
                        total_distance: float, operational_time: float,
                        distance_carrying_passengers: float) -> None:
        """Métricas acumuladas del VM al cierre de la corrida."""
        self._emit("vm_run_summary", t, {
            "vm_id":             vm_id,
            "total_distance":    total_distance,
            "operational_time":  operational_time,
            "distance_carrying_passengers": distance_carrying_passengers,
        })

    def vm_created(self, t: float, vm_id: int) -> None:
        """VM registrado en la flota al construirse la simulación."""
        self._emit("vm_created", t, {"vm_id": vm_id})

    def vm_trip_completed(self, t: float, vm_id: int,
                        passenger_count: int, lane_length: float) -> None:
        """VM completó el boarding lane. passenger_count=0 significa que pasó vacío."""
        self._emit("vm_trip_completed", t, {
            "vm_id":            vm_id,
            "passenger_count":  passenger_count,
            "lane_length":      lane_length,
        })

    # ── Etiquetas de slot ───────────────────────────────────────────────────

    def slot_reserved(self, t: float, slot_idx: int, station_id: int, vm_id: int,
                      target_idx: int, slot_offset: int, priority: str,
                      T_total: float, accel: float, prev_labels: dict) -> None:
        """Slot marcado como destino de aterrizaje para un VM que viene bajando."""
        self._emit("slot_reserved", t, {
            "slot_idx":    slot_idx,
            "station_id":  station_id,
            "vm_id":       vm_id,
            "target_idx":  target_idx,
            "slot_offset": slot_offset,
            "priority":    priority,
            "T_total":     round(T_total, 4),
            "accel":       round(accel, 4),
            "prev_labels": prev_labels,
        })

    def slot_reservation_cleared(self, t: float, slot_idx: int,
                                  station_id: int, reason: str) -> None:
        """Reserva liberada. reason: 'vm_arrived' | 'missed_junction'."""
        self._emit("slot_reservation_cleared", t, {
            "slot_idx":   slot_idx,
            "station_id": station_id,
            "reason":     reason,
        })

    def slot_demand_set(self, t: float, slot_idx: int, station_id: int,
                        priority: str, prev_labels: dict) -> None:
        """Slot marcado para satisfacer demanda de una estación."""
        self._emit("slot_demand_set", t, {
            "slot_idx":    slot_idx,
            "station_id":  station_id,
            "priority":    priority,
            "prev_labels": prev_labels,
        })

    def slot_demand_cleared(self, t: float, slot_idx: int,
                             station_id: int, reason: str) -> None:
        """Etiqueta de demanda limpiada. reason: 'vm_entered_tree' | 'commitment_broken'."""
        self._emit("slot_demand_cleared", t, {
            "slot_idx":   slot_idx,
            "station_id": station_id,
            "reason":     reason,
        })

    def slot_destination_set(self, t: float, slot_idx: int, station_id: int,
                              vm_id: int | None, source: str, prev_dest: int | None) -> None:
        """Destino del VM escrito en el slot. source: 'boarding_commit' | 'reservations_pass' | 'redirect'."""
        self._emit("slot_destination_set", t, {
            "slot_idx":   slot_idx,
            "station_id": station_id,
            "vm_id":      vm_id,
            "source":     source,
            "prev_dest":  prev_dest,
        })

    def slot_destination_cleared(self, t: float, slot_idx: int, station_id: int) -> None:
        """Destino limpiado cuando el VM sale del carril hacia el árbol UP."""
        self._emit("slot_destination_cleared", t, {
            "slot_idx":   slot_idx,
            "station_id": station_id,
        })

    def junction_vm_entered(self, t: float, station_id: int, vm_id: int,
                             slot_idx: int, forced: bool) -> None:
        """VM entró al árbol UP de la estación. forced=True si fue force_add_vm."""
        self._emit("junction_vm_entered", t, {
            "station_id": station_id,
            "vm_id":      vm_id,
            "slot_idx":   slot_idx,
            "forced":     forced,
        })

    def junction_commitment_broken(self, t: float, station_id: int,
                                    vm_id: int, slot_idx: int) -> None:
        """Árbol rechazó VM de demanda — compromiso roto, VM sigue en belt."""
        self._emit("junction_commitment_broken", t, {
            "station_id": station_id,
            "vm_id":      vm_id,
            "slot_idx":   slot_idx,
        })

    def slot_collision(self, t: float, slot_idx: int,
                       vm_arriving_id: int, vm_occupying_id: int,
                       prev_labels: dict) -> None:
        """Dos VMs en el mismo slot — reserva falló o llegó tarde."""
        self._emit("slot_collision", t, {
            "slot_idx":       slot_idx,
            "vm_arriving_id": vm_arriving_id,
            "vm_occupying_id": vm_occupying_id,
            "prev_labels":    prev_labels,
        })

    def slot_search_completed(self, t: float, context: str, station_id: int,
                            selected_slot_idx, selected_priority: str,
                            window: list) -> None:
        self._emit("slot_search_completed", t, {
            "context":            context,
            "station_id":         station_id,
            "selected_slot_idx":  selected_slot_idx,
            "selected_priority":  selected_priority,
            "window":             window,
        })

    # ── Árboles y colisiones en track ──────────────────────────────────────────

    def tree_vm_entered(self, t: float, station_id: int, tree_idx: int,
                        vm_id: int, forced: bool, reason: str,
                        vehicle_count_after: int, nearest_existing_distance) -> None:
        """VM entró a un árbol UP. tree_idx = índice del andén elegido dentro del junction."""
        self._emit("tree_vm_entered", t, {
            "station_id":              station_id,
            "tree_idx":                tree_idx,
            "vm_id":                   vm_id,
            "forced":                  forced,
            "reason":                  reason,
            "vehicle_count_after":     vehicle_count_after,
            "nearest_existing_distance": nearest_existing_distance,
        })

    def track_collision_started(self, t: float, track_id: int,
                                 vm_id_1: int, vm_id_2: int,
                                 separation, pos_x, pos_y, pos_z) -> None:
        """Dos VMs en el mismo track se acercaron a menos de TRAIN_VM_LENGTH."""
        self._emit("track_collision_started", t, {
            "track_id":   track_id,
            "vm_id_1":    vm_id_1,
            "vm_id_2":    vm_id_2,
            "separation": separation,
            "pos_x":      pos_x,
            "pos_y":      pos_y,
            "pos_z":      pos_z,
        })

    def track_collision_ended(self, t: float, track_id: int,
                               vm_id_1: int, vm_id_2: int,
                               separation, pos_x, pos_y, pos_z,
                               reason: str) -> None:
        """Par colisionando volvió a >= TRAIN_VM_LENGTH o uno salió del track."""
        self._emit("track_collision_ended", t, {
            "track_id":   track_id,
            "vm_id_1":    vm_id_1,
            "vm_id_2":    vm_id_2,
            "separation": separation,
            "pos_x":      pos_x,
            "pos_y":      pos_y,
            "pos_z":      pos_z,
            "reason":     reason,
        })

    # ── Station ────────────────────────────────────────────────────────────────

    def station_snapshot(self, t: float, station_id: int,
                        active_anden_count: int, pending_demand: int,
                        andenes: list) -> None:
        self._emit("station_snapshot", t, {
            "station_id":          station_id,
            "active_anden_count":  active_anden_count,
            "pending_demand":      pending_demand,
            "andenes":             andenes,
        })



    def close(self) -> None:
        """
        Vuelca el buffer pendiente a disco y cierra el archivo.
        Seguro llamarlo más de una vez — las llamadas extra no hacen nada.
        """
        if self._closed: return
        
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "seq":            self._seq,
            "t":              -1,
            "type":           "run_manifest",
            "event_types":    sorted(self._event_types_seen),
        }
        self._buffer.append(manifest)
        self._seq += 1

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
        self._event_types_seen.add(event_type)
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
    # ── Generales ─────────────────────────────────────────────────────────
    
    def run_started(self, t: float, config: dict) -> None: pass
        
    def run_ended(self, t: float, summary: dict) -> None: pass

    def close(self) -> None: pass

    # ── Pasajeros ─────────────────────────────────────────────────────────

    def passenger_spawned(self, t: float, passenger_id: int,
                      origin_station_id: int, destination_station_id: int) -> None: pass

    def passenger_boarded(self, t: float, passenger_id: int,
                        vm_id: int, spawn_time: float) -> None: pass

    def passenger_transit(self, t: float, passenger_id: int,
                        vm_id: int, station_id: int) -> None: pass

    def passenger_arrived(self, t: float, passenger_id: int,
                        station_id: int, spawn_time: float) -> None: pass

    def passenger_arrived_wrong(self, t: float, passenger_id: int,
                                 station_id: int, expected_station_id: int,
                                 spawn_time: float) -> None: pass

    # ── Modular Vehicles ────────────────────────────────────────────────────

    def vm_run_summary(self, t: float, vm_id: int,
                        total_distance: float, operational_time: float,
                        distance_carrying_passengers: float) -> None: pass

    def vm_created(self, t: float, vm_id: int) -> None: pass

    def vm_trip_completed(self, t: float, vm_id: int,
                        passenger_count: int, lane_length: float) -> None: pass

    # ── Etiquetas de slot ───────────────────────────────────────────────────

    def slot_reserved(self, t, slot_idx, station_id, vm_id, target_idx,
                      slot_offset, priority, T_total, accel, prev_labels): pass
    
    def slot_reservation_cleared(self, t, slot_idx, station_id, reason): pass

    def slot_demand_set(self, t, slot_idx, station_id, priority, prev_labels): pass

    def slot_demand_cleared(self, t, slot_idx, station_id, reason): pass

    def slot_destination_set(self, t, slot_idx, station_id, vm_id, source, prev_dest): pass

    def slot_destination_cleared(self, t, slot_idx, station_id): pass

    def junction_vm_entered(self, t, station_id, vm_id, slot_idx, forced): pass

    def junction_commitment_broken(self, t, station_id, vm_id, slot_idx): pass

    def slot_collision(self, t, slot_idx, vm_arriving_id, vm_occupying_id, prev_labels): pass

    def slot_search_completed(self, t, context, station_id,
                          selected_slot_idx, selected_priority, window): pass

    # ── Árboles y colisiones en track ──────────────────────────────────────────

    def tree_vm_entered(self, t, station_id, tree_idx, vm_id, forced, reason,
                        vehicle_count_after, nearest_existing_distance): pass
    
    def track_collision_started(self, t, track_id, vm_id_1, vm_id_2,
                                 separation, pos_x, pos_y, pos_z): pass
    
    def track_collision_ended(self, t, track_id, vm_id_1, vm_id_2,
                               separation, pos_x, pos_y, pos_z, reason): pass

    # ── Station ──────────────────────────────────────────────────────────────

    def station_snapshot(self, t, station_id, active_anden_count, pending_demand, andenes): pass


