"""Show overpayment as a negative balance on /miningtaxes/user_summary/<id>.

Stock ``views.user_summary`` computes ``taxes_due`` from the same
``life_tax - life_credits`` balance the page's own "Current Balance" field
(``balance`` / ``balance_raw``) already displays correctly (negative when a
member has paid more than they currently owe — the template even documents
this: "Green means that you do not owe taxes or have overpaid"). But
``taxes_due`` specifically then does::

    if taxes_due < 0:
        taxes_due = 0

clamping the "Amount Owed" field to zero whenever it would show a credit,
instead of the true negative figure — so a member who overpaid saw "0 ISK
owed" instead of "-X ISK" (a credit), inconsistent with the balance field
right next to it. This removes the clamp; everything else about the view is
unchanged.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _user_summary(request, user_pk: int):
    from django.contrib.auth.models import User
    from django.http import HttpResponseForbidden
    from django.shortcuts import render

    from allianceauth.eveonline.models import EveCharacter
    from app_utils.helpers import humanize_number
    from miningtaxes.models import Stats

    s = Stats.load()
    user = User.objects.get(pk=user_pk)
    if not (
        request.user == user or request.user.has_perm("miningtaxes.auditor_access")
    ):
        return HttpResponseForbidden()
    owned_chars_query = (
        EveCharacter.objects.filter(character_ownership__user=user)
        .select_related("miningtaxes_character")
        .order_by("character_name")
    )
    auth_characters = []
    unregistered_chars = []
    for eve_character in owned_chars_query:
        try:
            character = eve_character.miningtaxes_character
        except AttributeError:
            unregistered_chars.append(eve_character.character_name)
        else:
            auth_characters.append(character)
    unregistered_chars = sorted(unregistered_chars)
    main_character_id = user.profile.main_character.character_id
    main_data, _, user2taxes = s.main_data_helper(auth_characters)
    # The only change from stock: no clamp-to-zero on a negative (overpaid) balance.
    taxes_due = user2taxes[user][0]

    context = {
        "page_title": "Taxes Summary",
        "auth_characters": auth_characters,
        "unregistered_chars": unregistered_chars,
        "main_character_id": main_character_id,
        "balance": humanize_number(main_data[list(main_data.keys())[0]]["balance"]),
        "balance_raw": main_data[list(main_data.keys())[0]]["balance"],
        "taxes_due": taxes_due,
        "last_paid": main_data[list(main_data.keys())[0]]["last_paid"],
        "user_pk": user_pk,
    }
    return render(request, "miningtaxes/user_summary.html", context)


def apply_miningtaxes_negative_balance_patch() -> None:
    try:
        from miningtaxes import views as mt_views
    except ImportError:
        return
    if getattr(mt_views, "_eve_emu_negative_balance_patched", False):
        return

    mt_views.user_summary = _user_summary
    mt_views._eve_emu_negative_balance_patched = True
    logger.info(
        "miningtaxes_negative_balance_patch: user_summary no longer clamps an "
        "overpaid balance's \"amount owed\" to 0"
    )
