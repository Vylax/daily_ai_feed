import google.generativeai as genai
import logging
import json
from textwrap import dedent
import time

logger = logging.getLogger(__name__)

# --- Gemini API Initialization ---
def configure_gemini(api_key=None, credentials_path=None):
    """Configures the Gemini client using API key or credentials.
       Prioritizes credentials path if both are provided."""
    try:
        if credentials_path:
            # Assumes ADC or service account key path is set
            # The library handles GOOGLE_APPLICATION_CREDENTIALS automatically
            # if credentials_path is set as an env var, but explicit config might be needed in some setups
            # For now, we rely on the env var being set externally or direct API key
            logger.info(f"Attempting to configure Gemini using GOOGLE_APPLICATION_CREDENTIALS: {credentials_path}")
            # If direct configuration needed: genai.configure(credentials=...) - requires google-auth library
            genai.configure(api_key=api_key) # Still need API key potentially for certain auth flows?
            logger.info("Gemini configured using Application Default Credentials (assumed).")

        elif api_key:
            genai.configure(api_key=api_key)
            logger.info("Gemini configured using API Key.")
        else:
            raise ValueError("Either Gemini API Key or Google Application Credentials path must be provided.")
        # Test connection with a simple model listing (optional)
        # models = [m for m in genai.list_models()]
        # logger.info(f"Available Gemini models: {models}")
        return True
    except Exception as e:
        logger.error(f"Failed to configure Gemini: {e}", exc_info=True)
        return False

def get_gemini_model(model_name="gemini-1.5-flash-latest"):
    """Returns an instance of the specified Gemini model."""
    try:
        model = genai.GenerativeModel(model_name)
        logger.info(f"Using Gemini model: {model_name}")
        return model
    except Exception as e:
        logger.error(f"Failed to get Gemini model '{model_name}': {e}", exc_info=True)
        return None

# --- Prompt Definition ---
FILTERING_TAGGING_PROMPT_TEMPLATE = dedent("""
    You are an AI expert assistant analyzing news items for a highly technical CTO. Their priorities are: Google AI (Gemini, Vertex AI), LLMs, Prompt Engineering, MLOps, practical applications, market shifts (vs OpenAI/Anthropic/etc.), and actionable insights for their AI startup. They have a strong coding background but weaker theory.

    Analyze the following items fetched from RSS feeds (provided as Title, URL, Snippet, Source Feed). Prioritize based on the CTO's interests AND the source feed's priority (assume feeds provided earlier in the input list are higher priority).

    For the TOP ~15-20 most relevant items, provide a JSON list of objects, each containing:
    - "url": Original URL
    - "title": Original Title
    - "source": Source Feed URL
    - "relevance_score": (1-10, 10=highest relevance to CTO)
    - "justification": (Briefly why it's relevant)
    - "content_type": (Tag: "News", "Research Paper Abstract", "Tutorial/Guide", "Opinion", "Market/Competitor Info", "Company Update", "Other")
    - "keywords": (List of 3-5 relevant keywords)

    Filter out low-signal noise, marketing fluff, and duplicates aggressively. Focus on substantial updates, technical insights, and practical guides.

    Input Items (Title, URL, Snippet, Source Feed):
    {items_text}

    Output ONLY the JSON list.
""")

def format_items_for_prompt(items):
    """Formats the list of item dictionaries into a string for the prompt."""
    lines = []
    for item in items:
        # Truncate long summaries to keep the prompt size reasonable
        summary = item.get('summary', '')
        if summary and len(summary) > 500:
             summary = summary[:497] + '...'
        line = f"- Title: {item.get('title', 'N/A')}\n  URL: {item.get('link', 'N/A')}\n  Snippet: {summary}\n  Source Feed: {item.get('source_feed', 'N/A')}"
        lines.append(line)
    return "\n".join(lines)

def filter_and_tag_items(items, gemini_model, retries=3, delay=5):
    """Uses the Gemini API to filter and tag items based on relevance.

    Args:
        items: List of item dictionaries from ingestion.
        gemini_model: An initialized Gemini GenerativeModel instance.
        retries: Number of times to retry the API call on failure.
        delay: Delay in seconds between retries.

    Returns:
        A list of filtered and tagged item dictionaries (parsed from JSON), or None if failed.
    """
    if not items:
        logger.warning("No items provided for filtering and tagging.")
        return []
    if not gemini_model:
        logger.error("Gemini model not provided or initialized for filtering.")
        return None

    items_text = format_items_for_prompt(items)
    prompt = FILTERING_TAGGING_PROMPT_TEMPLATE.format(items_text=items_text)

    logger.info(f"Sending {len(items)} items to Gemini for filtering/tagging...")
    # logger.debug(f"Prompt for filtering/tagging:\n{prompt[:500]}...") # Log start of prompt

    for attempt in range(retries):
        try:
            response = gemini_model.generate_content(prompt)

            # Handle potential safety blocks or empty responses
            if not response.parts:
                 logger.warning(f"Gemini response has no parts (attempt {attempt + 1}/{retries}). Possibly blocked or empty. Finish reason: {response.prompt_feedback.block_reason if response.prompt_feedback else 'N/A'}")
                 # Consider checking response.prompt_feedback for block reasons
                 if attempt < retries - 1:
                     time.sleep(delay)
                     continue
                 else:
                     logger.error("Gemini filtering failed after multiple attempts due to empty/blocked response.")
                     return None

            raw_json = response.text
            # logger.debug(f"Raw JSON response from Gemini:\n{raw_json}")

            # Clean the response - Gemini might add markdown backticks
            cleaned_json = raw_json.strip().strip('`').strip()
            if cleaned_json.startswith('json'):
                cleaned_json = cleaned_json[4:].strip() # Remove potential leading 'json'

            # Parse the JSON response
            filtered_items = json.loads(cleaned_json)
            logger.info(f"Successfully received and parsed {len(filtered_items)} filtered items from Gemini.")
            return filtered_items

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response from Gemini (attempt {attempt + 1}/{retries}): {e}")
            logger.error(f"Problematic response snippet: {raw_json[:500]}...") # Log snippet of bad response
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                logger.error("Failed to filter items after multiple JSON decoding errors.")
                return None
        except Exception as e:
            # Catch other potential API errors (rate limits, connection issues, etc.)
            logger.error(f"An error occurred during Gemini API call (attempt {attempt + 1}/{retries}): {e}", exc_info=True)
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1)) # Exponential backoff might be better
            else:
                logger.error("Failed to filter items after multiple API errors.")
                return None

    return None # Should not be reached if retries are exhausted properly

# --- Example Usage (for testing) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Load config to get API key (requires a .env file)
    from config_loader import load_config
    config = load_config()

    # Configure Gemini (replace with your actual key or credentials method)
    if not configure_gemini(api_key=config.get('gemini_api_key'), credentials_path=config.get('google_application_credentials')):
        print("Exiting due to Gemini configuration failure.")
        exit()

    # Get the model
    model = get_gemini_model()
    if not model:
        print("Exiting because Gemini model could not be initialized.")
        exit()

    # Dummy items for testing
    test_items = [
        {'title': 'Google Announces New Gemini Features', 'link': 'http://google.com/gemini', 'summary': 'Google released updates to its Gemini model family, focusing on improved reasoning and code generation.', 'source_feed': 'google_blog'},
        {'title': 'Intro to LangGraph for Agentic Workflows', 'link': 'http://langchain.dev/langgraph', 'summary': 'Learn how to build stateful multi-actor applications with LangGraph, the latest addition to the LangChain ecosystem.', 'source_feed': 'langchain_blog'},
        {'title': 'OpenAI Competitor Releases New Model', 'link': 'http://competitor.com/model', 'summary': 'A new startup challenges OpenAI with a model claiming better performance on certain benchmarks.', 'source_feed': 'tech_news'},
        {'title': 'Why Python is Great for Beginners', 'link': 'http://python-basics.com', 'summary': 'An article explaining the benefits of Python for new programmers.', 'source_feed': 'coding_blog'},
        {'title': 'DeepMind Paper on AlphaFold 3', 'link': 'http://deepmind.com/af3', 'summary': 'DeepMind publishes groundbreaking research on AlphaFold 3, predicting the structure of protein complexes.', 'source_feed': 'deepmind_blog'},
    ]

    print(f"\nFiltering {len(test_items)} items...")
    filtered_results = filter_and_tag_items(test_items, model)

    if filtered_results:
        print("\n--- Filtered and Tagged Items ---")
        for item in filtered_results:
            print(json.dumps(item, indent=2))
    else:
        print("\nFailed to get filtered items from Gemini.") 