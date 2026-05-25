from allianceauth import hooks


@hooks.register("charlink")
def register_charlink_hook():
    return "industry_suite.charlink_hook"
