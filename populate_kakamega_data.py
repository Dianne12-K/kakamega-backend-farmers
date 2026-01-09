"""
Script to populate Kakamega County Sub-Counties and Wards
Run this once to initialize the database with all administrative areas
"""

from database import Database

def populate_kakamega_data():
    db = Database()

    print("=" * 60)
    print(" POPULATING KAKAMEGA COUNTY DATA")
    print("=" * 60)

    # Check if data already exists
    existing = db.get_all_subcounties()
    if existing:
        print(f"\n⚠️  Found {len(existing)} existing sub-counties.")
        response = input("Do you want to continue? This will add duplicates. (y/n): ")
        if response.lower() != 'y':
            print("Operation cancelled.")
            return

    # Sub-counties with their wards
    kakamega_data = [
        {
            'name': 'Butere',
            'code': 'BTR',
            'description': 'Butere Sub-County',
            'wards': [
                'Butsotso East',
                'Butsotso South',
                'Butsotso Central',
                'Shieywe',
                'Mahiakalo'
            ]
        },
        {
            'name': 'Mumias East',
            'code': 'MME',
            'description': 'Mumias East Sub-County',
            'wards': [
                'Mumias Central',
                'Mumias North',
                'Etenje',
                'Musanda'
            ]
        },
        {
            'name': 'Mumias West',
            'code': 'MMW',
            'description': 'Mumias West Sub-County',
            'wards': [
                'Koyonzo',
                'Kholera',
                'Khalaba',
                'Mayoni',
                'Namamali'
            ]
        },
        {
            'name': 'Matungu',
            'code': 'MTG',
            'description': 'Matungu Sub-County',
            'wards': [
                'Lusheya-Lubinu',
                'Malaha-Isongo-Makunga',
                'East Wanga'
            ]
        },
        {
            'name': 'Khwisero',
            'code': 'KHW',
            'description': 'Khwisero Sub-County',
            'wards': [
                'Kisa North',
                'Kisa East',
                'Kisa West',
                'Kisa Central'
            ]
        },
        {
            'name': 'Shinyalu',
            'code': 'SHY',
            'description': 'Shinyalu Sub-County',
            'wards': [
                'Isukha North',
                'Murhanda',
                'Isukha Central',
                'Isukha South',
                'Isukha East'
            ]
        },
        {
            'name': 'Lurambi',
            'code': 'LRB',
            'description': 'Lurambi Sub-County',
            'wards': [
                'Bunyala West',
                'Bunyala East',
                'Bunyala Central',
                'Ingotse-Matiha',
                'Shinoyi-Shikomari-Esumeiya'
            ]
        },
        {
            'name': 'Ikolomani',
            'code': 'IKL',
            'description': 'Ikolomani Sub-County',
            'wards': [
                'Idakho South',
                'Idakho East',
                'Idakho North',
                'Idakho Central'
            ]
        },
        {
            'name': 'Lugari',
            'code': 'LGR',
            'description': 'Lugari Sub-County',
            'wards': [
                'Mautuma',
                'Lugari',
                'Lumakanda',
                'Chekalini',
                'Chevaywa',
                'Lwandeti'
            ]
        },
        {
            'name': 'Likuyani',
            'code': 'LKY',
            'description': 'Likuyani Sub-County',
            'wards': [
                'Likuyani',
                'Sango',
                'Kongoni',
                'Nzoia',
                'Sinoko'
            ]
        },
        {
            'name': 'Malava',
            'code': 'MLV',
            'description': 'Malava Sub-County',
            'wards': [
                'West Kabaras',
                'Chemuche',
                'East Kabaras',
                'Butali-Chegulo',
                'Manda-Shivanga',
                'Shirugu-Mugai',
                'South Kabaras'
            ]
        },
        {
            'name': 'Navakholo',
            'code': 'NVK',
            'description': 'Navakholo Sub-County',
            'wards': [
                'Marama West',
                'Marama Central',
                'Marenyo-Shianda',
                'Marama North',
                'Marama South'
            ]
        }
    ]

    total_subcounties = 0
    total_wards = 0

    # Insert data
    for subcounty_data in kakamega_data:
        print(f"\n📍 Adding {subcounty_data['name']}...")

        # Add sub-county
        subcounty_id = db.add_subcounty(
            name=subcounty_data['name'],
            code=subcounty_data['code'],
            description=subcounty_data['description']
        )
        total_subcounties += 1

        # Add wards
        for ward_name in subcounty_data['wards']:
            ward_code = ''.join([w[0].upper() for w in ward_name.split()[:3]])
            db.add_ward(
                name=ward_name,
                subcounty_id=subcounty_id,
                code=ward_code
            )
            total_wards += 1
            print(f"   ✓ {ward_name}")

    print("\n" + "=" * 60)
    print(" DATA POPULATION COMPLETE")
    print("=" * 60)
    print(f" Sub-Counties Added: {total_subcounties}")
    print(f" Wards Added: {total_wards}")
    print("=" * 60)

    # Verify
    print("\nVerifying data...")
    subcounties = db.get_all_subcounties()
    print(f"✓ Total Sub-Counties in DB: {len(subcounties)}")

    total_wards_in_db = sum([db.get_ward_count_by_subcounty(sc['id']) for sc in subcounties])
    print(f"✓ Total Wards in DB: {total_wards_in_db}")
    print("\n Database successfully populated!")


if __name__ == '__main__':
    populate_kakamega_data()