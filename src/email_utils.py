import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import markdown # Required to convert markdown to HTML
# from sendgrid import SendGridAPIClient # Uncomment if using SendGrid
# from sendgrid.helpers.mail import Mail # Uncomment if using SendGrid

logger = logging.getLogger(__name__)

def send_email_smtp(subject, markdown_body, config):
    """Sends an email using SMTP."""
    sender_email = config.get('sender_email')
    receiver_email = config.get('recipient_email')
    password = config.get('smtp_password')
    smtp_server = config.get('smtp_server')
    smtp_port = config.get('smtp_port')

    if not all([sender_email, receiver_email, password, smtp_server, smtp_port]):
        logger.error("SMTP configuration is incomplete. Cannot send email.")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = receiver_email

    # Convert Markdown to HTML
    try:
        html_body = markdown.markdown(markdown_body, extensions=['extra', 'sane_lists'])
        # Basic styling for readability
        html_content = f"""
        <html>
        <head>
        <style>
          body {{ font-family: sans-serif; line-height: 1.6; padding: 20px; }}
          h1, h2, h3 {{ color: #333; }}
          h1 {{ border-bottom: 2px solid #eee; padding-bottom: 10px; }}
          h2 {{ border-bottom: 1px solid #eee; padding-bottom: 5px; }}
          code {{ background-color: #f4f4f4; padding: 2px 4px; border-radius: 4px; font-family: monospace; }}
          pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 4px; overflow-x: auto; }}
          pre code {{ background-color: transparent; padding: 0; }}
          a {{ color: #007bff; text-decoration: none; }}
          a:hover {{ text-decoration: underline; }}
          img {{ max-width: 100%; height: auto; vertical-align: middle; }}
          hr {{ border: none; border-top: 1px solid #eee; margin: 20px 0; }}
          ul, ol {{ padding-left: 20px; }}
        </style>
        </head>
        <body>
        {html_body}
        </body>
        </html>
        """
    except Exception as e:
        logger.error(f"Failed to convert Markdown to HTML: {e}")
        # Fallback to plain text if markdown conversion fails
        text_part = MIMEText(markdown_body, "plain")
        message.attach(text_part)
        html_content = None # Indicate no HTML available

    # Attach both plain text (optional fallback) and HTML parts
    # Some email clients prefer HTML, others might only show plain text
    text_part = MIMEText(markdown_body, "plain")
    message.attach(text_part)

    if html_content:
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) if smtp_port == 465 else smtplib.SMTP(smtp_server, smtp_port) as server:
            if smtp_port != 465: # Use STARTTLS for port 587
                server.starttls(context=context)
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        logger.info(f"Email sent successfully to {receiver_email} via SMTP.")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error(f"SMTP Authentication failed for {sender_email}. Check username/password/app password.")
        return False
    except Exception as e:
        logger.error(f"Failed to send email via SMTP: {e}", exc_info=True)
        return False

def send_email_sendgrid(subject, markdown_body, config):
    """Sends an email using SendGrid."""
    # sendgrid_api_key = config.get('sendgrid_api_key')
    # sender_email = config.get('sender_email')
    # receiver_email = config.get('recipient_email')
    #
    # if not all([sendgrid_api_key, sender_email, receiver_email]):
    #     logger.error("SendGrid configuration is incomplete. Cannot send email.")
    #     return False
    #
    # try:
    #     html_content = markdown.markdown(markdown_body, extensions=['extra', 'sane_lists'])
    #     message = Mail(
    #         from_email=sender_email,
    #         to_emails=receiver_email,
    #         subject=subject,
    #         html_content=html_content)
    #
    #     sg = SendGridAPIClient(sendgrid_api_key)
    #     response = sg.send(message)
    #     logger.info(f"Email sent successfully to {receiver_email} via SendGrid. Status code: {response.status_code}")
    #     return True
    # except Exception as e:
    #     logger.error(f"Failed to send email via SendGrid: {e}", exc_info=True)
    #     return False
    logger.warning("SendGrid provider selected but send_email_sendgrid function is commented out.")
    logger.warning("Install sendgrid library (`pip install sendgrid`) and uncomment the code if needed.")
    return False # Functionality disabled by default

def send_email(subject, markdown_body, config):
    """Sends the email using the configured provider."""
    provider = config.get('email_provider', 'smtp').lower()
    logger.info(f"Attempting to send email via {provider}...")

    if provider == 'smtp':
        return send_email_smtp(subject, markdown_body, config)
    elif provider == 'sendgrid':
        return send_email_sendgrid(subject, markdown_body, config)
    else:
        logger.error(f"Unsupported email provider specified: {provider}")
        return False

# --- Example Usage (for testing) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Dummy config (Load from .env in real use)
    # Requires a .env file with SMTP settings for this test to work
    from config_loader import load_config
    test_config = load_config()

    # Basic markdown example
    test_markdown = """
    # Test Digest

    This is a *test* email body.

    - Item 1
    - Item 2

    ```python
    print("Hello")
    ```
    """

    subject_prefix = test_config.get('email_subject_prefix', '[Test Digest]')
    test_subject = f"{subject_prefix} Test Email {datetime.date.today()}"

    print(f"Attempting to send test email to {test_config.get('recipient_email')}...")
    # Ensure you have configured .env with valid credentials before running this
    if not test_config.get('recipient_email') or not test_config.get('sender_email'):
         print("SKIPPING TEST: Recipient or Sender email not found in config (.env)")
    elif test_config.get('email_provider') == 'smtp' and not test_config.get('smtp_password'):
         print("SKIPPING TEST: SMTP provider chosen, but SMTP password not found in config (.env)")
    # Add similar check for SendGrid API key if testing SendGrid
    # elif test_config.get('email_provider') == 'sendgrid' and not test_config.get('sendgrid_api_key'):
    #      print("SKIPPING TEST: SendGrid provider chosen, but SendGrid API key not found in config (.env)")
    else:
        success = send_email(test_subject, test_markdown, test_config)
        if success:
            print("Test email sent successfully (check recipient inbox).")
        else:
            print("Test email sending failed. Check logs and .env configuration.") 