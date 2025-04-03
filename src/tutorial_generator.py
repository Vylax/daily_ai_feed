import google.generativeai as genai
import logging
import random
from textwrap import dedent
import time
import json # Added for example usage
import os # Added for example usage

# Import the centralized Gemini call function and token tracking
from src.processing import _make_gemini_call_with_tracking

logger = logging.getLogger(__name__)

# --- State for Topic Rotation ---
# In a more robust system, this state might be stored externally (db, file)
_tutorial_topics = []
_current_topic_index = 0

def load_tutorial_topics(initial_topics):
    """Initializes the list of tutorial topics."""
    global _tutorial_topics, _current_topic_index
    _tutorial_topics = initial_topics[:]
    _current_topic_index = 0
    logger.info(f"Loaded tutorial topics: {_tutorial_topics}")

def select_tutorial_topic():
    """Selects the next tutorial topic from the list (simple rotation)."""
    global _current_topic_index
    if not _tutorial_topics:
        logger.warning("No tutorial topics loaded or available.")
        return None

    selected_topic = _tutorial_topics[_current_topic_index]
    _current_topic_index = (_current_topic_index + 1) % len(_tutorial_topics) # Rotate index
    logger.info(f"Selected tutorial topic: {selected_topic}")
    return selected_topic

# --- Prompt Definition ---
TUTORIAL_GENERATION_PROMPT_TEMPLATE = dedent("""
    You are an expert AI educator creating a practical, concise tutorial for a highly technical CTO (Strong Python/AI background, high IQ, familiar with ML/LLMs, weak theory, time-poor) who wants to learn how to implement **{topic}**.

    Generate a step-by-step tutorial focusing on practical application and core concepts. Assume the user has Python 3.9+ and necessary libraries (mention them clearly). Output should be well-formatted Markdown.

    Structure the tutorial using Markdown:

    ## 🛠️ Skill Up Tutorial: {topic}

    **Objective:** (State clearly what the user will achieve by following this tutorial).
    **Core Concepts:** (Briefly explain 1-3 essential ideas SPECIFIC to implementing this task. Keep it extremely concise and practical, avoid deep theory).
    **Prerequisites:** (List specific Python libraries and their versions needed, e.g., `langgraph==0.0.30`, `google-generativeai`). Assume Python itself is installed.
    **Step-by-Step Implementation:**
        1.  **Setup:** Import necessary libraries.
        2.  **[Step 2 Name]:** Minimal code for the first part.
            ```python
            # Code for step 2
            ```
            *Explanation:* Briefly explain the purpose of this code block.
        3.  **[Step 3 Name]:** Next logical code block.
            ```python
            # Code for step 3
            ```
            *Explanation:* Briefly explain this code block.
        ... (Continue with minimal, logical steps)
        N.  **Running the Example:** Show how to run the complete minimal example.
            ```python
            # Example usage / main execution block
            if __name__ == "__main__":
                # ... setup and run the example ...
                pass
            ```
    **Key Considerations:** (Mention 1-2 important practical points, e.g., "API Key Management", "Handling potential errors", "State management in loops").
    **Next Steps / Further Learning:** (Provide 1-2 links to official documentation or a highly relevant advanced resource/article).

    Make the tutorial highly pedagogical, actionable, and digestible within 10-15 minutes reading/implementation time. Prioritize clarity, runnable code, and practical explanations over exhaustive detail. Ensure code blocks are complete where possible or clearly indicate dependencies between steps.
""")

# Modified signature to accept config
def generate_tutorial(topic, config):
    """Generates a Markdown tutorial for the given topic using the configured Gemini model."""
    if not topic:
        logger.error("No topic provided for tutorial generation.")
        return None

    # Get the model name from config
    gemini_config = config.get('gemini_models', {})
    model_name = gemini_config.get('TUTORIAL_MODEL', 'gemini-2.0-flash') # Default fallback

    prompt = TUTORIAL_GENERATION_PROMPT_TEMPLATE.format(topic=topic)
    logger.info(f"Requesting tutorial generation for topic: {topic} using {model_name}")

    # Use the centralized call function
    # Note: GenerationConfig (like temperature) would need to be handled within
    # _make_gemini_call_with_tracking or passed through if customization is needed per call type.
    response = _make_gemini_call_with_tracking(
        model_name=model_name,
        prompt=prompt,
        task_description=f"Tutorial Generation ({topic})"
        # retries=3, delay=10 # Can potentially override defaults here if needed
    )

    if not response or not response.text:
        logger.error(f"Gemini call for tutorial generation on '{topic}' failed or returned empty response.")
        return None

    tutorial_markdown = response.text
    logger.info(f"Successfully generated tutorial for topic: {topic}")
    # logger.debug(f"Generated tutorial Markdown (start):\n{tutorial_markdown[:500]}...")
    return tutorial_markdown

# --- Example Usage (for testing) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Load config
    try:
        # Assume config_loader is in the parent directory (src)
        from src.config_loader import load_config
        config = load_config()
        if not config:
            raise ValueError("Failed to load config")
    except (ImportError, ValueError, FileNotFoundError) as e:
        print(f"Error loading config: {e}. Using dummy config for testing tutorial_generator.py.")
        # Define a minimal dummy config for standalone testing
        config = {
            'gemini_api_key': os.environ.get("GEMINI_API_KEY"), # Try to get from env var for testing
            'google_application_credentials': None,
            'gemini_models': {
                 'TUTORIAL_MODEL': 'gemini-2.0-flash' # Use correct model name
            },
            'initial_tutorial_topics': [
                "LangGraph basics",
                "Label Studio intro",
                "Understanding Attention Mechanisms",
                "Fine-tuning a small LLM"
            ]
        }
        if not config['gemini_api_key']:
            print("Warning: GEMINI_API_KEY environment variable not set. Gemini calls may fail.")

    # Configure Gemini (needed for the imported tracking function)
    from src.processing import configure_gemini, reset_token_counts, get_token_counts
    if not configure_gemini(api_key=config.get('gemini_api_key'), credentials_path=config.get('google_application_credentials')):
        print("Exiting due to Gemini configuration failure.")
        exit()

    # Reset token counts for test run
    reset_token_counts()

    # Load topics from config
    load_tutorial_topics(config.get('initial_tutorial_topics', [
        "Fallback Topic 1", # Provide fallback if config loading failed
        "Fallback Topic 2"
    ]))

    # Select and generate a tutorial
    selected_topic = select_tutorial_topic()

    if selected_topic:
        # Pass config to the function
        generated_markdown = generate_tutorial(selected_topic, config)
        if generated_markdown:
            print(f"\n--- Generated Tutorial for: {selected_topic} ---")
            print(generated_markdown)

            # Test selection rotation
            print("\n--- Selecting next topic ---")
            next_topic = select_tutorial_topic()
            print(f"Next topic would be: {next_topic}")
        else:
            print(f"\nFailed to generate tutorial for {selected_topic}.")
    else:
        print("\nNo tutorial topic selected.")

    # Print final token counts for the test run
    final_counts = get_token_counts()
    print("\n--- Token Counts for Test Run ---")
    print(json.dumps(final_counts, indent=2)) 