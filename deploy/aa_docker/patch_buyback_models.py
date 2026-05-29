"""One-shot image build patch for buybackprogram.models (django-esi 9)."""

from __future__ import annotations

import pathlib
import re

MODELS = pathlib.Path(
    "/usr/local/lib/python3.12/site-packages/buybackprogram/models.py"
)

_FIRST_CONTRACT_EVENT_BLOCK = r'''            # Eve-emu: first_contract_event notification fix
            if not tracking.contract_id:
                try:
                    Tracking.objects.filter(pk=tracking.id).update(contract=obj)
                    tracking.refresh_from_db()
                except Error as e:
                    logger.error(
                        "Error linking contract %s with tracking %s: %s"
                        % (
                            contract["contract_id"],
                            tracking.tracking_number,
                            e,
                        )
                    )

            first_contract_event = created or (
                not link_before and tracking.contract_id
            )

            if first_contract_event:
                if created:
                    logger.debug(
                        "Contract %s created, linking tracking object %s"
                        % (
                            contract["contract_id"],
                            tracking.tracking_number,
                        )
                    )
                else:
                    logger.debug(
                        "Contract %s first linked to tracking %s"
                        % (contract["contract_id"], tracking.tracking_number)
                    )

                items = []
                corporations = CharacterOwnership.objects.filter(
                    user=tracking.program.owner.user
                ).values_list("character__corporation_id", flat=True)

                if not ContractItem.objects.filter(contract=obj).exists():
                    logger.debug(
                        "Starting item fetch for contract %s"
                        % contract["contract_id"]
                    )

                    character_id = self.character.character.character_id

                    corporation_id = self.character.character.corporation_id

                    logger.debug(
                        "Fetching items for %s with character %s. Corporation contract: %s"
                        % (
                            contract["contract_id"],
                            character_id,
                            contract["is_corporation"],
                        )
                    )

                    if not contract["is_corporation"]:
                        logger.debug(
                            "Looking up items for %s via character endpoint"
                            % contract["contract_id"]
                        )
                        contract_items = esi.client.Contracts.get_characters_character_id_contracts_contract_id_items(
                            character_id=character_id,
                            contract_id=contract["contract_id"],
                            token=token,
                        ).results(use_etag=False)

                    else:
                        logger.debug(
                            "Looking up items for %s via corporation endpoint"
                            % contract["contract_id"]
                        )
                        contract_items = esi.client.Contracts.get_corporations_corporation_id_contracts_contract_id_items(
                            corporation_id=corporation_id,
                            contract_id=contract["contract_id"],
                            token=token,
                        ).results(use_etag=False)
                    contract_items = [_esi_row_to_dict(i) for i in contract_items]

                    logger.debug(
                        "%s items found in contract %s"
                        % (len(contract_items), contract["contract_id"])
                    )

                    logger.debug("Got corporations for contract owner: %s" % corporations)

                    objs = []

                    for item in contract_items:
                        cont = Contract.objects.get(contract_id=contract["contract_id"])
                        itm, _ = EveType.objects.get_or_create_esi(id=item["type_id"])

                        contract_item = ContractItem(
                            contract=cont,
                            eve_type=itm,
                            quantity=item["quantity"],
                        )

                        objs.append(contract_item)

                        items.append(
                            str(EveType.objects.get(id=item["type_id"]))
                            + " x "
                            + str(item["quantity"])
                        )

                    try:
                        ContractItem.objects.bulk_create(objs)
                        logger.debug(
                            "Succesfully added %s items for contract %s into database"
                            % (len(objs), contract["contract_id"])
                        )
                    except Error as e:
                        logger.error(
                            "Error adding items for contract %s: %s"
                            % (contract["contract_id"], e)
                        )
                else:
                    for ci in ContractItem.objects.filter(contract=obj).select_related(
                        "eve_type"
                    ):
                        items.append(
                            str(ci.eve_type) + " x " + str(ci.quantity)
                        )

                # Check and see if any notifications/warnings should be set on the contract
                self._set_contract_notifications(
                    tracking, obj, corporations, tracking.program
                )

                # Notifications for users who have the notifications enabled

                if not contract["is_corporation"]:
                    assigned_to = self.character.character.character_name
                else:
                    assigned_to = self.character.character.corporation_name

                notifications = ContractNotification.objects.filter(
                    contract__contract_id=contract["contract_id"]
                )

                notes = str()

                if notifications:
                    for note in notifications:
                        notes += str(note.message)
                        notes += "\n\n"

                logger.debug("Contract contains %s" % "\n".join(items))

                # Check if the program wants to display the item list
                if tracking.program.discord_show_item_list:
                    contract_item_list = "\n".join(items)
                else:
                    contract_item_list = ""

                contract_url = (
                    get_site_url()
                    + "/buybackprogram/tracking/"
                    + tracking.tracking_number
                )

                if (
                    len(contract_item_list) > 2000
                    or not tracking.program.discord_show_item_list
                ):
                    contract_item_list = (
                        contract_item_list
                        + "\n[See all contract items ...]("
                        + contract_url
                        + ")"
                    )

                user_message = {
                    "contract": obj,
                    "contract_items": contract_item_list,
                    "tracking": tracking,
                    "notes": notes,
                    "title": "New buyback contract assigned for program {0}".format(
                        tracking.program.name
                    ),
                    "color": 0x5BC0DE,
                    "value": intcomma(int(contract["price"])),
                    "assigned_to": assigned_to,
                    "assigned_from": EveEntity.objects.resolve_name(
                        contract["issuer_id"]
                    ),
                }

                if tracking.program.discord_dm_notification:
                    send_user_notification(
                        user=self.user,
                        level="success",
                        message=user_message,
                    )
                else:
                    logger.debug(
                        "Program owner does not want DM notifications, passing"
                    )

                if tracking.program.discord_channel_notification:
                    logger.debug(
                        "Program wants channel notification, attempting to send via webhook"
                    )
                    send_message_to_discord_channel(
                        webhook=tracking.program.discord_channel_notification,
                        message=user_message,
                    )
                else:
                    logger.debug(
                        "Program owner does not want channel notifications, passing"
                    )
'''

HELPER = '''

def _esi_row_to_dict(row):
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "model_dump"):
        return row.model_dump()
    if hasattr(row, "__dict__"):
        return {k: v for k, v in row.__dict__.items() if not k.startswith("_")}
    raise TypeError("Cannot convert ESI row to dict: %r" % (type(row),))


'''


def _restore_models_if_broken() -> None:
    import py_compile
    import subprocess
    import sys

    try:
        py_compile.compile(str(MODELS), doraise=True)
        return
    except py_compile.PyCompileError:
        pass

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--force-reinstall",
            "aa-buybackprogram==2.3.4",
        ],
        check=True,
    )


def main() -> None:
    if MODELS.is_file():
        _restore_models_if_broken()
    text = MODELS.read_text(encoding="utf-8")
    text = text.replace("token=token.valid_access_token()", "token=token")
    if "_esi_row_to_dict" not in text:
        text = text.replace(
            "logger = get_extension_logger(__name__)\n",
            "logger = get_extension_logger(__name__)\n" + HELPER,
            1,
        )
    if ").results(use_etag=False)" not in text and ").results()" in text:
        text = text.replace(").results()", ").results(use_etag=False)")
    needle = (
        ").results(use_etag=False)\n\n                logger.debug(\n"
        '                    "%s items found in contract %s"'
    )
    if needle in text and "contract_items = [_esi_row_to_dict" not in text:
        text = text.replace(
            needle,
            ").results(use_etag=False)\n"
            "                contract_items = [_esi_row_to_dict(i) for i in contract_items]\n\n"
            "                logger.debug(\n"
            '                    "%s items found in contract %s"',
        )
    old_location = """        operation.request_config.also_return_response = True

        try:
            label, response = operation.result()
        except OSError as ex:
            logger.error("Error fetching location information %s" % (ex))
            return "Unknown"

        if response.status_code != 200:
            return "Unknown"
        return label["name"]"""
    new_location = """        try:
            label = operation.results(use_etag=False)
            if hasattr(label, "model_dump"):
                label = label.model_dump()
            if isinstance(label, list) and label:
                label = label[0]
                if hasattr(label, "model_dump"):
                    label = label.model_dump()
        except (OSError, Exception) as ex:
            logger.error("Error fetching location information %s" % (ex))
            return "Unknown"

        if isinstance(label, dict):
            return label.get("name", "Unknown")
        return "Unknown\""""
    if old_location in text:
        text = text.replace(old_location, new_location)
    text = re.sub(
        r"for esi_contract in esi_contracts:\n            contract = esi_contract\n            contract\[\"is_corporation\"\] = (False|True)",
        lambda m: (
            "for esi_contract in esi_contracts:\n"
            "            contract = _esi_row_to_dict(esi_contract)\n"
            f'            contract["is_corporation"] = {m.group(1)}'
        ),
        text,
        count=2,
    )
    text = _patch_buyback_notification_race(text)
    MODELS.write_text(text, encoding="utf-8")


def _patch_buyback_notification_race(text: str) -> str:
    """Notify on first link to tracking, not only ORM create (prefill race)."""
    marker = "# Eve-emu: first_contract_event notification fix"
    if marker in text:
        return text

    text = text.replace(
        "            # Create or update the found contract\n"
        "            obj, created = Contract.objects.update_or_create(",
        "            link_before = bool(tracking.contract_id)\n\n"
        "            # Create or update the found contract\n"
        "            obj, created = Contract.objects.update_or_create(",
        1,
    )

    # Match stock or partially-patched ``if created`` headers.
    old_headers = (
        "            # If we have created a new contract\n            if created:",
        "            if first_contract_event:",
    )
    start = -1
    old_header = ""
    for header in old_headers:
        start = text.find(header)
        if start != -1:
            old_header = header
            break
    if start == -1:
        return text

    end = text.find(
        "            # If contract was updated instead of created\n            else:",
        start,
    )
    if end == -1:
        return text

    new_block = _FIRST_CONTRACT_EVENT_BLOCK + "\n\n"
    text = text[:start] + new_block + text[end:]

    text = text.replace(
        """                        logger.debug(
                            "Contract %s already tracked, passing"
                            % contract["contract_id"]
                        )

                    except Tracking.DoesNotExist:""",
        """                        logger.debug(
                            "Contract %s matched tracking %s via prefill, processing"
                            % (contract["contract_id"], tracking.tracking_number)
                        )
                        self._process_contract(contract, tracking, token)
                        tracked_contrats.append(contract)

                    except Tracking.DoesNotExist:""",
        1,
    )

    old_status_notify = """                    send_user_notification(
                        user=tracking.issuer_user,
                        level=level,
                        message=user_message,
                    )
                else:
                    logger.debug(
                        "Contract assigner has notifications set to %s, passing"
                        % user_settings.disable_notifications
                    )"""

    new_status_notify = """                    send_user_notification(
                        user=tracking.issuer_user,
                        level=level,
                        message=user_message,
                    )
                    if tracking.program.discord_channel_notification:
                        send_message_to_discord_channel(
                            webhook=tracking.program.discord_channel_notification,
                            message=user_message,
                        )
                else:
                    logger.debug(
                        "Contract assigner has notifications set to %s, passing"
                        % user_settings.disable_notifications
                    )"""

    if old_status_notify in text:
        text = text.replace(old_status_notify, new_status_notify, 1)

    return text


if __name__ == "__main__":
    main()
