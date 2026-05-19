import importlib.util
import os
import sys
import types
from unittest.mock import call, patch

import Ice

from django.test import SimpleTestCase

from allianceauth.services.modules.mumble.authenticator import (
    _load_slice_compat, main,
)


class LoadSliceCompatTests(SimpleTestCase):
    def test_uses_ice_38_list_signature(self) -> None:
        slice_args = ["-I/usr/share/Ice/slice", "-I/tmp", "/tmp/MumbleServer.ice"]

        with patch("allianceauth.services.modules.mumble.authenticator.Ice.loadSlice") as mocked_load_slice:
            _load_slice_compat(slice_args)

        mocked_load_slice.assert_called_once_with(slice_args)

    def test_falls_back_to_legacy_string_signature(self) -> None:
        slice_args = ["-I/usr/share/Ice/slice", "-I/tmp", "/tmp/MumbleServer.ice"]

        with patch("allianceauth.services.modules.mumble.authenticator.Ice.loadSlice") as mocked_load_slice:
            mocked_load_slice.side_effect = [TypeError("new signature only"), None]

            _load_slice_compat(slice_args)

        mocked_load_slice.assert_has_calls([
            call(slice_args),
            call("-I/usr/share/Ice/slice -I/tmp /tmp/MumbleServer.ice"),
        ])

    def test_falls_back_to_legacy_two_argument_signature(self) -> None:
        slice_args = ["-I/usr/share/Ice/slice", "-I/tmp", "/tmp/MumbleServer.ice"]

        with patch("allianceauth.services.modules.mumble.authenticator.Ice.loadSlice") as mocked_load_slice:
            mocked_load_slice.side_effect = [
                TypeError("new signature only"),
                TypeError("string signature unavailable"),
                None,
            ]

            _load_slice_compat(slice_args)

        mocked_load_slice.assert_has_calls([
            call(slice_args),
            call("-I/usr/share/Ice/slice -I/tmp /tmp/MumbleServer.ice"),
            call("", slice_args),
        ])


class LoadSliceSmokeTests(SimpleTestCase):
    def test_bundled_slice_file_preprocesses(self) -> None:
        package_spec = importlib.util.find_spec(
            "allianceauth.services.modules.mumble"
        )
        self.assertIsNotNone(package_spec)
        self.assertTrue(package_spec.submodule_search_locations)

        package_dir = next(iter(package_spec.submodule_search_locations))
        slice_file = os.path.join(package_dir, "MumbleServer_1_6_870.ice")

        slice_args = []
        ice_slice_dir = Ice.getSliceDir()
        if ice_slice_dir:
            slice_args.append(f"-I{ice_slice_dir}")
        else:
            slice_args.extend(["-I/usr/share/Ice/slice", "-I/usr/share/slice"])

        slice_args.extend([f"-I{package_dir}", slice_file])

        _load_slice_compat(slice_args)


class MainSliceSetupTests(SimpleTestCase):
    def test_main_includes_ice_slice_dir_when_available(self) -> None:
        fake_server = types.SimpleNamespace(
            slice="MumbleServer_1_6_870.ice",
            watchdog=0,
            secret="",
            virtual_servers_list=lambda: [1],
            offset=1000000000,
            avatar_enable=True,
            reject_on_error=False,
            idler_handler=None,
        )
        fake_spec = types.SimpleNamespace(
            submodule_search_locations=["/fake/pkg/allianceauth/services/modules/mumble"]
        )

        fake_murmur = types.ModuleType("MumbleServer")
        fake_murmur.MetaCallback = type("MetaCallback", (), {})
        fake_murmur.ServerCallback = type("ServerCallback", (), {})
        fake_murmur.ServerUpdatingAuthenticator = type("ServerUpdatingAuthenticator", (), {})

        with (
            patch.dict(sys.modules, {"MumbleServer": fake_murmur}),
            patch("allianceauth.services.modules.mumble.authenticator.MumbleServerServer") as model_mock,
            patch("allianceauth.services.modules.mumble.authenticator.importlib.util.find_spec", return_value=fake_spec),
            patch("allianceauth.services.modules.mumble.authenticator.Ice.getSliceDir", return_value="/opt/ice/slice"),
            patch("allianceauth.services.modules.mumble.authenticator._load_slice_compat") as load_compat_mock,
            patch("allianceauth.services.modules.mumble.authenticator.Ice.InitializationData") as init_data_mock,
            patch("allianceauth.services.modules.mumble.authenticator.Ice.createProperties"),
            patch("allianceauth.services.modules.mumble.authenticator._run_ice_app_compat", return_value=0),
        ):
            model_mock.objects.get.return_value = fake_server
            init_data_mock.return_value = types.SimpleNamespace(properties=None)
            main(server_id=1)

        load_compat_mock.assert_called_once_with([
            "-I/opt/ice/slice",
            "-I/fake/pkg/allianceauth/services/modules/mumble",
            "/fake/pkg/allianceauth/services/modules/mumble/MumbleServer_1_6_870.ice",
        ])

    def test_main_uses_default_slice_dirs_when_no_ice_slice_dir(self) -> None:
        fake_server = types.SimpleNamespace(
            slice="MumbleServer_1_6_870.ice",
            watchdog=0,
            secret="",
            virtual_servers_list=lambda: [1],
            offset=1000000000,
            avatar_enable=True,
            reject_on_error=False,
            idler_handler=None,
        )
        fake_spec = types.SimpleNamespace(
            submodule_search_locations=["/fake/pkg/allianceauth/services/modules/mumble"]
        )

        fake_murmur = types.ModuleType("MumbleServer")
        fake_murmur.MetaCallback = type("MetaCallback", (), {})
        fake_murmur.ServerCallback = type("ServerCallback", (), {})
        fake_murmur.ServerUpdatingAuthenticator = type("ServerUpdatingAuthenticator", (), {})

        with (
            patch.dict(sys.modules, {"MumbleServer": fake_murmur}),
            patch("allianceauth.services.modules.mumble.authenticator.MumbleServerServer") as model_mock,
            patch("allianceauth.services.modules.mumble.authenticator.importlib.util.find_spec", return_value=fake_spec),
            patch("allianceauth.services.modules.mumble.authenticator.Ice.getSliceDir", return_value=None),
            patch("allianceauth.services.modules.mumble.authenticator._load_slice_compat") as load_compat_mock,
            patch("allianceauth.services.modules.mumble.authenticator.Ice.InitializationData") as init_data_mock,
            patch("allianceauth.services.modules.mumble.authenticator.Ice.createProperties"),
            patch("allianceauth.services.modules.mumble.authenticator._run_ice_app_compat", return_value=0),
        ):
            model_mock.objects.get.return_value = fake_server
            init_data_mock.return_value = types.SimpleNamespace(properties=None)
            main(server_id=1)

        load_compat_mock.assert_called_once_with([
            "-I/usr/share/Ice/slice",
            "-I/usr/share/slice",
            "-I/fake/pkg/allianceauth/services/modules/mumble",
            "/fake/pkg/allianceauth/services/modules/mumble/MumbleServer_1_6_870.ice",
        ])


class RunIceAppCompatTests(SimpleTestCase):
    def test_direct_init_path_sets_communicator_on_app(self) -> None:
        app = types.SimpleNamespace()
        app._communicator = None

        def set_communicator(communicator):
            app._communicator = communicator

        def run(args):
            self.assertIsNotNone(app._communicator)
            implicit_context = app._communicator.getImplicitContext()
            self.assertTrue(implicit_context is None or hasattr(implicit_context, "put"))
            return 0

        app.set_communicator = set_communicator
        app.run = run

        init_data = Ice.InitializationData()
        init_data.properties = Ice.createProperties()
        init_data.properties.setProperty("Ice.ImplicitContext", "Shared")

        from allianceauth.services.modules.mumble.authenticator import (
            _run_ice_app_compat,
        )

        self.assertEqual(_run_ice_app_compat(app, [], init_data), 0)
