import google.generativeai as genai
import logging
from textwrap import dedent
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Assuming Gemini is configured in processing.py or main.py
# from .processing import get_gemini_model # Or pass model instance

logger = logging.getLogger(__name__)

SUMMARIZATION_ANALYSIS_PROMPT_TEMPLATE = dedent("""
    For the following AI news item/article (Title, URL, Content Snippet/Text), provide a structured analysis tailored for a busy, technical CTO:

    Title: {title}
    URL: {url}
    Content Snippet: {content_snippet}

    Output Format (Use Markdown):
    ### {title}
    **Source:** {url}
    **Summary:** (3-4 sentence concise explanation of the core news/concept based on the snippet).
    **Key Technical Insight:** (Based SOLELY on the snippet, what is the specific technical innovation, method, or detail mentioned? If none is clear, state that.).
    **Market/Competitive Relevance:** (Based SOLELY on the snippet, potential impact on Google, OpenAI, Anthropic, the broader AI market, or competitors? If none is clear, state that.).
    **Actionable Idea/Question for CTO's Startup:** (Based SOLELY on the snippet, how could this potentially be leveraged? What experiment could be run? What strategic question does this raise? If none is clear, state that.).
    ---
""")

def _summarize_single_item(item, gemini_model, retries=2, delay=3):
    """Generates summary and analysis for a single item using Gemini."""
    if not gemini_model:
        logger.error(f"Gemini model not available for summarizing item: {item.get('title')}")
        return item.get('url'), None # Return URL to identify which failed

    # Prepare the prompt
    # TODO: Consider fetching full content here if desired and feasible
    # For now, we use the justification or original summary if available
    content_snippet = item.get('justification', item.get('summary', 'No content snippet available.'))
    # Truncate snippet if too long for the prompt context window
    if len(content_snippet) > 2000:
        content_snippet = content_snippet[:1997] + '...'

    prompt = SUMMARIZATION_ANALYSIS_PROMPT_TEMPLATE.format(
        title=item.get('title', 'N/A'),
        url=item.get('url', 'N/A'),
        content_snippet=content_snippet
    )

    logger.debug(f"Requesting summary for: {item.get('title')}")

    for attempt in range(retries):
        try:
            response = gemini_model.generate_content(prompt)

            if not response.parts:
                 logger.warning(f"Gemini summary response has no parts for '{item.get('title')}' (attempt {attempt + 1}/{retries}). Finish reason: {response.prompt_feedback.block_reason if response.prompt_feedback else 'N/A'}")
                 if attempt < retries - 1:
                     time.sleep(delay)
                     continue
                 else:
                     logger.error(f"Gemini summarization failed for '{item.get('title')}' after multiple attempts due to empty/blocked response.")
                     return item.get('url'), None # Failed

            summary_text = response.text
            # logger.debug(f"Generated summary for '{item.get('title')}':\n{summary_text}")
            return item.get('url'), summary_text # Return URL and summary

        except Exception as e:
            logger.error(f"Error summarizing item '{item.get('title')}' (attempt {attempt + 1}/{retries}): {e}", exc_info=True)
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
            else:
                logger.error(f"Failed to summarize '{item.get('title')}' after multiple API errors.")
                return item.get('url'), None # Failed

    return item.get('url'), None # Should not be reached

def summarize_and_analyze(items, gemini_model, num_news, num_tutorials, max_workers=3):
    """Selects top items, generates summaries/analyses, and separates them.

    Args:
        items: List of FILTERED and TAGGED item dictionaries from processing.
        gemini_model: An initialized Gemini GenerativeModel instance.
        num_news: Max number of general news/research items to summarize.
        num_tutorials: Max number of tutorial items to summarize.
        max_workers: Max concurrent API calls for summarization.

    Returns:
        A tuple: (list_of_news_summaries, list_of_tutorial_summaries)
        Each list contains Markdown strings for the summarized items.
    """
    if not items:
        logger.warning("No items provided for summarization.")
        return [], []
    if not gemini_model:
        logger.error("Gemini model not provided or initialized for summarization.")
        return [], []

    # Sort items by relevance score (descending)
    items.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

    # Separate tutorials from other content
    tutorial_items = [item for item in items if item.get('content_type') == 'Tutorial/Guide']
    other_items = [item for item in items if item.get('content_type') != 'Tutorial/Guide']

    # Select top N news/research and top M tutorials
    selected_news = other_items[:num_news]
    selected_tutorials = tutorial_items[:num_tutorials]
    items_to_summarize = selected_news + selected_tutorials

    if not items_to_summarize:
        logger.info("No relevant items selected for summarization.")
        return [], []

    logger.info(f"Summarizing top {len(selected_news)} news/other items and {len(selected_tutorials)} tutorial items...")

    summaries = {} # Store summaries keyed by URL
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(_summarize_single_item, item, gemini_model): item.get('url')
            for item in items_to_summarize
        }

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result_url, summary_text = future.result()
                if summary_text:
                    summaries[result_url] = summary_text
                else:
                    logger.warning(f"Failed to get summary for URL: {url}")
            except Exception as exc:
                logger.error(f"URL {url} generated an exception during summarization future processing: {exc}", exc_info=True)

    # Separate the generated summaries back into news and tutorials
    news_summaries_md = [summaries[item['url']] for item in selected_news if item['url'] in summaries]
    tutorial_summaries_md = [summaries[item['url']] for item in selected_tutorials if item['url'] in summaries]

    logger.info(f"Generated {len(news_summaries_md)} news summaries and {len(tutorial_summaries_md)} tutorial summaries.")

    return news_summaries_md, tutorial_summaries_md

# --- Example Usage (for testing) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Load config (assuming .env exists)
    from config_loader import load_config
    config = load_config()

    # Configure Gemini (requires API Key or ADC setup)
    from processing import configure_gemini, get_gemini_model
    if not configure_gemini(api_key=config.get('gemini_api_key'), credentials_path=config.get('google_application_credentials')):
        print("Exiting due to Gemini configuration failure.")
        exit()

    model = get_gemini_model()
    if not model:
        print("Exiting because Gemini model could not be initialized.")
        exit()

    # Dummy filtered items (output similar to processing.py)
    test_filtered_items = [
        {"url": "http://google.com/gemini", "title": "Google Announces New Gemini Features", "source": "google_blog", "relevance_score": 9, "justification": "Direct update on Gemini models.", "content_type": "Company Update", "keywords": ["gemini", "google ai", "llm update"]},
        {"url": "http://langchain.dev/langgraph", "title": "Intro to LangGraph for Agentic Workflows", "source": "langchain_blog", "relevance_score": 8, "justification": "Relevant tech (LangGraph) for building agents.", "content_type": "Tutorial/Guide", "keywords": ["langgraph", "langchain", "agents", "python"]},
        {"url": "http://deepmind.com/af3", "title": "DeepMind Paper on AlphaFold 3", "source": "deepmind_blog", "relevance_score": 7, "justification": "Significant Google research, less immediately applicable to startup.", "content_type": "Research Paper Abstract", "keywords": ["deepmind", "alphafold", "proteins", "research"]},
        {"url": "http://competitor.com/model", "title": "OpenAI Competitor Releases New Model", "source": "tech_news", "relevance_score": 8, "justification": "Important market/competitor info.", "content_type": "Market/Competitor Info", "keywords": ["llm", "competitor", "openai", "startup"]},
        {"url": "http://tutorial-site.com/vector-db", "title": "Getting Started with Vector Databases", "source": "coding_blog", "relevance_score": 6, "justification": "Useful concept, but potentially basic for CTO.", "content_type": "Tutorial/Guide", "keywords": ["vector database", "embeddings", "tutorial"]}
    ]

    num_news_config = 2
    num_tutorials_config = 1

    print(f"\nSummarizing {num_news_config} news and {num_tutorials_config} tutorial items...")
    news_summaries, tutorial_summaries = summarize_and_analyze(
        test_filtered_items,
        model,
        num_news=num_news_config,
        num_tutorials=num_tutorials_config
    )

    print("\n--- News/Other Summaries ---")
    if news_summaries:
        for summary in news_summaries:
            print(summary)
    else:
        print("No news summaries generated.")

    print("\n--- Feed Tutorial Summaries ---")
    if tutorial_summaries:
        for summary in tutorial_summaries:
            print(summary)
    else:
        print("No feed tutorial summaries generated.") 