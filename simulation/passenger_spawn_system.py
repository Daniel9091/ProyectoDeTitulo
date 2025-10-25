import uuid
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List

# Para evitar importaciones circulares, usamos TYPE_CHECKING para las anotaciones de tipo
if TYPE_CHECKING:
    from objects.brain import Brain

from objects.passenger import Passenger # Importación regular para instanciación en runtime
from objects.base import Vector3 # Importación regular para type hinting de posición

@dataclass
class PassengerGeneratorConfig:
    """
    Configuración para un generador de pasajeros en una estación específica.

    Almacena la tasa de generación, las probabilidades de destino y un acumulador
    para manejar tasas de generación fraccionales a lo largo del tiempo.

    Attributes:
        station_id (str): El ID de la estación donde se generan los pasajeros.
        spawn_rate_per_second (float): Tasa promedio de generación de pasajeros por segundo.
        destination_probabilities (Dict[str, float]): Mapeo de IDs de estaciones de destino
            a sus probabilidades relativas.
        _demand_accumulator (float): Acumulador interno para generar pasajeros cuando se
            alcanza un umbral, permitiendo tasas fraccionales. No se inicializa.
    """
    station_id: str
    spawn_rate_per_second: float
    destination_probabilities: Dict[str, float]
    _demand_accumulator: float = field(default=0.0, init=False)


class PassengerSpawnSystem:
    """
    Sistema responsable de crear (generar) nuevos pasajeros en la simulación
    basado en configuraciones de generadores por estación.
    """

    def __init__(self, brain: 'Brain'):
        """
        Inicializa el sistema de generación de pasajeros.

        Args:
            brain (Brain): La instancia del cerebro central de la simulación, usada para
                           acceder al estado global del sistema (ej. estaciones).
        """
        self.brain: 'Brain' = brain
        self.generators: List[PassengerGeneratorConfig] = []

    def add_generator(self, station_id: str, spawn_rate_per_second: float, destination_probabilities: Dict[str, float]) -> None:
        """
        Añade y configura un nuevo generador de pasajeros para una estación.

        Args:
            station_id (str): El ID de la estación donde se generarán los pasajeros.
            spawn_rate_per_second (float): Cuántos pasajeros se deben generar por segundo en promedio.
            destination_probabilities (Dict[str, float]): Un diccionario que mapea los IDs de las
                estaciones de destino a una probabilidad (un valor entre 0 y 1).
        """
        config = PassengerGeneratorConfig(
            station_id=station_id,
            spawn_rate_per_second=spawn_rate_per_second,
            destination_probabilities=destination_probabilities
        )
        self.generators.append(config)
        print(f"INFO: Generador de pasajeros añadido para estación '{station_id}' con tasa {spawn_rate_per_second}/s.")

    def update(self, dt: float) -> None:
        """
        Actualiza el sistema de generación de pasajeros, creando nuevos pasajeros
        basado en las tasas de generación configuradas.

        Args:
            dt (float): Delta time, el tiempo transcurrido desde la última actualización en segundos.
        """
        for generator in self.generators:
            # Acumular la demanda de pasajeros en base a la tasa de generación y el tiempo transcurrido
            generator._demand_accumulator += generator.spawn_rate_per_second * dt

            # Generar pasajeros si el acumulador alcanza o supera 1.0
            while generator._demand_accumulator >= 1.0:
                self._spawn_passenger(generator)
                generator._demand_accumulator -= 1.0 # Restar 1.0 por cada pasajero generado

    def _spawn_passenger(self, config: PassengerGeneratorConfig) -> None:
        """
        Crea y registra un nuevo pasajero en la simulación.

        Args:
            config (PassengerGeneratorConfig): La configuración del generador que solicita el spawn.
        """
        origin_station_id = config.station_id
        origin_station = self.brain.stations.get(origin_station_id)

        if not origin_station:
            print(f"ERROR: No se pudo generar pasajero. Estación de origen '{origin_station_id}' no encontrada.")
            return

        # Elegir un destino basado en las probabilidades configuradas
        destination_ids = list(config.destination_probabilities.keys())
        weights = list(config.destination_probabilities.values())

        if not destination_ids:
            print(f"ERROR: No se pudo generar pasajero. No hay destinos definidos para la estación '{origin_station_id}'.")
            return

        chosen_destination_id = random.choices(destination_ids, weights=weights, k=1)[0]

        # La posición inicial del pasajero es la posición de la estación de origen
        initial_position: Vector3 = origin_station.position

        # Generar un ID único para el pasajero
        passenger_id = f"P_{origin_station_id}_{str(uuid.uuid4())[:8]}"

        new_passenger = Passenger(passenger_id, origin_station_id, chosen_destination_id, initial_position)
        self.brain.register_new_passenger(new_passenger)
        print(f"✅ Pasajero {new_passenger.passenger_id} generado en '{origin_station_id}' con destino '{chosen_destination_id}'.")