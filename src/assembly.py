import logging
import datetime
import re

logger = logging.getLogger(__name__)

def extract_section(markdown_text, section_title):
    """Extracts a specific section (e.g., Actionable Idea) from the summary Markdown."""
    # Simple regex assuming the title is followed by ** and content ends with --- or end of string
    # This might need refinement based on actual Gemini output variations
    pattern = re.compile(rf"\*\*{section_title}:\*\*\s*(.*?)(?=\n\*\*|\n---\s*$|\Z)", re.IGNORECASE | re.DOTALL)
    match = pattern.search(markdown_text)
    if match:
        return match.group(1).strip()
    return None

def extract_title_link(markdown_text):
    """Extracts the title and link from the beginning of the summary Markdown."""
    title = None
    link = None
    title_match = re.search(r"^###\s*(.*?)\s*\n", markdown_text)
    if title_match:
        title = title_match.group(1).strip()
    link_match = re.search(r"\*\*Source:\*\*\s*<?(.*?)(?:>)?\s*\n", markdown_text) # Handle optional <>
    if link_match:
        link = link_match.group(1).strip()
    return title, link

def assemble_digest(news_items_md, feed_tutorials_md, generated_tutorial_md):
    """Assembles the final Markdown digest from the components."""
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")

    digest_parts = []

    # --- Header ---
    digest_parts.append(f"# AI Daily Digest - {date_str}")
    digest_parts.append("A curated selection of AI news, tutorials, and insights.")
    digest_parts.append("--- ")

    # --- Top Headlines/Insights (News & Research) ---
    digest_parts.append("## 📰 Top Headlines & Insights")
    if news_items_md:
        digest_parts.extend(news_items_md) # Already formatted markdown
    else:
        digest_parts.append("*No relevant news items found today.*")
    digest_parts.append("--- ")

    # --- Skill Up Tutorial (Generated) ---
    if generated_tutorial_md:
        # The generated tutorial should already have its own header
        digest_parts.append(generated_tutorial_md)
    else:
        digest_parts.append("## 🛠️ Skill Up Tutorial")
        digest_parts.append("*Tutorial generation failed or no topic selected today.*")
    digest_parts.append("--- ")

    # --- Feed Tutorials ---
    digest_parts.append("## 🎓 Tutorials From Your Feeds")
    if feed_tutorials_md:
        digest_parts.extend(feed_tutorials_md) # Already formatted markdown
    else:
        digest_parts.append("*No relevant tutorial items found in feeds today.*")
    digest_parts.append("--- ")

    # --- Google Spotlight (Filter from news_items_md) ---
    digest_parts.append("## <img src=\"https://www.google.com/favicon.ico\" width=\"16\" height=\"16\"> Google Spotlight")
    google_items = [item for item in news_items_md if 'google' in item.lower() or 'deepmind' in item.lower() or 'gemini' in item.lower() or 'vertex' in item.lower()]
    if google_items:
        digest_parts.extend(google_items)
    else:
        digest_parts.append("*No specific Google-related news found in the top items today.*")
    digest_parts.append("--- ")

    # --- Market Pulse (Filter from news_items_md) ---
    digest_parts.append("## 📈 Market Pulse")
    market_items = [item for item in news_items_md if extract_section(item, 'Market/Competitive Relevance')]
    # Could also filter based on keywords/tags if added during processing/summarization
    if market_items:
        digest_parts.extend(market_items)
    else:
        digest_parts.append("*No specific market analysis found in the top items today.*")
    digest_parts.append("--- ")

    # --- Actionable Ideas (Extract from all summarized items) ---
    digest_parts.append("## ✨ Actionable Ideas & Questions")
    actionable_ideas = []
    all_summaries = news_items_md + feed_tutorials_md
    for item_md in all_summaries:
        idea = extract_section(item_md, 'Actionable Idea/Question for CTO\'s Startup')
        title, link = extract_title_link(item_md)
        if idea and idea.lower() not in ["none", "n/a", "none is clear", "none clear", "no actionable idea could be derived solely from the provided snippet."]:
            title_str = f" (from *{title}*)" if title else ""
            link_str = f" [[Source]]({link})" if link else ""
            actionable_ideas.append(f"- {idea}{title_str}{link_str}")

    if actionable_ideas:
        digest_parts.extend(actionable_ideas)
    else:
        digest_parts.append("*No specific actionable ideas identified in today's items.*")
    digest_parts.append("--- ")

    # --- Further Reading (Links from original filtered list - optional) ---
    # This might be too noisy, consider adding only links from summarized items
    # digest_parts.append("## 📚 Further Reading Links")
    # Add logic here if needed

    logger.info("Digest assembly complete.")
    return "\n\n".join(digest_parts)

# --- Example Usage (for testing) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Dummy data (replace with actual outputs from previous steps)
    dummy_news = [
        "### Google Announces New Gemini Features\n**Source:** http://google.com/gemini\n**Summary:** Google updated Gemini for better reasoning.\n**Key Technical Insight:** Improved multi-modal processing.\n**Market/Competitive Relevance:** Keeps pace with OpenAI.\n**Actionable Idea/Question for CTO's Startup:** Explore new Gemini API endpoints for code tasks.\n---",
        "### OpenAI Competitor Releases New Model\n**Source:** http://competitor.com/model\n**Summary:** Startup X released model Y.\n**Key Technical Insight:** Claims better performance on MATH benchmark.\n**Market/Competitive Relevance:** Increases competition in the LLM space.\n**Actionable Idea/Question for CTO's Startup:** Benchmark model Y vs current solution for specific use cases.\n---"
    ]
    dummy_feed_tutorials = [
        "### Intro to LangGraph for Agentic Workflows\n**Source:** http://langchain.dev/langgraph\n**Summary:** LangGraph helps build stateful agents.\n**Key Technical Insight:** Uses graph structure for state management.\n**Market/Competitive Relevance:** Extends LangChain's capabilities for complex agent development.\n**Actionable Idea/Question for CTO's Startup:** Could LangGraph simplify our existing agent logic?\n---"
    ]
    dummy_generated_tutorial = "## 🛠️ Skill Up Tutorial: LangGraph Basics\n**Objective:** Learn to build a simple LangGraph agent.\n... (rest of tutorial markdown) ..."

    final_digest = assemble_digest(dummy_news, dummy_feed_tutorials, dummy_generated_tutorial)

    print("\n--- Assembled Digest --- ")
    print(final_digest)

    # Save to a file for inspection
    try:
        with open("digest_preview.md", "w", encoding="utf-8") as f:
            f.write(final_digest)
        print("\nDigest saved to digest_preview.md")
    except Exception as e:
        print(f"\nError saving digest preview: {e}") 