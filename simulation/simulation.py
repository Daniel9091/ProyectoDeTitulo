"""
Simulation - runner de NSim.

Responsabilidades:
    - Mantener el tiempo de simulación (current_time)
    - Ejecturar frames via brain.update(dt, current_time)
    - Ofrecer run_hadless para correr sin render

Lo que NO hace:
    - No conoce la geometría ni la red (eso es del builder)
    - No dibuja nada (eso es de render)
    - No kcrea ni destruye objetos (eso es de Brain y Station)
"""
from systems.brain import Brain
from config.constants import FPS

class Simulation:
    """
    Wrapper mínimo alrededor de Brian.

    Uso tipico:
        brain, stations = ecenario_base.build()
        sim = Simulation(brain, stations)
        sim.run_headless(n_ticks = 3000)
    """

    def __init__(self,brain: Brain, stations: dict):
        self._brian = brain
        self._stations = stations
        self.current_time: float = 0.0

    def step(self, dt: float) -> None:
        """ Avanza un frame de dt segundos."""
        self._brian.update(dt, self.current_time)
        self.current_time += dt
    
    def run_headless(self, n_ticks: int, dt: float = 1.0 / FPS) -> None:
        """
        Corre n_ticks frames sin render.
        dt por defecto = 1/FPS (un frame real a 30 FPS).
        """
        for _ in range(n_ticks):
            self.step(dt)

        

