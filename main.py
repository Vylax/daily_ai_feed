import logging
import schedule
import time
import datetime
import os
import argparse # For --resend flag (C9)
import json     # For deduplication (C8)
from pathlib import Path # For path handling

from src.config_loader import load_config
from src.ingestion import fetch_all_feeds
from src.processing import configure_gemini, filter_and_tag_items, reset_token_counts, get_token_counts
from src.summarization import summarize_and_analyze
from src.tutorial_generator import load_tutorial_topics, select_tutorial_topic, generate_tutorial
from src.assembly import assemble_digest
from src.email_utils import send_email

# --- Constants ---
PROCESSED_URLS_FILE = "data/processed_urls.json"
LAST_DIGEST_FILE = "outputs/last_digest.html"
PROJECT_CONTEXT_FILE = "project_context.md"

# --- Logging Setup ---
# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Create outputs directory if it doesn't exist
if not os.path.exists('outputs'):
    os.makedirs('outputs')

# Create data directory if it doesn't exist
if not os.path.exists('data'):
    os.makedirs('data')

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

# --- Context Loading Function (C7) ---
def load_project_context(filepath=PROJECT_CONTEXT_FILE):
    """Loads project context from the specified markdown file."""
    try:
        context_path = Path(filepath)
        if context_path.is_file():
            context = context_path.read_text(encoding="utf-8")
            logger.info(f"Successfully loaded project context from {filepath}")
            return context
        else:
            logger.warning(f"Project context file not found at {filepath}. Proceeding without project context.")
            # Ensure project_context.md exists with placeholder if not found
            try:
                placeholder_content = "# Project Context (Please Edit)\n\nReplace this text with details about your current projects, goals, and tech stacks.\nThis context will help the AI tailor actionable ideas.\n\nExample:\n## Project Hermes: API for X\n- Goal: ...\n- Tech: ...\n- Stage: ..."
                context_path.parent.mkdir(parents=True, exist_ok=True)
                context_path.write_text(placeholder_content, encoding="utf-8")
                logger.info(f"Created placeholder project context file at {filepath}")
                return placeholder_content
            except Exception as create_e:
                 logger.error(f"Failed to create placeholder context file at {filepath}: {create_e}")
                 return None
    except Exception as e:
        logger.error(f"Error reading project context file {filepath}: {e}", exc_info=True)
        return None

# --- Deduplication Functions (C8) ---
def load_processed_urls(filepath=PROCESSED_URLS_FILE):
    """Loads the list of processed URLs with timestamps."""
    processed_urls = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                processed_urls_raw = json.load(f)
                # Convert ISO timestamp strings back to datetime objects
                processed_urls = {url: datetime.datetime.fromisoformat(timestamp) 
                                   for url, timestamp in processed_urls_raw.items()}
            logger.info(f"Loaded {len(processed_urls)} processed URLs for deduplication.")
        except Exception as e:
            logger.error(f"Error loading processed URLs from {filepath}: {e}")
    else:
        logger.info(f"No processed URLs file found at {filepath}, starting fresh.")
        # Create directory structure if it doesn't exist
        if os.path.dirname(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    return processed_urls

def save_processed_urls(processed_urls, items_in_digest, filepath=PROCESSED_URLS_FILE):
    """Saves current digest URLs and removes old entries."""
    now = datetime.datetime.now()
    seven_days_ago = now - datetime.timedelta(days=7)

    # Add URLs from the current digest
    for item in items_in_digest:
        if item.get('url'):
            processed_urls[item['url']] = now

    # Filter out entries older than 7 days
    updated_processed_urls = {
        url: ts for url, ts in processed_urls.items()
        if ts >= seven_days_ago
    }

    # Convert datetime objects to ISO format strings for JSON serialization
    urls_to_save = {url: ts.isoformat() for url, ts in updated_processed_urls.items()}

    try:
        # Create directory structure if it doesn't exist
        if filepath and os.path.dirname(filepath):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(urls_to_save, f, indent=2)
        logger.info(f"Saved {len(urls_to_save)} processed URLs (removed {len(processed_urls) - len(updated_processed_urls)} old entries) to {filepath}")
    except Exception as e:
        logger.error(f"Error saving processed URLs to {filepath}: {e}")
        logger.error(f"Current working directory: {os.getcwd()}")

# --- Main Workflow Function ---
def run_daily_digest_pipeline(config, args):
    """Executes the complete pipeline for generating and sending the digest."""
    start_time = time.time()
    logger.info("Starting daily digest pipeline run...")

    # Get deduplication file path from config (B.4)
    processed_urls_filepath = config.get('processed_urls_filepath', PROCESSED_URLS_FILE)

    # Load Project Context (B.3)
    logger.info("Loading project context...")
    project_context = load_project_context()

    # Load Processed URLs for Deduplication (B.4)
    processed_urls = load_processed_urls(processed_urls_filepath)

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
    all_items = fetch_all_feeds(config.get('rss_feeds', []), config, processed_urls) # Pass processed_urls (B.4)
    logger.info(f"Ingestion complete. {len(all_items)} items fetched (deduplication handled during fetch)." ) # Logging reflects change

    items_to_process = all_items # No separate filtering needed here now

    if not items_to_process:
        logger.warning("No new items found after ingestion and deduplication. Pipeline might produce an empty digest.")
        # Optionally, skip the rest of the pipeline if no new items
        # return

    # 4. Processing - Filter & Tag
    logger.info("Filtering and tagging items...")
    # Pass config instead of gemini_model
    filtered_items = filter_and_tag_items(items_to_process, config)
    if filtered_items is None: # Check for None explicitly, as empty list is valid
        logger.error("Failed to filter and tag items. Aborting pipeline.")
        return
    logger.info(f"Processing complete. {len(filtered_items)} items selected for summarization/analysis.")
    if not filtered_items:
        logger.warning("No items remained after filtering. Pipeline might produce an empty digest.")

    # 5. Summarization - Summarize & Analyze
    logger.info("Summarizing and analyzing top items...")
    # Pass config instead of gemini_model
    # Pass project_context (C7)
    news_data, feed_tutorials_data = summarize_and_analyze(
        filtered_items,
        config,
        project_context=project_context, # Pass context here (B.3)
        num_news=config.get('num_news_items_to_summarize', 7),
        num_tutorials=config.get('num_feed_tutorials_to_include', 5)
    )
    logger.info("Summarization and analysis complete.")
    # Summarization function handles internal errors and returns empty lists

    # 6. Tutorial Generation
    logger.info("Generating custom tutorial...")
    load_tutorial_topics(config.get('initial_tutorial_topics', []))
    selected_topic = select_tutorial_topic()
    generated_tutorial_html = None
    if selected_topic:
        # Pass config instead of gemini_model
        generated_tutorial_html = generate_tutorial(selected_topic, config)
        if not generated_tutorial_html:
            logger.warning(f"Failed to generate tutorial for topic: {selected_topic}")
        else:
            logger.info(f"Tutorial generation complete for topic: {selected_topic}")
    else:
        logger.warning("No tutorial topic selected for generation.")

    # 7. Assembly - Create Digest
    logger.info("Assembling the digest...")
    # Pass the structured data and the selected_topic to assemble_digest
    final_digest_html = assemble_digest(news_data, feed_tutorials_data, generated_tutorial_html, selected_topic, code_theme='monokai', dark_code=True)
    logger.info("Digest assembly complete.")

    # Save digest locally BEFORE sending (C9)
    digest_filename_latest = LAST_DIGEST_FILE
    try:
        os.makedirs(os.path.dirname(digest_filename_latest), exist_ok=True)
        with open(digest_filename_latest, "w", encoding="utf-8") as f:
            f.write(final_digest_html)
        logger.info(f"Latest digest saved locally to {digest_filename_latest}")
    except Exception as e:
        logger.error(f"Error saving latest digest locally: {e}")

    # Optional: Save timestamped digest locally for debugging/archiving
    digest_filename_ts = f"logs/digest_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    try:
        with open(digest_filename_ts, "w", encoding="utf-8") as f:
            f.write(final_digest_html)
        logger.info(f"Timestamped digest saved locally to {digest_filename_ts}")
    except Exception as e:
        logger.error(f"Error saving timestamped digest locally: {e}")

    # 8. Delivery - Send Email
    send_attempted = False
    # Make sure email_config exists and is enabled
    if not config.get('email_config'):
        # Create email_config if it doesn't exist
        config['email_config'] = {
            'enabled': True,
            'email_provider': 'smtp',
            'smtp_server': config.get('smtp_server'),
            'smtp_port': config.get('smtp_port'),
            'smtp_username': config.get('smtp_username'),
            'smtp_password': config.get('smtp_password'),
            'sender_email': config.get('sender_email'),
            'recipient_email': config.get('recipient_email')
        }
        logger.info("Created email_config section in configuration")
    elif not config['email_config'].get('enabled'):
        # Enable email if it's disabled
        config['email_config']['enabled'] = True
        logger.info("Enabled email sending in configuration")

    if config.get('email_config') and config['email_config'].get('enabled', True) and final_digest_html:
        logger.info("Sending digest email...")
        email_subject = f"AI Daily Digest - {datetime.datetime.now().strftime('%B %d, %Y')}"
        email_sent = send_email(
            subject=email_subject,
            html_body=final_digest_html,
            config=config.get('email_config')
        )
        send_attempted = True
    else:
        logger.info("Email sending is disabled or digest is empty. Skipping email.")
        if not final_digest_html:
            logger.warning("Digest is empty - no content to send")
        elif not config.get('email_config'):
            logger.warning("Email configuration is missing")
        elif not config['email_config'].get('enabled'):
            logger.warning("Email sending is explicitly disabled in config")
        email_sent = False # Explicitly set to false if not attempted

    # 9. Update Processed URLs (B.4) - *After* successful send or if send was not attempted but digest was generated
    if final_digest_html: # Only update if a digest was actually generated
        items_actually_in_digest = news_data + feed_tutorials_data # Combine lists to get all items included
        if email_sent or not send_attempted:
            logger.info("Updating processed URLs file...")
            save_processed_urls(processed_urls, items_actually_in_digest, processed_urls_filepath)
        else:
            logger.warning("Email sending failed. Not updating processed URLs file to allow reprocessing.")
    else:
        logger.info("No digest content generated. Skipping update of processed URLs file.")

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

# --- Resend Function (C9) ---
def resend_last_digest(config):
    """Resends the last locally saved digest."""
    logger.info("Attempting to resend the last digest...")
    last_digest_path = Path(LAST_DIGEST_FILE)

    # Make sure email_config exists and is enabled
    if not config.get('email_config'):
        # Create email_config if it doesn't exist
        config['email_config'] = {
            'enabled': True,
            'email_provider': 'smtp',
            'smtp_server': config.get('smtp_server'),
            'smtp_port': config.get('smtp_port'),
            'smtp_username': config.get('smtp_username'),
            'smtp_password': config.get('smtp_password'),
            'sender_email': config.get('sender_email'),
            'recipient_email': config.get('recipient_email')
        }
        logger.info("Created email_config section in configuration for resend")
    elif not config['email_config'].get('enabled'):
        # Enable email if it's disabled
        config['email_config']['enabled'] = True
        logger.info("Enabled email sending in configuration for resend")

    if not config.get('email_config') or not config['email_config'].get('enabled', True):
        logger.error("Email sending is not enabled in the configuration. Cannot resend.")
        return

    if not last_digest_path.is_file():
        logger.error(f"Last digest file not found at {last_digest_path}. Cannot resend.")
        return

    try:
        last_digest_html = last_digest_path.read_text(encoding="utf-8")
        if not last_digest_html:
             logger.error(f"Last digest file {last_digest_path} is empty. Cannot resend.")
             return

        # Create a subject that indicates it's a resend
        email_subject = f"[Resend] AI Daily Digest - {datetime.datetime.now().strftime('%B %d, %Y')}"
        logger.info(f"Resending digest from {last_digest_path}...")

        email_sent = send_email(
            subject=email_subject,
            html_body=last_digest_html,
            config=config.get('email_config')
        )

        if email_sent:
            logger.info("Last digest resent successfully.")
        else:
            logger.error("Failed to resend the last digest.")

    except Exception as e:
        logger.error(f"Error during resend process: {e}", exc_info=True)

# --- Scheduling & Argument Parsing ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the AI Daily Digest pipeline.")
    parser.add_argument(
        "--resend",
        action="store_true",
        help="Resend the last successfully generated digest."
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run the pipeline once immediately instead of scheduling."
    )
    args = parser.parse_args()

    logger.info("AI Digest Agent starting up.")

    # Load configuration first
    config = load_config()
    if not config:
        logger.error("Failed to load configuration. Cannot start agent.")
        exit(1)

    # Handle --resend flag (C9)
    if args.resend:
        resend_last_digest(config)
        logger.info("Resend operation complete. Exiting.")
        exit(0)

    # Proceed with normal pipeline execution if --resend is not used
    run_mode = config.get('run_mode', 'schedule')

    if run_mode == 'once':
        logger.info("Running pipeline execution once...")
        run_daily_digest_pipeline(config, args)
        logger.info("Single run complete. Exiting.")
    elif run_mode == 'schedule':
        # Run once immediately if configured (e.g., initial_run = true in config)
        if config.get('schedule_initial_run', True):
            logger.info("Running initial pipeline execution before scheduling...")
            try:
                run_daily_digest_pipeline(config, args)
            except Exception as e:
                logger.error(f"Initial pipeline run failed: {e}", exc_info=True)
            logger.info("Initial run complete.")

        # Schedule the job
        schedule_time = config.get('schedule_time', "06:00")
        logger.info(f"Scheduling daily run at {schedule_time}")
        schedule.every().day.at(schedule_time).do(run_daily_digest_pipeline, config=config, args=args)

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
