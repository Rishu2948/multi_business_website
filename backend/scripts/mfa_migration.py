#!/usr/bin/env python3
"""
MFA Migration Script

Helps migrate existing privileged users to MFA enforcement.
Provides status checking, enrollment reminders, and migration tracking.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, List


async def get_privileged_users(db) -> List[Dict]:
    """Get all privileged users (super_admin, business_admin, staff)."""
    users = await db.users.find(
        {"role": {"$in": ["super_admin", "business_admin", "staff"]}},
        {"_id": 0, "user_id": 1, "email": 1, "role": 1, "mfa": 1}
    ).to_list(length=None)
    return users


async def get_mfa_enrollment_status(db, user_id: str) -> Dict:
    """Get MFA enrollment status for a user."""
    user = await db.users.find_one(
        {"user_id": user_id},
        {"_id": 0, "mfa": 1}
    )
    
    if not user:
        return {"enrolled": False, "exists": False}
    
    mfa_data = user.get("mfa", {})
    
    # Count remaining backup codes
    backup_codes_hashed = mfa_data.get("backup_codes_hashed", [])
    used_backup_codes = mfa_data.get("used_backup_codes", [])
    remaining = len([c for c in backup_codes_hashed if c not in used_backup_codes])
    
    return {
        "enrolled": mfa_data.get("enabled", False),
        "exists": True,
        "method": mfa_data.get("method"),
        "enrolled_at": mfa_data.get("enrolled_at"),
        "last_verified_at": mfa.get("last_verified_at"),
        "remaining_backup_codes": remaining,
        "total_backup_codes": len(backup_codes_hashed)
    }


async def generate_migration_report(db) -> Dict:
    """Generate migration report for all privileged users."""
    privileged_users = await get_privileged_users(db)
    
    total = len(privileged_users)
    enrolled = 0
    not_enrolled = 0
    by_role = {
        "super_admin": {"total": 0, "enrolled": 0, "not_enrolled": 0},
        "business_admin": {"total": 0, "enrolled": 0, "not_enrolled": 0},
        "staff": {"total": 0, "enrolled": 0, "not_enrolled": 0}
    }
    
    for user in privileged_users:
        role = user.get("role")
        status = await get_mfa_enrollment_status(db, user["user_id"])
        
        by_role[role]["total"] += 1
        
        if status["enrolled"]:
            enrolled += 1
            by_role[role]["enrolled"] += 1
        else:
            not_enrolled += 1
            by_role[role]["not_enrolled"] += 1
    
    return {
        "total_privileged_users": total,
        "total_enrolled": enrolled,
        "total_not_enrolled": not_enrolled,
        "enrollment_rate": (enrolled / total * 100) if total > 0 else 0,
        "by_role": by_role
    }


async def send_enrollment_reminder(db, user_id: str, email: str):
    """
    Send enrollment reminder to user (placeholder - would integrate with email service).
    
    In production, this would send an email reminder.
    For now, this just logs the reminder.
    """
    print(f"TODO: Send MFA enrollment reminder to {email} (user_id: {user_id})")
    print(f"      Reminder: MFA is required for your role ({user_id} has privileged access)")


async def main():
    """Main migration script entry point."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "multi_business_db")
    
    print("=" * 60)
    print("MFA Migration Assistant")
    print("=" * 60)
    print(f"MongoDB: {mongo_url}")
    print(f"Database: {db_name}")
    print()
    
    client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    
    try:
        # Verify connection
        await db.command('ping')
        print("✓ Connected to MongoDB")
        print()
        
        # Generate migration report
        print("Generating migration report...")
        report = await generate_migration_report(db)
        
        print()
        print("=" * 60)
        print("MFA Enrollment Status Report")
        print("=" * 60)
        print(f"Total privileged users: {report['total_privileged_users']}")
        print(f"Enrolled in MFA: {report['total_enrolled']} ({report['enrollment_rate']:.1f}%)")
        print(f"Not enrolled: {report['total_not_enrolled']}")
        print()
        
        print("By Role:")
        for role, stats in report['by_role'].items():
            print(f"  {role}:")
            print(f"    Total: {stats['total']}")
            print(f"    Enrolled: {stats['enrolled']} ({stats['enrolled']/stats['total']*100 if stats['total'] > 0 else 0:.1f}%)")
            print(f"    Not enrolled: {stats['not_enrolled']}")
        print()
        
        # List users not enrolled
        if report['total_not_enrolled'] > 0:
            print("Users not enrolled in MFA:")
            privileged_users = await get_privileged_users(db)
            
            for user in privileged_users:
                status = await get_mfa_enrollment_status(db, user["user_id"])
                if not status["enrolled"]:
                    print(f"  - {user['email']} ({user['role']})")
            print()
        
        print("=" * 60)
        print("Migration Actions")
        print("=" * 60)
        print("1. Review the report above")
        print("2. Set MFA_ENFORCE_FOR_ADMINS=true in environment")
        print("3. Users will be prompted to enroll on next login")
        print("4. Monitor enrollment progress with this script")
        print()
        print("Commands:")
        print("  python mfa_migration.py --report     # Show enrollment status")
        print("  python mfa_migration.py --remind      # Send reminders (not implemented)")
        print("  python mfa_migration.py --enroll     # Force enrollment (admin only)")
        print()
        
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MFA migration assistant")
    parser.add_argument("--report", action="store_true", help="Show enrollment status report")
    parser.add_argument("--remind", action="store_true", help="Send enrollment reminders")
    parser.add_argument("--enroll", action="store_true", help="Force enrollment (admin only)")
    
    args = parser.parse_args()
    
    if args.report:
        asyncio.run(main())
    elif args.remind:
        print("Reminder functionality not yet implemented")
    elif args.enroll:
        print("Force enrollment not yet implemented")
    else:
        asyncio.run(main())
