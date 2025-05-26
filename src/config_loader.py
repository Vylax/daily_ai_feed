import os
import logging
import yaml
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def load_config():
    """Loads configuration from config.yaml and .env file, with .env taking precedence for sensitive data."""
    # Load environment variables first
    load_dotenv(override=True)

    config = {}

    # --- Load YAML Configuration ---
    config_yaml_path = Path("config.yaml")
    if config_yaml_path.exists():
        try:
            with open(config_yaml_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f) or {}
            logger.info("Successfully loaded configuration from config.yaml")
            
            # Merge YAML config into main config
            config.update(yaml_config)
            
        except Exception as e:
            logger.error(f"Error loading config.yaml: {e}")
            logger.warning("Continuing with .env configuration only")
    else:
        logger.warning("config.yaml not found, using .env configuration only")

    # --- Override with Environment Variables (for sensitive data) ---
    
    # Gemini API (environment variables take precedence)
    if os.getenv('GEMINI_API_KEY'):
        config['gemini_api_key'] = os.getenv('GEMINI_API_KEY')
    if os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        config['google_application_credentials'] = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    
    if not config.get('gemini_api_key') and not config.get('google_application_credentials'):
        logger.warning("Gemini API key or Google Application Credentials not found in .env or config.yaml")

    # --- RSS Feeds ---
    # Use RSS feeds from config.yaml if available, otherwise fall back to .env
    if not config.get('rss_feeds'):
        rss_feeds_str = os.getenv('RSS_FEEDS', '')
        config['rss_feeds'] = [url.strip() for url in rss_feeds_str.split(',') if url.strip()]
        if config['rss_feeds']:
            logger.info(f"Loaded {len(config['rss_feeds'])} RSS feeds from .env")
    else:
        logger.info(f"Loaded {len(config['rss_feeds'])} RSS feeds from config.yaml")
    
    if not config.get('rss_feeds'):
        logger.warning("No RSS feeds found in config.yaml or .env file.")
        config['rss_feeds'] = []

    # --- Processing Configuration ---
    # Environment variables can override YAML settings
    if os.getenv('NUM_NEWS_ITEMS_TO_SUMMARIZE'):
        try:
            config['num_news_items_to_summarize'] = int(os.getenv('NUM_NEWS_ITEMS_TO_SUMMARIZE'))
        except ValueError:
            logger.warning("Invalid NUM_NEWS_ITEMS_TO_SUMMARIZE in .env, using config.yaml or default")
    
    if not config.get('num_news_items_to_summarize'):
        config['num_news_items_to_summarize'] = 7

    if os.getenv('NUM_FEED_TUTORIALS_TO_INCLUDE'):
        try:
            config['num_feed_tutorials_to_include'] = int(os.getenv('NUM_FEED_TUTORIALS_TO_INCLUDE'))
        except ValueError:
            logger.warning("Invalid NUM_FEED_TUTORIALS_TO_INCLUDE in .env, using config.yaml or default")
    
    if not config.get('num_feed_tutorials_to_include'):
        config['num_feed_tutorials_to_include'] = 5

    # Tutorial topics from environment or config
    if os.getenv('INITIAL_TUTORIAL_TOPICS'):
        tutorial_topics_str = os.getenv('INITIAL_TUTORIAL_TOPICS')
        config['initial_tutorial_topics'] = [topic.strip() for topic in tutorial_topics_str.split(',') if topic.strip()]
    
    if not config.get('initial_tutorial_topics'):
        config['initial_tutorial_topics'] = []

    # --- Email Configuration (environment variables take precedence for sensitive data) ---
    email_config = config.get('email_config', {})
    
    # Override with environment variables
    if os.getenv('EMAIL_PROVIDER'):
        email_config['email_provider'] = os.getenv('EMAIL_PROVIDER').lower().strip()
    if os.getenv('RECIPIENT_EMAIL'):
        email_config['recipient_email'] = os.getenv('RECIPIENT_EMAIL')
    if os.getenv('SENDER_EMAIL'):
        email_config['sender_email'] = os.getenv('SENDER_EMAIL')
    if os.getenv('EMAIL_SUBJECT_PREFIX'):
        email_config['email_subject_prefix'] = os.getenv('EMAIL_SUBJECT_PREFIX')
    
    # Set defaults
    if not email_config.get('enabled'):
        email_config['enabled'] = True
    if not email_config.get('email_provider'):
        email_config['email_provider'] = 'smtp'
    if not email_config.get('email_subject_prefix'):
        email_config['email_subject_prefix'] = '[AI Digest]'

    if not email_config.get('recipient_email') or not email_config.get('sender_email'):
        logger.warning("Recipient or Sender email not configured in .env or config.yaml. Email delivery will fail.")

    if email_config['email_provider'] == 'smtp':
        # SMTP configuration (environment variables take precedence)
        if os.getenv('SMTP_SERVER'):
            email_config['smtp_server'] = os.getenv('SMTP_SERVER')
        if os.getenv('SMTP_PORT'):
            try:
                email_config['smtp_port'] = int(os.getenv('SMTP_PORT'))
            except (ValueError, TypeError):
                logger.warning("Invalid SMTP_PORT in .env, using config.yaml or default 587")
        if os.getenv('SMTP_USERNAME'):
            email_config['smtp_username'] = os.getenv('SMTP_USERNAME')
        if os.getenv('SMTP_PASSWORD'):
            email_config['smtp_password'] = os.getenv('SMTP_PASSWORD')
        
        # Set defaults
        if not email_config.get('smtp_port'):
            email_config['smtp_port'] = 587
        if not email_config.get('smtp_username'):
            email_config['smtp_username'] = email_config.get('sender_email')
        
        # Log the SMTP configuration for debugging (without revealing password)
        logger.debug(f"SMTP Configuration loaded: Server={email_config.get('smtp_server')}, "
                    f"Port={email_config.get('smtp_port')}, Username={email_config.get('smtp_username')}")
        
        if not all([email_config.get('smtp_server'), email_config.get('smtp_port'), email_config.get('smtp_password')]):
            logger.error("SMTP configuration is incomplete. Please check your .env file and ensure "
                      "SMTP_SERVER, SMTP_PORT, and SMTP_PASSWORD are set correctly. "
                      "Email functionality will not work without these values.")
                
    elif email_config['email_provider'] == 'sendgrid':
        if os.getenv('SENDGRID_API_KEY'):
            email_config['sendgrid_api_key'] = os.getenv('SENDGRID_API_KEY')
        if not email_config.get('sendgrid_api_key'):
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