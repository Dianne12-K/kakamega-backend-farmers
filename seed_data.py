"""
seed_data.py — Run once to populate kakamega_smart_farm database
Usage: python seed_data.py
"""

import sys
import random
from datetime import datetime, timedelta, date, timezone
from app import create_app
from extensions import db
from core.models import (
    Subcounty, Ward, Farm,
    NDVIReading, MoistureReading,
    WeatherData, Market, MarketPrice, Recommendation
)


def seed():
    app = create_app()
    with app.app_context():
        print("🌱 Seeding Kakamega Smart Farm database...")

        # ── 1. SUBCOUNTIES ──────────────────────────────────────────
        print("  → Subcounties...")
        subcounty_data = [
            ("Lugari",      "LUG"),
            ("Likuyani",    "LIK"),
            ("Malava",      "MAL"),
            ("Lurambi",     "LUR"),
            ("Navakholo",   "NAV"),
            ("Mumias East", "MUE"),
            ("Mumias West", "MUW"),
            ("Matungu",     "MAT"),
            ("Butere",      "BUT"),
            ("Khwisero",    "KHW"),
            ("Shinyalu",    "SHI"),
            ("Ikolomani",   "IKO"),
        ]

        subcounties = {}
        for name, code in subcounty_data:
            existing = Subcounty.query.filter_by(name=name).first()
            if not existing:
                sc = Subcounty(name=name, code=code)
                db.session.add(sc)
                db.session.flush()
                subcounties[name] = sc
            else:
                subcounties[name] = existing

        db.session.commit()
        print(f"     ✓ {len(subcounties)} subcounties")

        # ── 2. WARDS ────────────────────────────────────────────────
        print("  → Wards...")
        ward_data = [
            ("Lugari",      ["Lugari", "Chekalini", "Mautuma"]),
            ("Likuyani",    ["Likuyani", "Sango", "Nzoia"]),
            ("Malava",      ["Malava", "Shirere", "Chemuche", "East Kabras"]),
            ("Lurambi",     ["Sheywe", "Mahiakalo", "East Bunyore"]),
            ("Navakholo",   ["Ingostse", "West Kabras", "Butali"]),
            ("Mumias East", ["Mumias", "Etenje", "Lusheya"]),
            ("Mumias West", ["Musanda", "Chemo", "Mumias West"]),
            ("Matungu",     ["Koyonzo", "Khalaba", "Mayoni", "Namamali"]),
            ("Butere",      ["Butere", "Marama West", "Marama Central"]),
            ("Khwisero",    ["Khwisero", "Kisa North", "Kisa East"]),
            ("Shinyalu",    ["Shinyalu", "Esava", "Ikutha"]),
            ("Ikolomani",   ["Idakho North", "Idakho East", "Idakho South"]),
        ]

        wards = {}
        for sc_name, ward_names in ward_data:
            sc = subcounties.get(sc_name)
            if not sc:
                continue
            for wname in ward_names:
                existing = Ward.query.filter_by(name=wname).first()
                if not existing:
                    w = Ward(
                        name=wname,
                        subcounty_id=sc.id,
                        population=random.randint(8000, 25000),
                        area_sq_km=round(random.uniform(20, 80), 2),
                    )
                    db.session.add(w)
                    db.session.flush()
                    wards[wname] = w
                else:
                    wards[wname] = existing

        db.session.commit()
        print(f"     ✓ {len(wards)} wards")

        # ── 3. FARMS ────────────────────────────────────────────────
        print("  → Farms...")

        # Kakamega County approximate center coords per subcounty
        sc_coords = {
            "Lugari":      (0.3667,  34.9333),
            "Likuyani":    (0.2167,  34.9500),
            "Malava":      (0.4500,  34.7333),
            "Lurambi":     (0.2833,  34.7500),
            "Navakholo":   (0.2000,  34.6667),
            "Mumias East": (0.3333,  34.4833),
            "Mumias West": (0.3500,  34.4500),
            "Matungu":     (0.4167,  34.4667),
            "Butere":      (0.2000,  34.4833),
            "Khwisero":    (0.1167,  34.5000),
            "Shinyalu":    (0.3667,  34.7667),
            "Ikolomani":   (0.2667,  34.7500),
        }

        crop_types  = ["maize", "sugarcane", "tea", "beans", "sorghum", "cassava", "vegetables", "sunflower"]
        soil_types  = ["clay", "loam", "sandy_loam", "clay_loam"]
        irrig_types = ["rainfed", "drip", "sprinkler", "furrow"]
        statuses    = ["active", "active", "active", "fallow", "harvested"]

        owner_names = [
            "John Wekesa",    "Mary Achieng",   "Peter Barasa",   "Grace Nafula",
            "David Simiyu",   "Jane Nekesa",    "Paul Wafula",    "Alice Atieno",
            "Samuel Odhiambo","Rose Auma",      "James Makokha",  "Beatrice Imbisi",
            "Charles Masinde","Lydia Khisa",    "George Wasike",  "Esther Wangila",
            "Henry Wanyonyi", "Phoebe Otieno",  "Robert Shitsama","Dorcas Mukhweso",
            "Moses Ingosi",   "Naomi Likhayo",  "Joshua Lutiali", "Cynthia Maelo",
            "Stephen Juma",   "Tabitha Khaukha","Daniel Wambani", "Angela Muliro",
            "Michael Injendi","Sarah Mukhwana",
        ]

        sc_list    = list(subcounties.values())
        sc_names   = list(subcounties.keys())
        farm_records = []

        for i in range(30):
            sc_name = sc_names[i % len(sc_names)]
            sc      = subcounties[sc_name]
            base_lat, base_lon = sc_coords.get(sc_name, (0.28, 34.75))
            crop    = random.choice(crop_types)
            owner   = owner_names[i]
            name    = f"{owner.split()[1]} {crop.capitalize()} Farm"
            lat     = round(base_lat + random.uniform(-0.08, 0.08), 6)
            lon     = round(base_lon + random.uniform(-0.08, 0.08), 6)

            # pick a ward in this subcounty
            ward = Ward.query.filter_by(subcounty_id=sc.id).first()

            existing = Farm.query.filter_by(name=name).first()
            if existing:
                farm_records.append(existing)
                continue

            farm = Farm(
                name=name,
                crop_type=crop,
                area_ha=round(random.uniform(0.5, 15.0), 2),
                latitude=lat,
                longitude=lon,
                soil_type=random.choice(soil_types),
                irrigation=random.choice(irrig_types),
                yield_estimate_tons=round(random.uniform(0.5, 8.0), 2),
                status=random.choice(statuses),
                ward_id=ward.id if ward else None,
                planting_date=date.today() - timedelta(days=random.randint(30, 120)),
            )
            db.session.add(farm)
            db.session.flush()
            farm_records.append(farm)

        db.session.commit()
        print(f"     ✓ {len(farm_records)} farms")

        # ── 4. NDVI READINGS ────────────────────────────────────────
        print("  → NDVI readings...")
        ndvi_count = 0
        for farm in farm_records:
            for week in range(6):
                d = date.today() - timedelta(weeks=week)
                existing = NDVIReading.query.filter_by(farm_id=farm.id, date=d).first()
                if existing:
                    continue
                score = random.randint(30, 98)
                nr = NDVIReading(
                    farm_id=farm.id,
                    date=d,
                    ndvi_value=round(random.uniform(0.2, 0.85), 4),
                    health_score=score,
                    status="good" if score >= 60 else "fair" if score >= 40 else "poor",
                    source="sentinel-2",
                )
                db.session.add(nr)
                ndvi_count += 1

        db.session.commit()
        print(f"     ✓ {ndvi_count} NDVI readings")

        # ── 5. MOISTURE READINGS ────────────────────────────────────
        print("  → Moisture readings...")
        moist_count = 0
        for farm in farm_records:
            for week in range(6):
                d = date.today() - timedelta(weeks=week)
                existing = MoistureReading.query.filter_by(farm_id=farm.id, date=d).first()
                if existing:
                    continue
                pct = round(random.uniform(15, 85), 2)
                mr = MoistureReading(
                    farm_id=farm.id,
                    date=d,
                    moisture_percent=pct,
                    status="optimal" if 40 <= pct <= 70 else "low" if pct < 40 else "high",
                    days_since_rain=random.randint(0, 14),
                )
                db.session.add(mr)
                moist_count += 1

        db.session.commit()
        print(f"     ✓ {moist_count} moisture readings")

        # ── 6. WEATHER DATA ─────────────────────────────────────────
        print("  → Weather data...")
        weather_count = 0
        conditions_list = ["Sunny", "Partly Cloudy", "Cloudy", "Light Rain", "Heavy Rain", "Clear"]
        for sc_name, (base_lat, base_lon) in sc_coords.items():
            for day in range(14):
                d = date.today() - timedelta(days=day)
                existing = WeatherData.query.filter_by(latitude=base_lat, date=d).first()
                if existing:
                    continue
                w = WeatherData(
                    latitude=base_lat,
                    longitude=base_lon,
                    date=d,
                    temperature=round(random.uniform(18, 32), 2),
                    humidity=random.randint(55, 90),
                    rain_probability=random.randint(0, 100),
                    rain_amount=round(random.uniform(0, 25), 2),
                    conditions=random.choice(conditions_list),
                    source="openweather",
                )
                db.session.add(w)
                weather_count += 1

        db.session.commit()
        print(f"     ✓ {weather_count} weather records")

        # ── 7. MARKETS ──────────────────────────────────────────────
        print("  → Markets...")
        market_data = [
            ("Kakamega Main Market",  "Lurambi",    0.2833, 34.7519, "daily"),
            ("Mumias Market",         "Mumias East",0.3333, 34.4833, "daily"),
            ("Malava Market",         "Malava",     0.4500, 34.7333, "weekly"),
            ("Lugari Market",         "Lugari",     0.3667, 34.9333, "twice_weekly"),
            ("Matungu Market",        "Matungu",    0.4167, 34.4667, "weekly"),
            ("Butere Market",         "Butere",     0.2000, 34.4833, "weekly"),
            ("Likuyani Market",       "Likuyani",   0.2167, 34.9500, "twice_weekly"),
            ("Navakholo Market",      "Navakholo",  0.2000, 34.6667, "weekly"),
        ]

        markets = []
        for mname, sc_name, lat, lon, freq in market_data:
            sc = subcounties.get(sc_name)
            existing = Market.query.filter_by(name=mname).first()
            if existing:
                markets.append(existing)
                continue
            m = Market(
                name=mname,
                location_text=sc_name,
                latitude=lat,
                longitude=lon,
                operating_days=freq,
                contact_person="Market Manager",
                contact_phone=f"+2547{random.randint(10000000,99999999)}",
                payment_terms="Cash on delivery",
                is_active=True,
            )
            db.session.add(m)
            db.session.flush()
            markets.append(m)

        db.session.commit()
        print(f"     ✓ {len(markets)} markets")

        # ── 8. MARKET PRICES ────────────────────────────────────────
        print("  → Market prices...")
        price_ranges = {
            "maize":      (25, 35),
            "sugarcane":  (30, 45),
            "tea":        (50, 80),
            "beans":      (80, 120),
            "sorghum":    (20, 30),
            "cassava":    (15, 25),
            "vegetables": (30, 60),
            "sunflower":  (40, 60),
        }
        price_count = 0
        for market in markets:
            for crop, (low, high) in price_ranges.items():
                for day in range(14):
                    d = date.today() - timedelta(days=day)
                    existing = MarketPrice.query.filter_by(
                        market_id=market.id, crop_type=crop, date_recorded=d
                    ).first()
                    if existing:
                        continue
                    mp = MarketPrice(
                        market_id=market.id,
                        crop_type=crop,
                        price=round(random.uniform(low, high), 2),
                        unit="per 90kg bag",
                        grade="A",
                        date_recorded=d,
                        is_current=(day == 0),
                    )
                    db.session.add(mp)
                    price_count += 1

        db.session.commit()
        print(f"     ✓ {price_count} price records")

        # ── 9. RECOMMENDATIONS ──────────────────────────────────────
        print("  → Recommendations...")
        rec_templates = [
            ("Apply nitrogen fertilizer", "fertilizer", "high",
             "Soil nitrogen levels are low. Apply CAN at 50kg/acre within 7 days."),
            ("Irrigation needed", "irrigation", "high",
             "Soil moisture below 30%. Schedule irrigation within 48 hours."),
            ("Pest scouting advised", "pest_control", "medium",
             "Stalk borer risk elevated. Scout and apply if infestation >5%."),
            ("Harvest window approaching", "harvest", "medium",
             "Crop maturity expected in 14 days. Prepare storage and transport."),
            ("Weed control required", "weeding", "low",
             "Weed pressure detected. Manual or herbicide control recommended."),
        ]
        rec_count = 0
        for farm in farm_records[:20]:
            action, category, priority, reason = random.choice(rec_templates)
            existing = Recommendation.query.filter_by(farm_id=farm.id, action=action).first()
            if existing:
                continue
            r = Recommendation(
                farm_id=farm.id,
                action=action,
                reason=reason,
                category=category,
                priority=priority,
                is_resolved=random.choice([True, False]),
            )
            db.session.add(r)
            rec_count += 1

        db.session.commit()
        print(f"     ✓ {rec_count} recommendations")

        # ── SUMMARY ─────────────────────────────────────────────────
        print("\n✅ Seed complete!")
        print(f"   Subcounties    : {Subcounty.query.count()}")
        print(f"   Wards          : {Ward.query.count()}")
        print(f"   Farms          : {Farm.query.count()}")
        print(f"   NDVI readings  : {NDVIReading.query.count()}")
        print(f"   Moisture recs  : {MoistureReading.query.count()}")
        print(f"   Weather recs   : {WeatherData.query.count()}")
        print(f"   Markets        : {Market.query.count()}")
        print(f"   Market prices  : {MarketPrice.query.count()}")
        print(f"   Recommendations: {Recommendation.query.count()}")
        print("\n🚀 Hit http://localhost:5000/api/farms to see real data!")


if __name__ == "__main__":
    try:
        seed()
    except Exception as e:
        print(f"\n❌ Seed failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)