"""Kør kvalitetsporten og render manglende medier for alle opslag i queue/.

Brug: python3 pipeline/build.py [--force]
Afslutter med fejl, hvis et opslag ikke består kvalitetsporten. Der renderes intet før alt består.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
import lint  # noqa: E402
import render  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="render alt forfra")
    args = ap.parse_args()

    items = list(common.queue_items())
    failed = False
    for item in items:
        probs = lint.check(item)
        if probs:
            failed = True
            print(f"FEJL  {item.get('id', item['_path'].name)}")
            for x in probs:
                print(f"        {x}")
    if failed:
        print("\nIntet renderet. Ret fejlene og kør igen.")
        return 1

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for item in items:
            changed = render.render_item(page, item, args.force)
            print(("rendret  " if changed else "uændret  ") + item["id"])
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
