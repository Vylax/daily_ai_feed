# AI Personalized News & Learning Agent

This project implements an automated pipeline using Python and the Google Gemini API to create a personalized daily AI news digest and learning resource for a technically-focused user (e.g., a CTO).

## Features

*   Fetches content from a configurable list of RSS feeds.
*   Uses the Gemini API to filter, tag, and prioritize content based on user preferences (Google AI, LLMs, MLOps, etc.).
*   Summarizes and analyzes the most relevant news items, providing technical insights and actionable ideas.
*   Generates a custom, pedagogical tutorial on a rotating AI topic using the Gemini API.
*   Assembles a structured Markdown digest with sections for headlines, tutorials, Google news, market pulse, and actionable ideas.
*   Delivers the digest daily via email (supports SMTP and SendGrid - SendGrid requires uncommenting code and installing the library).
*   Scheduled daily execution using the `schedule` library.
*   Configuration managed via a `.env` file.

## Prerequisites

*   Python 3.10 or higher
*   Git (for cloning, if applicable)
*   Access to the Google Gemini API (either an API Key or configured Google Cloud Application Default Credentials)
*   Email account credentials (for SMTP) or a SendGrid account/API key.

## Setup Instructions

1.  **Clone the Repository (if applicable):**
    ```bash
    git clone <repository-url>
    cd <repository-directory> 
    ```
    *(If you received the code directly, just navigate to the project directory)*

2.  **Create and Activate a Virtual Environment (Recommended):**
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate

    # macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    *   Copy the example environment file: `cp .env.example .env` (or `copy .env.example .env` on Windows).
    *   **Edit the `.env` file** and fill in the required values:
        *   **Gemini API:**
            *   Provide your `GEMINI_API_KEY` **OR**
            *   Ensure `GOOGLE_APPLICATION_CREDENTIALS` points to your service account key file if using ADC.
        *   **RSS Feeds:** Keep the defaults or customize the comma-separated `RSS_FEEDS` list.
        *   **Processing:** Adjust `NUM_NEWS_ITEMS_TO_SUMMARIZE`, `NUM_FEED_TUTORIALS_TO_INCLUDE`, and `INITIAL_TUTORIAL_TOPICS` if desired.
        *   **Email:**
            *   Set `EMAIL_PROVIDER` (`smtp` or `sendgrid`).
            *   Enter the `RECIPIENT_EMAIL` and `SENDER_EMAIL`.
            *   If using `smtp`, provide `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, and `SMTP_PASSWORD`. **Important:** For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.
            *   If using `sendgrid`, provide your `SENDGRID_API_KEY` (and uncomment the SendGrid code in `src/email_utils.py` and potentially install `pip install sendgrid`).

5.  **Run the Agent:**
    ```bash
    python main.py
    ```
    *   The script will start the scheduler. By default, it's set to run the pipeline daily at 6:00 AM local time.
    *   The first run will occur at the next scheduled time. You can uncomment the immediate execution lines in `main.py` (`if __name__ == "__main__":` block) for testing.
    *   Logs will be created in the `logs/` directory.

## Project Structure

```
.
├── .env.example          # Example environment variables
├── .env                  # Your actual environment variables (Create this!)
├── main.py               # Main script: Orchestration and scheduling
├── requirements.txt      # Python dependencies
├── logs/                 # Log files and saved digests (created on run)
├── src/                  # Source code modules
│   ├── __init__.py
│   ├── assembly.py         # Assembles the final Markdown digest
│   ├── config_loader.py    # Loads configuration from .env
│   ├── email_utils.py      # Handles sending email (SMTP/SendGrid)
│   ├── ingestion.py        # Fetches and parses RSS feeds
│   ├── processing.py       # Filters/tags items using Gemini API (Prompt 1)
│   ├── summarization.py    # Summarizes/analyzes items using Gemini API (Prompt 2)
│   └── tutorial_generator.py # Generates custom tutorials using Gemini API (Prompt 3)
└── README.md             # This file
```

## Customization

*   **Feeds:** Modify the `RSS_FEEDS` list in your `.env` file.
*   **Tutorial Topics:** Change the `INITIAL_TUTORIAL_TOPICS` in `.env`.
*   **Prompts:** Edit the prompt templates directly within the `processing.py`, `summarization.py`, and `tutorial_generator.py` files to tailor the AI's behavior.
*   **Digest Structure:** Modify `src/assembly.py` to change the layout or sections of the Markdown digest.
*   **Schedule:** Change the `schedule_time` variable in `main.py`.

## Token Cost Estimation (Gemini API)

Running this pipeline incurs costs based on the usage of the Google Gemini API. Costs are calculated based on the number of input and output tokens processed by the model.

**API Calls Per Run:**

1.  **Filtering/Tagging (`filter_and_tag_items`):** 1 call.
    *   *Input:* Base prompt + text from *all* fetched RSS items (titles, links, snippets). Can be large.
    *   *Output:* JSON list of ~15-20 prioritized items.
2.  **Summarization/Analysis (`summarize_and_analyze`):** N + M calls (default: 7 + 5 = 12 calls).
    *   *Input (per call):* Base prompt + title/link/snippet of one filtered item.
    *   *Output (per call):* Markdown analysis for that item.
3.  **Tutorial Generation (`generate_tutorial`):** 1 call.
    *   *Input:* Base prompt + selected tutorial topic.
    *   *Output:* Full Markdown tutorial.

**Estimating Costs:**

*   **Filtering:** The input cost depends heavily on the number of RSS feeds and items fetched. If you fetch 50 items with an average of 100 tokens each for title/snippet, that's 5000 input tokens plus the prompt (~500 tokens). Output might be ~1500-2000 tokens for the JSON.
*   **Summarization:** 12 calls * (Prompt ~200 tokens + Input Item ~100 tokens) = ~3600 input tokens. 12 calls * (~250 output tokens/summary) = ~3000 output tokens.
*   **Tutorial:** Prompt ~500 tokens + Topic ~10 tokens = ~510 input tokens. Output can vary significantly (1000-3000+ tokens depending on complexity).

**Total Rough Estimate (Example):**
*   Input: ~500 (Filter Prompt) + ~5000 (Filter Items) + ~3600 (Summaries) + ~510 (Tutorial) = **~9610 input tokens**
*   Output: ~1700 (Filter JSON) + ~3000 (Summaries) + ~2000 (Tutorial) = **~6700 output tokens**

**Disclaimer:** This is a **very rough estimate**. Actual usage will vary based on feed content, item lengths, and tutorial complexity.

**Recommendations:**

*   **Check Official Pricing:** Refer to the official [Google AI pricing page](https://ai.google.dev/pricing) for the specific model you are using (e.g., `gemini-1.5-flash-latest`). Prices are per 1000 tokens and differ for input vs. output.
*   **Monitor Usage:** Check your Google Cloud Console for actual API usage and costs.
*   **Optimize:**
    *   Use cost-effective models like `gemini-1.5-flash-latest` where appropriate.
    *   Limit the number of RSS feeds in `.env`.
    *   Reduce `NUM_NEWS_ITEMS_TO_SUMMARIZE` and `NUM_FEED_TUTORIALS_TO_INCLUDE` in `.env`.
    *   Refine prompts to be more concise if possible.
    *   Consider implementing more robust caching or only fetching full article content (which would increase summarization costs) for highly relevant items. 