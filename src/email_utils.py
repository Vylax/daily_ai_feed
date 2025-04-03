import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
# from sendgrid import SendGridAPIClient # Uncomment if using SendGrid
# from sendgrid.helpers.mail import Mail # Uncomment if using SendGrid

logger = logging.getLogger(__name__)

def send_email_smtp(subject, html_body, config):
    """Sends an email using SMTP, assuming html_body is already HTML."""
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

    # We still need a plain text part for email clients that don't support HTML.
    # Create a basic plain text version (e.g., stripping tags or a simple message).
    # For now, a simple message is sufficient. A more robust solution could strip HTML tags.
    plain_text_fallback = "Please view this email in an HTML-compatible client to see the full digest."
    text_part = MIMEText(plain_text_fallback, "plain")
    message.attach(text_part)

    # Attach the HTML part directly
    # The html_body argument is now assumed to be the full HTML document string
    html_part = MIMEText(html_body, "html")
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

def send_email_sendgrid(subject, html_body, config):
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
    #         html_content=html_body)
    #
    #     sg = SendGridAPIClient(sendgrid_api_key)
    #     response = sg.send(message)
    logger.warning("SendGrid provider selected but send_email_sendgrid function is commented out.")
    logger.warning("Install sendgrid library (`pip install sendgrid`) and uncomment the code if needed.")
    return False # Functionality disabled by default

def send_email(subject, html_body, config):
    """Sends the email using the configured provider."""
    provider = config.get('email_provider', 'smtp').lower()
    logger.info(f"Attempting to send email via {provider}...")

    if provider == 'smtp':
        return send_email_smtp(subject, html_body, config)
    elif provider == 'sendgrid':
        return send_email_sendgrid(subject, html_body, config)
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

    # Basic HTML example
    test_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Digest</title>
        <style>
            body { font-family: sans-serif; }
            h1 { color: blue; }
        </style>
    </head>
    <body>
        <h1>Test Digest</h1>
        <p>This is a <em>test</em> email body.</p>
        <ul><li>Item 1</li><li>Item 2</li></ul>
        <pre><code>print("Hello")</code></pre>
    </body>
    </html>
    """

    subject_prefix = test_config.get('email_subject_prefix', '[Test Digest]')
    test_subject = f"{subject_prefix} Test HTML Email {datetime.date.today()}"

    print(f"Attempting to send test HTML email to {test_config.get('recipient_email')}...")
    # Ensure you have configured .env with valid credentials before running this
    if not test_config.get('recipient_email') or not test_config.get('sender_email'):
         print("SKIPPING TEST: Recipient or Sender email not found in config (.env)")
    elif test_config.get('email_provider') == 'smtp' and not test_config.get('smtp_password'):
         print("SKIPPING TEST: SMTP provider chosen, but SMTP password not found in config (.env)")
    # Add similar check for SendGrid API key if testing SendGrid
    # elif test_config.get('email_provider') == 'sendgrid' and not test_config.get('sendgrid_api_key'):
    #      print("SKIPPING TEST: SendGrid provider chosen, but SendGrid API key not found in config (.env)")
    else:
        success = send_email(test_subject, test_html, test_config)
        if success:
            print("Test email sent successfully (check recipient inbox).")
        else:
            print("Test email sending failed. Check logs and .env configuration.") 