import google.generativeai as genai
import logging
import json
from textwrap import dedent
import time
from collections import defaultdict # Import defaultdict
import os

logger = logging.getLogger(__name__)

# --- Global Variables for Model Cache and Token Tracking ---
_gemini_models = {} # Cache for initialized models {model_name: model_instance}
_token_counts = defaultdict(int) # { 'prompt_tokens': 0, 'candidates_tokens': 0, 'total_tokens': 0 }

# --- Gemini API Initialization and Model Management ---
def configure_gemini(api_key=None, credentials_path=None):
    """Configures the Gemini client using API key or credentials.
       Prioritizes credentials path if both are provided."""
    try:
        # The library often implicitly uses GOOGLE_APPLICATION_CREDENTIALS if set
        # Explicit configuration might be needed depending on auth setup
        if api_key:
            genai.configure(api_key=api_key)
            logger.info("Gemini configured using API Key.")
            # Simple test to confirm configuration is likely working
            # genai.list_models() # This might incur a small cost or require specific permissions
            return True
        elif credentials_path:
            # Assuming GOOGLE_APPLICATION_CREDENTIALS env var is set to credentials_path
            # No explicit genai.configure() needed if ADC is correctly set up
            logger.info(f"Attempting to configure Gemini using Application Default Credentials (via env var pointing to {credentials_path}).")
            # Simple test to confirm configuration is likely working
            # genai.list_models()
            # If direct configuration needed (less common for ADC):
            # import google.auth
            # credentials, project_id = google.auth.default()
            # genai.configure(credentials=credentials)
            return True
        else:
            raise ValueError("Either Gemini API Key or Google Application Credentials path must be provided in config.")

    except Exception as e:
        logger.error(f"Failed to configure or test Gemini connection: {e}", exc_info=True)
        return False

def get_gemini_model(model_name):
    """Returns an instance of the specified Gemini model, using a cache."""
    if model_name in _gemini_models:
        logger.debug(f"Using cached Gemini model: {model_name}")
        return _gemini_models[model_name]
    else:
        try:
            logger.info(f"Initializing Gemini model: {model_name}")
            model = genai.GenerativeModel(model_name)
            _gemini_models[model_name] = model
            return model
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model '{model_name}': {e}", exc_info=True)
            return None

# --- Token Count Management ---
def reset_token_counts():
    """Resets the global token counters for a new pipeline run."""
    global _token_counts
    _token_counts = defaultdict(int)
    logger.info("Token counts reset.")

def get_token_counts():
    """Returns the current aggregated token counts."""
    return dict(_token_counts) # Return a copy

# --- Core Gemini Call Function with Tracking and Retries ---
def _make_gemini_call_with_tracking(model_name, prompt, task_description, retries=3, delay=5):
    """Makes a call to the Gemini API, tracks token usage, and handles retries."""
    global _token_counts
    model = get_gemini_model(model_name)
    if not model:
        logger.error(f"Cannot make Gemini call for {task_description}: Model '{model_name}' not initialized.")
        return None

    logger.info(f"Calling Gemini model '{model_name}' for task: {task_description}...")
    # Consider logging prompt length or a snippet for debugging large inputs
    # logger.debug(f"Prompt (first 500 chars): {prompt[:500]}...")

    for attempt in range(retries):
        try:
            start_time = time.time()
            # TODO: Add GenerationConfig here if needed (temperature, max_output_tokens, etc.)
            # generation_config = genai.types.GenerationConfig(temperature=0.7)
            response = model.generate_content(prompt) #, generation_config=generation_config)
            end_time = time.time()
            logger.info(f"Gemini call for {task_description} completed in {end_time - start_time:.2f} seconds.")

            # --- Token Tracking --- START
            try:
                if response.usage_metadata:
                    prompt_tokens = response.usage_metadata.prompt_token_count
                    candidates_tokens = response.usage_metadata.candidates_token_count
                    total_tokens = response.usage_metadata.total_token_count

                    _token_counts['prompt_tokens'] += prompt_tokens
                    _token_counts['candidates_tokens'] += candidates_tokens
                    _token_counts['total_tokens'] += total_tokens

                    logger.info(f"Token Usage for {task_description} ({model_name}): Prompt={prompt_tokens}, Candidates={candidates_tokens}, Total={total_tokens}")
                    logger.info(f"Cumulative Tokens: {_token_counts['total_tokens']}")
                else:
                    logger.warning(f"No usage metadata found in response for {task_description}.")
            except Exception as usage_e:
                logger.error(f"Error processing usage metadata for {task_description}: {usage_e}")
            # --- Token Tracking --- END

            # Handle potential safety blocks or empty responses AFTER tracking potential tokens
            if not response.parts:
                feedback = response.prompt_feedback
                block_reason = feedback.block_reason if feedback else 'N/A'
                safety_ratings = feedback.safety_ratings if feedback else []
                logger.warning(f"Gemini response has no parts (attempt {attempt + 1}/{retries}) for {task_description}. Block Reason: {block_reason}. Safety Ratings: {safety_ratings}")
                if attempt < retries - 1:
                    logger.info(f"Retrying after empty/blocked response for {task_description}...")
                    time.sleep(delay * (attempt + 1)) # Exponential backoff
                    continue
                else:
                    logger.error(f"Gemini call for {task_description} failed after multiple attempts due to empty/blocked response.")
                    return None # Return None to indicate final failure

            # If successful, return the full response object
            return response

        except Exception as e:
            # Catch other potential API errors (rate limits, connection issues, invalid requests etc.)
            logger.error(f"An error occurred during Gemini API call for {task_description} (attempt {attempt + 1}/{retries}): {e}", exc_info=False) # Set exc_info=True for full traceback if needed
            if attempt < retries - 1:
                logger.info(f"Retrying after API error for {task_description}...")
                time.sleep(delay * (attempt + 1)) # Exponential backoff
            else:
                logger.error(f"Failed Gemini call for {task_description} after multiple API errors.")
                return None # Return None to indicate final failure

    logger.error(f"Gemini call for {task_description} failed after exhausting retries.")
    return None # Should be reached if retries are exhausted

# --- Prompt Definition (Keeping Filter/Tag Prompt Here) ---
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
        # Include published date if available for context? Might add tokens.
        # pub_date = item.get('published')
        # pub_str = time.strftime('%Y-%m-%d', pub_date) if pub_date else 'N/A'
        line = f"- Title: {item.get('title', 'N/A')}\n  URL: {item.get('link', 'N/A')}\n  Snippet: {summary}\n  Source Feed: {item.get('source_feed', 'N/A')}"
        lines.append(line)
    return "\n".join(lines)

# Modified function signature to accept config
def filter_and_tag_items(items, config):
    """Uses the Gemini API to filter and tag items based on relevance, using the specified model from config.

    Args:
        items: List of item dictionaries from ingestion.
        config: The loaded configuration dictionary.

    Returns:
        A list of filtered and tagged item dictionaries (parsed from JSON), or None if failed.
    """
    if not items:
        logger.warning("No items provided for filtering and tagging.")
        return []

    # Get the model name from config
    model_name = config.get('gemini_models', {}).get('FILTERING_MODEL', 'gemini-2.0-flash-lite') # Default fallback updated

    items_text = format_items_for_prompt(items)
    prompt = FILTERING_TAGGING_PROMPT_TEMPLATE.format(items_text=items_text)

    logger.info(f"Sending {len(items)} items to Gemini model '{model_name}' for filtering/tagging...")

    # Use the centralized call function
    response = _make_gemini_call_with_tracking(
        model_name=model_name,
        prompt=prompt,
        task_description="Filtering and Tagging"
    )

    if not response:
        logger.error("Gemini call for filtering/tagging failed after retries.")
        return None

    try:
        raw_json = response.text
        # logger.debug(f"Raw JSON response from Gemini for filtering:\n{raw_json}")

        # Clean the response - Gemini might add markdown backticks or prefix
        cleaned_json = raw_json.strip().strip('`').strip()
        if cleaned_json.lower().startswith('json'):
            cleaned_json = cleaned_json[4:].strip() # Remove potential leading 'json' prefix (case-insensitive)

        # Parse the JSON response
        filtered_items = json.loads(cleaned_json)
        logger.info(f"Successfully received and parsed {len(filtered_items)} filtered items from Gemini ({model_name}).")
        return filtered_items

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON response from Gemini for filtering ({model_name}): {e}")
        logger.error(f"Problematic response snippet: {response.text[:500]}...") # Log snippet of bad response
        return None
    except Exception as e:
        # Catch unexpected errors during response processing
        logger.error(f"An error occurred processing the Gemini response for filtering ({model_name}): {e}", exc_info=True)
        return None

# --- Example Usage (for testing) - Needs Update ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Load config to get API key and model names
    try:
        from src.config_loader import load_config # Adjusted import path
        config = load_config()
        if not config:
            raise ValueError("Failed to load config")
    except (ImportError, ValueError) as e:
        print(f"Error loading config: {e}. Ensure config.yaml exists and is valid, and config_loader.py is in src.")
        print("Falling back to dummy config for testing processing.py directly.")
        # Define a minimal dummy config for standalone testing
        config = {
            'gemini_api_key': os.environ.get("GEMINI_API_KEY"), # Try to get from env var for testing
            'google_application_credentials': None,
            'gemini_models': {
                'FILTERING_MODEL': 'gemini-2.0-flash-lite' # Use the model name from config.yaml
            }
        }
        if not config['gemini_api_key']:
             print("Warning: GEMINI_API_KEY environment variable not set. Gemini calls may fail.")

    # Configure Gemini
    if not configure_gemini(api_key=config.get('gemini_api_key'), credentials_path=config.get('google_application_credentials')):
        print("Exiting due to Gemini configuration failure.")
        exit()

    # Reset token counts for the test run
    reset_token_counts()

    # Dummy items for testing
    test_items = [
        {'title': 'Google Announces New Gemini Features', 'link': 'http://google.com/gemini', 'summary': 'Google released updates to its Gemini model family, focusing on improved reasoning and code generation.', 'source_feed': 'google_blog'},
        {'title': 'Intro to LangGraph for Agentic Workflows', 'link': 'http://langchain.dev/langgraph', 'summary': 'Learn how to build stateful multi-actor applications with LangGraph, the latest addition to the LangChain ecosystem.', 'source_feed': 'langchain_blog'},
        {'title': 'OpenAI Competitor Releases New Model', 'link': 'http://competitor.com/model', 'summary': 'A new startup challenges OpenAI with a model claiming better performance on certain benchmarks.', 'source_feed': 'tech_news'},
        {'title': 'Why Python is Great for Beginners', 'link': 'http://python-basics.com', 'summary': 'An article explaining the benefits of Python for new programmers.', 'source_feed': 'coding_blog'},
        {'title': 'DeepMind Paper on AlphaFold 3', 'link': 'http://deepmind.com/af3', 'summary': 'DeepMind publishes groundbreaking research on AlphaFold 3, predicting the structure of protein complexes.', 'source_feed': 'deepmind_blog'},
    ]

    print(f"\nFiltering {len(test_items)} items using model from config...")
    # Pass the config object to the function
    filtered_results = filter_and_tag_items(test_items, config)

    if filtered_results:
        print("\n--- Filtered and Tagged Items ---")
        for item in filtered_results:
            print(json.dumps(item, indent=2))
    else:
        print("\nFailed to get filtered items from Gemini.")

    # Print final token counts for the test run
    final_counts = get_token_counts()
    print("\n--- Token Counts for Test Run ---")
    print(json.dumps(final_counts, indent=2))

    # --- Cost Calculation --- START
    print("\n--- Estimated Cost for Test Run ---")
    cost_calculated = False
    # Ensure config and necessary keys exist
    if config and 'gemini_pricing' in config and 'gemini_models' in config:
        # Get the specific model used in this test run (FILTERING_MODEL)
        model_used = config.get('gemini_models', {}).get('FILTERING_MODEL')
        pricing_info = config.get('gemini_pricing', {}).get(model_used)

        if model_used and pricing_info:
            try:
                input_price_per_m = float(pricing_info.get('input', 0))
                output_price_per_m = float(pricing_info.get('output', 0))

                prompt_tokens = final_counts.get('prompt_tokens', 0)
                # Assuming candidates_tokens maps to output tokens for pricing
                candidates_tokens = final_counts.get('candidates_tokens', 0)

                input_cost = (prompt_tokens / 1_000_000) * input_price_per_m
                output_cost = (candidates_tokens / 1_000_000) * output_price_per_m
                total_cost = input_cost + output_cost

                print(f"Model Used: {model_used}")
                print(f"Input Price (per 1M tokens): ${input_price_per_m:.4f}")
                print(f"Output Price (per 1M tokens): ${output_price_per_m:.4f}")
                print(f"Input Cost: ${input_cost:.6f}")
                print(f"Output Cost: ${output_cost:.6f}")
                print(f"Total Estimated Cost: ${total_cost:.6f}")
                cost_calculated = True
            except (ValueError, TypeError) as e:
                 print(f"Warning: Could not parse pricing info for model '{model_used}'. Check format in config.yaml. Error: {e}")
            except Exception as e:
                 print(f"Warning: An unexpected error occurred during cost calculation: {e}")
        else:
            if not model_used:
                print("Warning: FILTERING_MODEL not found in config['gemini_models'] for cost calculation.")
            elif not pricing_info:
                print(f"Warning: Pricing information not found for model '{model_used}' in config['gemini_pricing'].")

    if not cost_calculated:
        print("Could not calculate cost. Ensure 'gemini_pricing' and model entry exist in config.yaml and config loaded successfully.")
    # --- Cost Calculation --- END 