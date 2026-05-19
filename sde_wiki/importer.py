"""Import django-eveonline-sde data into Wiki.js."""

from __future__ import annotations

import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass

from eve_sde.models import (
    BlueprintActivity,
    BlueprintActivityMaterial,
    BlueprintActivityProduct,
    Constellation,
    DogmaAttribute,
    DogmaEffect,
    EveSDE,
    ItemCategory,
    ItemGroup,
    ItemMarketGroup,
    ItemType,
    ItemTypeMaterials,
    Region,
    SolarSystem,
    TypeDogma,
    TypeEffect,
)

from .progress import ImportProgress
from .renderers import field_table, md_link, md_table, wiki_path
from .wiki_db import WikiDbBulkWriter
from .wikijs_client import WikiJsClient

_thread_local = threading.local()


@dataclass
class ImportStats:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    dry_run: int = 0
    errors: int = 0

    def record(self, action: str) -> None:
        if action == "created":
            self.created += 1
        elif action == "updated":
            self.updated += 1
        elif action == "skipped":
            self.skipped += 1
        elif action == "dry-run":
            self.dry_run += 1


class SDEWikiImporter:
    ROOT = "sde"
    LOCALE_PREFIX = "/en"

    def __init__(
        self,
        client: WikiJsClient,
        *,
        skip_existing: bool = True,
        dry_run: bool = False,
        include_unpublished_types: bool = True,
        stdout=None,
        progress_interval: int = 25,
        workers: int = 1,
        fast_import: bool = False,
        remainder_mode: bool = False,
        db_writer: WikiDbBulkWriter | None = None,
    ):
        self.client = client
        self.db_writer = db_writer
        self.skip_existing = skip_existing
        self.dry_run = dry_run
        self.include_unpublished_types = include_unpublished_types
        self.stdout = stdout
        self.stats = ImportStats()
        self._progress: ImportProgress | None = None
        self._progress_interval = progress_interval
        self.workers = max(1, workers)
        self.fast_import = fast_import and not remainder_mode
        self.remainder_mode = remainder_mode
        self._executor: ThreadPoolExecutor | None = None
        self._futures: set = set()
        self._stats_lock = threading.Lock()

    def _log(self, msg: str) -> None:
        if self.stdout:
            self.stdout.write(msg)

    def _page_link(self, path: str, label: str) -> str:
        return md_link(f"{self.LOCALE_PREFIX}/{path}", label)

    def _thread_client(self) -> WikiJsClient:
        if self.workers <= 1:
            return self.client
        client = getattr(_thread_local, "wikijs_client", None)
        if client is None:
            client = self.client.clone()
            _thread_local.wikijs_client = client
        return client

    def _upsert_impl(
        self,
        path: str,
        title: str,
        content: str,
        *,
        description: str = "",
        tags: list[str] | None = None,
        force: bool = False,
    ) -> None:
        try:
            if self.db_writer is not None:
                action = self.db_writer.upsert(
                    path=path,
                    title=title,
                    content=content,
                    description=description,
                    dry_run=self.dry_run,
                    force_update=force,
                )
            else:
                action = self._thread_client().upsert_page(
                    path=path,
                    title=title,
                    content=content,
                    description=description,
                    tags=tags,
                    skip_existing=self.skip_existing and not force,
                    dry_run=self.dry_run,
                )
            with self._stats_lock:
                self.stats.record(action)
        except Exception as exc:
            with self._stats_lock:
                self.stats.errors += 1
            self._log(f"ERROR {path}: {exc}")
        finally:
            if self._progress:
                self._progress.tick()

    def _drain_futures(self, block: bool = False) -> None:
        if not self._futures:
            return
        if block:
            done, pending = wait(self._futures)
            self._futures = set(pending)
        else:
            done, self._futures = wait(self._futures, return_when=FIRST_COMPLETED)
        for future in done:
            future.result()

    def _flush_workers(self) -> None:
        if self._executor:
            self._drain_futures(block=True)
            self._executor.shutdown(wait=True)
            self._executor = None

    def _upsert(
        self,
        path: str,
        title: str,
        content: str,
        *,
        description: str = "",
        tags: list[str] | None = None,
        force: bool = False,
    ) -> None:
        if self.workers <= 1 or self.dry_run:
            self._upsert_impl(
                path,
                title,
                content,
                description=description,
                tags=tags,
                force=force,
            )
            return
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self.workers)
        future = self._executor.submit(
            self._upsert_impl,
            path,
            title,
            content,
            description=description,
            tags=tags,
            force=force,
        )
        self._futures.add(future)
        if len(self._futures) >= self.workers * 12:
            self._drain_futures(block=False)

    def import_home(self) -> None:
        meta = EveSDE.objects.first()
        build = meta.build_number if meta else "unknown"
        released = meta.release_date if meta else "unknown"
        content = f"""# EVE Static Data Export (SDE)

Reference wiki generated from the **django-eveonline-sde** database loaded in Alliance Auth.

| | |
|---|---|
| SDE build | {build} |
| Release date | {released} |

## Browse

- {self._page_link(wiki_path(self.ROOT, "map", "regions"), "Universe map")}
- {self._page_link(wiki_path(self.ROOT, "types", "categories"), "Item categories")}
- {self._page_link(wiki_path(self.ROOT, "types", "groups"), "Item groups")}
- {self._page_link(wiki_path(self.ROOT, "types", "market-groups"), "Market groups")}
- {self._page_link(wiki_path(self.ROOT, "dogma", "attributes"), "Dogma attributes")}
- {self._page_link(wiki_path(self.ROOT, "dogma", "effects"), "Dogma effects")}
- {self._page_link(wiki_path(self.ROOT, "industry", "blueprints"), "Industry blueprints")}

> Item types live under `{self.ROOT}/types/items/<type_id>` (full import) or on **group** pages (fast import). Use Wiki.js search or group pages to navigate.
"""
        if self.fast_import:
            content += (
                "\n\n_Note: **fast import** — no per-type, per-system, or per-dogma detail pages; "
                "browse via group and constellation pages._"
            )
        self._upsert(self.ROOT, "EVE SDE", content, tags=["sde", "home"])

    def import_map(self) -> None:
        if self.remainder_mode:
            self._import_map_remainder()
            return
        n_regions = Region.objects.count()
        n_constellations = Constellation.objects.count()
        phase_total = 1 + n_regions + n_constellations
        if not self.fast_import:
            phase_total += SolarSystem.objects.count()
        if self._progress:
            self._progress.set_phase("map", phase_total)
        self._import_regions_index()
        for region in Region.objects.order_by("id").iterator(chunk_size=200):
            self._import_region(region)
        for constellation in Constellation.objects.select_related("region").order_by("id").iterator(
            chunk_size=500
        ):
            self._import_constellation(constellation)
        if self.fast_import:
            self._log(
                "Fast import: skipping per-system pages (systems are listed on constellation pages)."
            )
        else:
            for system in SolarSystem.objects.select_related(
                "constellation", "constellation__region"
            ).order_by("id").iterator(chunk_size=500):
                self._import_solar_system(system)

    def _import_map_remainder(self) -> None:
        n_constellations = Constellation.objects.count()
        n_systems = SolarSystem.objects.count()
        if self._progress:
            self._progress.set_phase("map", n_constellations + n_systems)
        self._log("Remainder: solar system pages + refresh constellation links…")
        for constellation in Constellation.objects.select_related("region").order_by("id").iterator(
            chunk_size=500
        ):
            self._import_constellation(constellation)
        for system in SolarSystem.objects.select_related(
            "constellation", "constellation__region"
        ).order_by("id").iterator(chunk_size=500):
            self._import_solar_system(system)

    def _import_regions_index(self) -> None:
        rows = []
        for r in Region.objects.order_by("name"):
            path = wiki_path(self.ROOT, "map", "regions", r.id)
            rows.append([str(r.id), self._page_link(path, r.name)])
        content = "# Regions\n\n" + md_table(["ID", "Name"], rows)
        self._upsert(wiki_path(self.ROOT, "map", "regions"), "Regions", content, tags=["sde", "map"])

    def _import_region(self, region: Region) -> None:
        constellations = list(
            region.constellations.order_by("name").values_list("id", "name")
        )
        rows = [
            [
                str(cid),
                self._page_link(wiki_path(self.ROOT, "map", "constellations", cid), cname),
            ]
            for cid, cname in constellations
        ]
        content = f"""# {region.name}

{field_table({
    "ID": region.id,
    "Description": (region.description or "")[:500],
    "Faction ID": region.faction_id_raw,
    "Wormhole class ID": region.wormhole_class_id_raw,
    "Position": f"{region.x}, {region.y}, {region.z}" if region.x is not None else None,
})}

## Constellations

{md_table(["ID", "Name"], rows) if rows else "_None._"}
"""
        self._upsert(
            wiki_path(self.ROOT, "map", "regions", region.id),
            region.name,
            content,
            tags=["sde", "map", "region"],
        )

    def _import_constellation(self, constellation: Constellation) -> None:
        region = constellation.region
        systems = list(
            SolarSystem.objects.filter(constellation=constellation)
            .order_by("name")
            .values_list("id", "name", "security_status")[:500]
        )
        rows = [
            [
                str(sid),
                self._page_link(wiki_path(self.ROOT, "map", "systems", sid), sname),
                f"{sec:.2f}" if sec is not None else "",
            ]
            for sid, sname, sec in systems
        ]
        more = ""
        total = SolarSystem.objects.filter(constellation=constellation).count()
        if total > 500:
            more = f"\n\n_Showing 500 of {total} systems. Use search for others._"
        content = f"""# {constellation.name}

{field_table({
    "ID": constellation.id,
    "Region": self._page_link(wiki_path(self.ROOT, "map", "regions", region.id), region.name) if region else None,
})}

## Solar systems

{md_table(["ID", "Name", "Sec"], rows) if rows else "_None._"}{more}
"""
        self._upsert(
            wiki_path(self.ROOT, "map", "constellations", constellation.id),
            constellation.name,
            content,
            tags=["sde", "map", "constellation"],
            force=self.remainder_mode,
        )

    def _import_solar_system(self, system: SolarSystem) -> None:
        constellation = system.constellation
        region = constellation.region if constellation else None
        content = f"""# {system.name}

{field_table({
    "ID": system.id,
    "Security": system.security_status,
    "Security class": system.security_class,
    "Constellation": (
        self._page_link(wiki_path(self.ROOT, "map", "constellations", constellation.id), constellation.name)
        if constellation else None
    ),
    "Region": (
        self._page_link(wiki_path(self.ROOT, "map", "regions", region.id), region.name)
        if region else None
    ),
    "Hub": system.hub,
    "Border": system.border,
    "Luminosity": system.luminosity,
    "Position": f"{system.x}, {system.y}, {system.z}" if system.x is not None else None,
})}
"""
        self._upsert(
            wiki_path(self.ROOT, "map", "systems", system.id),
            system.name,
            content,
            tags=["sde", "map", "system"],
        )

    def import_types(self) -> None:
        if self.remainder_mode:
            self._import_types_remainder()
            return
        n_categories = ItemCategory.objects.count()
        n_groups = ItemGroup.objects.count()
        n_market = ItemMarketGroup.objects.count()
        type_qs = ItemType.objects.all()
        if not self.include_unpublished_types:
            type_qs = type_qs.filter(published=True)
        n_types = type_qs.count()
        phase_total = (1 + n_categories) + (1 + n_groups) + (1 + n_market)
        if not self.fast_import:
            phase_total += n_types
        if self._progress:
            self._progress.set_phase("types", phase_total)
        self._import_categories()
        self._import_groups_index()
        for group in ItemGroup.objects.select_related("category").order_by("id").iterator(chunk_size=200):
            self._import_group(group)
        self._import_market_groups_index()
        for mg in ItemMarketGroup.objects.order_by("id").iterator(chunk_size=200):
            self._import_market_group(mg)
        if not self.fast_import:
            self._import_item_types()

    def _import_types_remainder(self) -> None:
        type_qs = ItemType.objects.all()
        if not self.include_unpublished_types:
            type_qs = type_qs.filter(published=True)
        n_types = type_qs.count()
        n_groups = ItemGroup.objects.count()
        n_market = ItemMarketGroup.objects.count()
        if self._progress:
            self._progress.set_phase("types", n_types + n_groups + n_market)
        self._log("Remainder: per-type pages, then refresh group/market-group links…")
        self._import_item_types()
        for group in ItemGroup.objects.select_related("category").order_by("id").iterator(
            chunk_size=200
        ):
            self._import_group(group)
        for mg in ItemMarketGroup.objects.order_by("id").iterator(chunk_size=200):
            self._import_market_group(mg)

    def _import_categories(self) -> None:
        rows = []
        for cat in ItemCategory.objects.order_by("name"):
            path = wiki_path(self.ROOT, "types", "categories", cat.id)
            rows.append([str(cat.id), self._page_link(path, cat.name), str(cat.published)])
        content = "# Item categories\n\n" + md_table(["ID", "Name", "Published"], rows)
        self._upsert(
            wiki_path(self.ROOT, "types", "categories"),
            "Item categories",
            content,
            tags=["sde", "types"],
        )
        for cat in ItemCategory.objects.order_by("id").iterator(chunk_size=100):
            groups = ItemGroup.objects.filter(category=cat).order_by("name")
            grow = [
                [
                    str(g.id),
                    self._page_link(wiki_path(self.ROOT, "types", "groups", g.id), g.name),
                ]
                for g in groups
            ]
            body = f"# {cat.name}\n\n{field_table({'ID': cat.id, 'Published': cat.published})}\n\n## Groups\n\n"
            body += md_table(["ID", "Name"], grow) if grow else "_None._"
            self._upsert(
                wiki_path(self.ROOT, "types", "categories", cat.id),
                cat.name,
                body,
                tags=["sde", "types", "category"],
            )

    def _import_groups_index(self) -> None:
        rows = []
        for g in ItemGroup.objects.select_related("category").order_by("name")[:3000]:
            cat = g.category.name if g.category else ""
            rows.append(
                [
                    str(g.id),
                    self._page_link(wiki_path(self.ROOT, "types", "groups", g.id), g.name),
                    cat,
                ]
            )
        note = ""
        total = ItemGroup.objects.count()
        if total > 3000:
            note = f"\n\n_First 3000 of {total} groups listed. Use search for others._"
        content = "# Item groups\n\n" + md_table(["ID", "Name", "Category"], rows) + note
        self._upsert(
            wiki_path(self.ROOT, "types", "groups"),
            "Item groups",
            content,
            tags=["sde", "types"],
        )

    def _import_group(self, group: ItemGroup) -> None:
        qs = ItemType.objects.filter(group=group).order_by("name")
        if not self.include_unpublished_types:
            qs = qs.filter(published=True)
        types = list(qs.values_list("id", "name", "published")[:400])
        rows = []
        for tid, tname, pub in types:
            name_cell = (
                tname
                if self.fast_import
                else self._page_link(wiki_path(self.ROOT, "types", "items", tid), tname)
            )
            rows.append([str(tid), name_cell, str(pub)])
        total = qs.count()
        more = f"\n\n_Showing 400 of {total} types._" if total > 400 else ""
        cat = group.category
        content = f"""# {group.name}

{field_table({
    "ID": group.id,
    "Category": (
        self._page_link(wiki_path(self.ROOT, "types", "categories", cat.id), cat.name)
        if cat else None
    ),
    "Published": group.published,
    "Anchorable": group.anchorable,
})}

## Types in this group

{md_table(["ID", "Name", "Published"], rows) if rows else "_None._"}{more}
"""
        self._upsert(
            wiki_path(self.ROOT, "types", "groups", group.id),
            group.name,
            content,
            tags=["sde", "types", "group"],
        )

    def _import_market_groups_index(self) -> None:
        roots = ItemMarketGroup.objects.filter(parent_group__isnull=True).order_by("name")
        rows = [
            [
                str(mg.id),
                self._page_link(wiki_path(self.ROOT, "types", "market-groups", mg.id), mg.name),
            ]
            for mg in roots
        ]
        content = "# Market groups (root)\n\n" + md_table(["ID", "Name"], rows)
        self._upsert(
            wiki_path(self.ROOT, "types", "market-groups"),
            "Market groups",
            content,
            tags=["sde", "types", "market"],
        )

    def _import_market_group(self, mg: ItemMarketGroup) -> None:
        children = ItemMarketGroup.objects.filter(parent_group=mg).order_by("name")
        child_rows = [
            [
                str(c.id),
                self._page_link(wiki_path(self.ROOT, "types", "market-groups", c.id), c.name),
            ]
            for c in children
        ]
        types = ItemType.objects.filter(market_group=mg).order_by("name")[:200]
        type_rows = []
        for t in types:
            name_cell = (
                t.name
                if self.fast_import
                else self._page_link(wiki_path(self.ROOT, "types", "items", t.id), t.name)
            )
            type_rows.append([str(t.id), name_cell])
        parent = mg.parent_group
        content = f"""# {mg.name}

{field_table({
    "ID": mg.id,
    "Parent": (
        self._page_link(wiki_path(self.ROOT, "types", "market-groups", parent.id), parent.name)
        if parent else None
    ),
    "Description": (mg.description or "")[:400],
})}

## Child market groups

{md_table(["ID", "Name"], child_rows) if child_rows else "_None._"}

## Types

{md_table(["ID", "Name"], type_rows) if type_rows else "_None._"}
"""
        self._upsert(
            wiki_path(self.ROOT, "types", "market-groups", mg.id),
            mg.name,
            content,
            tags=["sde", "types", "market"],
            force=self.remainder_mode,
        )

    def _import_item_types(self) -> None:
        qs = ItemType.objects.select_related("group", "market_group").order_by("id")
        if not self.include_unpublished_types:
            qs = qs.filter(published=True)
        for item in qs.iterator(chunk_size=250):
            self._import_item_type(item)

    def _import_item_type(self, item: ItemType) -> None:
        dogma_rows = []
        for td in TypeDogma.objects.filter(item_type=item).select_related("dogma_attribute")[:80]:
            attr = td.dogma_attribute
            if not attr:
                continue
            dogma_rows.append(
                [
                    str(attr.id),
                    self._page_link(wiki_path(self.ROOT, "dogma", "attributes", attr.id), attr.name),
                    str(td.value),
                ]
            )
        effect_rows = []
        for te in TypeEffect.objects.filter(item_type=item).select_related("dogma_effect")[:40]:
            eff = te.dogma_effect
            if not eff:
                continue
            effect_rows.append(
                [
                    str(eff.id),
                    self._page_link(wiki_path(self.ROOT, "dogma", "effects", eff.id), eff.name),
                ]
            )
        mat_rows = []
        for mat in ItemTypeMaterials.objects.filter(item_type=item).select_related(
            "material_item_type"
        )[:30]:
            mid = mat.material_item_type_id
            mname = mat.material_item_type.name if mat.material_item_type else str(mid)
            mat_rows.append(
                [
                    self._page_link(wiki_path(self.ROOT, "types", "items", mid), mname),
                    str(mat.quantity or f"{mat.quantity_min}-{mat.quantity_max}"),
                ]
            )
        mat_section = ""
        if mat_rows:
            mat_section = "\n## Materials\n\n" + md_table(["Material", "Qty"], mat_rows) + "\n"

        group = item.group
        mg = item.market_group
        desc = (item.description or "").strip()
        if len(desc) > 2000:
            desc = desc[:2000] + "…"
        content = f"""# {item.name}

{field_table({
    "Type ID": item.id,
    "Published": item.published,
    "Group": (
        self._page_link(wiki_path(self.ROOT, "types", "groups", group.id), group.name)
        if group else None
    ),
    "Market group": (
        self._page_link(wiki_path(self.ROOT, "types", "market-groups", mg.id), mg.name)
        if mg else None
    ),
    "Mass": item.mass,
    "Volume": item.volume,
    "Packaged volume": item.packaged_volume,
    "Base price": item.base_price,
    "Meta group ID": item.meta_group_id_raw,
    "Race ID": item.race_id,
})}

## Description

{desc or "_No description._"}
{mat_section}
## Dogma attributes

{md_table(["ID", "Attribute", "Value"], dogma_rows) if dogma_rows else "_None._"}

## Dogma effects

{md_table(["ID", "Effect"], effect_rows) if effect_rows else "_None._"}
"""
        self._upsert(
            wiki_path(self.ROOT, "types", "items", item.id),
            item.name,
            content,
            tags=["sde", "types", "item"],
        )

    def import_dogma(self) -> None:
        n_attr = DogmaAttribute.objects.count()
        n_eff = DogmaEffect.objects.count()
        phase_total = 2 if self.fast_import else (1 + n_attr) + (1 + n_eff)
        if self._progress:
            self._progress.set_phase("dogma", phase_total)
        attr_rows = []
        for attr in DogmaAttribute.objects.order_by("name").iterator(chunk_size=500):
            if len(attr_rows) < 2500:
                link = attr.name
                if not self.fast_import:
                    link = self._page_link(
                        wiki_path(self.ROOT, "dogma", "attributes", attr.id), attr.name
                    )
                attr_rows.append(
                    [
                        str(attr.id),
                        link,
                        str(getattr(attr, "published", "")),
                    ]
                )
            if not self.fast_import:
                self._import_dogma_attribute(attr)
        content = "# Dogma attributes\n\n" + md_table(["ID", "Name", "Published"], attr_rows)
        if DogmaAttribute.objects.count() > 2500:
            content += f"\n\n_Index shows 2500 of {DogmaAttribute.objects.count()}._"
        self._upsert(
            wiki_path(self.ROOT, "dogma", "attributes"),
            "Dogma attributes",
            content,
            tags=["sde", "dogma"],
        )

        eff_rows = []
        for eff in DogmaEffect.objects.order_by("name").iterator(chunk_size=500):
            if len(eff_rows) < 2500:
                link = eff.name
                if not self.fast_import:
                    link = self._page_link(
                        wiki_path(self.ROOT, "dogma", "effects", eff.id), eff.name
                    )
                eff_rows.append([str(eff.id), link])
            if not self.fast_import:
                self._import_dogma_effect(eff)
        content = "# Dogma effects\n\n" + md_table(["ID", "Name"], eff_rows)
        self._upsert(
            wiki_path(self.ROOT, "dogma", "effects"),
            "Dogma effects",
            content,
            tags=["sde", "dogma"],
            force=self.remainder_mode,
        )

    def _import_dogma_attribute(self, attr: DogmaAttribute) -> None:
        content = f"""# {attr.name}

{field_table({
    "ID": attr.id,
    "Description": (getattr(attr, "description", None) or "")[:800],
    "Default value": getattr(attr, "default_value", None),
    "Published": getattr(attr, "published", None),
    "Stackable": getattr(attr, "stackable", None),
    "High is good": getattr(attr, "high_is_good", None),
})}
"""
        self._upsert(
            wiki_path(self.ROOT, "dogma", "attributes", attr.id),
            attr.name,
            content,
            tags=["sde", "dogma", "attribute"],
        )

    def _import_dogma_effect(self, eff: DogmaEffect) -> None:
        content = f"""# {eff.name}

{field_table({
    "ID": eff.id,
    "Description": (getattr(eff, "description", None) or "")[:800],
    "Published": getattr(eff, "published", None),
    "Is offensive": getattr(eff, "is_offensive", None),
    "Is assistance": getattr(eff, "is_assistance", None),
})}
"""
        self._upsert(
            wiki_path(self.ROOT, "dogma", "effects", eff.id),
            eff.name,
            content,
            tags=["sde", "dogma", "effect"],
        )

    def import_industry(self) -> None:
        blueprint_types = (
            BlueprintActivity.objects.values_list("blueprint_item_type_id", flat=True)
            .distinct()
            .order_by("blueprint_item_type_id")
        )
        n_blueprints = blueprint_types.count()
        if self._progress:
            self._progress.set_phase("industry", 1 + n_blueprints)
        rows = []
        for bp_type_id in blueprint_types.iterator(chunk_size=500):
            if len(rows) >= 3000:
                break
            item = ItemType.objects.filter(id=bp_type_id).first()
            label = item.name if item else str(bp_type_id)
            path = wiki_path(self.ROOT, "industry", "blueprints", bp_type_id)
            rows.append([str(bp_type_id), self._page_link(path, label)])
        content = "# Industry blueprints\n\n" + md_table(["Blueprint type ID", "Name"], rows[:3000])
        total = blueprint_types.count()
        if total > 3000:
            content += f"\n\n_Index shows 3000 of {total} blueprints._"
        self._upsert(
            wiki_path(self.ROOT, "industry", "blueprints"),
            "Industry blueprints",
            content,
            tags=["sde", "industry"],
        )

        for bp_type_id in blueprint_types.iterator(chunk_size=100):
            self._import_blueprint(bp_type_id)

    def _import_blueprint(self, bp_type_id: int) -> None:
        item = ItemType.objects.filter(id=bp_type_id).first()
        title = item.name if item else f"Blueprint {bp_type_id}"
        activities = BlueprintActivity.objects.filter(blueprint_item_type_id=bp_type_id)
        act_rows = []
        for act in activities:
            products = BlueprintActivityProduct.objects.filter(blueprint_activity=act).select_related(
                "item_type"
            )[:20]
            materials = BlueprintActivityMaterial.objects.filter(blueprint_activity=act).select_related(
                "item_type"
            )[:20]
            prod_lines = []
            for p in products:
                tid = p.item_type_id
                tname = p.item_type.name if p.item_type else str(tid)
                prod_lines.append(
                    f"- {p.quantity}× {self._page_link(wiki_path(self.ROOT, 'types', 'items', tid), tname)}"
                )
            mat_lines = []
            for m in materials:
                tid = m.item_type_id
                tname = m.item_type.name if m.item_type else str(tid)
                mat_lines.append(
                    f"- {m.quantity}× {self._page_link(wiki_path(self.ROOT, 'types', 'items', tid), tname)}"
                )
            act_rows.append(
                f"### {act.activity}\n\n"
                f"- Time: {act.time}s\n"
                f"- Max production limit: {act.max_production_limit}\n\n"
                f"**Products**\n\n{chr(10).join(prod_lines) or '_None._'}\n\n"
                f"**Materials**\n\n{chr(10).join(mat_lines) or '_None._'}\n"
            )
        item_link = ""
        if item:
            item_link = self._page_link(wiki_path(self.ROOT, "types", "items", item.id), item.name)
        content = f"""# {title}

Blueprint type ID: **{bp_type_id}**  
Item: {item_link or '_unknown_'}

{"".join(act_rows) if act_rows else "_No activities._"}
"""
        self._upsert(
            wiki_path(self.ROOT, "industry", "blueprints", bp_type_id),
            title,
            content,
            tags=["sde", "industry", "blueprint"],
        )

    def estimate_page_count(self, sections: set[str]) -> int:
        total = 0
        if "home" in sections:
            total += 1
        if "map" in sections:
            total += 1 + Region.objects.count() + Constellation.objects.count()
            if not self.fast_import:
                total += SolarSystem.objects.count()
        if "types" in sections:
            total += (
                1
                + ItemCategory.objects.count()
                + 1
                + ItemGroup.objects.count()
                + 1
                + ItemMarketGroup.objects.count()
            )
            if not self.fast_import:
                type_qs = ItemType.objects.all()
                if not self.include_unpublished_types:
                    type_qs = type_qs.filter(published=True)
                total += type_qs.count()
        if "dogma" in sections:
            if self.fast_import:
                total += 2
            else:
                total += 1 + DogmaAttribute.objects.count() + 1 + DogmaEffect.objects.count()
        if "industry" in sections:
            total += (
                1
                + BlueprintActivity.objects.values_list("blueprint_item_type_id", flat=True)
                .distinct()
                .count()
            )
        return total

    def run(self, sections: set[str]) -> ImportStats:
        if not self.dry_run:
            if self.db_writer is not None:
                loaded = self.db_writer.preload_paths(self.ROOT)
                self._log(
                    f"Preloaded {loaded:,} existing /{self.ROOT} paths from Wiki.js DB "
                    f"(bulk insert, no per-page GraphQL)."
                )
            else:
                loaded = self.client.preload_paths(self.ROOT)
                self._log(
                    f"Preloaded {loaded:,} existing /{self.ROOT} paths (skip without per-page API calls)."
                )

        if self.stdout:
            self._progress = ImportProgress(
                self.stdout, interval=self._progress_interval
            )
            self._progress.start(self.estimate_page_count(sections))

        if self.remainder_mode:
            self._log(
                "Remainder import (after --fast): systems, item types, dogma detail, "
                "plus link refresh on group/constellation pages."
            )
        if "home" in sections and not self.remainder_mode:
            if self._progress:
                self._progress.set_phase("home", 1)
            self._log("Importing SDE home...")
            self.import_home()
        if "map" in sections:
            self._log("Importing map (regions, constellations, systems)...")
            self.import_map()
        if "types" in sections:
            self._log("Importing types (categories, groups, market groups, all item types)...")
            self.import_types()
        if "dogma" in sections:
            self._log("Importing dogma...")
            self.import_dogma()
        if "industry" in sections:
            self._log("Importing industry blueprints...")
            self.import_industry()

        self._flush_workers()
        if not self.dry_run:
            if self.db_writer is not None:
                flushed = self.db_writer.flush()
                if flushed:
                    self._log(f"Inserted {flushed:,} page row(s) into Wiki.js DB.")
            self._log("Rebuilding Wiki.js page tree…")
            try:
                self.client.rebuild_page_tree()
            except Exception as exc:
                self._log(f"WARNING: rebuildTree failed ({exc}); navigation may be incomplete.")
            self._log("Flushing Wiki.js cache…")
            self.client.flush_wiki_cache()
            if self.db_writer is not None:
                self._log(
                    "NOTE: --via-db pages need HTML render. Run: "
                    "python manage.py wikijs_render_sde"
                )

        if self._progress:
            self._progress.finish()
        return self.stats
