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
    # Get username, default to sender_email if not provided
    smtp_username = config.get('smtp_username', sender_email)
    password = config.get('smtp_password')
    smtp_server = config.get('smtp_server')
    smtp_port = config.get('smtp_port')

    print(f"SMTP_SERVER: {smtp_server}")
    print(f"SMTP_PORT: {smtp_port}")
    print(f"SMTP_USERNAME: {smtp_username}")
    print(f"SMTP_PASSWORD: {'******' if password else 'MISSING'}")
    print(f"SENDER_EMAIL: {sender_email}")
    print(f"RECIPIENT_EMAIL: {receiver_email}")
    
    # Log all config keys for debugging (without sensitive values)
    logger.debug("Full email config keys: %s", ', '.join(config.keys()))

    # Check configuration completeness
    missing_config = []
    if not sender_email: missing_config.append("sender_email")
    if not receiver_email: missing_config.append("recipient_email")
    if not password: missing_config.append("smtp_password")
    if not smtp_server: missing_config.append("smtp_server")
    if not smtp_port: missing_config.append("smtp_port")
    
    if missing_config:
        logger.error(f"SMTP configuration is incomplete. Missing: {', '.join(missing_config)}")
        return False

    if not all([sender_email, receiver_email, password, smtp_server, smtp_port]):
        logger.error("SMTP configuration is incomplete (missing sender, recipient, password, server, or port). Cannot send email.")
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

    # Authentication methods to try in order
    auth_methods = ['', 'PLAIN', 'LOGIN', 'CRAM-MD5']  # '' means let the server choose
    
    # Initialize variables for tracking auth attempts
    auth_errors = []
    last_exception = None
    
    try:
        logger.info(f"SMTP ATTEMPT: Connecting to {smtp_server}:{smtp_port}")
        
        # Create SSL context
        context = ssl.create_default_context()
        logger.info(f"SSL Context created for SMTP connection")
        
        # Note whether we're using explicit or implicit SSL
        use_ssl = smtp_port == 465
        logger.info(f"Using {'SSL (implicit)' if use_ssl else 'STARTTLS (explicit)'} for connection")
        
        # Set up the SMTP connection based on port
        if use_ssl:
            logger.info(f"Creating SMTP_SSL connection to {smtp_server}:{smtp_port}")
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context)
        else:
            logger.info(f"Creating SMTP connection to {smtp_server}:{smtp_port}")
            server = smtplib.SMTP(smtp_server, smtp_port)
            logger.info("SMTP connection established, attempting STARTTLS")
            # Enable debug output on the SMTP connection if needed
            # server.set_debuglevel(1)
            server.starttls()
            logger.info("STARTTLS completed successfully")
        
        # Try each authentication method until one works
        try:
            for auth_method in auth_methods:
                try:
                    if auth_method == '':
                        logger.info(f"Attempting login with username: {smtp_username} (server's preferred method)")
                        server.login(smtp_username, password)
                    elif auth_method == 'PLAIN':
                        logger.info(f"Attempting login with username: {smtp_username} (method: PLAIN)")
                        # For PLAIN, we could do the specific encoding ourselves, but for simplicity,
                        # let's try the normal login which will often select PLAIN automatically
                        server.login(smtp_username, password) 
                    elif auth_method == 'LOGIN':
                        logger.info(f"Attempting login with username: {smtp_username} (method: LOGIN)")
                        # Similar to PLAIN, we'll use the standard login which usually works for LOGIN
                        server.login(smtp_username, password)
                    elif auth_method == 'CRAM-MD5':
                        logger.info(f"Attempting login with username: {smtp_username} (method: CRAM-MD5)")
                        # Standard login often selects CRAM-MD5 if available
                        server.login(smtp_username, password)
                    else:
                        # Fallback
                        logger.info(f"Attempting login with username: {smtp_username} (method: {auth_method})")
                        server.login(smtp_username, password)
                    
                    logger.info(f"Login successful for {smtp_username}")
                    break  # Success! Break out of the auth method loop
                except smtplib.SMTPAuthenticationError as e:
                    auth_error = f"Auth method {auth_method or 'default'} failed: {e}"
                    logger.warning(auth_error)
                    auth_errors.append(auth_error)
                    last_exception = e
                    continue  # Try the next auth method
                except Exception as e:
                    auth_error = f"Unexpected error with auth method {auth_method or 'default'}: {e}"
                    logger.warning(auth_error)
                    auth_errors.append(auth_error)
                    last_exception = e
                    continue  # Try the next auth method
            else:
                # We only get here if all auth methods failed (didn't break out of loop)
                auth_errors_str = "; ".join(auth_errors)
                logger.error(f"All authentication methods failed: {auth_errors_str}")
                if last_exception:
                    raise last_exception
                else:
                    raise smtplib.SMTPAuthenticationError(535, b"All authentication methods failed")
            
            # Send the email
            logger.info(f"Sending email from '{smtp_username}' to '{receiver_email}'")
            server.sendmail(smtp_username, receiver_email, message.as_string())
            logger.info(f"Email sent successfully to {receiver_email}")
            
            return True
        finally:
            # Always close the connection
            try:
                server.quit()
                logger.info("SMTP connection closed")
            except Exception as e:
                logger.warning(f"Error closing SMTP connection: {e}")
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP Authentication failed for {smtp_username}. Error: {str(e)}")
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