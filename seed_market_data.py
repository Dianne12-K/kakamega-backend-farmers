"""
Script to seed initial market data into SQLite database
Run this once to populate your database with initial market data
Usage: python seed_market_data.py
"""
from database import Database
from datetime import date


def seed_markets(db):
    """Create initial markets"""
    markets_data = [
        {
            'name': 'Kakamega Town Market',
            'location': 'Kakamega Town',
            'contact_phone': '+254 712 345 678',
            'operating_days': 'Monday-Saturday',
            'payment_terms': 'Cash on delivery'
        },
        {
            'name': 'Mumias Market',
            'location': 'Mumias Town',
            'contact_phone': '+254 712 345 679',
            'operating_days': 'Daily',
            'payment_terms': 'Cash on delivery'
        },
        {
            'name': 'Butere Market',
            'location': 'Butere',
            'contact_phone': '+254 712 345 680',
            'operating_days': 'Monday-Saturday',
            'payment_terms': 'Cash on delivery'
        },
        {
            'name': 'NCPB Depot',
            'location': 'Kakamega',
            'operating_days': 'Monday-Friday',
            'payment_terms': 'Bank transfer within 7 days'
        },
        {
            'name': 'Mumias Sugar Company',
            'location': 'Mumias',
            'contact_phone': '+254 712 345 681',
            'operating_days': 'Daily',
            'payment_terms': 'Monthly payment'
        },
        {
            'name': 'Butali Sugar',
            'location': 'Butali',
            'contact_phone': '+254 712 345 682',
            'operating_days': 'Daily',
            'payment_terms': 'Monthly payment'
        },
        {
            'name': 'West Kenya Sugar',
            'location': 'Kakamega',
            'contact_phone': '+254 712 345 683',
            'operating_days': 'Monday-Saturday',
            'payment_terms': 'Bi-weekly payment'
        },
        {
            'name': 'Khayega Market',
            'location': 'Khayega',
            'contact_phone': '+254 712 345 684',
            'operating_days': 'Wednesday, Saturday',
            'payment_terms': 'Cash on delivery'
        }
    ]

    created_markets = {}
    for market_data in markets_data:
        market_id = db.add_market(**market_data)
        created_markets[market_data['name']] = market_id
        print(f"✓ Created market: {market_data['name']} (ID: {market_id})")

    return created_markets


def seed_prices(db, market_ids):
    """Create initial market prices"""
    prices_data = [
        # Maize prices
        {'market': 'Kakamega Town Market', 'crop_type': 'maize', 'price': 4200, 'unit': 'per 90kg bag', 'grade': 'Grade 1'},
        {'market': 'Mumias Market', 'crop_type': 'maize', 'price': 4500, 'unit': 'per 90kg bag', 'grade': 'Grade 1'},
        {'market': 'Butere Market', 'crop_type': 'maize', 'price': 4000, 'unit': 'per 90kg bag', 'grade': 'Grade 1'},
        {'market': 'NCPB Depot', 'crop_type': 'maize', 'price': 3600, 'unit': 'per 90kg bag', 'grade': 'Grade 2'},

        # Sugarcane prices
        {'market': 'Mumias Sugar Company', 'crop_type': 'sugarcane', 'price': 4500, 'unit': 'per ton', 'grade': 'Standard'},
        {'market': 'Butali Sugar', 'crop_type': 'sugarcane', 'price': 4800, 'unit': 'per ton', 'grade': 'Premium'},
        {'market': 'West Kenya Sugar', 'crop_type': 'sugarcane', 'price': 4600, 'unit': 'per ton', 'grade': 'Standard'},

        # Beans prices
        {'market': 'Kakamega Town Market', 'crop_type': 'beans', 'price': 12000, 'unit': 'per 90kg bag', 'grade': 'Grade 1'},
        {'market': 'Khayega Market', 'crop_type': 'beans', 'price': 11500, 'unit': 'per 90kg bag', 'grade': 'Grade 1'},
        {'market': 'Butere Market', 'crop_type': 'beans', 'price': 11000, 'unit': 'per 90kg bag', 'grade': 'Grade 2'},

        # Tea prices
        {'market': 'Kakamega Town Market', 'crop_type': 'tea', 'price': 45, 'unit': 'per kg', 'grade': 'Green Leaf'},
        {'market': 'Mumias Market', 'crop_type': 'tea', 'price': 48, 'unit': 'per kg', 'grade': 'Green Leaf'},
    ]

    today = date.today().isoformat()

    for price_data in prices_data:
        market_name = price_data.pop('market')
        market_id = market_ids.get(market_name)

        if market_id:
            db.add_market_price(
                market_id=market_id,
                date_recorded=today,
                **price_data
            )
            print(f"✓ Created price: {price_data['crop_type']} at {market_name} - KES {price_data['price']}")


def seed_collection_centers(db):
    """Create initial collection centers"""
    centers_data = [
        {
            'name': 'Kakamega Main Collection Center',
            'location': 'Kakamega Town',
            'latitude': 0.2827,
            'longitude': 34.7519,
            'crops_accepted': ['maize', 'beans'],
            'contact_phone': '+254 712 345 678',
            'operating_days': 'Monday-Saturday',
            'operating_hours': '7:00 AM - 5:00 PM',
            'storage_capacity': 'Large',
            'payment_terms': 'Cash on delivery',
            'minimum_quantity': '1 bag',
            'quality_requirements': 'Moisture content < 13.5%, No aflatoxins'
        },
        {
            'name': 'Mumias Sugar Collection Point',
            'location': 'Mumias',
            'latitude': 0.3347,
            'longitude': 34.4877,
            'crops_accepted': ['sugarcane'],
            'contact_phone': '+254 712 345 679',
            'operating_days': 'Daily',
            'operating_hours': '6:00 AM - 6:00 PM',
            'storage_capacity': 'Very Large',
            'payment_terms': 'Monthly payment',
            'minimum_quantity': '1 ton',
            'quality_requirements': 'Minimum sugar content 10%, Fresh cane preferred'
        },
        {
            'name': 'Butere Farmers Cooperative',
            'location': 'Butere',
            'latitude': 0.2077,
            'longitude': 34.4889,
            'crops_accepted': ['maize', 'beans'],
            'contact_phone': '+254 712 345 680',
            'operating_days': 'Monday-Friday',
            'operating_hours': '8:00 AM - 4:00 PM',
            'storage_capacity': 'Medium',
            'payment_terms': 'Weekly payment',
            'minimum_quantity': '5 bags',
            'quality_requirements': 'Grade 1 or 2, properly dried'
        },
        {
            'name': 'Khayega Market Collection',
            'location': 'Khayega',
            'latitude': 0.2500,
            'longitude': 34.6000,
            'crops_accepted': ['beans', 'maize'],
            'contact_phone': '+254 712 345 684',
            'operating_days': 'Wednesday, Saturday',
            'operating_hours': '6:00 AM - 2:00 PM',
            'storage_capacity': 'Small',
            'payment_terms': 'Cash on delivery',
            'minimum_quantity': '1 bag'
        },
        {
            'name': 'West Kenya Tea Factory',
            'location': 'Kakamega',
            'latitude': 0.2900,
            'longitude': 34.7600,
            'crops_accepted': ['tea'],
            'contact_phone': '+254 712 345 685',
            'operating_days': 'Daily',
            'operating_hours': '6:00 AM - 6:00 PM',
            'storage_capacity': 'Large',
            'payment_terms': 'Monthly payment',
            'minimum_quantity': '10 kg',
            'quality_requirements': 'Fresh green leaf only, no yellowing'
        }
    ]

    for center_data in centers_data:
        center_id = db.add_collection_center(**center_data)
        print(f"✓ Created collection center: {center_data['name']} (ID: {center_id})")


def main():
    """Main seeding function"""
    print("\n" + "="*60)
    print("MARKET DATA SEEDING SCRIPT")
    print("="*60 + "\n")

    # Initialize database
    db = Database()

    # Check if data already exists
    existing_markets = db.get_all_markets(active_only=False)
    if existing_markets:
        print(f"⚠  Warning: {len(existing_markets)} markets already exist in database")
        response = input("Do you want to continue and add more data? (y/n): ")
        if response.lower() != 'y':
            print("\n❌ Seeding cancelled\n")
            return

    try:
        print("\n📍 Step 1: Creating markets...")
        print("-" * 60)
        market_ids = seed_markets(db)

        print("\n💰 Step 2: Creating market prices...")
        print("-" * 60)
        seed_prices(db, market_ids)

        print("\n🏢 Step 3: Creating collection centers...")
        print("-" * 60)
        seed_collection_centers(db)

        print("\n" + "="*60)
        print("✅ SEEDING COMPLETED SUCCESSFULLY!")
        print("="*60)

        # Summary
        all_markets = db.get_all_markets(active_only=False)
        all_centers = db.get_all_collection_centers(active_only=False)

        print(f"\n📊 Summary:")
        print(f"   - Markets created: {len(all_markets)}")
        print(f"   - Collection centers created: {len(all_centers)}")

        print("\n💡 Next steps:")
        print("   1. Check your database to verify the data")
        print("   2. Update prices weekly using the API or admin interface")
        print("   3. Add more markets and collection centers as needed\n")

    except Exception as e:
        print(f"\n❌ Error during seeding: {str(e)}")
        print("Please check your database configuration and try again.\n")
        raise


if __name__ == '__main__':
    main()