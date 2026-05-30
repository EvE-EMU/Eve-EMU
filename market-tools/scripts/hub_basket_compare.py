#!/usr/bin/env python3
"""Compare buy cost for pasted item quantities across Jita, Amarr, Hek, Dodixie, Rens.

Examples::

    python scripts/hub_basket_compare.py --file shopping.txt
    python scripts/hub_basket_compare.py - <<EOF
    Broadcast Node x900
    Marines x225
    EOF

    Get-Content market-tools\\examples\\hub_basket.example.txt -Raw |
      docker compose exec -T market-api python scripts/hub_basket_compare.py

    docker compose cp market-tools/examples/hub_basket.example.txt market-api:/tmp/list.txt
    docker compose exec market-api python scripts/hub_basket_compare.py -f /tmp/list.txt

Paste format matches /appraisal (``Name x Qty``, ``Qty x Name``, or tab-separated).
Uses public ESI sell orders — no Janice API key required.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.hub_basket import (  # noqa: E402
    format_hub_basket_report,
    run_hub_basket_compare,
)


def _read_text(args: argparse.Namespace) -> str:
    if args.file:
        path = Path(args.file)
        if not path.is_file():
            raise SystemExit(
                f"File not found: {path}\n"
                "Use a path that exists inside the container, pipe stdin, or run on the host:\n"
                "  python market-tools/scripts/hub_basket_compare.py -f market-tools/examples/hub_basket.example.txt"
            )
        return path.read_text(encoding="utf-8")
    if args.text:
        return args.text
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Provide --file, --text, or stdin.")


async def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare full-quantity buy prices across EVE trade hubs (ESI)."
    )
    parser.add_argument("--file", "-f", help="Path to item list (one line per item)")
    parser.add_argument("--text", "-t", help="Inline paste text")
    parser.add_argument(
        "--hubs",
        nargs="+",
        default=None,
        help="Hub keys: jita amarr dodixie rens hek (default: all)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=8,
        help="Max ESI order pages per type per hub (stops early when qty fills)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=6,
        help="Parallel ESI fetches (default 6)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print progress to stderr while fetching ESI prices",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON instead of text report",
    )
    args = parser.parse_args()
    text = _read_text(args)

    def _progress(done: int, total: int, name: str, hub: str) -> None:
        print(f"[{done}/{total}] {name} @ {hub}", file=sys.stderr, flush=True)

    on_progress = _progress if args.verbose else None
    if args.verbose:
        lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        print(
            f"Fetching prices for {len(lines)} item(s) across hubs (parallel={args.concurrency})…",
            file=sys.stderr,
            flush=True,
        )

    result = await run_hub_basket_compare(
        text,
        hubs=args.hubs,
        max_pages=args.max_pages,
        concurrency=args.concurrency,
        on_progress=on_progress,
    )
    if args.json:
        import json

        print(json.dumps(result, indent=2))
    else:
        print(format_hub_basket_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
