"""Convert nextseller/data/products.csv (+ product_scores.csv) into the TaoYongStudio product import format.

Read-only on both sides: it only writes nextseller/data/taoyong_import.csv, which you then import in the app
(Trends > import CSV). Nothing is posted. Affiliate links are copied only when NextsellerAI has them.
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

D = Path(__file__).resolve().parent / "data"
FIELDS = ["name", "item_id", "shop_id", "shop_name", "variant", "category", "price_min", "price_max",
          "commission_rate", "sales", "rating", "image_url", "product_url", "offer_link", "observed_at", "source_ref"]


def read(name):
    p = D / name
    if not p.is_file():
        sys.exit(f"ไม่พบ {p} — รัน nextseller/pull_nextseller_products.ps1 ก่อน")
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def jl(v):
    try:
        x = json.loads(v or "[]")
        return x if isinstance(x, list) else []
    except json.JSONDecodeError:
        return []


def main():
    scores = {r["product_id"]: r for r in read("product_scores.csv")} if (D / "product_scores.csv").is_file() else {}
    now = datetime.now(timezone.utc).isoformat()
    out = []
    for r in read("products.csv"):
        price = r.get("sale_price") or r.get("original_price") or ""
        rate = r.get("commission_rate") or ""
        try:
            rate = f"{float(rate) / 100:g}"  # NextsellerAI stores percent (9.00); the importer wants a fraction
        except ValueError:
            rate = ""
        sc = scores.get(r["id"], {})
        out.append({"name": r["name"], "item_id": r.get("external_id", ""), "shop_id": "", "shop_name": r.get("seller_name", ""),
                    "variant": "", "category": r.get("category", ""), "price_min": price, "price_max": price,
                    "commission_rate": rate, "sales": r.get("sold_count", ""), "rating": r.get("rating", ""),
                    "image_url": r.get("image_url", ""), "product_url": r.get("product_url", ""),
                    "offer_link": r.get("affiliate_url", ""), "observed_at": now,
                    "source_ref": f"nextseller:{r['id']}:score={sc.get('score', '')}:{sc.get('decision', '')}"})
    with (D / "taoyong_import.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out)
    # angles + risks go to a side file for the clip planner (not part of the product import)
    ang = {pid: {"angles": jl(s.get("suggested_angles")), "risks": jl(s.get("risks")), "score": s.get("score")}
           for pid, s in scores.items()}
    (D / "angles.json").write_text(json.dumps(ang, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out)} สินค้า → {D / 'taoyong_import.csv'}; มุมคลิปของ {len(ang)} สินค้า → angles.json")


if __name__ == "__main__":
    main()
