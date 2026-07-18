"""Email queue processor for batch sending digest emails."""
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from database import EmailQueue, Digest, Member, get_db
from email_service import EmailService
from logger_utils import log


class EmailQueueProcessor:
    """Process email queue in batches to avoid timeouts."""
    
    def __init__(self, batch_size: int = 10, delay_between_emails: float = 0.5):
        """
        Initialize email queue processor.
        
        Args:
            batch_size: Number of emails to process per batch
            delay_between_emails: Delay in seconds between each email to avoid rate limits
        """
        self.batch_size = batch_size
        self.delay_between_emails = delay_between_emails
        self.email_service = EmailService()
        
    def process_queue(self, max_emails: Optional[int] = None) -> dict:
        """
        Process pending emails in the queue.

        Args:
            max_emails: Maximum number of emails to process (None = process all)

        Returns:
            Dictionary with processing statistics
        """
        db = get_db()
        stats = {
            'processed': 0,
            'sent': 0,
            'failed': 0,
            'skipped': 0,
            'errors': []
        }

        try:
            # Get pending emails, ordered by priority (lower number = higher priority) and scheduled time
            query = db.query(EmailQueue).filter(
                EmailQueue.status.in_(['pending', 'retry']),
                EmailQueue.attempts < EmailQueue.max_attempts
            ).order_by(
                EmailQueue.priority.asc(),
                EmailQueue.scheduled_at.asc()
            )

            if max_emails:
                query = query.limit(max_emails)

            pending_emails = query.all()

            log.section("Email Queue Processor")
            log.info(f"Found {len(pending_emails)} emails to process", indent=1)

            for email_item in pending_emails:
                stats['processed'] += 1

                try:
                    # Send the email
                    success, error_msg = self.email_service.send_email(
                        to_email=email_item.recipient_email,
                        subject=email_item.subject,
                        html_body=email_item.html_body,
                        to_name=None
                    )

                    # Update email status
                    email_item.attempts += 1

                    if success:
                        email_item.status = 'sent'
                        email_item.sent_at = datetime.now(timezone.utc)
                        stats['sent'] += 1
                        log.success(f"Sent email to {email_item.recipient_email}", indent=1)
                    else:
                        # Check if we should retry
                        if email_item.attempts >= email_item.max_attempts:
                            email_item.status = 'failed'
                            stats['failed'] += 1
                            log.error(f"Failed to send to {email_item.recipient_email} (max attempts)", indent=1)
                        else:
                            email_item.status = 'retry'
                            stats['failed'] += 1
                            log.warning(f"Failed to send to {email_item.recipient_email}, will retry", indent=1)

                        email_item.error_message = error_msg
                        stats['errors'].append({
                            'email': email_item.recipient_email,
                            'error': error_msg
                        })

                    db.commit()

                    # Delay between emails to avoid rate limits
                    if stats['processed'] < len(pending_emails):
                        time.sleep(self.delay_between_emails)

                except Exception as e:
                    # Rollback the transaction on error
                    db.rollback()

                    error_msg = f"Exception processing email {email_item.id}: {str(e)}"
                    log.error(error_msg, indent=1)

                    try:
                        # Re-fetch the email item after rollback
                        email_item = db.query(EmailQueue).filter_by(id=email_item.id).first()
                        if email_item:
                            email_item.attempts += 1
                            email_item.status = 'failed' if email_item.attempts >= email_item.max_attempts else 'retry'
                            email_item.error_message = error_msg
                            db.commit()
                    except Exception as rollback_error:
                        log.error(f"Error during rollback recovery: {str(rollback_error)}", indent=1)
                        db.rollback()

                    stats['errors'].append({
                        'email': email_item.recipient_email,
                        'error': error_msg
                    })
                    stats['failed'] += 1

        except Exception as e:
            log.error(f"Critical error in process_queue: {str(e)}")
            db.rollback()
        finally:
            db.close()

        log.info(f"Processing complete: {stats['processed']} total, {stats['sent']} sent, {stats['failed']} failed\n")

        return stats
    
    def queue_digest_email(
        self,
        db: Session,
        digest: Digest,
        priority: int = 5,
        base_url: str = "http://localhost:8501"
    ) -> EmailQueue:
        """
        Add a digest email to the queue.
        
        Args:
            db: Database session
            digest: Digest object to send
            priority: Email priority (1-10, lower = higher priority)
            base_url: Base URL for email links
            
        Returns:
            EmailQueue object
        """
        member = digest.member
        member_interests = [i.name for i in member.interests]
        
        # Prepare digest data for email
        digest_data = {
            'title': digest.document.title,
            'summary': digest.summary,
            'relevance_score': digest.relevance_score or 0,
            'date': digest.created_at.strftime('%B %d, %Y'),
            'view_url': f"{base_url}/?page=view_digests"
        }
        
        # Create email HTML
        subject, html_body = self.email_service.create_digest_email(
            member_name=member.name,
            member_email=member.email,
            member_interests=member_interests,
            digests=[digest_data],
            base_url=base_url
        )
        
        # Create queue entry
        email_queue = EmailQueue(
            digest_id=digest.id,
            member_id=member.id,
            recipient_email=member.email,
            subject=subject,
            html_body=html_body,
            status='pending',
            priority=priority
        )
        
        db.add(email_queue)
        return email_queue