import logging
import schedule
import time
import datetime
import os

from src.config_loader import load_config
from src.ingestion import fetch_all_feeds
from src.processing import configure_gemini, get_gemini_model, filter_and_tag_items
from src.summarization import summarize_and_analyze
from src.tutorial_generator import load_tutorial_topics, select_tutorial_topic, generate_tutorial
from src.assembly import assemble_digest
from src.email_utils import send_email

# --- Logging Setup ---
# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

log_filename = f"logs/ai_digest_agent_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler() # Also print to console
    ]
)
logger = logging.getLogger(__name__)

# --- Main Workflow Function ---
def run_daily_digest_pipeline():
    """Executes the complete pipeline for generating and sending the digest."""
    logger.info("Starting daily digest pipeline run...")

    # 1. Load Configuration
    logger.info("Loading configuration...")
    config = load_config()
    if not config:
        logger.error("Failed to load configuration. Aborting pipeline.")
        return

    # 2. Configure Gemini API
    logger.info("Configuring Gemini API...")
    if not configure_gemini(api_key=config.get('gemini_api_key'), credentials_path=config.get('google_application_credentials')):
        logger.error("Failed to configure Gemini API. Aborting pipeline.")
        return
    gemini_model = get_gemini_model() # Use default model (flash)
    if not gemini_model:
        logger.error("Failed to initialize Gemini model. Aborting pipeline.")
        return

    # 3. Ingestion - Fetch RSS Feeds
    logger.info("Fetching RSS feeds...")
    all_items = fetch_all_feeds(config.get('rss_feeds', []))
    if not all_items:
        logger.warning("No items fetched from RSS feeds. Pipeline might produce an empty digest.")
        # Decide if to continue or abort if no items
        # return # Example: abort if nothing fetched

    # 4. Processing - Filter & Tag
    logger.info("Filtering and tagging items...")
    filtered_items = filter_and_tag_items(all_items, gemini_model)
    if filtered_items is None: # Check for None explicitly, as empty list is valid
        logger.error("Failed to filter and tag items. Aborting pipeline.")
        return
    if not filtered_items:
        logger.warning("No items remained after filtering. Pipeline might produce an empty digest.")

    # 5. Summarization - Summarize & Analyze
    logger.info("Summarizing and analyzing top items...")
    news_summaries_md, feed_tutorials_md = summarize_and_analyze(
        filtered_items,
        gemini_model,
        num_news=config.get('num_news_items_to_summarize', 7),
        num_tutorials=config.get('num_feed_tutorials_to_include', 5)
    )
    # Summarization function handles internal errors and returns empty lists

    # 6. Tutorial Generation
    logger.info("Generating custom tutorial...")
    load_tutorial_topics(config.get('initial_tutorial_topics', []))
    selected_topic = select_tutorial_topic()
    generated_tutorial_md = None
    if selected_topic:
        generated_tutorial_md = generate_tutorial(selected_topic, gemini_model)
        if not generated_tutorial_md:
            logger.warning(f"Failed to generate tutorial for topic: {selected_topic}")
    else:
        logger.warning("No tutorial topic selected for generation.")

    # 7. Assembly - Create Digest
    logger.info("Assembling the digest...")
    final_digest_md = assemble_digest(news_summaries_md, feed_tutorials_md, generated_tutorial_md)

    # Optional: Save digest locally for debugging/archiving
    digest_filename = f"logs/digest_{datetime.datetime.now().strftime('%Y%m%d')}.md"
    try:
        with open(digest_filename, "w", encoding="utf-8") as f:
            f.write(final_digest_md)
        logger.info(f"Digest saved locally to {digest_filename}")
    except Exception as e:
        logger.error(f"Error saving digest locally: {e}")

    # 8. Delivery - Send Email
    logger.info("Sending digest via email...")
    subject = f"{config.get('email_subject_prefix', '[AI Digest]')} {datetime.date.today()}"
    if config.get('recipient_email') and config.get('sender_email'):
        success = send_email(subject, final_digest_md, config)
        if success:
            logger.info("Digest email sent successfully.")
        else:
            logger.error("Failed to send digest email.")
    else:
        logger.warning("Recipient or Sender email not configured. Skipping email delivery.")

    logger.info("Daily digest pipeline run finished.")

# --- Scheduling --- 
if __name__ == "__main__":
    logger.info("AI Digest Agent starting up.")

    # Run once immediately for testing (optional)
    # logger.info("Running initial pipeline execution...")
    # run_daily_digest_pipeline()
    # logger.info("Initial run complete.")

    # Schedule the job
    schedule_time = "06:00"
    logger.info(f"Scheduling daily run at {schedule_time}")
    schedule.every().day.at(schedule_time).do(run_daily_digest_pipeline)

    # Keep the script running to allow the scheduler to work
    logger.info("Scheduler started. Waiting for scheduled jobs...")
    while True:
        schedule.run_pending()
        time.sleep(60) # Check every minute
