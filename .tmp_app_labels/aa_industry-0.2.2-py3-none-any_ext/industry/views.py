import logging

from allianceauth.eveonline.models import EveCharacter
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect

from esi.decorators import token_required
from esi.models import Token
from esi.clients import esi_client_factory

from allianceauth.authentication.models import CharacterOwnership
from .models import UserCharacters

from .helper import _get_personal_jobs, _get_corp_jobs, _process_jobs

logger = logging.getLogger(__name__)

_scopes = [
    'esi-industry.read_character_jobs.v1',
    'esi-industry.read_corporation_jobs.v1',
    'esi-universe.read_structures.v1',
]

cache_facility_id = {}
cache_character_id = {}


@login_required
@permission_required("industry.view_industry")
def index(request):
    # return redirect('industry:list_jobs', character_id=request.user.profile.main_character.character_id)
    characters = list()

    tokens = Token.objects.filter(user__pk=request.user.pk).require_scopes(_scopes).require_valid()
    if tokens:
        for u in UserCharacters.objects.filter(user=request.user):
            characters.append(u.character_ownership.character)

    if len(characters) == 1:
        return redirect('industry:list_jobs', character_id=request.user.profile.main_character.character_id)

    context = {
        "characters": characters
    }
    return render(request, "industry/registered_characters.html", context)


@login_required
@permission_required("industry.view_industry")
@token_required(scopes=_scopes)
def char_selector(request, t):
    token_char = EveCharacter.objects.get(character_id=t.character_id)
    character_ownership = CharacterOwnership.objects.select_related(
        "character"
    ).get(user=request.user, character=token_char)

    if character_ownership:
        uc = UserCharacters.objects.filter(character_ownership=character_ownership)
        if not uc:
            UserCharacters.objects.create(
                character_ownership=character_ownership,
                user=request.user
            )

    return redirect('industry:list_jobs', character_id=t.character_id)


@login_required
@permission_required("industry.view_industry")
def list_jobs(request, character_id):
    corp_id = request.user.profile.main_character.corporation_id

    t = Token.objects.filter(user__pk=request.user.pk, character_id=character_id)\
        .require_scopes(_scopes).require_valid().first()
    if not t:
        return redirect('industry:selector')

    _request_headers = {
        'accept': 'application/json',
        'Cache-Control': 'no-cache',
        'authorization': 'Bearer ' + t.valid_access_token()
    }

    jobs = _get_personal_jobs(t.character_id, _request_headers)
    _processed_jobs = _process_jobs(_request_headers, jobs)

    jobs = _get_corp_jobs(corp_id, _request_headers)
    _corp_jobs = _process_jobs(_request_headers, jobs, True)

    if _corp_jobs:
        _processed_jobs += _corp_jobs

    character_data = {
        'character_name': t.character_name,
        'character_id': t.character_id,
        'token_id': t.pk
    }

    context = {
        "items": _processed_jobs,
        "character_data": character_data,
        # "user_tokens": CharacterOwnership.objects.filter(user=request.user).all(),
        "user_tokens": UserCharacters.objects.filter(user=request.user).all(),
    }

    return render(request, "industry/index.html", context)
