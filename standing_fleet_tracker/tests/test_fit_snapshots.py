from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from allianceauth.eveonline.models import EveCharacter

from standing_fleet_tracker.models import FleetSession, ShipFitSnapshot
from standing_fleet_tracker.services.fit_snapshots import find_best_snapshot
from standing_fleet_tracker.services.ship_fit import fitting_payload_for_character


class FindBestSnapshotTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.character = EveCharacter.objects.create(
            character_id=90000001,
            character_name="Test Pilot",
        )
        cls.session = FleetSession.objects.create(
            character=cls.character,
            fleet_id=1,
            started_at=timezone.now() - timedelta(hours=2),
        )
        cls.charon_type = 20185
        cls.mega_type = 641
        now = timezone.now()
        cls.charon_snap = ShipFitSnapshot.objects.create(
            character=cls.character,
            session=cls.session,
            ship_item_id=100,
            ship_type_id=cls.charon_type,
            ship_name="Freighter",
            modules_json=[{"flag": "HiSlot0", "type_id": 1, "quantity": 1}],
            modules_fingerprint="charon",
            eft_text="Charon, Freighter\n\nModule",
            recorded_at=now - timedelta(hours=1),
        )
        cls.mega_snap = ShipFitSnapshot.objects.create(
            character=cls.character,
            session=cls.session,
            ship_item_id=200,
            ship_type_id=cls.mega_type,
            ship_name="DPS",
            modules_json=[{"flag": "HiSlot0", "type_id": 2, "quantity": 1}],
            modules_fingerprint="mega",
            eft_text="Megathron, DPS\n\nBlaster",
            recorded_at=now - timedelta(minutes=10),
        )

    def test_finds_charon_snapshot_not_latest_mega(self):
        start = self.charon_snap.recorded_at - timedelta(minutes=5)
        end = self.charon_snap.recorded_at + timedelta(minutes=5)
        snap = find_best_snapshot(
            self.character.character_id,
            self.charon_type,
            session_id=self.session.pk,
            first_seen=start,
            last_seen=end,
        )
        self.assertEqual(snap.pk, self.charon_snap.pk)

    def test_historical_payload_does_not_use_live_esi(self):
        with patch(
            "standing_fleet_tracker.services.ship_fit.live_ship_fit_payload"
        ) as live_mock:
            payload = fitting_payload_for_character(
                self.character.character_id,
                self.charon_type,
                session_id=self.session.pk,
                first_seen=self.charon_snap.recorded_at - timedelta(minutes=1),
                last_seen=self.charon_snap.recorded_at + timedelta(minutes=1),
            )
        live_mock.assert_not_called()
        self.assertEqual(payload["source"], "snapshot")
        self.assertIn("Charon", payload["eft"])

    def test_missing_snapshot_no_live_fallback(self):
        with patch(
            "standing_fleet_tracker.services.ship_fit.live_ship_fit_payload"
        ) as live_mock:
            payload = fitting_payload_for_character(
                self.character.character_id,
                99999,
                session_id=self.session.pk,
            )
        live_mock.assert_not_called()
        self.assertFalse(payload.get("has_fitting") or payload.get("source") == "esi_live")
