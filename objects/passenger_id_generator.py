"""
PassengerIdGenerator - Contador global de IDs de pasajeros

Una sola instancia por simulaicon. Se pasa a cada Station como parametro.
Garantiza IDs unicos entre todas las estaciones sin limite por estacion.
"""

class PassengerIdGenerator:
    """
    Genera IDs enteros unicos y crecientes para psajeros.
    La trazabilidad de la estacion se lee en passenger.origin_station_id,
    no en el ID en sí.
    """
    def __init__(self):
        self._counter: int = 0
        
    def next_id(self) -> int:
        """
        Retorna el siguiente ID disponible e incrementa el contador.
        """
        pid = self._counter
        self._counter += 1
        return pid