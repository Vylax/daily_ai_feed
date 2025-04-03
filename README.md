# AI Personalized News & Learning Agent

This project implements an automated pipeline using Python and the Google Gemini API to create a personalized daily AI news digest and learning resource for a technically-focused user (e.g., a CTO).

## Features

*   Fetches content from a configurable list of RSS feeds.
*   **Aggressive Pre-filtering:** Filters items by publish date, keywords, and per-feed limits *before* sending to AI, reducing cost and noise (Configurable via `config.yaml`).
*   **Strategic Model Usage:** Uses different Gemini models for specific tasks (e.g., `gemini-2.0-flash-lite` for filtering/basic summary, `gemini-2.0-flash` for analysis/tutorial generation) for cost and quality optimization (Configurable via `config.yaml`).
*   Uses the Gemini API to filter, tag, and prioritize content based on user preferences (Google AI, LLMs, MLOps, etc.).
*   **Two-Step Summarization:** Generates a concise summary (lite model) and then deeper analysis including technical insights and actionable ideas (reasoning model).
*   Generates a custom, pedagogical tutorial on a rotating AI topic using the Gemini API.
*   Assembles a structured Markdown digest with sections for headlines, tutorials, Google news, market pulse, and actionable ideas, enhanced with emojis.
*   **Token Tracking & Cost Estimation:** Tracks Gemini API token usage per run and logs totals. Optionally estimates cost based on configurable pricing.
*   Delivers the digest daily via email (supports SMTP and SendGrid - SendGrid requires uncommenting code and installing the library).
*   Scheduled daily execution using the `schedule` library or runs once.
*   Configuration managed via a `config.yaml` file.
*   Includes basic unit tests for email sending (`tests/test_email.py`).

## Prerequisites

*   Python 3.10 or higher
*   Git (for cloning, if applicable)
*   Access to the Google Gemini API (either an API Key or configured Google Cloud Application Default Credentials). Ensure the specified models (e.g., `gemini-2.0-flash`, `gemini-2.0-flash-lite`) are available to your project/API key.
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
    *   Ensure you have `pip` installed.
    *   Install required libraries:
        ```bash
        pip install -r requirements.txt
        ```
        *(Make sure `requirements.txt` includes `google-generativeai`, `feedparser`, `schedule`, `markdown`, `PyYAML`, `python-dotenv`)*

4.  **Configure `config.yaml`:**
    *   Copy the example configuration file: `cp config.example.yaml config.yaml` (or `copy config.example.yaml config.yaml` on Windows).
    *   **Edit the `config.yaml` file** and fill in the required values:
        *   **Gemini API:**
            *   Provide your `gemini_api_key` **OR**
            *   Ensure `google_application_credentials` points to your service account key file path if using ADC.
        *   **RSS Feeds:** Customize the `rss_feeds` list.
        *   **Ingestion Settings:**
            *   Review and adjust `ingestion -> max_hours_since_published`.
            *   Configure `ingestion -> feed_limits` (set `default` and add specific limits for high-volume feeds by URL).
            *   Refine `ingestion -> required_keywords` or leave empty to disable keyword filtering.
            *   Add problematic feed URLs to `ingestion -> skip_feeds`.
        *   **Gemini Models:** Verify or change the model names under `gemini_models` (e.g., `FILTERING_MODEL`, `SUMMARIZATION_LITE_MODEL`, `ANALYSIS_MODEL`, `TUTORIAL_MODEL`).
        *   **(Optional) Cost Estimation:** Update `gemini_pricing` with current prices per million tokens (input/output) for the models used if you want cost estimation logging.
        *   **Processing:** Adjust `num_news_items_to_summarize`, `num_feed_tutorials_to_include`, and `initial_tutorial_topics` if desired.
        *   **Email:**
            *   Set `email_provider` (`smtp` or `sendgrid`).
            *   Enter the `recipient_email` and `sender_email`.
            *   If using `smtp`, provide `smtp_server`, `smtp_port`, and `smtp_password`. **Important:** For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.
            *   If using `sendgrid`, provide your `sendgrid_api_key` (and uncomment the SendGrid code in `src/email_utils.py` and potentially install `pip install sendgrid`).
        *   **Scheduling:** Configure `run_mode` (`schedule` or `once`), `schedule_time`, and `schedule_initial_run`.

5.  **Run the Agent:**
    ```bash
    python main.py
    ```
    *   Based on `run_mode` in `config.yaml`, the script will either run the pipeline once or start the scheduler.
    *   If scheduling, the first run may happen immediately based on `schedule_initial_run` and subsequent runs occur daily at `schedule_time`.
    *   Logs will be created in the `logs/` directory, including total token counts and estimated cost (if enabled).

6.  **Run Tests (Optional):**
    ```bash
    python -m unittest discover tests
    ```

## Project Structure

```
.
├── config.example.yaml   # Example configuration file
├── config.yaml           # Your actual configuration (Create this!)
├── main.py               # Main script: Orchestration and scheduling
├── requirements.txt      # Python dependencies
├── logs/                 # Log files and saved digests (created on run)
├── src/                  # Source code modules
│   ├── __init__.py
│   ├── assembly.py         # Assembles the final Markdown digest
│   ├── config_loader.py    # Loads configuration from config.yaml
│   ├── email_utils.py      # Handles sending email (SMTP/SendGrid)
│   ├── ingestion.py        # Fetches, pre-filters, and parses RSS feeds
│   ├── processing.py       # Filters/tags items using Gemini API, tracks tokens
│   ├── summarization.py    # Summarizes/analyzes items using Gemini API (2 steps)
│   └── tutorial_generator.py # Generates custom tutorials using Gemini API
├── tests/                # Unit tests
│   ├── __init__.py
│   └── test_email.py       # Tests for email sending logic
└── README.md             # This file
```

## Customization

*   **Configuration:** Most parameters (feeds, limits, models, schedule, emails, etc.) are controlled via `config.yaml`.
*   **Prompts:** Edit the prompt templates directly within the `processing.py`, `summarization.py`, and `tutorial_generator.py` files to tailor the AI's behavior.
*   **Digest Structure:** Modify `src/assembly.py` to change the layout or sections of the Markdown digest.

## Token Cost Estimation (Gemini API)

Running this pipeline incurs costs based on the usage of the Google Gemini API. Costs are calculated based on the number of input and output tokens processed by the configured models.

**API Calls Per Run (Typical):**

1.  **Filtering/Tagging (`filter_and_tag_items`):** 1 call using `FILTERING_MODEL` (e.g., `gemini-2.0-flash-lite`).
    *   *Input:* Base prompt + text from *pre-filtered* RSS items. Number of items significantly reduced by ingestion filtering.
    *   *Output:* JSON list of ~15-20 prioritized items.
2.  **Basic Summarization (`summarize_and_analyze`):** N calls using `SUMMARIZATION_LITE_MODEL` (e.g., `gemini-2.0-flash-lite`), where N = `num_news` + `num_tutorials`.
    *   *Input (per call):* Summary prompt + title/link/snippet of one filtered item.
    *   *Output (per call):* Basic summary text.
3.  **Deeper Analysis (`summarize_and_analyze`):** N calls using `ANALYSIS_MODEL` (e.g., `gemini-2.0-flash`), where N = `num_news` + `num_tutorials`.
    *   *Input (per call):* Analysis prompt + title/link/snippet + *basic summary*.
    *   *Output (per call):* Markdown analysis (Insight, Market, Actionable Idea).
4.  **Tutorial Generation (`generate_tutorial`):** 1 call (if topic available) using `TUTORIAL_MODEL` (e.g., `gemini-2.0-flash`).
    *   *Input:* Tutorial prompt + selected tutorial topic.
    *   *Output:* Full Markdown tutorial.

**Estimating Costs:**

*   **Pre-filtering:** The most significant cost optimization. Reduces items sent to the Filtering/Tagging model dramatically.
*   **Model Choice:** Using `gemini-2.0-flash-lite` for high-volume, simpler tasks (filtering, basic summary) reduces cost compared to using `gemini-2.0-flash` for everything.
*   **Token Tracking:** The script logs the total `prompt_tokens`, `candidates_tokens`, and `total_tokens` used per run. You can use these numbers with official pricing for accurate cost calculation.
*   **Optional Cost Estimation:** If `gemini_pricing` is configured in `config.yaml`, the script will log a rough estimated cost (based on a simplified calculation).

**Example Token Flow (Highly Variable):**
*   Ingestion fetches 1000+ items, pre-filters down to < 100 items.
*   Filtering (Lite Model): Input ~500 (Prompt) + ~80 items * ~80 tokens/item = ~6900 tokens. Output ~2000 tokens (JSON).
*   Basic Summaries (Lite Model): 12 calls * (~150 Prompt + ~100 Item Snippet) = ~3000 input tokens. Output: 12 * ~70 tokens/summary = ~840 tokens.
*   Deeper Analysis (Flash Model): 12 calls * (~200 Prompt + ~100 Item + ~70 Basic Summary) = ~4440 input tokens. Output: 12 * ~180 tokens/analysis = ~2160 tokens.
*   Tutorial (Flash Model): Input ~500 tokens. Output ~2000 tokens.
*   **Total Rough Estimate:** Input ~14840 tokens, Output ~7000 tokens. (Actuals depend heavily on content and model responses).

**Recommendations:**

*   **Check Official Pricing:** Refer to the official [Google AI pricing page](https://ai.google.dev/pricing) for `gemini-2.0-flash-lite` and `gemini-2.0-flash`.
*   **Monitor Usage:** Check your Google Cloud Console for actual API usage and costs.
*   **Tune `config.yaml`:** Adjust `ingestion` filters (hours, limits, keywords), number of summaries (`num_news`, `num_tutorials`), and `rss_feeds` to balance cost and content.
*   **Review Logs:** Check the application logs for token counts per run.
*   **Further Optimization:** Consider fetching full article text only for top 1-2 items (would require adding scraping logic, e.g., using `requests` and `BeautifulSoup4`, and increase analysis cost but potentially improve quality). 