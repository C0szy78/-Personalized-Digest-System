
#!/usr/bin/env python3
"""
Standalone script for running digest automation.

This script can be run independently via cron or system scheduler.
It reads configuration from the database and processes WordPress posts,
generates digests, and sends emails.

Usage:
    python run_digest_automation.py [--once] [--process-queue-only]
    
Options:
    --once              Run once and exit (for cron jobs)
    --process-queue-only Only process the email queue, skip digest generation
    
Examples:
    # Run as a daemon (keeps running, uses APScheduler)
    python run_digest_automation.py
    
    # Run once (for cron jobs)
    python run_digest_automation.py --once
    
    # Only send queued emails
    python run_digest_automation.py --once --process-queue-only
    
Cron Example (run daily at 9 AM):
    0 9 * * * cd /path/to/tag_ai && python run_digest_automation.py --once >> logs/digest.log 2>&1
"""

import sys
import os
import argparse
import time
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from database import init_db, get_db, SchedulerConfig
from scheduler_service import DigestScheduler
from email_queue_processor import EmailQueueProcessor
from logger_utils import log


def run_once():
    """Run digest generation and email processing once, then exit."""
    log.header("Digest Automation - Single Run")
    
    # Initialize database
    init_db()
    
    # Create scheduler and run
    scheduler = DigestScheduler()
    scheduler.run_scheduled_digest()

    log.success("Single run completed\n")


def process_queue_only():
    """Process email queue only, without generating new digests."""
    log.header("Email Queue Processor - Single Run")
    
    # Initialize database
    init_db()
    
    # Process queue
    processor = EmailQueueProcessor()
    stats = processor.process_queue()

    log.section("Email Processing Stats")
    log.info(f"Processed: {stats['processed']}", indent=1)
    log.info(f"Sent:      {stats['sent']}", indent=1)
    log.info(f"Failed:    {stats['failed']}", indent=1)
    log.info(f"Skipped:   {stats['skipped']}", indent=1)

    if stats['errors']:
        log.warning(f"Errors encountered: {len(stats['errors'])}")
        for error in stats['errors'][:5]:  # Show first 5 errors
            log.error(f"{error['email']}: {error['error']}", indent=1)

    log.success("Queue processing completed\n")


def run_daemon():
    """Run as a daemon using APScheduler."""
    log.header("Digest Automation - Daemon Mode")
    
    # Initialize database
    init_db()
    
    # Check if scheduler is enabled
    db = get_db()
    try:
        config = db.query(SchedulerConfig).first()
        if not config:
            log.warning("No scheduler configuration found. Creating default config...")
            config = SchedulerConfig()
            db.add(config)
            db.commit()

        if not config.enabled:
            log.warning("Scheduler is disabled in database. Enable it via the admin UI.")
            log.info("Exiting...")
            return

        log.info(f"Schedule: {config.schedule_time} on days {config.schedule_days}")
        if config.wordpress_url:
            log.info(f"WordPress URL: {config.wordpress_url}")
        log.info(f"Send emails immediately: {'Yes' if config.send_immediately else 'No'}")
        
    finally:
        db.close()
    
    # Start scheduler
    scheduler = DigestScheduler()
    scheduler.start()

    log.success("Scheduler is running. Press Ctrl+C to stop.\n")

    try:
        # Keep the script running
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        log.info("\nShutting down scheduler...")
        scheduler.stop()
        log.success("Scheduler stopped. Goodbye!\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Automated digest generation and email delivery',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit (for cron jobs)'
    )
    parser.add_argument(
        '--process-queue-only',
        action='store_true',
        help='Only process email queue, skip digest generation'
    )
    
    args = parser.parse_args()
    
    try:
        if args.process_queue_only:
            process_queue_only()
        elif args.once:
            run_once()
        else:
            run_daemon()
    except Exception as e:
        log.error(f"Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()