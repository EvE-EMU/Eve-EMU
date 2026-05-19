from django.test import SimpleTestCase

from corp_orders.models import FreightOrder
from corp_orders.services.lifecycle import CANCELLABLE_STATUSES, TERMINAL_STATUSES, can_cancel_order


class LifecycleTests(SimpleTestCase):
    def test_pending_contract_is_cancellable(self):
        order = FreightOrder(status=FreightOrder.Status.PENDING_CONTRACT)
        self.assertTrue(can_cancel_order(order))

    def test_completed_not_cancellable(self):
        order = FreightOrder(status=FreightOrder.Status.COMPLETED)
        self.assertFalse(can_cancel_order(order))

    def test_cancellable_disjoint_from_terminal(self):
        self.assertFalse(CANCELLABLE_STATUSES & TERMINAL_STATUSES)
