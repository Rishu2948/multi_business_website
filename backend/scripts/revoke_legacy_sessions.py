#!/usr/bin/env python3
"""
Revoke all legacy session tokens.

This script deletes all legacy session tokens from the user_sessions collection
as part of the legacy session cutover procedure.

Usage:
    python revoke_legacy_sessions.py

Environment variables:
    MONGO_URL: MongoDB connection string
    DB_NAME: Database name
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient


async def revoke_legacy_sessions():
    """Revoke all legacy session tokens."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "multi_business_db")
    
    print(f"Connecting to MongoDB: {mongo_url}")
    print(f"Database: {db_name}")
    
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    
    try:
        # Verify connection
        await db.command('ping')
        print("✓ Connected to MongoDB")
        
        # Count legacy sessions before deletion
        legacy_count = await db.user_sessions.count_documents({
            "session_token": {"$exists": True}
        })
        print(f"Found {legacy_count} legacy sessions")
        
        if legacy_count == 0:
            print("No legacy sessions to revoke")
            return
        
        # Confirm deletion
        confirm = input(f"Revoke {legacy_count} legacy sessions? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled")
            return
        
        # Delete all sessions with session_token field (legacy sessions)
        result = await db.user_sessions.delete_many({
            "session_token": {"$exists": True}
        })
        
        print(f"✓ Revoked {result.deleted_count} legacy sessions")
        
        # Verify deletion
        remaining = await db.user_sessions.count_documents({
            "session_token": {"$exists": True}
        })
        print(f"✓ {remaining} legacy sessions remaining")
        
        # Count JWT sessions (sessions without session_token)
        jwt_count = await db.user_sessions.count_documents({
            "session_token": {"$exists": False}
        })
        print(f"✓ {jwt_count} JWT sessions preserved")
        
        # Log to audit
        try:
            audit_event = {
                "event_type": "LEGACY_SESSION_REVOCATION",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {
                    "revoked_count": result.deleted_count,
                    "jwt_count": jwt_count,
                    "method": "script_revocation"
                },
                "success": True
            }
            await db.audit_logs.insert_one(audit_event)
            print("✓ Audit event logged")
        except Exception as e:
            print(f"⚠ Failed to log audit event: {e}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    finally:
        client.close()
        print("✓ Connection closed")


async def legacy_session_stats():
    """Show statistics about legacy vs JWT sessions."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "multi_business_db")
    
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    
    try:
        # Count legacy sessions
        legacy_count = await db.user_sessions.count_documents({
            "session_token": {"$exists": True}
        })
        
        # Count JWT sessions
        jwt_count = await db.user_sessions.count_documents({
            "session_token": {"$exists": False}
        })
        
        # Total sessions
        total_count = legacy_count + jwt_count
        
        print("\n=== Session Statistics ===")
        print(f"Total sessions: {total_count}")
        print(f"Legacy sessions: {legacy_count} ({legacy_count/total_count*100:.1f}%)" if total_count > 0 else "Legacy sessions: 0")
        print(f"JWT sessions: {jwt_count} ({jwt_count/total_count*100:.1f}%)" if total_count > 0 else "JWT sessions: 0")
        print("========================\n")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Revoke legacy session tokens")
    parser.add_argument("--stats", action="store_true", help="Show session statistics only")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
    
    args = parser.parse_args()
    
    if args.stats:
        asyncio.run(legacy_session_stats())
    else:
        asyncio.run(revoke_legacy_sessions())
