from django.test import SimpleTestCase

from corp_orders.models import FreightOrder
from corp_orders.services.claim_tokens import make_claim_token, read_claim_token
from corp_orders.services.claims import can_claim_order


class ClaimTokenTests(SimpleTestCase):
    def test_roundtrip(self):
        token = make_claim_token(42)
        self.assertEqual(read_claim_token(token), 42)

    def test_bad_token(self):
        self.assertIsNone(read_claim_token("not-valid"))


class CanClaimTests(SimpleTestCase):
    def test_unclaimed_pending(self):
        order = FreightOrder(status=FreightOrder.Status.PENDING_CONTRACT)
        self.assertTrue(can_claim_order(order))

    def test_already_claimed(self):
        order = FreightOrder(
            status=FreightOrder.Status.PENDING_CONTRACT,
            claimed_by_id=1,
        )
        self.assertFalse(can_claim_order(order))

    def test_cancelled(self):
        order = FreightOrder(status=FreightOrder.Status.CANCELLED)
        self.assertFalse(can_claim_order(order))
