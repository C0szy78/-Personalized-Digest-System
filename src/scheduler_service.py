"""Scheduler service for automated digest generation and email delivery."""
import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database import (
    get_db, SchedulerConfig, Member, Interest, Document, Digest, EmailQueue
)
from llm_service import LLMService
from wordpress_fetcher import WordPressFetcher
from email_queue_processor import EmailQueueProcessor
from logger_utils import log


class DigestScheduler:
    """Manages scheduled digest generation and email delivery."""
    
    def __init__(self):
        """Initialize the digest scheduler."""
        self.scheduler = BackgroundScheduler()
        self.llm_service = LLMService()
        self.email_processor = EmailQueueProcessor()
        self.is_running = False
        
    def start(self):
        """Start the scheduler."""
        if not self.is_running:
            self._load_schedule()
            self.scheduler.start()
            self.is_running = True
            print("📅 Digest scheduler started")
    
    def stop(self):
        """Stop the scheduler."""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            print("📅 Digest scheduler stopped")
    
    def _load_schedule(self):
        """Load schedule configuration from database."""
        db = get_db()
        try:
            config = db.query(SchedulerConfig).first()
            
            if not config:
                # Create default config
                config = SchedulerConfig()
                db.add(config)
                db.commit()
            
            if config.enabled:
                self._update_schedule(config)
        finally:
            db.close()
    
    def _update_schedule(self, config: SchedulerConfig):
        """Update the scheduler with new configuration."""
        # Remove existing jobs
        self.scheduler.remove_all_jobs()
        
        # Parse schedule time
        hour, minute = map(int, config.schedule_time.split(':'))
        
        # Parse schedule days (0=Monday, 6=Sunday)
        days_of_week = config.schedule_days
        
        # Create cron trigger
        trigger = CronTrigger(
            day_of_week=days_of_week,
            hour=hour,
            minute=minute
        )
        
        # Add job
        self.scheduler.add_job(
            func=self.run_scheduled_digest,
            trigger=trigger,
            id='digest_generation',
            name='Automated Digest Generation',
            replace_existing=True
        )
        
        # Update next run time
        db = get_db()
        try:
            config.next_run = self.scheduler.get_job('digest_generation').next_run_time
            db.commit()
        finally:
            db.close()
        
        print(f"✅ Schedule updated: {config.schedule_time} on days {config.schedule_days}")
    
    def run_scheduled_digest(self):
        """Execute the scheduled digest generation and email sending."""
        log.header("Scheduled Digest Generation")
        
        db = get_db()
        try:
            config = db.query(SchedulerConfig).first()
            
            if not config or not config.enabled:
                log.warning("Scheduler is disabled, skipping run")
                return

            # Update last run time
            config.last_run = datetime.now(timezone.utc)
            log.info(f"Last run time: {config.last_run.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Fetch WordPress posts if configured
            if config.wordpress_url:
                log.section("Fetching WordPress Posts")
                log.info(f"WordPress URL: {config.wordpress_url}", indent=1)
                log.info(f"Fetching {config.posts_per_run} posts...", indent=1)

                # Initialize WordPress fetcher with URL
                wp_fetcher = WordPressFetcher(config.wordpress_url)
                posts = wp_fetcher.get_posts_with_content(per_page=config.posts_per_run)
                log.success(f"Fetched {len(posts)} posts", indent=1)
                
                # Process each post
                for post in posts:
                    self._process_post(db, post, config)
            else:
                log.warning("No WordPress URL configured, skipping post fetch")
            
            # Process email queue if send_immediately is enabled
            if config.send_immediately:
                log.section("Processing Email Queue")
                stats = self.email_processor.process_queue()
                log.success(f"Emails sent: {stats['sent']}, Failed: {stats['failed']}")

            db.commit()

            log.success("Scheduled digest generation completed\n")
            
        except Exception as e:
            log.error(f"Error in scheduled digest generation: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()
    
    def _process_post(self, db, post, config):
        """Process a single WordPress post."""
        try:
            # Check if post already exists
            existing = db.query(Document).filter_by(title=post['title']).first()
            if existing:
                log.info(f"Skipping duplicate: {post['title']}", indent=1)
                return

            content = post.get('scraped_content', '')
            if not content:
                log.warning(f"No content for post: {post['title']}", indent=1)
                return

            # Get available interest tags
            all_interests = db.query(Interest).all()
            available_tags = [i.name for i in all_interests]

            # LLM Task 1: Extract interest tags
            log.info(f"Processing: {post['title'][:60]}...", indent=1)
            log.debug("Extracting interest tags...", indent=2)
            extraction_result = self.llm_service.extract_interest_tags(content, available_tags)
            log.debug(f"Tags: {extraction_result.get('tags', [])}", indent=2)

            # Create document
            document = Document(
                title=post['title'],
                content=content,
                source_type='wordpress',
                extracted_tags=json.dumps(extraction_result)
            )
            db.add(document)
            db.flush()  # Get document ID

            # Generate digests for all members
            members = db.query(Member).all()
            document_tags = extraction_result.get('tags', [])
            log.debug(f"Generating digests for {len(members)} members...", indent=2)

            digests_created = 0
            for member in members:
                member_interest_names = [i.name for i in member.interests]

                # Calculate relevance score
                matching_tags = set(member_interest_names) & set(document_tags)
                relevance_score = len(matching_tags) * 10 + len(member_interest_names)

                # Generate personalized digest using LLM Task 2
                summary = self.llm_service.generate_personalized_digest(
                    content=document.content,
                    title=document.title,
                    member_interests=member_interest_names,
                    document_tags=document_tags
                )

                # Create digest
                digest = Digest(
                    member_id=member.id,
                    document_id=document.id,
                    summary=summary,
                    relevance_score=relevance_score,
                    status='published'  # Auto-publish scheduled digests
                )
                db.add(digest)
                db.flush()

                # Queue email if enabled
                if config.send_immediately:
                    self.email_processor.queue_digest_email(db, digest)

                digests_created += 1

            db.commit()
            log.success(f"Created {digests_created} digests for: {post['title'][:60]}...", indent=2)

        except Exception as e:
            log.error(f"Error processing post {post.get('title', 'Unknown')}: {str(e)}", indent=1)
            import traceback
            traceback.print_exc()

    def run_now(self):
        """Run digest generation immediately (for testing/manual trigger)."""
        self.run_scheduled_digest()