from django.core.exceptions import ValidationError
from django.test import TestCase

from blueprints.validators import validate_material_efficiency, validate_time_efficiency


class TestValidateMaterialEfficiencyValue(TestCase):
    def test_should_pass_when_valid(self):
        for value in [0, 4, 10]:
            with self.subTest(value=value):
                self.assertIsNone(validate_material_efficiency(value))

    def test_should_raise_error_when_invalid(self):
        for value in [-5, -0.1, 10.1, 20]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_material_efficiency(value)


class TestValidateTimeEfficiencyValue(TestCase):
    def test_should_pass_when_valid(self):
        for value in [0, 4, 10, 20]:
            with self.subTest(value=value):
                self.assertIsNone(validate_time_efficiency(value))

    def test_should_raise_error_when_invalid(self):
        for value in [-5, -0.1, 3, 7, 20.1, 100]:
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_time_efficiency(value)
