"""Email service for sending digest emails with branded templates."""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Optional
from jinja2 import Template
from dotenv import load_dotenv

load_dotenv()


class EmailService:
    """Service for sending branded digest emails."""
    
    def __init__(self):
        """Initialize email service with SMTP configuration."""
        # SMTP Configuration from environment variables
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.from_email = os.getenv('FROM_EMAIL', self.smtp_username)
        self.from_name = os.getenv('FROM_NAME', 'Personalized Digest System')
        
        # Brand configuration
        self.brand_name = os.getenv('BRAND_NAME', 'Personalized Digest')
        self.brand_color = os.getenv('BRAND_COLOR', '#4F46E5')
        self.logo_url = os.getenv('LOGO_URL', '')
        self.support_email = os.getenv('SUPPORT_EMAIL', self.from_email)
        
    def get_email_template(self) -> str:
        """Get the branded HTML email template."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ brand_name }} - Your Personalized Digest</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 20px 0;">
        <tr>
            <td align="center">
                <!-- Main Container -->
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, {{ brand_color }} 0%, {{ brand_color }}dd 100%); padding: 40px 30px; text-align: center;">
                            {% if logo_url %}
                            <img src="{{ logo_url }}" alt="{{ brand_name }}" style="max-width: 150px; height: auto; margin-bottom: 15px;">
                            {% endif %}
                            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700;">{{ brand_name }}</h1>
                            <p style="color: #ffffff; margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">Your Personalized Content Digest</p>
                        </td>
                    </tr>
                    
                    <!-- Greeting -->
                    <tr>
                        <td style="padding: 30px;">
                            <h2 style="color: #1f2937; margin: 0 0 15px 0; font-size: 22px;">Hi {{ member_name }},</h2>
                            <p style="color: #4b5563; margin: 0 0 20px 0; font-size: 16px; line-height: 1.6;">
                                Here's your personalized digest based on your interests: <strong>{{ member_interests }}</strong>
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Digest Content -->
                    {% for digest in digests %}
                    <tr>
                        <td style="padding: 0 30px 30px 30px;">
                            <div style="background-color: #f9fafb; border-left: 4px solid {{ brand_color }}; padding: 20px; border-radius: 4px; margin-bottom: 20px;">
                                <h3 style="color: {{ brand_color }}; margin: 0 0 10px 0; font-size: 20px;">
                                    📰 {{ digest.title }}
                                </h3>
                                <p style="color: #6b7280; margin: 0 0 10px 0; font-size: 14px;">
                                    {{ digest.date }} | Relevance: {{ digest.relevance_score }}/100
                                </p>
                                <div style="color: #374151; font-size: 15px; line-height: 1.7; margin-bottom: 15px;">
                                    {{ digest.summary }}
                                </div>
                                <p style="margin: 0;">
                                    <a href="{{ digest.view_url }}" style="display: inline-block; background-color: {{ brand_color }}; color: #ffffff; padding: 10px 20px; text-decoration: none; border-radius: 4px; font-weight: 600; font-size: 14px;">
                                        Read Full Article
                                    </a>
                                </p>
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                    
                    <!-- Footer CTA -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 25px 30px; text-align: center; border-top: 1px solid #e5e7eb;">
                            <p style="color: #6b7280; margin: 0 0 15px 0; font-size: 14px;">
                                Want to update your interests or manage your preferences?
                            </p>
                            <a href="{{ manage_interests_url }}" style="display: inline-block; background-color: #ffffff; color: {{ brand_color }}; padding: 10px 25px; text-decoration: none; border-radius: 4px; font-weight: 600; border: 2px solid {{ brand_color }}; font-size: 14px;">
                                Manage Interests
                            </a>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #1f2937; padding: 30px; text-align: center; color: #9ca3af; font-size: 13px; line-height: 1.6;">
                            <p style="margin: 0 0 10px 0;">
                                © {{ current_year }} {{ brand_name }}. All rights reserved.
                            </p>
                            <p style="margin: 0 0 10px 0;">
                                Questions? Contact us at <a href="mailto:{{ support_email }}" style="color: {{ brand_color }}; text-decoration: none;">{{ support_email }}</a>
                            </p>
                            <p style="margin: 0; font-size: 12px; color: #6b7280;">
                                You're receiving this because you subscribed to personalized digests.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
    
    def create_digest_email(
        self,
        member_name: str,
        member_email: str,
        member_interests: List[str],
        digests: List[Dict],
        base_url: str = "http://localhost:8501"
    ) -> tuple[str, str]:
        """
        Create branded HTML email for digest delivery.

        Args:
            member_name: Name of the member
            member_email: Email address
            member_interests: List of member's interest tags
            digests: List of digest dictionaries with title, summary, relevance_score, date
            base_url: Base URL for links

        Returns:
            Tuple of (subject, html_body)
        """
        template = Template(self.get_email_template())

        # Prepare digest data
        digest_count = len(digests)
        today = datetime.now().strftime('%B %d, %Y')

        # Render email
        html_body = template.render(
            brand_name=self.brand_name,
            brand_color=self.brand_color,
            logo_url=self.logo_url,
            member_name=member_name,
            member_interests=', '.join(member_interests),
            digests=digests,
            manage_interests_url=f"{base_url}/?page=manage",
            support_email=self.support_email,
            current_year=datetime.now().year
        )

        # Create subject line
        subject = f"📰 Your {self.brand_name} - {digest_count} New Article{'s' if digest_count != 1 else ''} | {today}"

        return subject, html_body

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        to_name: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Send an email via SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML email body
            to_name: Optional recipient name

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = f"{to_name} <{to_email}>" if to_name else to_email

            # Attach HTML body
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)

            # Send via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            return True, None

        except Exception as e:
            error_msg = f"Failed to send email to {to_email}: {str(e)}"
            print(error_msg)
            return False, error_msg

    def test_connection(self) -> tuple[bool, Optional[str]]:
        """Test SMTP connection."""
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
            return True, "SMTP connection successful!"
        except Exception as e:
            return False, f"SMTP connection failed: {str(e)}"