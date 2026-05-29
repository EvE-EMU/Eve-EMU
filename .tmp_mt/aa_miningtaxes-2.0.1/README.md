![partner](screens/partner.jpg)

Please join the `miningtaxes` thread in the Community Creations section on the  [Alliance Auth Discord Server](https://discord.gg/4SEyDZKB) for giveaways and support for this plugin!

# Mining Taxes

An Alliance Auth app for tracking mining activities and charging taxes.

[![pipeline](https://gitlab.com/arctiru/aa-miningtaxes/badges/master/pipeline.svg)](https://gitlab.com/arctiru/aa-miningtaxes/-/commits/master)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Credit to AA's [memberaudit](https://gitlab.com/ErikKalkoken/aa-memberaudit) and [buyback](https://gitlab.com/paulipa/allianceauth-buyback-program) plugins which formed the foundation for this plugin.

## Screenshots
![monthly](screens/screen1.jpg)
![oreprices](screens/screen2.jpg)
![leaderboards](screens/screen3.jpg)

## Features

- Monthly leaderboards to show top miners.
- Supports multiple corps under one system (Add one character with the accountant role per corp in the admin setup)
- Supports corp moon mining tracking.
- Able to track when unrecognized characters are mining your corp's private moons.
- Tax credit system to offset, zero, or award tax credits to a given user.
- Supports separate tax rates for Regular Ore, Mercoxit, Gas, Ice, R64, R32, R16, R8, and R4.
- Tracks tax payments into the corp master wallet filtering with a user defined phrase.
- Set a monthly interest rate that penalizes for unpaid tax balances.
- Automatic monthly notifications and monthly interest applied with unpaid balance.
- Supports Fuzzworks and Janice for daily price updates.
- Supports refined price calculation versus raw ore prices (the higher price will be the taxed price).
- Supports multiple mining characters under one user.
- Monthly statistics and detailed tax calculations available to each user and auditor.
- Provides a current Ore price chart that is updated each day with the latest prices.
- Export tax information in CSV format.
- Supports whitelisting and blacklisting of systems, and turning taxing on and off by security status.

## Installation instructions

- Install `django-eveonline-sde`
- If you would like to use [Janice](https://janice.e-351.com/) for pricing information, obtain an API key by following the instructions at the top of the [Swagger documentation](https://janice.e-351.com/api/rest/docs/index.html) and [FAQ](https://janice.e-351.com/about).
- Install using pip: `pip install aa-miningtaxes`
- Add `miningtaxes` and `django_celery_results` to INSTALLED_APPS in `myauth/settings/local.py`
- Run migrations: `python manage.py migrate`
- Collect and deploy static assets: `python manage.py collectstatic`
- Preload pricing information `python manage.py miningtaxes_preload_prices`
- Set local settings
```
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'

MININGTAXES_PRICE_JANICE_API_KEY = "XXXX"
MININGTAXES_PRICE_METHOD = "Janice"

CELERYBEAT_SCHEDULE['miningtaxes_update_daily'] = {
    'task': 'miningtaxes.tasks.update_daily',
    'schedule':  crontab(minute=0, hour='1'),
}

# Notifiy everyone of their current taxes on the second day of every month.
CELERYBEAT_SCHEDULE['miningtaxes_notifications'] = {
    'task': 'miningtaxes.tasks.notify_taxes_due',
    'schedule': crontab(0, 0, day_of_month='2'),
}

# Charge interest and notify everyone on the 15th of every month.
CELERYBEAT_SCHEDULE['miningtaxes_apply_interest'] = {
    'task': 'miningtaxes.tasks.apply_interest',
    'schedule': crontab(0, 0, day_of_month='15'),
}
```
- Navigate to the admin panel and setup the accountants (1 per corp)

## Post-Setup instructions

- After you have setup your accountants (1 per corp) in the Admin Setup panel, invite all the members of your corp to add their characters.
- If you enable `MININGTAXES_TAX_ONLY_CORP_MOONS`, remember that only moon mining of your corp moons will be taxes and other moons will be ignored.
- After everyone in the corp has added their characters, consider running to the `miningtaxes_zero_all` command to zero out everyone's taxes to prevent mining activity from the past from being taxed.
- When a new user joins your corp and adds their character to the plugin, also consider going into the audit tables and providing a tax credit so that it will zero out their past mining activity.

## Local settings


Name | Description | Default
-- | -- | --
MININGTAXES_CORP_WALLET_DIVISION | Corp Wallet Division to seek for tax payments (this option will be used for ALL admin toons linked) | 1
MININGTAXES_UNKNOWN_TAX_RATE | The tax rate when a new type of ore is encountered that has not yet been added to the plugin in float (eg 0.10 means 10%) | 0.10
MININGTAXES_TAX_ONLY_CORP_MOONS | Only tax corporate moons using moon observers as opposed to all moons appearing in the personal mining ledgers. | True
MININGTAXES_UPDATE_LEDGER_STALE | Minutes after which a character's mining ledger is considered stale | 240
MININGTAXES_REFINED_RATE | Refining rate for ores. | 0.9063
MININGTAXES_ALWAYS_TAX_REFINED | Always tax the refined rate instead of the raw ore price (if higher) | False
MININGTAXES_PRICE_METHOD | By default Fuzzwork API will be used for pricing, if this is set to "Janice" then the Janice API will be used. | Fuzzwork
MININGTAXES_PRICE_JANICE_API_KEY | The API key to access Janice API. |
MININGTAXES_PRICE_JANICE_TIMING | Choices are `immediatePrices` or `top5AveragePrices` | top5AveragePrices
MININGTAXES_PRICE_JANICE_BUY | Choices are `buyPrice`, `splitPrice`, `buyPrice5DayMedian`, `splitPrice5DayMedian`, `buyPrice30DayMedian`, `splitPrice30DayMedian`  | buyPrice5DayMedian
MININGTAXES_PRICE_SOURCE_ID | Station ID for fetching base prices. Supports IDs listed on [Fuzzworks API](https://market.fuzzwork.co.uk/api/). Does not work with Janice API!| 60003760
MININGTAXES_ALLOW_ANALYTICS | Allow analytics to be sent for plugin usage. | True
MININGTAXES_LEADERBOARD_TAXABLE_ONLY | Only track leaderboards for activity that is taxed by this plugin. | False
MININGTAXES_BLACKLIST | List of system names that taxes should be ignored in. Case sensitive.  | []
MININGTAXES_TAX_HISEC | Include taxing for mining activity in High Security Space | True
MININGTAXES_TAX_LOSEC | Include taxing for mining activity in Low Security Space | True
MININGTAXES_TAX_NULLSEC | Include taxing for mining activity in Null Security Space | True
MININGTAXES_TAX_JSPACE | Include taxing for mining activity in J-Space (Wormhole) | True
MININGTAXES_TAX_POCHVEN | Include taxing for mining activity in Pochven (Trig Space) | True
MININGTAXES_WHITELIST | List of the ONLY system names that taxes should be collected. Case sensitive.  | []
MININGTAXES_PING_THRESHOLD | Threshold to send reminder when "Taxes past due". | 0.01
MININGTAXES_PING_FIRST_MSG | Format of message to send on the first reminder (should be set on the 1st to 5th of each month). This is triggered by `notify_taxes_due` task | Please pay {:,.2f} ISK or you will be charged interest!
MININGTAXES_PING_SECOND_MSG | Format of message to send on the second reminder (should be set on the 10th to 14th of each month). This is triggered by `notify_second_taxes_due` task | Please pay {:,.2f} ISK or you will be charged interest!
MININGTAXES_PING_INTEREST_APPLIED | Format of message once interest is applied (usually on the 15th of each month). This is triggered by the `apply_interest` task | An interest of {:,.2f} ISK has been charged for late taxes.
MININGTAXES_PING_CURRENT_THRESHOLD | The threshold for Current taxes notification. | 1000000000
MININGTAXES_PING_CURRENT_MSG | Format of the message for Current taxes notification (usually set to run every day). This is triggered by the `notify_current_taxes_threshold` task | Please pay your taxes. Current tax balance: {:,.2f} ISK

## Whitelisting and Blacklisting
The logic around whitelisting and blacklisting is a bit complex so I will describe the implementation here.

If any systems are entered into `MININGTAXES_WHITELIST` then taxes are collected in these systems regardless of what the other settings say. Basically `MININGTAXES_BLACKLIST`, `MININGTAXES_TAX_HISEC`, `MININGTAXES_TAX_LOSEC`, `MININGTAXES_TAX_NULLSEC`, `MININGTAXES_TAX_JSPACE`, `MININGTAXES_TAX_POCHVEN` are completely ignored.

If there NO systems entered into `MININGTAXES_WHITELIST` (the default state), then the system will look at whether they fall into the exclusion rules and tax accordingly.


## Permissions

Name | Purpose | Example Target Audience
-- | -- | --
basic_access | Can access this app and see own tax information, current ore prices, and FAQ. | Member State
auditor_access | Can view everyone's tax information and see statistics on taxes. | Auditors
admin_access | Can set tax rate and add characters with the accountant role to pull information from the corp Master Wallet and the corp moons. | Leadership


## Commands

Name | Description
-- | --
miningtaxes_preload_prices | Preload all ores and refined materials from chosen Pricing API (Fuzzworks or Janice).
miningtaxes_zero_all | Zero the tax balance of ALL characters.
miningtaxes_update_manual | Trigger a manual update for all data
miningtaxes_prune_non_corpies | Prune all toons who are not in a corp that is covered by the accountants (Use this with care!). Specifically this tool purges characters where their main is not in a tracked corp.
