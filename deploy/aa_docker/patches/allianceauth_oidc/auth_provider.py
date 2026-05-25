from oauth2_provider.oauth2_validators import OAuth2Validator


def _safe_name(request):
    try:
        profile = request.user.profile
        main = profile.main_character
        if main is not None:
            return main.character_name
    except Exception:
        pass
    return request.user.get_username()


def _safe_email(request):
    return request.user.email or ""


def _safe_groups(request):
    groups = list(request.user.groups.all().values_list("name", flat=True))
    try:
        state = request.user.profile.state
        if state is not None:
            groups.append(state.name)
    except Exception:
        pass
    return groups


class AllianceAuthOAuth2Validator(OAuth2Validator):
    oidc_claim_scope = OAuth2Validator.oidc_claim_scope
    oidc_claim_scope.update({"groups": "profile"})

    def _load_application(self, client_id, request):
        client = super()._load_application(client_id, request)
        return client

    def get_additional_claims(self):
        return {
            "name": _safe_name,
            "preferred_username": _safe_name,
            "nickname": _safe_name,
            "email": _safe_email,
            "groups": _safe_groups,
        }
