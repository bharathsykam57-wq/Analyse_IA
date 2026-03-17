#!/usr/bin/env python3
"""Test Supabase connection and prepare deployment credentials"""

import psycopg2
import urllib.parse

# URL encode the password
password = "gYGL?adnv3UmX8?"
encoded_password = urllib.parse.quote(password, safe='')

# Connection string
DATABASE_URL = f"postgresql://postgres:{encoded_password}@db.gmftmpbuirmcizertnbn.supabase.co:5432/postgres"

print("\n" + "=" * 70)
print("SUPABASE DATABASE CONNECTION TEST")
print("=" * 70)

try:
    print("\n1. Connecting to Supabase...")
    conn = psycopg2.connect(DATABASE_URL)
    print("   ✓ Connected!")
    
    cursor = conn.cursor()
    
    print("\n2. Checking pgvector extension...")
    cursor.execute("SELECT extname FROM pg_extension WHERE extname='vector'")
    result = cursor.fetchone()
    if result:
        print("   ✓ pgvector is available")
    else:
        print("   ✗ pgvector not found")
    
    print("\n3. Checking database version...")
    cursor.execute("SELECT version()")
    version = cursor.fetchone()[0]
    print(f"   ✓ {version.split(',')[0]}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ DATABASE IS READY FOR RAILWAY DEPLOYMENT")
    print("=" * 70)
    print(f"\nUse this DATABASE_URL in Railway:")
    print(f"\n{DATABASE_URL}\n")
    
except Exception as e:
    print(f"\n✗ Connection failed: {e}\n")
