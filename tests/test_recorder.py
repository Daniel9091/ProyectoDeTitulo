"""
Qué se verifica aquí:
    - Que cada evento queda escrito con los campos base correctos
    - Que seq sube uno por evento
    - Que el buffer no se escribe a disco hasta llegar al umbral
    - Que close() vuelca lo que queda aunque no llegue al umbral
    - Que close() es seguro llamarlo dos veces
    - Que los Enum en el payload se convierten a su .value
    - Que NullRecorder no crea ningún archivo

Todos los tests usan tmp_path (directorio temporal de pytest) para no
dejar archivos en el repositorio.
"""
import json
from pathlib import Path
from enum import Enum

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telemetry.recorder import Recorder, NullRecorder

class _FakeEnum(Enum):
    """Enum de mentira para probar la serialización sin depender de tipos del dominio."""
    FOO = "foo"

def _read_lines(path: Path) -> list[dict]:
    """Lee un archivo JSONL y retorna sus líneas como lista de dicts."""
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]

class TestRecorderMechanism:
    """Verifica el comportamiento interno: buffer, flush, seq, cierre."""

    def test_run_started_writes_base_fields_on_close(self, tmp_path):
        """
        Un evento run_started debe quedar en disco (después de close) con los
        cuatro campos base: schema_version=1, seq=0, t correcto, type="run_started",
        más el campo específico config con el dict que se pasó.
        """
        recorder = Recorder(run_dir=tmp_path, run_id="test_run")
        recorder.run_started(t=0.0, config={"seed": 42})
        recorder.close()

        lines = _read_lines(tmp_path / "events.jsonl")
        assert len(lines) == 1
        event = lines[0]
        assert event["schema_version"] == 1
        assert event["seq"] == 0
        assert event["t"] == 0.0
        assert event["type"] == "run_started"
        assert event["config"] == {"seed": 42}

    def test_seq_increments_across_events(self, tmp_path):
        """
        seq debe subir uno por cada evento emitido, sin importar el tipo.
        Primer evento → seq=0, segundo → seq=1. El type también debe coincidir
        con el orden de llamada.
        """
        recorder = Recorder(run_dir=tmp_path, run_id="test_run")
        recorder.run_started(t=0.0, config={})
        recorder.run_ended(t=10.0, summary={})
        recorder.close()

        lines = _read_lines(tmp_path / "events.jsonl")
        assert [e["seq"] for e in lines] == [0, 1]
        assert [e["type"] for e in lines] == ["run_started", "run_ended"]

    def test_flushes_to_disk_at_threshold(self, tmp_path):
        """
        Con flush_every=3, los primeros 2 eventos deben quedarse en memoria
        (el archivo existe pero está vacío). Al emitir el 3er evento, el buffer
        se vuelca y el archivo debe tener las 3 líneas.
        """
        recorder = Recorder(run_dir=tmp_path, run_id="test_run", flush_every=3)
        events_path = tmp_path / "events.jsonl"

        recorder.run_started(t=0.0, config={})
        recorder.run_started(t=1.0, config={})
        assert events_path.read_text() == ""  # existe pero sin datos (todavia no llega al umbral)

        recorder.run_started(t=2.0, config={})  # 3er evento -> flush
        assert len(_read_lines(events_path)) == 3

    def test_close_flushes_pending_buffer_below_threshold(self, tmp_path):
        """
        Si hay eventos en el buffer pero no se llegó al umbral, close() debe
        volcarlos de todas formas. Sin esto, el último trozo de eventos se
        perdería al cerrar la simulación.
        """
        recorder = Recorder(run_dir=tmp_path, run_id="test_run", flush_every=100)
        recorder.run_started(t=0.0, config={})
        recorder.close()

        assert len(_read_lines(tmp_path / "events.jsonl")) == 1

    def test_close_is_safe_to_call_twice(self, tmp_path):
        """
        close() puede llamarse más de una vez sin error. Esto importa porque
        main.py lo llama desde un bloque finally que puede ejecutarse después
        de que el loop ya lo haya cerrado normalmente.
        """
        recorder = Recorder(run_dir=tmp_path, run_id="test_run")
        recorder.run_started(t=0.0, config={})
        recorder.close()
        recorder.close()  # no debe lanzar excepcion

        assert len(_read_lines(tmp_path / "events.jsonl")) == 1

    def test_enum_field_serializes_to_its_value(self, tmp_path):
        """
        Si un campo del evento contiene un Enum (ej. ModularVehicleState.MOVING),
        debe guardarse en el JSONL como su .value string ("MOVING"), no como el
        objeto Python que json no sabe serializar.
        """
        recorder = Recorder(run_dir=tmp_path, run_id="test_run")
        recorder.run_started(t=0.0, config={"mode": _FakeEnum.FOO})
        recorder.close()

        lines = _read_lines(tmp_path / "events.jsonl")
        assert lines[0]["config"]["mode"] == "foo"

class TestNullRecorder:
    """Verifica que NullRecorder no crea archivos ni falla."""

    def test_null_recorder_creates_no_files(self, tmp_path):
        """
        NullRecorder no debe crear ningún archivo ni directorio aunque se llamen
        todos sus métodos. Sirve cuando TELEMETRY_ENABLED=False — el código del
        dominio llama igual a los métodos y simplemente no pasa nada.
        """
        recorder = NullRecorder()
        recorder.run_started(t=0.0, config={"seed": 42})
        recorder.run_ended(t=10.0, summary={})
        recorder.close()

        assert list(tmp_path.iterdir()) == []

class TestPassenerEvents:
    """Verifica que cada evento de ciclo de vida escribe los campos correctos."""

    def test_passenger_spawned_writes_fields(self, tmp_path):
        """
        passenger_spawned debe escribir los campos de identidad del pasajero:
        origen, destino, y su id. No incluye spawn_time porque t == spawn_time al generarse.
        """
        recorder = Recorder(run_dir=tmp_path, run_id="test_run")
        recorder.passenger_spawned(t=5.0, passenger_id=1, origin_station_id=1, destination_station_id=3)
        recorder.close()

        event = _read_lines(tmp_path / "events.jsonl")[0]
        assert event["type"] == "passenger_spawned"
        assert event["t"] == 5.0
        assert event["passenger_id"] == 1
        assert event["origin_station_id"] == 1
        assert event["destination_station_id"] == 3

    def test_passenger_boarded_writes_fields(self, tmp_path):
        """
        passenger_boarded debe incluir el vm_id y spawn_time del pasajero.
        Con estos dos campos y el t del evento se puede calcular wait_time = t - spawn_time.
        """
        recorder = Recorder(run_dir=tmp_path, run_id="test_run")
        recorder.passenger_boarded(t=20.0, passenger_id=1, vm_id=7, spawn_time=5.0)
        recorder.close()

        event = _read_lines(tmp_path / "events.jsonl")[0]
        assert event["type"] == "passenger_boarded"
        assert event["passenger_id"] == 1
        assert event["vm_id"] == 7
        assert event["spawn_time"] == 5.0

    def test_passenger_transit_writes_fields(self, tmp_path):
        """
        passenger_transit se emite cuando el VM del pasajero pasa por una estación
        que no es su destino. Registra qué estación y en qué VM iba el pasajero.
        """
        recorder = Recorder(run_dir=tmp_path, run_id="test_run")
        recorder.passenger_transit(t=35.0, passenger_id=1, vm_id=7, station_id=2)
        recorder.close()

        event = _read_lines(tmp_path / "events.jsonl")[0]
        assert event["type"] == "passenger_transit"
        assert event["passenger_id"] == 1
        assert event["vm_id"] == 7
        assert event["station_id"] == 2

    def test_passenger_arrived_writes_fields(self,tmp_path):
        """
        passenger_arrived incluye spawn_time para que el análisis pueda calcular
        travel_time = t - spawn_time sin necesitar cruzar con passenger_spawned.
        """
        recorder = Recorder(run_dir=tmp_path, run_id="test_run")
        recorder.passenger_arrived(t=78.0, passenger_id=1, station_id=3, spawn_time=5.0)
        recorder.close()

        event = _read_lines(tmp_path / "events.jsonl")[0]
        assert event["type"] == "passenger_arrived"
        assert event["passenger_id"] == 1
        assert event["station_id"] == 3
        assert event["spawn_time"] == 5.0

    def test_passenger_arrived_wrong_writes_fields(self, tmp_path):
        """
        passenger_arrived_wrong debe incluir la estación real donde bajó
        y expected_station_id para saber adónde debía ir.
        """
        recorder = Recorder(run_dir=tmp_path, run_id="test_run")
        recorder.passenger_arrived_wrong(t=78.0, passenger_id=1,
                                        station_id=2, expected_station_id=3,
                                        spawn_time=5.0)
        recorder.close()

        event = _read_lines(tmp_path / "events.jsonl")[0]
        assert event["type"] == "passenger_arrived_wrong"
        assert event["passenger_id"] == 1
        assert event["station_id"] == 2
        assert event["expected_station_id"] == 3
        assert event["spawn_time"] == 5.0



