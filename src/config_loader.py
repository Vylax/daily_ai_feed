import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def load_config():
    """Loads configuration from .env file and returns it as a dictionary."""
    load_dotenv(override=True) # Force reload of environment variables from .env file

    config = {}

    # --- Gemini API ---
    config['gemini_api_key'] = os.getenv('GEMINI_API_KEY')
    config['google_application_credentials'] = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not config['gemini_api_key'] and not config['google_application_credentials']:
        logger.warning("Gemini API key or Google Application Credentials not found in .env")
        # Consider raising an error if the API key is strictly required upfront
        # raise ValueError("Gemini API Key or Google Application Credentials must be set in .env")

    # --- RSS Feeds ---
    rss_feeds_str = os.getenv('RSS_FEEDS', '')
    config['rss_feeds'] = [url.strip() for url in rss_feeds_str.split(',') if url.strip()]
    if not config['rss_feeds']:
        logger.warning("No RSS_FEEDS found in .env file.")
        config['rss_feeds'] = []

    # --- Processing Configuration ---
    try:
        config['num_news_items_to_summarize'] = int(os.getenv('NUM_NEWS_ITEMS_TO_SUMMARIZE', '7'))
    except ValueError:
        logger.warning("Invalid NUM_NEWS_ITEMS_TO_SUMMARIZE in .env, using default 7.")
        config['num_news_items_to_summarize'] = 7

    try:
        config['num_feed_tutorials_to_include'] = int(os.getenv('NUM_FEED_TUTORIALS_TO_INCLUDE', '5'))
    except ValueError:
        logger.warning("Invalid NUM_FEED_TUTORIALS_TO_INCLUDE in .env, using default 5.")
        config['num_feed_tutorials_to_include'] = 5

    tutorial_topics_str = os.getenv('INITIAL_TUTORIAL_TOPICS', '')
    config['initial_tutorial_topics'] = [topic.strip() for topic in tutorial_topics_str.split(',') if topic.strip()]
    if not config['initial_tutorial_topics']:
        logger.warning("No INITIAL_TUTORIAL_TOPICS found in .env. Tutorial generation might be limited.")
        config['initial_tutorial_topics'] = [] # Default to empty list

    # --- Email Configuration ---
    email_config = {
        'enabled': True,  # Default to enabled
        'email_provider': os.getenv('EMAIL_PROVIDER', 'smtp').lower().strip(),
        'recipient_email': os.getenv('RECIPIENT_EMAIL'),
        'sender_email': os.getenv('SENDER_EMAIL'),
        'email_subject_prefix': os.getenv('EMAIL_SUBJECT_PREFIX', '[AI Digest]')
    }

    if not email_config['recipient_email'] or not email_config['sender_email']:
        logger.warning("Recipient or Sender email not configured in .env. Email delivery will fail.")

    if email_config['email_provider'] == 'smtp':
        email_config['smtp_server'] = os.getenv('SMTP_SERVER')
        try:
            email_config['smtp_port'] = int(os.getenv('SMTP_PORT', 587))
        except (ValueError, TypeError):
            logger.warning("Invalid SMTP_PORT in .env, using default 587")
            email_config['smtp_port'] = 587
            
        email_config['smtp_username'] = os.getenv('SMTP_USERNAME', email_config.get('sender_email'))
        email_config['smtp_password'] = os.getenv('SMTP_PASSWORD')
        
        # Log the SMTP configuration for debugging (without revealing password)
        logger.debug(f"SMTP Configuration loaded: Server={email_config.get('smtp_server')}, "
                    f"Port={email_config.get('smtp_port')}, Username={email_config.get('smtp_username')}")
        
        if not all([email_config['smtp_server'], email_config['smtp_port'], email_config['smtp_password']]):
            logger.error("SMTP configuration is incomplete in .env file. Please check your .env file and ensure "
                      "SMTP_SERVER, SMTP_PORT, and SMTP_PASSWORD are set correctly. "
                      "Email functionality will not work without these values.")
                
    elif email_config['email_provider'] == 'sendgrid':
        email_config['sendgrid_api_key'] = os.getenv('SENDGRID_API_KEY')
        if not email_config['sendgrid_api_key']:
            logger.error("SendGrid API Key not found in .env. Please set SENDGRID_API_KEY in your .env file.")
    else:
        logger.error(f"Unsupported email provider: '{email_config['email_provider']}'. Please set EMAIL_PROVIDER=smtp "
                  f"or EMAIL_PROVIDER=sendgrid in your .env file. Defaulting to 'smtp', but email functionality "
                  f"will not work correctly without proper configuration.")
        email_config['email_provider'] = 'smtp'

    # Add the email config to the main config
    config['email_config'] = email_config

    return config

if __name__ == '__main__':
    # Basic test loading
    logging.basicConfig(level=logging.INFO)
    loaded_config = load_config()
    print("Configuration Loaded:")
    # Basic print, avoid printing sensitive keys like passwords/api keys in real logs
    for key, value in loaded_config.items():
         if 'key' not in key.lower() and 'password' not in key.lower():
             print(f"  {key}: {value}")
         else:
             print(f"  {key}: ********") 