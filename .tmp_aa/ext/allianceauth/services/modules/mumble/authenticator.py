#!/usr/bin/env python

# Copyright (C) 2010 Stefan Hacker <dd0t@users.sourceforge.net>
# All rights reserved.
# Adapted by Adarnof for AllianceAuth
# Further modified by the Alliance Auth team and contributors
# Rewritten for Django Context by the Alliance Auth Team
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:

# - Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
# - Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# - Neither the name of the Mumble Developers nor the names of its
#   contributors may be used to endorse or promote products derived from this
#   software without specific prior written permission.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# `AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE FOUNDATION OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import importlib.util
import logging
import os
import sys
from datetime import datetime, timezone
from hashlib import sha1
from threading import Timer
from typing import TYPE_CHECKING, Any
from urllib.request import urlopen

import Ice
from passlib.hash import bcrypt_sha256

from allianceauth import __version__
from allianceauth.services.modules.mumble.models import (
    MumbleServerServer, MumbleUser, TempUser,
)

logger = logging.getLogger("mumble_authenticator")

FALL_THROUGH = -2
AUTH_REFUSED = -1


def _run_ice_app_compat(app, args: list[str], initdata: Ice.InitializationData) -> int:
    """Open the ice communicator, falling back to a non class version for Ice 3.8
    """
    try:
        communicator = Ice.initialize(args, initdata)  # Ice 3.7
    except Exception as e:
        logger.error(f"Failed to initialize Ice communicator: {e}")
        raise

    try:
        app.set_communicator(communicator)  # Ice 3.7
        return app.run(args)
    finally:
        app.set_communicator(None)  # Ice 3.8
        try:
            communicator.destroy()
        except Exception as e:
            logger.debug(f"Error destroying communicator: {e}")


def _load_slice_compat(slice_args: list[str]) -> None:
    """loadSlice keeps changing, try all known options.
    """

    load_attempts = (
        (slice_args,),
        (" ".join(slice_args),),
        ("", slice_args),
    )
    labels = (
        "loadSlice(list[str])",  # Ice 3.8
        "loadSlice(str)",  # Ice 3.7
        "loadSlice(str, list[str])",  # Ice 3.7 legacy?
    )

    for index, args in enumerate(load_attempts):
        try:
            Ice.loadSlice(*args)
            logger.debug("Loaded Slice using %s", labels[index])
            return
        except TypeError:
            if index == len(load_attempts) - 1:
                raise


def main(server_id: int = 1) -> None:
    """_summary_

    Args:
        server_id (int, optional): _description_. Defaults to 1.

    Raises:
        e: _description_
        Murmur.InvalidSecretException: _description_
        e: _description_

    Returns:
        _type_: _description_
    """
    server_config_obj = MumbleServerServer.objects.get(pk=server_id)

    package_spec = importlib.util.find_spec("allianceauth.services.modules.mumble")
    if not package_spec or not package_spec.submodule_search_locations:
        raise RuntimeError("Could not locate allianceauth.services.modules.mumble package")
    package_dir = next(iter(package_spec.submodule_search_locations))
    package_ice = os.path.join(package_dir, server_config_obj.slice)

    logger.info(f"Using slice file: {package_ice}")

    ice_slice_dir = Ice.getSliceDir()
    if ice_slice_dir:
        slice_args = [f"-I{ice_slice_dir}"]
    else:
        slice_args = ["-I/usr/share/Ice/slice", "-I/usr/share/slice"]

    slice_args.extend([f"-I{os.path.dirname(package_ice)}", package_ice])
    _load_slice_compat(slice_args)

    if TYPE_CHECKING:
        import allianceauth.services.modules.mumble.MumbleServer_1_6_870_ice as Murmur
    else:
        try:
            import MumbleServer as Murmur  # Mumble >=1.5.17
        except ImportError:
            import Murmur  # Mumble <=1.5.17

    class AllianceAuthAuthenticatorApp:
        _communicator = None
        request_context: dict[str, str] = {}

        def set_communicator(self, communicator) -> None:
            self._communicator = communicator

        def run(self, args: list[str]) -> int:  # pyright: ignore[reportIncompatibleMethodOverride]
            if not self.initializeIceConnection():
                return 1

            if server_config_obj.watchdog > 0:
                self.failedWatch = True
                self.checkConnection()

            # Serve till we are stopped
            communicator = self._communicator
            if communicator is None:
                logger.error("Ice communicator is not initialized")
                return 1
            try:
                communicator.waitForShutdown()
            except Exception as e:
                logger.error(f"Error during communicator shutdown wait: {e}")
                return 1
            finally:
                if hasattr(self, 'watchdog') and self.watchdog:
                    self.watchdog.cancel()

            return 0

        def initializeIceConnection(self) -> bool:
            """
            Establishes the two-way Ice connection and adds the authenticator to the
            configured servers
            """
            ice = self._communicator
            if ice is None:
                logger.error("Ice communicator is not initialized")
                return False

            self.request_context = {"secret": server_config_obj.secret}

            try:
                implicit_context: Ice.ImplicitContextI | None = ice.getImplicitContext()
                if implicit_context is not None:
                    logger.debug("Using shared ice secret with communicator implicit context")
                    implicit_context.put("secret", server_config_obj.secret)
                else:
                    logger.debug(
                        "Ice implicit context is not available; falling back to explicit proxy context "
                        "(expected in Ice 3.8+)"
                    )
            except AttributeError:
                logger.debug(
                    "getImplicitContext() not available; falling back to explicit proxy context "
                    "(Ice 3.8+)"
                )

            logger.info(f"Connecting to Ice server ({server_config_obj.ip}:{server_config_obj.port})")
            base = ice.stringToProxy(f"Meta:tcp -h {server_config_obj.ip} -p {server_config_obj.port}")
            self.meta = Murmur.MetaPrx.uncheckedCast(base)
            if self.request_context:
                self.meta = self.meta.ice_context(self.request_context)

            adapter = ice.createObjectAdapterWithEndpoints(
                "Callback.Client",
                f"tcp -h {server_config_obj.endpoint}"
            )
            adapter.activate()
            self.adapter = adapter  # Accessed by ServerCallback later

            metacbprx = adapter.addWithUUID(metaCallback(self))
            self.metacb = Murmur.MetaCallbackPrx.uncheckedCast(metacbprx)

            authprx = adapter.addWithUUID(AllianceAuthAuthenticator())
            self.auth = Murmur.ServerUpdatingAuthenticatorPrx.uncheckedCast(authprx)

            return self.attachCallbacks()

        def attachCallbacks(self, quiet=False) -> bool:
            """
            Attaches all callbacks for meta and authenticators
            """

            # Ice.ConnectionRefusedException
            # logger.debug('Attaching callbacks')
            try:
                logger.info("Attaching Murmur Meta Callback")
                self.meta.addCallback(self.metacb)

                virtual_servers = self.meta.getBootedServers()
                config_servers = server_config_obj.virtual_servers_list()

                logger.info(f"Found Virtual Servers:{[server.id() for server in virtual_servers]}, Connecting To:{config_servers}")

                for server in self.meta.getBootedServers():
                    if self.request_context:
                        server = server.ice_context(self.request_context)

                    if server.id() in server_config_obj.virtual_servers_list():

                        server.setAuthenticator(self.auth)
                        logger.info("Attached Authenticator for virtual server: %d", server.id())

                        servercbprx = self.adapter.addWithUUID(serverCallback(self, server))
                        self.servercb = Murmur.ServerCallbackPrx.uncheckedCast(servercbprx)
                        self.servercb.server = server
                        server.addCallback(self.servercb)
                        logger.info("Attached Login Info Callback for virtual server: %d", server.id())

                        if server_config_obj.idler_handler:
                            idler_handler(server, server_config_obj)
                            logger.info("Attached Idler Handler for virtual server: %d", server.id())

            except (Murmur.InvalidSecretException, Ice.UnknownUserException, Ice.ConnectionRefusedException) as e:
                logger.exception(e)
                if isinstance(e, Ice.ConnectionRefusedException):
                    logger.error("Server refused connection")
                elif (isinstance(e, Murmur.InvalidSecretException) or isinstance(e, Ice.UnknownUserException) and (e.unknown == "Murmur::InvalidSecretException")):
                    logger.error("Invalid ice secret")
                else:
                    # We do not actually want to handle this one, re-raise it
                    raise e

                self.connected = False
                return False

            self.connected = True
            return True

        def checkConnection(self) -> None:
            """
            Tries reapplies all callbacks to make sure the authenticator
            survives server restarts and disconnects.
            """
            try:
                if not self.attachCallbacks(quiet=not self.failedWatch):
                    self.failedWatch = True
                else:
                    self.failedWatch = False
            except Ice.Exception as e:
                logger.error(f"Failed connection check, will retry in next watchdog run ({server_config_obj.watchdog}s)")
                logger.exception(e)
                self.failedWatch = True

            # Renew the timer
            self.watchdog = Timer(server_config_obj.watchdog, self.checkConnection)
            self.watchdog.start()

    def checkSecret(func):
        """
        Decorator that checks whether the server transmitted the right secret
        if a secret is supposed to be used.
        """
        if not server_config_obj.secret:
            return func

        def newfunc(*args, **kws):
            if "current" in kws:
                current = kws["current"]
            else:
                current = args[-1]

            if not current or "secret" not in current.ctx or current.ctx["secret"] != server_config_obj.secret:
                logger.error("Server transmitted invalid secret. Possible injection attempt.")
                raise Murmur.InvalidSecretException()

            return func(*args, **kws)

        return newfunc

    def fortifyIceFu(retval=None, exceptions=(Ice.Exception,)):
        """
        Decorator that catches exceptions,logs them and returns a safe retval
        value. This helps preventing the authenticator getting stuck in
        critical code paths. Only exceptions that are instances of classes
        given in the exceptions list are not caught.

        The default is to catch all non-Ice exceptions.
        """

        def newdec(func):
            def newfunc(*args, **kws):
                try:
                    return func(*args, **kws)
                except Exception as e:
                    catch = True
                    for ex in exceptions:
                        if isinstance(e, ex):
                            catch = False
                            break
                    if catch:
                        logger.critical("Unexpected exception caught")
                        logger.exception(e)
                        return retval
                    raise

            return newfunc

        return newdec

    class metaCallback(Murmur.MetaCallback):
        def __init__(self, app: AllianceAuthAuthenticatorApp) -> None:
            Murmur.MetaCallback.__init__(self)
            self.app = app

        @fortifyIceFu()
        @checkSecret
        def started(self, srv, current=None) -> None:
            """
            This function is called when a virtual server is started
            and makes sure an authenticator gets attached if needed.
            """
            if srv.id() in server_config_obj.virtual_servers_list():
                logger.info("Setting authenticator for virtual server %d", srv.id())
                try:
                    if self.app.request_context:
                        srv = srv.ice_context(self.app.request_context)
                    srv.setAuthenticator(self.app.auth)
                # Apparently this server was restarted without us noticing
                except (Murmur.InvalidSecretException, Ice.UnknownUserException) as e:
                    if (hasattr(e, "unknown") and e.unknown != "Murmur::InvalidSecretException"):
                        # Special handling for Murmur 1.2.2 servers with invalid slice files
                        raise e
                    logger.error("Invalid ice secret")
                    return
            else:
                logger.debug(f"Virtual server {srv.id()} got started")

        @fortifyIceFu()
        @checkSecret
        def stopped(self, srv, current=None) -> None:
            """
            This function is called when a virtual server is stopped
            """
            if self.app.connected:
                # Only try to output the server id if we think we are still connected to prevent
                # flooding of our thread pool
                try:
                    if srv.id() in server_config_obj.virtual_servers_list():
                        logger.info(f"Authenticated virtual server {srv.id()} got stopped")
                    else:
                        logger.debug(f"Virtual server {srv.id()} got stopped")
                    return
                except Ice.ConnectionRefusedException:
                    self.app.connected = False

            logger.debug("Server shutdown stopped a virtual server")

    if server_config_obj.reject_on_error:  # Python 2.4 compat
        authenticateFortifyResult = (-1, None, None)
    else:
        authenticateFortifyResult = (FALL_THROUGH, None, None)

    class serverCallback(Murmur.ServerCallback):
        def __init__(self, app: AllianceAuthAuthenticatorApp, server: "Murmur.ServerPrx") -> None:
            Murmur.ServerCallback.__init__(self)
            self.app = app
            self.server = server

        @checkSecret
        def userConnected(self, state: "Murmur.User", current=None) -> None:
            try:
                mumble_user = MumbleUser.objects.get(pk=state.userid - server_config_obj.offset)
                mumble_user.release = state.release
                mumble_user.version = state.version
                mumble_user.last_connect = datetime.now(tz=timezone.utc)
                mumble_user.save(update_fields=["release", "version", "last_connect"])
            except MumbleUser.DoesNotExist:
                try:
                    mumble_user = TempUser.objects.get(pk=state.userid - server_config_obj.offset * 2)
                    mumble_user.release = state.release
                    mumble_user.version = state.version
                    mumble_user.last_connect = datetime.now(tz=timezone.utc)
                    mumble_user.save(update_fields=["release", "version", "last_connect"])
                except TempUser.DoesNotExist:
                    return
                except Exception as b:
                    logger.exception(b)
            except Exception as a:
                logger.exception(a)

        @checkSecret
        def userDisconnected(self, state: "Murmur.User", current=None) -> None:
            try:
                mumble_user = MumbleUser.objects.get(pk=state.userid - server_config_obj.offset)
                mumble_user.last_disconnect = datetime.now(tz=timezone.utc)
                mumble_user.save(update_fields=["last_disconnect"])
            except MumbleUser.DoesNotExist:
                try:
                    mumble_user = TempUser.objects.get(pk=state.userid - server_config_obj.offset * 2)
                    mumble_user.last_disconnect = datetime.now(tz=timezone.utc)
                    mumble_user.save(update_fields=["last_disconnect"])
                except TempUser.DoesNotExist:
                    return
                except Exception as b:
                    logger.exception(b)
            except Exception as a:
                logger.exception(a)

        @checkSecret
        def userStateChanged(self, state: "Murmur.User", current=None) -> None:
            pass

        @checkSecret
        def userTextMessage(self, state: "Murmur.User", message: "Murmur.TextMessage", current=None) -> None:
            if message.text == "!kicktemps":
                self.server.sendMessage(state.session, "Checking permissions for kicking templink clients...")
                if self.server.hasPermission(state.session, 0, 0x10000):
                    self.server.sendMessage(state.session, "Kicking all templink clients!")

                    users: dict[int, "Murmur.User"] = self.server.getUsers()
                    for _, auser in users.items():
                        if auser.userid > (server_config_obj.offset * 2):
                            self.server.kickUser(auser.session, "Kicking all temp users! :-)")

                    self.server.sendMessage(state.session, "All templink clients kicked!")

                else:
                    self.server.sendMessage(state.session, "You do not have kick permissions!")

        @checkSecret
        def channelCreated(self, state: "Murmur.Channel", current=None) -> None:
            pass

        @checkSecret
        def channelRemoved(self, state: "Murmur.Channel", current=None) -> None:
            pass

        @checkSecret
        def channelStateChanged(self, state: "Murmur.Channel", current=None) -> None:
            pass

    class AllianceAuthAuthenticator(Murmur.ServerUpdatingAuthenticator):
        texture_cache = {}

        def __init__(self) -> None:
            Murmur.ServerUpdatingAuthenticator.__init__(self)

        @fortifyIceFu(authenticateFortifyResult)
        @checkSecret
        def authenticate(
            self, name: str, pw: str, certlist, certhash: str, certstrong: bool, current=None
        ) -> tuple[int, None, None] | tuple[Any, str, str] | tuple[Any, str, list[str]]:
            """Authenticate a user.

            Args:
                name (str): the Username of the connecting user
                pw (str): the Password of the connecting user
                certlist (_type_): Not Currently Used
                certhash (str): The hash of the user's certificate
                certstrong (bool): indicates if the certificate is strong
                current (_type_, optional): Current Context = None

            Returns:
                tuple[int, str | None, str | None]: User ID, Display Name, Group List
            """

            if name == "SuperUser":
                logger.debug("Forced fall through for SuperUser")

                return (FALL_THROUGH, None, None)

            try:
                auth_user = MumbleUser.objects.get(username=name)
                logger.debug(f"checking password with hash function: {auth_user.hashfn}")

                if allianceauth_check_hash(pw, auth_user.pwhash, auth_user.hashfn):
                    logger.info(f'User authenticated: {auth_user.display_name} {auth_user.pk + server_config_obj.offset}')
                    logger.debug(f"Group memberships: {auth_user.groups}")

                    auth_user.certhash = certhash
                    auth_user.save(update_fields=["certhash"])

                    return auth_user.pk + server_config_obj.offset, auth_user.display_name, auth_user.groups
                else:
                    logger.info(f'Failed authentication attempt for user: {name} {auth_user.pk}')

                    return (AUTH_REFUSED, None, None)
            except MumbleUser.DoesNotExist:
                try:
                    temp_user = TempUser.objects.get(username=name)
                    logger.debug(f"checking password with hash function: {temp_user.hashfn}")

                    if allianceauth_check_hash(pw, temp_user.pwhash, temp_user.hashfn):
                        logger.info(f'TEMP User authenticated: {temp_user.display_name} {temp_user.pk + server_config_obj.offset}')
                        logger.debug(f"TEMP Group memberships: {temp_user.groups}")
                        temp_user.certhash = certhash
                        temp_user.save(update_fields=["certhash"])

                        return (temp_user.pk + server_config_obj.offset * 2, temp_user.display_name, temp_user.groups)
                    else:
                        logger.info(f'Failed authentication attempt for TEMP user: {name} {temp_user.pk + server_config_obj.offset}')

                        return (AUTH_REFUSED, None, None)
                except TempUser.DoesNotExist:
                    return (FALL_THROUGH, None, None)  # No Standard or Temp User
                except Exception as a:
                    logger.exception(a)

                    return (FALL_THROUGH, None, None)  # An unexpected error, but same result, fail the auth
            except Exception as b:
                logger.exception(b)

                return (FALL_THROUGH, None, None)  # An unexpected error, but same result, fail the auth

        @fortifyIceFu((False, None))
        @checkSecret
        def getInfo(self, id: int, current=None) -> tuple[bool, None]:
            """Fetch user specific information, We override this and blank it out.

            Args:
                id (int): User ID
                current (_type_, optional): Current Context = None

            Returns:
                tuple[bool, None]: Always returns False and None
            """
            return (False, None)

        @fortifyIceFu(FALL_THROUGH)
        @checkSecret
        def nameToId(self, name: str, current=None) -> int:
            """Map a user id to a username. SuperUser will FALL_THROUGH

            Args:
                name (str): Username
                current (_type_, optional): Current Context = None

            Returns:
                int: User ID
            """
            if name == "SuperUser":
                logger.debug("nameToId SuperUser -> forced fall through")
                return FALL_THROUGH

            try:
                return (MumbleUser.objects.get(username=name).pk + server_config_obj.offset)
            except MumbleUser.DoesNotExist:
                try:
                    return (TempUser.objects.get(username=name).pk + server_config_obj.offset * 2)
                except TempUser.DoesNotExist:
                    return FALL_THROUGH

        @fortifyIceFu("")
        @checkSecret
        def idToName(self, id: int, current=None) -> str:
            """
            Gets called to get the username for a given id
            """
            if id < server_config_obj.offset:
                return ""  # FALL_THROUGH

            try:
                mumble_user = MumbleUser.objects.get(pk=id - server_config_obj.offset)
                mumble_user.username
            except MumbleUser.DoesNotExist:
                try:
                    mumble_user = TempUser.objects.get(pk=id - server_config_obj.offset * 2)
                    mumble_user.username
                except TempUser.DoesNotExist:
                    return ""  # FALL_THROUGH

            # I dont quite rightly know why we have this
            # SuperUser shouldnt be in our Authenticator?
            # But Maybe it can be?
            if MumbleUser.objects.get(pk=id - server_config_obj.offset).username == "SuperUser":
                logger.debug('idToName %d -> "SuperUser" caught')
                return ""  # FALL_THROUGH
            else:
                return mumble_user.username

        @fortifyIceFu("")
        @checkSecret
        def idToTexture(self, id: int, current=None) -> bytes:
            """
            Gets called to get the corresponding texture for a user
            """
            if server_config_obj.avatar_enable is False:
                logger.debug(f"idToTexture {id} -> avatar display disabled, fall through")
                return b""  # FALL_THROUGH

            if id < server_config_obj.offset:
                return b""  # FALL_THROUGH

            try:
                avatar_url = MumbleUser.objects.get(pk=id - server_config_obj.offset).user.profile.main_character.portrait_url(size=256)
            except MumbleUser.DoesNotExist:
                try:
                    avatar_url = TempUser.objects.get(pk=id - server_config_obj.offset * 2).character.portrait_url(size=256)
                except TempUser.DoesNotExist:
                    return b""  # FALL_THROUGH
                except Exception as b:
                    logger.exception(b)
                    return b""  # FALL_THROUGH
            except Exception as a:
                logger.exception(a)
                return b""  # FALL_THROUGH

            if avatar_url:
                if avatar_url in self.texture_cache:
                    logger.debug(f'idToTexture {id} -> cached avatar returned: {avatar_url}')
                    return self.texture_cache[avatar_url]

                # Not cached? Try to retrieve from CCP image server.
                try:
                    logger.debug(f'idToTexture {id} -> try file "{avatar_url}"')
                    handle = urlopen(avatar_url)

                except (OSError, Exception) as e:
                    logger.exception(e)
                    logger.debug(f'idToTexture {id} -> image download for {avatar_url} failed, fall through')
                    return b""  # FALL_THROUGH
                else:
                    file = handle.read()
                    handle.close()

                # Cache resulting avatar by file address and return image.
                self.texture_cache[avatar_url] = file
                logger.debug(f'idToTexture {id} -> avatar from {avatar_url} retrieved and returned')
                return self.texture_cache[avatar_url]

            else:
                logger.debug(f"idToTexture {id} -> empty avatar_url, final fall through")
                return b""  # FALL_THROUGH

        @fortifyIceFu(-2)
        @checkSecret
        def registerUser(self, info, current=None) -> int:
            """
            Gets called when the server is asked to register a user.
            """
            logger.debug(f'registerUser {info} -> fall through')
            return FALL_THROUGH

        @fortifyIceFu(-1)
        @checkSecret
        def unregisterUser(self, id: int, current=None) -> int:
            """
            Gets called when the server is asked to unregister a user.
            """
            # Return -1 to fall through to internal server database, so as to not modify Alliance Auth
            # but we can make murmur delete all additional logger.information it got this way.
            logger.debug(f"unregisterUser {id} -> fall through", )
            return -1  # FALL_THROUGH

        @fortifyIceFu({})
        @checkSecret
        def getRegisteredUsers(self, filter: str, current=None) -> dict[int, str]:
            """
            Returns a list of usernames in the AllianceAuth database which contain
            filter as a substring.
            """

            if not filter:
                mumble_users = MumbleUser.objects.all()
            else:
                mumble_users = MumbleUser.objects.filter(username__icontains=filter)

            if not mumble_users.exists():
                logger.debug(f'getRegisteredUsers -> empty list for filter {filter}', )
                return {}
            logger.debug(f'getRegisteredUsers -> {len(mumble_users)} results for filter {filter}')

            return {mumble_user.user_id + server_config_obj.offset: mumble_user.username for mumble_user in mumble_users}

        @fortifyIceFu(-1)
        @checkSecret
        def setInfo(self, id: int, info, current=None) -> int:
            """
            Gets called when the server is supposed to save additional information
            about a user to his database
            """
            # Return -1 to fall through to the internal server handler.
            # Store this in Murmur, Not Alliance Auth
            logger.debug(f"setInfo {id} -> fall through")
            return -1  # FALL_THROUGH

        @fortifyIceFu(-1)
        @checkSecret
        def setTexture(self, id: int, tex: bytes, current=None) -> int:
            """
            Gets called when the server is asked to update the user texture of a user
            """
            # Return -1 to fall through to the internal server handler.
            # Store this in Murmur, Not Alliance Auth
            logger.debug(f"setTexture {id} -> fall through")
            return -1  # FALL_THROUGH

    #
    # --- Start of authenticator
    #
    logger.info(f"Starting AllianceAuth Mumble Authenticator V:{__version__} for Server ID: {server_id}")
    initdata = Ice.InitializationData()
    # Ice 3.8+ compatible initialization (type: ignore for direct property assignment)
    properties = Ice.createProperties()  # type: ignore[attr-defined]
    properties.setProperty('Ice.ImplicitContext', 'Shared')
    properties.setProperty('Ice.Default.EncodingVersion', '1.0')
    initdata.properties = properties  # type: ignore[attr-defined]
    initdata.logger = logger  # type: ignore[attr-defined]

    app = AllianceAuthAuthenticatorApp()
    try:
        _run_ice_app_compat(app, sys.argv, initdata)
    except Exception as e:
        logger.error(f"Fatal error in authenticator: {e}")
        logger.exception(e)
        sys.exit(1)
    logger.info('Shutdown complete')


def allianceauth_check_hash(password, hash, hash_type) -> bool:
    """
    :param password: Password to be verified
    :param hash: Hash for the password to be checked against
    :param hash_type: Hashing function originally used to generate the hash
    """
    if hash_type == "sha1":
        return sha1(password).hexdigest() == hash
    elif hash_type == "bcrypt-sha256":
        return bcrypt_sha256.verify(password, hash)
    else:
        logger.warning(f"No valid hash function found for {hash_type}")
        return False


def idler_handler(server: "Murmur.Server", server_config_obj: MumbleServerServer) -> None:
    logger.debug("IdlerHandler: Starting")
    get_users: dict[int, "Murmur.User"] = server.getUsers()
    users: list["Murmur.User"] = list(get_users.values())

    if server_config_obj.idler_handler is None:
        logger.debug("IdleHandler: No idler handler configured, skipping")
        # Here for typehinting
        return
    logger.debug("IdleHandler: Fetched All Users")
    for user in users:
        logger.debug(f"IdleHandler: Checking user {user.name}")
        if isinstance(user, int):
            logger.debug(f"IdleHandler: Skipping user id {user}, This happens occasionally")
            continue

        user_idlesecs = user.idlesecs
        if user_idlesecs > server_config_obj.idler_handler.seconds:
            logger.debug(
                f"IdleHandler: User {user.name} is AFK, for {user_idlesecs}/{server_config_obj.idler_handler.seconds}"
            )
            state = server.getState(user.session)
            if state:
                # AllowList > DenyList
                if server_config_obj.idler_handler.denylist is False:
                    if state.channel not in server_config_obj.idler_handler.list:
                        return
                elif server_config_obj.idler_handler.denylist is True:
                    if state.channel in server_config_obj.idler_handler.list:
                        return

                if state.channel == server_config_obj.idler_handler.channel:
                    return

                state.channel = server_config_obj.idler_handler.channel
                state.selfMute = True
                state.selfDeaf = True
                server.setState(state)
                logger.debug(f"IdleHandler: Moved AFK User {user.name}")

    Timer(server_config_obj.idler_handler.interval, idler_handler, (server, server_config_obj)).start()


if __name__ == "__main__":
    main()
