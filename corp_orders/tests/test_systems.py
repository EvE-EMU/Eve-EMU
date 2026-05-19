from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from corp_orders.services.systems import search_solar_system_names


class SystemSearchTests(SimpleTestCase):
    @patch("corp_orders.services.systems._solar_system_model")
    def test_empty_query_puts_default_first(self, mock_model_fn):
        mock_model = MagicMock()
        mock_model_fn.return_value = mock_model
        mock_model.objects.filter.return_value.order_by.return_value.values_list.return_value = [
            "3-FKCZ",
            "3-FKNA",
        ]

        names = search_solar_system_names("")

        self.assertEqual(names[0], "3-F")
        self.assertIn("3-FKCZ", names)
