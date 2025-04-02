import google.generativeai as genai
import logging
import random
from textwrap import dedent
import time

# Assumes Gemini is configured elsewhere
# from .processing import get_gemini_model

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

def generate_tutorial(topic, gemini_model, retries=3, delay=10):
    """Generates a Markdown tutorial for the given topic using Gemini."""
    if not topic:
        logger.error("No topic provided for tutorial generation.")
        return None
    if not gemini_model:
        logger.error(f"Gemini model not available for generating tutorial on: {topic}")
        return None

    prompt = TUTORIAL_GENERATION_PROMPT_TEMPLATE.format(topic=topic)
    logger.info(f"Requesting tutorial generation for topic: {topic}")
    # logger.debug(f"Tutorial prompt (start):\n{prompt[:500]}...")

    for attempt in range(retries):
        try:
            # Increase timeout if tutorials are complex and take longer
            generation_config = genai.types.GenerationConfig(temperature=0.7) # Adjust creativity
            response = gemini_model.generate_content(prompt, generation_config=generation_config)

            if not response.parts:
                 logger.warning(f"Gemini tutorial response has no parts for '{topic}' (attempt {attempt + 1}/{retries}). Finish reason: {response.prompt_feedback.block_reason if response.prompt_feedback else 'N/A'}")
                 if attempt < retries - 1:
                     time.sleep(delay)
                     continue
                 else:
                     logger.error(f"Gemini tutorial generation failed for '{topic}' after multiple attempts due to empty/blocked response.")
                     return None # Failed

            tutorial_markdown = response.text
            logger.info(f"Successfully generated tutorial for topic: {topic}")
            # logger.debug(f"Generated tutorial Markdown (start):\n{tutorial_markdown[:500]}...")
            return tutorial_markdown

        except Exception as e:
            logger.error(f"Error generating tutorial for '{topic}' (attempt {attempt + 1}/{retries}): {e}", exc_info=True)
            if attempt < retries - 1:
                # Use longer delay for potentially more complex generation tasks
                time.sleep(delay * (attempt + 1))
            else:
                logger.error(f"Failed to generate tutorial for '{topic}' after multiple API errors.")
                return None # Failed

    return None # Should not be reached

# --- Example Usage (for testing) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Load config (assuming .env exists)
    from config_loader import load_config
    config = load_config()

    # Configure Gemini
    from processing import configure_gemini, get_gemini_model
    if not configure_gemini(api_key=config.get('gemini_api_key'), credentials_path=config.get('google_application_credentials')):
        print("Exiting due to Gemini configuration failure.")
        exit()

    model = get_gemini_model()
    if not model:
        print("Exiting because Gemini model could not be initialized.")
        exit()

    # Load topics from config
    load_tutorial_topics(config.get('initial_tutorial_topics', [
        "LangGraph basics",
        "Label Studio intro",
        "Understanding Attention Mechanisms",
        "Fine-tuning a small LLM"
        ]))

    # Select and generate a tutorial
    selected_topic = select_tutorial_topic()

    if selected_topic:
        generated_markdown = generate_tutorial(selected_topic, model)
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