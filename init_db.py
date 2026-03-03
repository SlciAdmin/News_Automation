#!/usr/bin/env python3
"""Initialize PostgreSQL database tables and run migrations"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

from config import Config
import database

if __name__ == "__main__":
    print("🗄️ Initializing PostgreSQL database...")
    print(f"   Connection: {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
    
    # Step 1: Initialize database tables (creates tables if not exist)
    if not database.init_db():
        print("❌ Failed to initialize database tables")
        sys.exit(1)
    
    print("✅ Database tables created/verified successfully!")
    
    # Step 2: ✅ Run migration to add missing columns (safe to run multiple times)
    print("\n🔄 Running database migration...")
    if database.migrate_database():
        print("✅ Migration completed - all columns verified/added")
    else:
        print("⚠️ Migration had issues - check logs for details")
    
    # Summary
    print("\n📋 Tables created/verified:")
    print("   • subscribers - Stores subscriber phone numbers & preferences")
    print("   • broadcast_logs - Records auto-broadcast attempts")
    print("   • admin_logs - Tracks admin actions")
    print("\n🔧 Columns in broadcast_logs:")
    print("   • english_duration INTEGER - English audio length in seconds")
    print("   • hindi_duration INTEGER - Hindi audio length in seconds")
    print("\n✨ Database setup complete! You can now run: python run.py")