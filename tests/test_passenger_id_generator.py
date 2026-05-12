"""
Tests para PassengerIdGenerator

PassengerIdGenerator es responsable de:
    - Proveer IDs enteros únicos y crecientes para pasajeros
    - Mantener independencia entre instancias distintas
    - Garantizar unicidad global sin importar cuántos pasajeros se generen

Se usa directamente sin stubs — el objeto es puro y no tiene dependencias externas.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from objects.passenger_id_generator import PassengerIdGenerator

class Test_Init:
    """
    El generador inicia correctamente y el primer ID es 0.
    """
    def test_first_id_is_zero(self):
        """
        El primer ID retornado debe ser 0 — el contador parte desde cero.
        """
        gen = PassengerIdGenerator()
        assert gen.next_id() == 0

class Test_Sequence:
    """
    Los IDs generados son secuenciales y únicos.
    """
    def test_ids_are_sequential(self):
        """
        Tres llamadas consecutivas deben retornar 0, 1 y 2 en ese orden.
        """
        gen = PassengerIdGenerator()
        assert gen.next_id() == 0
        assert gen.next_id() == 1
        assert gen.next_id() == 2

    def test_all_ids_are_unique(self):
        """
        Después de N llamadas, todos los IDs retornados deben ser distintos.
        """
        gen = PassengerIdGenerator()
        ids = [gen.next_id() for _ in range(50)]
        assert len(set(ids)) == 50

class Test_EdgeCases:
    """
    Casos borde: independencia entre instancias y volumen alto de llamadas.
    """
    def test_two_generators_are_independent(self):
        """
        Dos instancias distintas son completamente independientes:
        ambas empiezan en 0 y no se interfieren entre sí.
        """
        gen_a = PassengerIdGenerator()
        gen_b = PassengerIdGenerator()
        assert gen_a.next_id() == 0
        assert gen_b.next_id() == 0
        assert gen_a.next_id() == 1
        assert gen_b.next_id() == 1

    def test_large_volume_still_sequential(self):
        """
        Con 1000 llamadas, el último ID debe ser 999 — no hay saturación ni saltos.
        """
        gen = PassengerIdGenerator()
        last = None
        for _ in range(1000):
            last = gen.next_id()
        assert last == 999

