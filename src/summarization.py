import google.generativeai as genai
import logging
from textwrap import dedent
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
import html # For escaping

# Import the centralized Gemini call function and token tracking
from src.processing import _make_gemini_call_with_tracking

logger = logging.getLogger(__name__)

# Prompt for the lightweight summarization model
SUMMARIZATION_LITE_PROMPT_TEMPLATE = dedent("""
    Concisely summarize the core news or concept from the following AI-related item (Title, URL, Content Snippet) in 3-4 sentences.
    Focus on the main takeaway.

    Title: {title}
    URL: {url}
    Content Snippet: {content_snippet}

    Output ONLY the summary text, with no additional formatting or labels.
""")

# Prompt for the deeper analysis model, requesting specific fields
# Updated to reinforce clean output for each field.
ANALYSIS_PROMPT_TEMPLATE = dedent("""
    Analyze the following AI news item for a technical CTO, based on the provided snippet and its initial summary.
    Focus ONLY on information derivable from the text provided.

    Title: {title}
    URL: {url}
    Content Snippet: {content_snippet}
    Basic Summary: {basic_summary}

    Provide the following analysis points. Output ONLY the text content for each point, prefixed with the specific label EXACTLY as shown below:
    💡 Key Technical Insight: [Text content]
    📊 The Competitive Angle: [Text content]
    🚀 Your Potential Move: [Text content]

    Ensure each point starts on a new line. Do NOT include any HTML tags, markdown formatting, or extra explanations.
""")

def _extract_analysis_field(text, label):
    """Extracts text following a specific label on a new line."""
    # Match label at the start of a line, capture everything after it until the next label or end of string
    pattern = re.compile(rf"^{re.escape(label)}\s*(.*?)(?=\n(?:💡|��|🚀)|\\Z)", re.MULTILINE | re.DOTALL)
    match = pattern.search(text)
    if match:
        # Clean up the captured text: strip whitespace, remove potential code blocks/extra notes
        content = match.group(1).strip()
        # Remove potential markdown code blocks or html blocks incorrectly added by LLM
        content = re.sub(r"```[a-zA-Z]*\n.*?\n```", "", content, flags=re.DOTALL)
        content = re.sub(r"<[^>]+>", "", content) # Basic HTML tag stripping
        # Remove common non-committal phrases if they are the *only* content
        non_committal_patterns = [
            r"\[analysis generation failed\]",
            r"none",
            r"n/a",
            r"none is clear",
            r"none clear",
            r"no actionable idea"
        ]
        if any(re.fullmatch(pattern, content, re.IGNORECASE) for pattern in non_committal_patterns):
            return None # Treat non-committal as empty

        return html.unescape(content).strip() # Unescape HTML entities like &amp;
    return None

def _process_single_item(item, config):
    """Generates summary & analysis for a single item, returning structured data."""
    gemini_config = config.get('gemini_models', {})
    # Use 2.0 models as defaults, matching user preference and config
    lite_model_name = gemini_config.get('SUMMARIZATION_LITE_MODEL', 'gemini-2.0-flash-lite')
    analysis_model_name = gemini_config.get('ANALYSIS_MODEL', 'gemini-2.0-flash')

    item_title = item.get('title', 'N/A')
    item_url = item.get('url', 'N/A')
    item_type = item.get('content_type', 'News') # Default to News

    # Prepare the snippet
    content_snippet = item.get('justification', item.get('summary', 'No content snippet available.'))
    if len(content_snippet) > 2000: # Keep snippet reasonable for both models
        content_snippet = content_snippet[:1997] + '...'

    # --- 1. Generate Basic Summary (Lite Model) ---
    logger.debug(f"Requesting basic summary for: {item_title} using {lite_model_name}")
    summary_prompt = SUMMARIZATION_LITE_PROMPT_TEMPLATE.format(
        title=item_title,
        url=item_url,
        content_snippet=content_snippet
    )
    summary_response = _make_gemini_call_with_tracking(
        model_name=lite_model_name,
        prompt=summary_prompt,
        task_description=f"Basic Summary ({item_title[:30]}...)"
    )

    basic_summary = None
    if summary_response and summary_response.text:
        # Clean summary: strip, remove potential markdown/html if LLM added it
        basic_summary = summary_response.text.strip()
        basic_summary = re.sub(r"```[a-zA-Z]*\n.*?\n```", "", basic_summary, flags=re.DOTALL)
        basic_summary = re.sub(r"<[^>]+>", "", basic_summary)
        basic_summary = html.unescape(basic_summary).strip()
        logger.debug(f"Generated basic summary for: {item_title}")
    else:
        logger.warning(f"Failed to generate basic summary for: {item_title}. Proceeding without it.")
        basic_summary = None # Use None if failed

    # --- 2. Generate Deeper Analysis (Reasoning Model) ---
    logger.debug(f"Requesting analysis for: {item_title} using {analysis_model_name}")
    analysis_prompt = ANALYSIS_PROMPT_TEMPLATE.format(
        title=item_title,
        url=item_url,
        content_snippet=content_snippet,
        basic_summary=basic_summary or "[Summary generation failed]" # Pass placeholder if summary failed
    )
    analysis_response = _make_gemini_call_with_tracking(
        model_name=analysis_model_name,
        prompt=analysis_prompt,
        task_description=f"Deeper Analysis ({item_title[:30]}...)"
    )

    analysis_data = {
        'insight': None,
        'angle': None,
        'move': None
    }
    if analysis_response and analysis_response.text:
        raw_analysis_text = analysis_response.text.strip()
        logger.debug(f"Raw analysis output for {item_title}: {raw_analysis_text[:200]}...")
        # Extract each field using the helper
        analysis_data['insight'] = _extract_analysis_field(raw_analysis_text, "💡 Key Technical Insight:")
        analysis_data['angle'] = _extract_analysis_field(raw_analysis_text, "📊 The Competitive Angle:")
        analysis_data['move'] = _extract_analysis_field(raw_analysis_text, "🚀 Your Potential Move:")
        logger.debug(f"Parsed analysis for {item_title}: {analysis_data}")
    else:
        logger.warning(f"Failed to generate analysis for: {item_title}.")
        # analysis_data fields remain None

    # --- 3. Combine into Structured Dictionary ---
    result_data = {
        'url': item_url,
        'title': item_title,
        'type': item_type,
        'summary': basic_summary,
        'insight': analysis_data['insight'],
        'angle': analysis_data['angle'],
        'move': analysis_data['move'],
    }

    return result_data # Return dictionary

# Modified signature to accept config
# Updated return type
def summarize_and_analyze(items, config, num_news, num_tutorials, max_workers=3):
    """Selects top items, generates summaries/analyses (as structured data), and separates them.

    Args:
        items: List of FILTERED and TAGGED item dictionaries from processing.
        config: The loaded configuration dictionary.
        num_news: Max number of general news/research items to summarize.
        num_tutorials: Max number of tutorial items to summarize.
        max_workers: Max concurrent API calls for summarization.

    Returns:
        A tuple: (list_of_news_data, list_of_tutorial_data)
        Each list contains dictionaries with keys:
        'url', 'title', 'type', 'summary', 'insight', 'angle', 'move'
    """
    if not items:
        logger.warning("No items provided for summarization.")
        return [], []

    # Sort items by relevance score (descending)
    # Ensure 'relevance_score' exists and is numeric, default to 0 if not
    items.sort(key=lambda x: float(x.get('relevance_score', 0) if isinstance(x.get('relevance_score'), (int, float, str)) and str(x.get('relevance_score')).replace('.','',1).isdigit() else 0), reverse=True)

    # Separate tutorials from other content
    # Ensure 'content_type' exists
    tutorial_items = [item for item in items if item.get('content_type') == 'Tutorial/Guide']
    other_items = [item for item in items if item.get('content_type') != 'Tutorial/Guide']

    # Select top N news/research and top M tutorials
    selected_news = other_items[:num_news]
    selected_tutorials = tutorial_items[:num_tutorials]
    items_to_process = selected_news + selected_tutorials

    if not items_to_process:
        logger.info("No relevant items selected for summarization/analysis.")
        return [], []

    logger.info(f"Summarizing/analyzing top {len(selected_news)} news/other items and {len(selected_tutorials)} tutorial items (generating structured data)...")

    processed_results = {} # Store results keyed by URL: {dict_from__process_single_item}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Pass config to the worker function
        future_to_url = {
            executor.submit(_process_single_item, item, config): item.get('url')
            for item in items_to_process
        }

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            if url is None: # Should not happen if items have URLs, but safety check
                logger.warning("Future completed for an item without a URL.")
                continue
            try:
                # Returns the full dictionary now
                result_dict = future.result()
                if result_dict:
                    # Check if essential data is present before storing
                    if result_dict.get('url') and result_dict.get('title'):
                        processed_results[url] = result_dict
                    else:
                        logger.warning(f"Processed item for {url} missing essential keys (url/title). Skipping.")
                else:
                    # Worker function logs failures, but we note it here too
                    logger.warning(f"Did not receive valid data dictionary for URL: {url}")
            except Exception as exc:
                logger.error(f"URL {url} generated an exception during processing future: {exc}", exc_info=True)

    # Separate the generated dictionaries back into news and tutorials
    news_data = [
        processed_results[item['url']]
        for item in selected_news
        if item.get('url') in processed_results
    ]
    tutorial_data = [
        processed_results[item['url']]
        for item in selected_tutorials
        if item.get('url') in processed_results
    ]

    logger.info(f"Generated structured data for {len(news_data)} news/other items and {len(tutorial_data)} tutorial items.")

    # Return lists of dictionaries
    return news_data, tutorial_data

# --- Example Usage (for testing) ---
if __name__ == '__main__':
    import os
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Load config
    try:
        from src.config_loader import load_config # Adjusted import
        config = load_config()
        if not config:
            raise ValueError("Failed to load config")
    except (ImportError, ValueError, FileNotFoundError) as e:
        print(f"Error loading config: {e}. Using dummy config for testing summarization.py.")
        # Define a minimal dummy config for standalone testing
        config = {
            'gemini_api_key': os.environ.get("GEMINI_API_KEY"), # Try to get from env var for testing
            'google_application_credentials': None,
            'gemini_models': {
                'SUMMARIZATION_LITE_MODEL': 'gemini-2.0-flash-lite', # Use correct model names
                'ANALYSIS_MODEL': 'gemini-2.0-flash'
            },
            'num_news_items_to_summarize': 2,
            'num_feed_tutorials_to_include': 1
        }
        if not config['gemini_api_key']:
            print("Warning: GEMINI_API_KEY environment variable not set. Gemini calls may fail.")

    # Configure Gemini (required by the imported processing function)
    from src.processing import configure_gemini, reset_token_counts, get_token_counts
    if not configure_gemini(api_key=config.get('gemini_api_key'), credentials_path=config.get('google_application_credentials')):
        print("Exiting due to Gemini configuration failure.")
        exit()

    # Reset token counts for the test run
    reset_token_counts()

    # Dummy filtered items (output similar to processing.py)
    test_filtered_items = [
        {"url": "http://google.com/gemini", "title": "Google Announces New Gemini Features", "source": "google_blog", "relevance_score": 9, "justification": "Direct update on Gemini models. Includes details on new vision capabilities.", "content_type": "Company Update", "keywords": ["gemini", "google ai", "llm update"]},
        {"url": "http://langchain.dev/langgraph", "title": "Intro to LangGraph for Agentic Workflows", "source": "langchain_blog", "relevance_score": 8, "justification": "Relevant tech (LangGraph) for building agents. Shows graph structure.", "content_type": "Tutorial/Guide", "keywords": ["langgraph", "langchain", "agents", "python"]},
        {"url": "http://deepmind.com/af3", "title": "DeepMind Paper on AlphaFold 3", "source": "deepmind_blog", "relevance_score": 7, "justification": "Significant Google research, less immediately applicable to startup.", "content_type": "Research Paper Abstract", "keywords": ["deepmind", "alphafold", "proteins", "research"]},
        {"url": "http://competitor.com/model", "title": "OpenAI Competitor Releases New Model", "source": "tech_news", "relevance_score": 8, "justification": "Important market/competitor info. Model uses sparse attention.", "content_type": "Market/Competitor Info", "keywords": ["llm", "competitor", "openai", "startup"]},
        {"url": "http://tutorial-site.com/vector-db", "title": "Getting Started with Vector Databases", "source": "coding_blog", "relevance_score": 6, "justification": "Useful concept, but potentially basic for CTO.", "content_type": "Tutorial/Guide", "keywords": ["vector database", "embeddings", "tutorial"]}
    ]

    # Configurable numbers
    num_news_config = config.get('num_news_items_to_summarize', 2) # Example defaults
    num_tutorials_config = config.get('num_feed_tutorials_to_include', 1)

    print(f"\nSummarizing/Analyzing {num_news_config} news and {num_tutorials_config} tutorial items (Structured Data output)...")
    # Pass config to the function
    # Returns list of dicts now
    news_data, tutorial_data = summarize_and_analyze(
        test_filtered_items,
        config, # Pass config
        num_news=num_news_config,
        num_tutorials=num_tutorials_config
    )

    print("\n--- News/Other Summaries & Analyses (Structured Data) ---")
    if news_data:
        # Use json.dumps for pretty printing the dict output
        print(json.dumps(news_data, indent=2))
    else:
        print("No news data generated.")

    print("\n--- Feed Tutorial Summaries & Analyses (Structured Data) ---")
    if tutorial_data:
        print(json.dumps(tutorial_data, indent=2))
    else:
        print("No feed tutorial data generated.")

    # Print final token counts for the test run
    final_counts = get_token_counts()
    print("\n--- Token Counts for Test Run ---")
    print(json.dumps(final_counts, indent=2)) 