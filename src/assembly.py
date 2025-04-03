import logging
import datetime
import re
import html # For escaping
import markdown # Import the markdown library

logger = logging.getLogger(__name__)

# --- Helper Functions (May need adjustments for HTML) ---

def extract_text_from_html(html_string, label):
    """Extracts text content following a specific bolded label within a <p> tag."""
    # Regex to find <p><strong>Label:</strong> Content</p>
    # It captures the content part, handling potential whitespace and HTML entities
    pattern = re.compile(rf"<p><strong>{re.escape(label)}:</strong>\\s*(.*?)\\s*</p>", re.IGNORECASE | re.DOTALL)
    match = pattern.search(html_string)
    if match:
        # Basic unescaping for common entities, more robust parsing might be needed for complex HTML
        text = match.group(1).strip()
        text = html.unescape(text)
        # Remove potential leftover simple tags if needed, e.g., from unexpected model output
        text = re.sub(r"<[^>]+>", "", text)
        return text
    return None

def get_tutorial_topic_from_html(generated_tutorial_html):
    """Extracts the tutorial topic from the H2 tag in the generated tutorial HTML."""
    if not generated_tutorial_html:
        return "N/A"
    # Look for the pattern like: <h2 ...>🛠️ Skill Up Tutorial: [Topic]</h2>
    match = re.search(r"<h2[^>]*>.*?Skill Up Tutorial:\\s*(.*?)</h2>", generated_tutorial_html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback if the exact pattern isn't found
    match = re.search(r"<h2[^>]*>(.*?)</h2>", generated_tutorial_html, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip() # Return the whole H2 content as fallback
    return "Unknown Topic"

# --- Main Assembly Function (Generates HTML) ---

def assemble_digest(news_items_data, feed_tutorials_data, generated_tutorial_md, selected_tutorial_topic):
    """Assembles the final HTML digest from the components with improved styling and overview section."""
    now = datetime.datetime.now()
    # Format like: April 3, 2025
    date_str = now.strftime("%B %d, %Y")

    # Data format from summarization: [{'url':..., 'title':..., 'type':..., 'summary':..., 'insight':..., 'angle':..., 'move':...}, ...]
    # Tutorial is still Markdown string: generated_tutorial_md

    # --- Convert Tutorial Markdown to HTML ---
    generated_tutorial_html = ""
    # Use the passed-in topic, handle None case
    tutorial_topic_display = selected_tutorial_topic if selected_tutorial_topic else "No custom tutorial today." [cite: 158]
    if generated_tutorial_md: # Rename generated_tutorial_md to generated_tutorial_html
        try:
            # REMOVE OR COMMENT OUT THIS BLOCK STARTING HERE [cite: 161]
            # generated_tutorial_html = markdown.markdown(
            #     generated_tutorial_md,
            #     extensions=['fenced_code', 'tables', 'sane_lists', 'codehilite'] # Added codehilite
            # )
            # REMOVE OR COMMENT OUT THIS BLOCK ENDING HERE

            # Assign the raw HTML directly (assuming the variable name is updated)
            generated_tutorial_html = generated_tutorial_html # Or whatever the input variable is named

            # This regex might still be needed if the generator adds an H2 you don't want,
            # but it should operate on the raw HTML, not the result of a markdown conversion.
            # Consider coordinating whether the generator or assembly adds the H2.
            generated_tutorial_html = re.sub(r'<h2(?: id="[^\"]*")?>.*?Skill Up Tutorial:.*?</h2>', '', generated_tutorial_html, count=1, flags=re.IGNORECASE | re.DOTALL).strip() [cite: 163]

        except Exception as e:
            logger.error(f"Failed to process generated tutorial HTML: {e}") # Update error message
            generated_tutorial_html = "<p><em>Error processing tutorial content.</em></p>"
            tutorial_topic_display = "Processing Error" # Update error state [cite: 164]


    # --- Start HTML Document ---
    html_parts = []
    html_parts.append("<!DOCTYPE html>")
    html_parts.append("<html>")
    html_parts.append("<head>")
    html_parts.append("<meta charset=\"UTF-8\">")
    html_parts.append(f"<title>AI Daily Digest - {date_str}</title>")
    # Updated CSS for better spacing, code blocks, etc.
    html_parts.append("""<style>
        body { font-family: 'Segoe UI', 'Roboto', 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0; background-color: #f8f9fa; color: #24292e; } /* Updated base color */
        .container { width: 95%; max-width: 800px; margin: 20px auto; background-color: #ffffff; border: 1px solid #dfe2e5; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 8px rgba(0,0,0,0.05); } /* Adjusted border/shadow */
        .header { background-color: #0366d6; color: #ffffff; padding: 25px 30px; text-align: center; border-bottom: 5px solid #005cc5; } /* GitHub blue */
        .header h1 { margin: 0; font-size: 28px; font-weight: 600; }
        .header p { margin: 5px 0 0; font-size: 16px; font-style: italic; opacity: 0.9; }
        .overview { background-color: #f6f8fa; padding: 15px 25px; margin: 25px; border-left: 4px solid #0366d6; border-radius: 4px; } /* Lighter blue */
        .overview h3 { margin-top: 0; margin-bottom: 10px; color: #005cc5; font-size: 18px; }
        .overview ul { margin: 0; padding-left: 20px; }
        .overview li { margin-bottom: 5px; }
        .section { padding: 20px 30px; border-bottom: 1px solid #eaecef; } /* Lighter border */
        .section:last-child { border-bottom: none; }
        .section h2 { background-color: #f6f8fa; padding: 12px 20px; margin: -20px -30px 20px -30px; font-size: 20px; font-weight: 600; color: #24292e; border-bottom: 1px solid #eaecef; display: flex; align-items: center; } /* Lighter header */
        .section h2 img.google-icon { margin-right: 8px; }
        .item { margin-bottom: 25px; padding-bottom: 25px; border-bottom: 1px dashed #d1d5da; } /* Slightly darker dashed border */
        .item:last-child { margin-bottom: 0; padding-bottom: 0; border-bottom: none; }
        .item h3 { margin-top: 0; margin-bottom: 5px; font-size: 18px; color: #0366d6; font-weight: 600; } /* GitHub blue link color */
        .item p { margin-top: 5px; margin-bottom: 12px; font-size: 15px; color: #24292e; }
        .item p strong { color: #24292e; font-weight: 600; }
        .item a { color: #0366d6; text-decoration: none; }
        .item a:hover { text-decoration: underline; }
        .source-link { font-size: 0.9em; color: #586069; margin-top: -8px !important; margin-bottom: 15px !important; word-break: break-all; } /* GitHub secondary text color */
        .google-icon { width: 16px; height: 16px; vertical-align: middle; }
        .actionable-ideas-list ul { list-style-type: disc; padding-left: 20px; margin-top: 10px;}
        .actionable-ideas-list li { background-color: transparent; margin-bottom: 10px; padding: 0; border-left: none; border-radius: 0px; }
        .actionable-ideas-list li em { color: #586069; font-size: 0.9em; display: block; margin-top: 4px;}
        .market-pulse-list ul { list-style-type: disc; padding-left: 20px; }
        .market-pulse-list li { margin-bottom: 8px; }
        .market-pulse-list li .source-title { color: #586069; font-size: 0.9em; display: block; margin-top: 2px;} /* C.7 */
        .footer { text-align: center; padding: 20px; font-size: 12px; color: #586069; background-color: #f6f8fa; border-top: 1px solid #eaecef; }

        /* Styles for code blocks - aiming for VS Code Light+ look (GitHub inspired) */
        .codehilite { background: #f6f8fa; border: 1px solid #dfe2e5; padding: 12px 15px; border-radius: 6px; overflow-x: auto; font-family: Consolas, 'SFMono-Regular', 'Liberation Mono', Menlo, monospace; font-size: 14px; margin: 1em 0; line-height: 1.45; }
        .codehilite pre { margin: 0; padding: 0; background: transparent; border: none; font-family: inherit; font-size: inherit; white-space: pre; word-wrap: normal; } /* Ensure pre doesn't add extra styles */
        /* Pygments Classes - Based on GitHub Light theme */
        .codehilite .hll { background-color: #fffbdd; } /* Highlighted line */
        .codehilite .c { color: #6a737d; font-style: italic; } /* Comment */
        .codehilite .c1 { color: #6a737d; font-style: italic; } /* Comment.Single */
        .codehilite .cs { color: #6a737d; font-style: italic; } /* Comment.Special */
        .codehilite .k { color: #d73a49; } /* Keyword */
        .codehilite .kc { color: #d73a49; } /* Keyword.Constant */
        .codehilite .kd { color: #d73a49; } /* Keyword.Declaration */
        .codehilite .kn { color: #d73a49; } /* Keyword.Namespace */
        .codehilite .kp { color: #d73a49; } /* Keyword.Pseudo */
        .codehilite .kr { color: #d73a49; } /* Keyword.Reserved */
        .codehilite .kt { color: #d73a49; } /* Keyword.Type */
        .codehilite .m { color: #005cc5; } /* Literal.Number */
        .codehilite .mf { color: #005cc5; } /* Literal.Number.Float */
        .codehilite .mh { color: #005cc5; } /* Literal.Number.Hex */
        .codehilite .mi { color: #005cc5; } /* Literal.Number.Integer */
        .codehilite .mo { color: #005cc5; } /* Literal.Number.Oct */
        .codehilite .s { color: #032f62; } /* Literal.String */
        .codehilite .sa { color: #032f62; } /* Literal.String.Affix */
        .codehilite .sb { color: #032f62; } /* Literal.String.Backtick */
        .codehilite .sc { color: #032f62; } /* Literal.String.Char */
        .codehilite .dl { color: #032f62; } /* Literal.String.Delimiter */
        .codehilite .sd { color: #032f62; font-style: italic; } /* Literal.String.Doc */
        .codehilite .s2 { color: #032f62; } /* Literal.String.Double */
        .codehilite .se { color: #005cc5; } /* Literal.String.Escape */
        .codehilite .sh { color: #032f62; } /* Literal.String.Heredoc */
        .codehilite .si { color: #032f62; } /* Literal.String.Interpol */
        .codehilite .sx { color: #032f62; } /* Literal.String.Other */
        .codehilite .sr { color: #032f62; } /* Literal.String.Regex */
        .codehilite .s1 { color: #032f62; } /* Literal.String.Single */
        .codehilite .ss { color: #032f62; } /* Literal.String.Symbol */
        .codehilite .na { color: #005cc5; } /* Name.Attribute */
        .codehilite .nb { color: #005cc5; } /* Name.Builtin */
        .codehilite .nc { color: #6f42c1; } /* Name.Class */
        .codehilite .no { color: #005cc5; } /* Name.Constant */
        .codehilite .nd { color: #6f42c1; } /* Name.Decorator */
        .codehilite .ni { color: #005cc5; } /* Name.Entity */
        .codehilite .ne { color: #d73a49; font-weight: bold; } /* Name.Exception */
        .codehilite .nf { color: #6f42c1; } /* Name.Function */
        .codehilite .nl { color: #d73a49; } /* Name.Label */
        .codehilite .nn { color: #6f42c1; } /* Name.Namespace */
        .codehilite .nt { color: #22863a; } /* Name.Tag */
        .codehilite .nv { color: #e36209; } /* Name.Variable */
        .codehilite .ow { color: #d73a49; font-weight: bold; } /* Operator.Word */
        .codehilite .w { color: #bbbbbb; } /* Text.Whitespace */
        .codehilite .bp { color: #005cc5; } /* Name.Builtin.Pseudo */
        .codehilite .fm { color: #6f42c1; } /* Name.Function.Magic */
        .codehilite .py { color: #24292e; } /* Name */
        .codehilite .vc { color: #e36209; } /* Name.Variable.Class */
        .codehilite .vg { color: #e36209; } /* Name.Variable.Global */
        .codehilite .vi { color: #e36209; } /* Name.Variable.Instance */
        .codehilite .vm { color: #6f42c1; } /* Name.Variable.Magic */
    </style>""")
    html_parts.append("</head>")
    html_parts.append("<body>")
    html_parts.append("<div class=\"container\">")

    # --- Header ---
    html_parts.append("<div class=\"header\">")
    html_parts.append(f"<h1>🚀 AI Daily Digest</h1>")
    html_parts.append(f"<p>{date_str}</p>")
    html_parts.append("</div>")

    # --- ✨ Today's Overview Section ✨ ---
    html_parts.append("<div class=\"overview\">")
    html_parts.append("<h3>Today's Highlights:</h3>")
    html_parts.append("<ul>")
    html_parts.append(f"<li>Analysis of <strong>{len(news_items_data)} key AI developments</strong>.</li>")
    # Use the tutorial_topic_display variable
    html_parts.append(f"<li>Skill up tutorial on: <strong>{html.escape(tutorial_topic_display)}</strong>.</li>")
    # TODO: Optional theme detection could be added here later
    html_parts.append("</ul>")
    # Add Jump Links / TOC (C10)
    html_parts.append("<p style=\"font-size: 0.9em; margin-top: 15px;\">Jump to: ")
    links = [
        '<a href="#headlines">Headlines</a>',
        '<a href="#tutorial">Tutorial</a>',
        '<a href="#guides">Guides</a>',
        '<a href="#spotlight">Google Spotlight</a>',
        '<a href="#market">Market</a>',
        '<a href="#actions">Actionable Ideas</a>'
    ]
    html_parts.append(" | ".join(links))
    html_parts.append("</p>")
    html_parts.append("</div>")

    # --- Helper to format a single item ---
    def format_item_html(item_data):
        parts = ["<div class='item'>"]
        escaped_title = html.escape(item_data.get('title', 'N/A'))
        item_url = item_data.get('url', '#')
        # Removed emoji from item H3 (B6)
        parts.append(f"<h3>{escaped_title}</h3>")
        parts.append(f"<p class='source-link'><a href=\"{item_url}\" target=\"_blank\">{item_url}</a></p>")

        summary = item_data.get('summary')
        if summary:
             # Escape summary content, ensure no leading/trailing spaces or nbsp; (B6)
             summary_clean = html.escape(summary.strip()).replace('&amp;nbsp;', ' ').replace('nbsp;', ' ')
             parts.append(f"<p><strong>Summary:</strong> {summary_clean.strip()}</p>")

        insight = item_data.get('insight')
        if insight:
             insight_clean = html.escape(insight.strip()).replace('&amp;nbsp;', ' ').replace('nbsp;', ' ')
             parts.append(f"<p><strong>💡 Key Technical Insight:</strong> {insight_clean.strip()}</p>")

        angle = item_data.get('angle')
        if angle:
             angle_clean = html.escape(angle.strip()).replace('&amp;nbsp;', ' ').replace('nbsp;', ' ')
             parts.append(f"<p><strong>📊 The Competitive Angle:</strong> {angle_clean.strip()}</p>")

        move = item_data.get('move')
        if move:
             move_clean = html.escape(move.strip()).replace('&amp;nbsp;', ' ').replace('nbsp;', ' ')
             parts.append(f"<p><strong>🚀 Your Potential Move:</strong> {move_clean.strip()}</p>")

        parts.append("</div>")
        # No <hr> tag is added here, spacing/dividers handled by CSS
        return "\n".join(parts)

    # --- Top Headlines/Insights (News & Research) ---
    html_parts.append("<div class=\"section\">")
    # Add id for TOC (C10)
    html_parts.append(f'<h2 id="headlines">📰 Top Headlines & Insights</h2>')
    if news_items_data:
        for item_data in news_items_data:
            html_parts.append(format_item_html(item_data))
    else:
        html_parts.append("<p><em>No relevant news items found today.</em></p>")
    html_parts.append("</div>")

    # --- Skill Up Tutorial (Generated) ---
    html_parts.append("<div class=\"section\">")
    html_parts.append(f'<h2 id="tutorial">🧑‍🏫 Skill Up: Custom Tutorial - {html.escape(tutorial_topic_display)}</h2>') # This adds the H2
    if generated_tutorial_html:
        # Insert the (now correctly handled) HTML directly [cite: 260]
        html_parts.append(generated_tutorial_html)
    else:
        html_parts.append("<p><em>Tutorial generation failed or no topic selected today.</em></p>")
    html_parts.append("</div>")

    # --- Feed Tutorials ---
    html_parts.append("<div class=\"section\">")
    # Add id for TOC (C10)
    html_parts.append(f'<h2 id="guides">⚙️ Guides & Tutorials From Your Feeds</h2>')
    if feed_tutorials_data:
        for item_data in feed_tutorials_data:
             html_parts.append(format_item_html(item_data))
    else:
        html_parts.append("<p><em>No relevant tutorial items found in feeds today.</em></p>")
    html_parts.append("</div>")

    # --- Google Spotlight ---
    google_items_data_filtered = []
    google_keywords = ['google', 'gemini', 'deepmind', 'vertex', 'gcp', 'tensorflow']
    # Filter from all items (news + tutorials) to catch any Google-related guide too
    all_analyzed_items = news_items_data + feed_tutorials_data
    for item_data in all_analyzed_items:
        title_lower = item_data.get('title', '').lower()
        url_lower = item_data.get('url', '').lower()
        summary_lower = item_data.get('summary', '').lower() if item_data.get('summary') else ''
        insight_lower = item_data.get('insight', '').lower() if item_data.get('insight') else ''

        # Check keywords in title, url, summary, or insight
        is_google_related = False
        for keyword in google_keywords:
            if keyword in title_lower or keyword in url_lower or keyword in summary_lower or keyword in insight_lower:
                is_google_related = True
                break
        if is_google_related:
            google_items_data_filtered.append(item_data)

    html_parts.append("<div class=\"section\">")
    # Add id for TOC (C10)
    html_parts.append(f'<h2 id="spotlight"><img src="https://www.google.com/favicon.ico" class="google-icon" alt="G"> Google Spotlight</h2>')
    if google_items_data_filtered:
        # Display as a linked list (B4)
        html_parts.append("<ul>")
        for item_data in google_items_data_filtered:
            escaped_title = html.escape(item_data.get('title', 'N/A'))
            item_url = item_data.get('url', '#')
            html_parts.append(f'<li><a href="{item_url}" target="_blank">📰 {escaped_title}</a></li>')
        html_parts.append("</ul>")
    else:
        html_parts.append("<p><em>No specific Google-related news or guides found in today's items.</em></p>")
    html_parts.append("</div>")

    # --- Market Pulse ---
    market_pulse_points = []
    all_items_data = news_items_data + feed_tutorials_data
    processed_urls_for_market = set()

    for item_data in all_items_data:
        angle = item_data.get('angle')
        url = item_data.get('url')
        title = item_data.get('title', 'Source')

        if angle and url not in processed_urls_for_market:
            title_str = f" (from: <em>{html.escape(title)}</em>)" if title else ""
            # Improved formatting for source reference (B5)
            market_pulse_points.append(f"<li>{html.escape(angle.strip())} &ndash; <a href=\"{url}\" style='font-size: 0.9em; color: #6c757d;'>Source</a></li>")
            if url: processed_urls_for_market.add(url)

    html_parts.append("<div class=\"section market-pulse-list\">") # Added class for styling
    # Add id for TOC (C10)
    html_parts.append(f'<h2 id="market">📈 Market Pulse</h2>')
    # Add intro sentence (B5)
    html_parts.append("<p><em>Key market shifts and competitive observations today include:</em></p>")
    if market_pulse_points:
        html_parts.append("<ul>")
        html_parts.extend(market_pulse_points)
        html_parts.append("</ul>")
    else:
        html_parts.append("<p><em>No specific market analysis points identified in today's items.</em></p>")
    html_parts.append("</div>")

    # --- Actionable Ideas & Questions ---
    actionable_moves = []
    for item_data in news_items_data: # Focus on news items for actionable project ideas
        move = item_data.get('move')
        url = item_data.get('url')
        title = item_data.get('title', 'N/A')
        # Filter out the default "no specific application" message (C7)
        if move and move != "No specific project application identified for this item.":
            actionable_moves.append({'text': move.strip(), 'url': url, 'title': title})

    html_parts.append("<div class=\"section actionable-ideas-list\">") # Added class for styling
    # Add id for TOC (C10)
    html_parts.append(f'<h2 id="actions">⚡ Actionable Ideas & Questions</h2>')
    if actionable_moves:
        html_parts.append("<ul>")
        for move_data in actionable_moves:
            # Improved formatting with link to original item
            html_parts.append(f"<li>{html.escape(move_data['text'])}<br><em>(Context: <a href=\"{move_data['url']}\">{html.escape(move_data['title'])}</a>)</em></li>")
        html_parts.append("</ul>")
    else:
        # Display appropriate message if no context-specific moves were found (C7)
        html_parts.append("<p><em>No specific project applications identified in today's items based on provided context.</em></p>")
    html_parts.append("</div>")

    # --- Footer ---
    html_parts.append("<div class=\"footer\">")
    html_parts.append("Generated by AI Digest Agent.")
    html_parts.append("</div>")

    # --- End HTML Document ---
    html_parts.append("</div>") # Close container
    html_parts.append("</body>")
    html_parts.append("</html>")

    logger.info("HTML Digest assembly complete.")
    return "\n".join(html_parts)

# --- Example Usage ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Dummy data using the new structured format
    dummy_news_data = [
        {
            'url': 'http://google.com/gemini',
            'title': 'Google Announces New Gemini Features',
            'type': 'Company Update',
            'summary': 'Google updated Gemini for better reasoning and added new vision capabilities.',
            'insight': 'Improved multi-modal processing allows integrating text and image analysis seamlessly.',
            'angle': 'This directly competes with OpenAI\'s GPT-4 vision capabilities, aiming to keep Google relevant in enterprise AI.',
            'move': 'Evaluate the new Gemini Vision API endpoint for automating visual content moderation in your app.'
        },
        {
            'url': 'http://competitor.com/model',
            'title': 'OpenAI Competitor Releases New Model',
            'type': 'Market/Competitor Info',
            'summary': 'Startup X released model Y, claiming state-of-the-art performance.',
            'insight': 'Model Y utilizes a novel sparse attention mechanism, potentially reducing compute costs.',
            'angle': 'Increases pressure on both OpenAI and Google, especially if cost/performance ratio is favorable.',
            'move': 'Benchmark model Y\'s API (if available) against your current LLM for a core text generation task, focusing on latency and cost.'
        }
    ]
    dummy_feed_tutorials_data = [
         {
            'url': 'http://langchain.dev/langgraph',
            'title': 'Intro to LangGraph for Agentic Workflows',
            'type': 'Tutorial/Guide',
            'summary': 'LangGraph provides tools for building stateful, multi-actor agent applications.',
            'insight': 'It uses a graph structure where nodes are computation steps and edges represent control flow, enabling cycles and complex state management.',
            'angle': 'Enhances the LangChain ecosystem, offering a more structured approach compared to simpler agent loops, potentially competing with frameworks like AutoGen.',
            'move': 'Refactor one of your existing complex agent workflows using LangGraph to see if it simplifies the state logic and improves maintainability.'
        }
    ]
    # Generated tutorial now expected as MARKDOWN
    dummy_generated_tutorial_md = """## 🛠️ Skill Up Tutorial: LangGraph Basics

**Objective:** Learn to build a simple LangGraph agent.
**Core Concepts:** Graphs for state, Nodes for functions/LLMs, Edges for control flow.
**Prerequisites:** `langgraph`, `langchain_openai`

**Step-by-Step Implementation:**
1. **Setup:**
   ```python
   import os
   from langgraph.graph import StateGraph, END
   from typing import TypedDict, Annotated
   import operator
   # Add API key setup
   # os.environ["OPENAI_API_KEY"] = "your_key_here"
   ```
   *Explanation:* Import necessary components.

2. **Define State:**
   ```python
   class AgentState(TypedDict):
       messages: Annotated[list, operator.add]
   ```
   *Explanation:* Define the structure to hold messages passed between nodes.

3. **Define Nodes:**
   ```python
   def call_model(state):
       # Replace with actual LLM call
       print("Calling model...")
       response = "Action: Do something" # Dummy response
       return {"messages": [response]}

   def take_action(state):
       # Replace with actual action execution
       print("Taking action...")
       result = "Action Result: OK"
       return {"messages": [result]}
   ```
   *Explanation:* Define functions representing agent steps (model call, action).

4. **Build Graph:**
   ```python
   workflow = StateGraph(AgentState)
   workflow.add_node("agent", call_model)
   workflow.add_node("action", take_action)
   workflow.set_entry_point("agent")
   # Simple conditional edge (replace with real logic)
   workflow.add_conditional_edges("agent", lambda x: "action" if "Action: " in x['messages'][-1] else END)
   workflow.add_edge("action", END)
   app = workflow.compile()
   ```
   *Explanation:* Construct the graph, defining nodes and transitions.

5. **Running the Example:**
   ```python
   if __name__ == "__main__":
       inputs = {"messages": ["User query"]}
       for output in app.stream(inputs):
           for key, value in output.items():
               print(f"Output from node '{key}': {value}")
   ```

**Key Considerations:** Error handling within nodes is crucial.
**Next Steps / Further Learning:** [LangGraph Docs](https://langchain.dev/docs/langgraph)
    """ # End Markdown

    final_digest_html = assemble_digest(dummy_news_data, dummy_feed_tutorials_data, dummy_generated_tutorial_md, "LangGraph Basics")

    print("\n--- Assembled HTML Digest --- ")
    # print(final_digest_html) # Avoid printing very long string to console

    # Save to a file for inspection
    try:
        with open("digest_preview.html", "w", encoding="utf-8") as f:
            f.write(final_digest_html)
        print("\nHTML Digest saved to digest_preview.html")
    except Exception as e:
        print(f"\nError saving HTML digest preview: {e}")

# Removed old Markdown helper functions as they are replaced by HTML parsing
# def extract_section(markdown_text, section_title): ...
# def extract_title_link(markdown_text): ... 