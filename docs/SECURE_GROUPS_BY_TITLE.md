# Auto-assign Secure Groups by corp + in-game title / role

Your Docker image already includes **[Secure Groups](https://apps.allianceauth.org/apps/detail/allianceauth-securegroups)**, **[CorpTools](https://apps.allianceauth.org/apps/detail/allianceauth-corptools)**, **[Member Audit](https://gitlab.com/ErikKalkoken/aa-memberaudit)**, and the **[Member Audit Secure Groups integration](https://gitlab.com/ErikKalkoken/aa-memberaudit-securegroups)** (same project lineage as [eclipse-expeditions/aa-memberaudit-securegroups](https://gitlab.com/eclipse-expeditions/aa-memberaudit-securegroups)). Together they can automatically add or remove users from a Django auth group (for example a “Secure Directors” group) based on:

- membership in a specific corporation, and  
- either the **corporation role** “Director” (ESI roles) or a **custom corp title** whose text is `Director`.

**Member Audit filters** (activity, assets, compliance, skill points, skill sets, character age) appear under **Admin → Secure Groups → Smart Filter** after Member Audit has run at least once (`memberaudit_load_eve` + characters registered). See the integration README on [GitLab](https://gitlab.com/ErikKalkoken/aa-memberaudit-securegroups).

All filters on one Smart Group must pass (**AND** logic).

---

## 1. One-time server setup

Run these if you have not already (from the repo root):

```bash
docker compose exec aa-web python manage.py migrate
docker compose exec aa-web python manage.py setup_securegroup_task
docker compose exec aa-web python manage.py corptools ct_setup
```

- **`setup_securegroup_task`** — hourly Celery job that applies Smart Group rules.  
- **`corptools ct_setup`** — CorpTools periodic tasks (character audits, including titles/roles).

Confirm in **Django Admin → Periodic tasks** that **Secure Group Updater** exists and is enabled.

### CCP developer application scopes

On [developers.eveonline.com](https://developers.eveonline.com/), add these scopes to the same application AA uses (`ESI_CLIENT_ID` / `AA_ESI_SSO_*`):

- `esi-characters.read_corporation_roles.v1` and `esi-characters.read_titles.v1` (CorpTools login scopes)
- `esi-characters.read_corporation_roles.v1` (for **Director** *role*)
- `esi-characters.read_titles.v1` (for custom **Director** *title* text)

After changing scopes, users must **re-add characters via Charlink** so tokens include the new scopes.

This repo merges the CorpTools role/title scopes into `LOGIN_TOKEN_SCOPES` when CorpTools is enabled (see `deploy/aa_docker/extensions/settings.py`). Override with `AA_CORPTOOLS_LOGIN_SCOPES` in `.env` if needed.

---

## 2. Create the target auth group

1. **Django Admin → Authentication and Authorization → Groups → Add**  
2. Name it e.g. `Secure Directors` (this is the group you will protect with services / permissions).  
3. Under **Group management** (Alliance Auth), configure the group as you normally would:
   - **Hidden** / not public if only auto-assignment should apply  
   - **Open** off if you do not want manual self-join  
   - Restrict to your **Member** state(s) if guests should never get it  

---

## 3. Create filters (Django Admin)

### A. Must be in corporation X

**Admin → Secure Groups → Smart Filter: Character in Corporation → Add**

| Field | Value |
|--------|--------|
| Name / description | e.g. `In corp <Your Corp>` |
| **alt_corp** | Your corporation (`Eve Corporation Info`) |

Saving creates a linked **Smart filter** row automatically.

If the corp is missing from the dropdown, ensure at least one character from that corp has logged in, or add the corp via SDE / CorpTools corp audit.

### B. Director check — pick **one** of these

#### Option 1 — EVE **Director role** (most common)

Use when “Director” means the built-in corp role (can open corp hangars, etc.), not a custom title string.

**Admin → CorpTools → Smart Filter: Corporate Role checks → Add**

| Field | Value |
|--------|--------|
| Name / description | e.g. `Has Director role in corp` |
| **has_director** | ✓ |
| **corps_filter** | Same corporation as above |
| **main_only** | Optional: only check the user’s **main** character |

#### Option 2 — Custom corp **title** text `Director`

Use when your corp assigns a **named title** in-game (Corp → Titles) and you want that exact string.

1. Ensure characters have been **audited** (CorpTools → Member Audit; wait for roles/titles sync).  
2. **Admin → CorpTools → Character titles** — find an entry like `(Your Corp) - Director`.  
3. **Admin → CorpTools → Smart Filter: Corporate Title checks → Add**  
   - **titles** → select that `CharacterTitle` row  

Title matching is per **corporation + title name** as stored by CorpTools, not fuzzy text.

---

## 4. Wire the Smart Group

**Admin → Secure Groups → Smart Groups → Add**

| Field | Value |
|--------|--------|
| **group** | `Secure Directors` (the auth group from step 2) |
| **filters** | Select **both** Smart filters (corp + director role **or** title) |
| **auto_group** | ✓ — automatically add/remove members |
| **enabled** | ✓ |
| **include_in_updates** | ✓ — re-check on the hourly task |
| **can_grace** | Optional — grace period before removal if someone loses the role |
| **States** (on the auth group in Group Management) | Limit to `Member` (recommended) |

Save. On the next **Secure Group Updater** run (or trigger Celery beat), users who pass **all** filters are added; others are removed (subject to grace settings).

---

## 5. Verify

1. **Auth → Secure Groups** (user menu) — user can see pass/fail per filter if exposed.  
2. **Admin → Secure Groups → Smart Groups** — open your group and use audit tools if available (`audit_sec_group` permission).  
3. For a test user (e.g. Sevey): confirm CorpTools shows **Director** role or title on an alt in corp X, then run:

```bash
docker compose exec aa-web python manage.py shell -c "
from django.contrib.auth import get_user_model
from securegroups.models import SmartGroup
u = get_user_model().objects.get(username='THE_USERNAME')
sg = SmartGroup.objects.get(group__name='Secure Directors')
print(sg.check_user(u))
"
```

---

## 6. Multiple corps or titles

- **One Smart Group per rule set** (e.g. `Secure Directors - Corp A`, `Secure Directors - Corp B`), or  
- Use **Filter expression** (Secure Groups) to combine filters with AND/OR if you need complex logic.

---

## Troubleshooting

| Symptom | Likely cause |
|--------|----------------|
| Nobody auto-joins | `auto_group` off, Smart Group disabled, wrong **state**, or hourly task not running |
| Corp filter fails | Character not in corp on auth record; main not in that corp |
| Role filter fails | Missing `esi-characters.read_corporation_roles.v1` on token; audit stale — force refresh in Member Audit |
| Title filter fails | Title not synced; wrong `CharacterTitle` row; use Role filter if they have Director **role** not custom title |
| **Title missing from** `/admin/corptools/titlefilter/add/` | CorpTools only lists titles **already seen on an audited character** via ESI — not every in-corp title definition. See below. |
| Added then removed quickly | User lost role; grace not enabled; conflicting second Smart Group |

### Title missing from the dropdown (e.g. Commander, Logistics)

The **titles** field on [Title filter add](https://auth.eve-emu.com/admin/corptools/titlefilter/add/) is a foreign key to **CharacterTitle** rows. Those rows are created when CorpTools runs `update_character_titles` for a character who **currently has** that title assigned in-game ([CorpTools source](https://github.com/Solar-Helix-Independent-Transport/allianceauth-corp-tools)).

So if Commander / Logistics exist as corp titles but **no audited Auth character** has them assigned, they will not appear in the list.

**Fix (recommended):**

1. In-game, assign **Commander** (or **Logistics**) to any character that is on Auth (Charlink).
2. Ensure the token has `esi-characters.read_titles.v1` (re-add via Charlink after adding the scope on your CCP app).
3. Refresh titles for that character:

```bash
docker compose exec aa-web python manage.py shell -c "
from corptools.models import CharacterAudit
from corptools.task_helpers.char_tasks import update_character_titles
cid = YOUR_CHARACTER_ID  # e.g. main in False Gods
update_character_titles(cid, force_refresh=True)
"
```

4. Check **Admin → CorpTools → Character titles** (search `False Gods`) — you should see `(False Gods) - Commander` etc.
5. Create the **Title filter** again; the title should be in the dropdown.

**Bulk refresh** all audited False Gods alts (does not invent titles nobody holds):

```bash
docker compose exec aa-web python manage.py shell -c "
from corptools.models import CharacterAudit
from corptools.task_helpers.char_tasks import update_character_titles
for a in CharacterAudit.objects.filter(character__corporation_id=98799892):
    update_character_titles(a.character.character_id, force_refresh=True)
"
```

**Optional seed** (only if you know `title_id` from ESI after one sync, or from your emu DB): `deploy/aa_docker/scripts/corptools_seed_character_title.py`.

Match the **exact** in-game title string (symbols matter), e.g. `☜★☞ Director` vs `Director`.

---

## Related

- [Alliance Auth extensions](./ALLIANCE_AUTH.md) — bundled apps and `setup_securegroup_task`  
- [Secure Groups app page](https://apps.allianceauth.org/apps/detail/allianceauth-securegroups)  
- [CorpTools app page](https://apps.allianceauth.org/apps/detail/allianceauth-corptools)
