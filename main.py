import logging
import schedule
import time
import datetime
import os

from src.config_loader import load_config
from src.ingestion import fetch_all_feeds
from src.processing import configure_gemini, filter_and_tag_items, reset_token_counts, get_token_counts
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

# --- Helper Function for Cost Estimation (Optional) ---
def _calculate_estimated_cost(token_counts, pricing_config):
    """Calculates estimated cost based on token counts and pricing config."""
    if not pricing_config or not isinstance(pricing_config, dict):
        return 0.0

    # Assuming pricing is per Million tokens
    prompt_tokens_m = token_counts.get('prompt_tokens', 0) / 1_000_000
    candidates_tokens_m = token_counts.get('candidates_tokens', 0) / 1_000_000

    # This is a simplification - assumes all tokens used the same pricing
    # A more accurate approach would track tokens per model and use specific pricing
    # For now, let's use a default or average price if available
    # Example: Use 'gemini-2.0-flash' pricing as a proxy if available
    flash_pricing = pricing_config.get('gemini-2.0-flash')
    if flash_pricing and isinstance(flash_pricing, dict):
        input_price = flash_pricing.get('input', 0.0)
        output_price = flash_pricing.get('output', 0.0)
    else:
         # Fallback: Use 1.5 flash pricing or a generic placeholder if 2.0 flash not defined
         flash_15_pricing = pricing_config.get('gemini-1.5-flash-latest')
         if flash_15_pricing and isinstance(flash_15_pricing, dict):
             input_price = flash_15_pricing.get('input', 0.0)
             output_price = flash_15_pricing.get('output', 0.0)
         else:
             logger.warning("Could not find suitable pricing info in config for cost estimation.")
             return 0.0 # Cannot estimate

    estimated_cost = (prompt_tokens_m * input_price) + (candidates_tokens_m * output_price)
    return estimated_cost

# --- Main Workflow Function ---
def run_daily_digest_pipeline():
    """Executes the complete pipeline for generating and sending the digest."""
    start_time = time.time()
    logger.info("Starting daily digest pipeline run...")

    # 1. Load Configuration
    logger.info("Loading configuration...")
    config = load_config()
    if not config:
        logger.error("Failed to load configuration. Aborting pipeline.")
        return

    # Reset token counters at the beginning of the run
    reset_token_counts()

    # 2. Configure Gemini API
    logger.info("Configuring Gemini API...")
    if not configure_gemini(api_key=config.get('gemini_api_key'), credentials_path=config.get('google_application_credentials')):
        logger.error("Failed to configure Gemini API. Aborting pipeline.")
        return
    # No longer need to get a default model instance here
    # Models are fetched dynamically in processing, summarization, tutorial generation

    # 3. Ingestion - Fetch RSS Feeds
    logger.info("Fetching RSS feeds...")
    all_items = fetch_all_feeds(config.get('rss_feeds', []), config) # Pass config
    logger.info(f"Ingestion complete. {len(all_items)} items passed pre-filtering.")
    if not all_items:
        logger.warning("No items fetched from RSS feeds after pre-filtering. Pipeline might produce an empty digest.")
        # Decide if to continue or abort if no items
        # return # Example: abort if nothing fetched

    # 4. Processing - Filter & Tag
    logger.info("Filtering and tagging items...")
    # Pass config instead of gemini_model
    filtered_items = filter_and_tag_items(all_items, config)
    if filtered_items is None: # Check for None explicitly, as empty list is valid
        logger.error("Failed to filter and tag items. Aborting pipeline.")
        return
    logger.info(f"Processing complete. {len(filtered_items)} items selected for summarization/analysis.")
    if not filtered_items:
        logger.warning("No items remained after filtering. Pipeline might produce an empty digest.")

    # 5. Summarization - Summarize & Analyze
    logger.info("Summarizing and analyzing top items...")
    # Pass config instead of gemini_model
    news_data, feed_tutorials_data = summarize_and_analyze(
        filtered_items,
        config,
        num_news=config.get('num_news_items_to_summarize', 7),
        num_tutorials=config.get('num_feed_tutorials_to_include', 5)
    )
    logger.info("Summarization and analysis complete.")
    # Summarization function handles internal errors and returns empty lists

    # 6. Tutorial Generation
    logger.info("Generating custom tutorial...")
    load_tutorial_topics(config.get('initial_tutorial_topics', []))
    selected_topic = select_tutorial_topic()
    generated_tutorial_md = None
    if selected_topic:
        # Pass config instead of gemini_model
        generated_tutorial_md = generate_tutorial(selected_topic, config)
        if not generated_tutorial_md:
            logger.warning(f"Failed to generate tutorial for topic: {selected_topic}")
        else:
            logger.info(f"Tutorial generation complete for topic: {selected_topic}")
    else:
        logger.warning("No tutorial topic selected for generation.")

    # 7. Assembly - Create Digest
    logger.info("Assembling the digest...")
    # Pass the structured data to assemble_digest
    final_digest_html = assemble_digest(news_data, feed_tutorials_data, generated_tutorial_md)
    logger.info("Digest assembly complete.")

    # Optional: Save digest locally for debugging/archiving
    digest_filename = f"logs/digest_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html" # Save as .html
    try:
        with open(digest_filename, "w", encoding="utf-8") as f:
            f.write(final_digest_html)
        logger.info(f"Digest saved locally to {digest_filename}")
    except Exception as e:
        logger.error(f"Error saving digest locally: {e}")

    # 8. Delivery - Send Email
    logger.info("Sending digest via email...")
    subject = f"{config.get('email_subject_prefix', '[AI Digest]')} {datetime.date.today()}"
    if config.get('recipient_email') and config.get('sender_email'):
        # Pass the generated HTML directly to send_email
        success = send_email(subject, final_digest_html, config)
        if success:
            logger.info("Digest email sent successfully.")
        else:
            logger.error("Failed to send digest email.")
    else:
        logger.warning("Recipient or Sender email not configured. Skipping email delivery.")

    # --- Pipeline End & Reporting ---
    end_time = time.time()
    total_duration = end_time - start_time

    # Get final token counts
    final_token_counts = get_token_counts()
    logger.info(f"--- Pipeline Run Summary ---")
    logger.info(f"Total execution time: {total_duration:.2f} seconds")
    logger.info(f"Final Token Counts: Prompt={final_token_counts.get('prompt_tokens', 0)}, Candidates={final_token_counts.get('candidates_tokens', 0)}, Total={final_token_counts.get('total_tokens', 0)}")

    # Optional: Estimate cost
    pricing_info = config.get('gemini_pricing')
    if pricing_info:
        estimated_cost = _calculate_estimated_cost(final_token_counts, pricing_info)
        if estimated_cost > 0:
            logger.info(f"Estimated Gemini API Cost for this run: ${estimated_cost:.4f}")
        else:
            logger.info("Could not calculate estimated cost (check pricing config).")

    logger.info("Daily digest pipeline run finished.")

# --- Scheduling --- 
if __name__ == "__main__":
    logger.info("AI Digest Agent starting up.")

    # Load configuration first
    config = load_config()
    if not config:
        logger.error("Failed to load configuration. Cannot start agent.")
        # Exit or handle appropriately if config fails to load at startup
        exit(1) # Or raise an exception

    run_mode = config.get('run_mode', 'schedule') # Add config option: 'schedule' or 'once'

    if run_mode == 'once':
        logger.info("Running pipeline execution once...")
        run_daily_digest_pipeline()
        logger.info("Single run complete. Exiting.")
    elif run_mode == 'schedule':
        # Run once immediately if configured (e.g., initial_run = true in config)
        if config.get('schedule_initial_run', True):
            logger.info("Running initial pipeline execution before scheduling...")
            try:
                run_daily_digest_pipeline()
            except Exception as e:
                logger.error(f"Initial pipeline run failed: {e}", exc_info=True)
            logger.info("Initial run complete.")

        # Schedule the job
        schedule_time = config.get('schedule_time', "06:00")
        logger.info(f"Scheduling daily run at {schedule_time}")
        schedule.every().day.at(schedule_time).do(run_daily_digest_pipeline)

        # Keep the script running to allow the scheduler to work
        logger.info("Scheduler started. Waiting for scheduled jobs... (Press Ctrl+C to stop)")
        try:
            while True:
                schedule.run_pending()
                time.sleep(60) # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user.")
    else:
        logger.error(f"Invalid run_mode specified in config: '{run_mode}'. Use 'schedule' or 'once'.")
