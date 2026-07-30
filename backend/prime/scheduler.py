"""
Prime Subscription Scheduler

Handles scheduled tasks for Prime membership management:
- Renewal processing
- Grace period retries
- Expiry handling
- Renewal reminder emails
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from .renewals import run_renewal_job
from .service import expire_membership
from .access import sync_is_prime_shim

logger = logging.getLogger(__name__)


class PrimeScheduler:
    """Scheduler for Prime membership maintenance tasks."""

    def __init__(self, db):
        self.db = db
        self.is_running = False
        self.tasks = []

    async def start(self):
        """Start the scheduler background tasks."""
        if self.is_running:
            logger.warning("Prime scheduler is already running")
            return

        self.is_running = True
        logger.info("Starting Prime scheduler")

        # Start background tasks
        self.tasks = [
            asyncio.create_task(self._renewal_task()),
            asyncio.create_task(self._expiry_task()),
            asyncio.create_task(self._reminder_task()),
        ]

    async def stop(self):
        """Stop the scheduler background tasks."""
        if not self.is_running:
            return

        self.is_running = False
        logger.info("Stopping Prime scheduler")

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []

    async def _renewal_task(self):
        """Run renewal job every 15 minutes."""
        while self.is_running:
            try:
                logger.info("Running renewal task")
                results = await run_renewal_job(self.db)
                logger.info(f"Renewal task completed: {results}")
            except Exception as e:
                logger.error(f"Renewal task failed: {e}")

            # Wait 15 minutes
            for _ in range(15 * 60):
                if not self.is_running:
                    return
                await asyncio.sleep(1)

    async def _expiry_task(self):
        """Run expiry task every hour."""
        while self.is_running:
            try:
                logger.info("Running expiry task")
                await self._process_expirations()
                logger.info("Expiry task completed")
            except Exception as e:
                logger.error(f"Expiry task failed: {e}")

            # Wait 1 hour
            for _ in range(60 * 60):
                if not self.is_running:
                    return
                await asyncio.sleep(1)

    async def _reminder_task(self):
        """Run reminder task daily."""
        while self.is_running:
            try:
                logger.info("Running reminder task")
                await self._send_renewal_reminders()
                logger.info("Reminder task completed")
            except Exception as e:
                logger.error(f"Reminder task failed: {e}")

            # Wait 24 hours
            for _ in range(24 * 60 * 60):
                if not self.is_running:
                    return
                await asyncio.sleep(1)

    async def _process_expirations(self):
        """Process expired memberships."""
        now = datetime.now(timezone.utc)

        # Find expired memberships that are not in grace period
        cursor = self.db.prime_memberships.find({
            "status": "active",
            "expires_at": {"$lt": now},
            "auto_renew": False,  # Only expire non-auto-renew
        })

        expired = await cursor.to_list(length=None)
        logger.info(f"Found {len(expired)} expired memberships to process")

        for membership in expired:
            try:
                await expire_membership(
                    self.db,
                    membership["user_id"],
                    membership["business_id"]
                )
                logger.info(f"Expired membership {membership['membership_id']}")
            except Exception as e:
                logger.error(f"Error expiring membership {membership['membership_id']}: {e}")

    async def _send_renewal_reminders(self):
        """Send renewal reminder emails."""
        now = datetime.now(timezone.utc)
        reminder_window = now + timedelta(days=7)

        # Find memberships expiring in 7 days with auto_renew enabled
        cursor = self.db.prime_memberships.find({
            "status": "active",
            "auto_renew": True,
            "expires_at": {
                "$gte": now,
                "$lte": reminder_window,
            }
        })

        memberships = await cursor.to_list(length=None)
        logger.info(f"Found {len(memberships)} memberships for renewal reminders")

        # TODO: Implement email sending
        # For now, just log that reminders would be sent
        for membership in memberships:
            logger.info(f"Would send renewal reminder for {membership['membership_id']}")
            # In production:
            # await send_renewal_reminder_email(membership)


# Global scheduler instance
_scheduler = None


def get_scheduler(db):
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = PrimeScheduler(db)
    return _scheduler


async def start_scheduler(db):
    """Start the Prime scheduler."""
    scheduler = get_scheduler(db)
    await scheduler.start()


async def stop_scheduler():
    """Stop the Prime scheduler."""
    global _scheduler
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None
