""""
Test de las funciones mas importantes del archivo objects/math3d.py
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from objects.math3d import Vector3

class TestVector3Add:
    """
    Test para la funion __add__
    """

    def test_normal_case(self):
        assert Vector3(1,2,3) + Vector3(4,5,6) == Vector3(5,7,9)
    
    def test_zero_case(self):
        assert Vector3(0,0,0) + Vector3(0,0,0) == Vector3(0,0,0)
    
    def test_negative_case(self):
        assert Vector3(1,2,3) + Vector3(-4,-5,-6) == Vector3(-3,-3,-3)
    
    def test_float_case(self):
        assert Vector3(1.32, 2.5, 3.7) + Vector3(0.68, 0.5, 0.3) == Vector3(2.0, 3.0, 4.0)

class TestVector3Sub:
    """
    Test para la función __sub__
    """
    def test_normal_case(self):
        assert Vector3(10, 10, 10) - Vector3(4, 5, 6) == Vector3(6, 5, 4)

    def test_negative_result(self):
        assert Vector3(1, 1, 1) - Vector3(2, 2, 2) == Vector3(-1, -1, -1)

    def test_zero_vector(self):
        assert Vector3(1, 2, 3) - Vector3(1, 2, 3) == Vector3(0, 0, 0)

class TestVector3Neg:
    """
    Test para la función __neg__
    """
    def test_normal_case(self):
        assert -Vector3(1, 2, 3) == Vector3(-1, -2, -3)

    def test_zero_vector(self):
        assert -Vector3(0, 0, 0) == Vector3(0, 0, 0)

class TestVector3Mul:
    """
    Test específicos para la función __mul__
    """
    def test_normal_case(self):
        assert Vector3(1, 2, 3) * 2 == Vector3(2, 4, 6)

    def test_zero_case(self):
        assert Vector3(1, 2, 3) * 0 == Vector3(0, 0, 0)

    def test_vector_zero_case(self):
        assert Vector3(0, 0, 0) * 2 == Vector3(0, 0, 0)
    
    def test_negative_case(self):
        assert Vector3(1, 2, 3) * -2 == Vector3(-2, -4, -6)

class TestVector3TrueDiv:
    """
    Test para la función __truediv__
    """
    def test_normal_case(self):
        assert Vector3(10, 20, 30) / 2 == Vector3(5, 10, 15)

    def test_float_division(self):
        assert Vector3(1, 1, 1) / 2 == Vector3(0.5, 0.5, 0.5)

    def test_zero_division(self):
        with pytest.raises(ZeroDivisionError):
            Vector3(1, 2, 3) / 0

class TestVector3Length:
    """
    Test para la funcion length
    """
    def test_zero_length(self):
        assert Vector3(0, 0, 0).length() == 0.0

    def test_unit_vector(self):
        assert Vector3(1, 0, 0).length() == 1.0

    def test_known_vector(self):
        assert Vector3(3, 4, 0).length() == 5.0

class TestVector3Normalize:
    """
    Test para la función normalize
    """

    def test_normal_case(self):
        v = Vector3(1, 2, 3).normalize()
        assert abs(v.length() - 1.0) < 1e-9


    def test_zero_vector(self):
        v = Vector3(0, 0, 0).normalize()
        assert v == Vector3(0, 0, 0)

class TestVector3Dot:
    """
    Test para la función dot
    """
    def normal_case(self):
        assert Vector3(1, 2, 3).dot(Vector3(4, 5, 6)) == 32

    def test_orthogonal(self):
        assert Vector3(1, 0, 0).dot(Vector3(0, 1, 0)) == 0.0

    def test_parallel(self):
        assert Vector3(1, 2, 3).dot(Vector3(1, 2, 3)) == 14.0

class TestVector3DistanceTo:
    """
    Test para la función distance_to
    """
    def test_same_point(self):
        assert Vector3(1, 1, 1).distance_to(Vector3(1, 1, 1)) == 0.0

    def test_known_distance(self):
        assert Vector3(0, 0, 0).distance_to(Vector3(3, 4, 0)) == 5.0

