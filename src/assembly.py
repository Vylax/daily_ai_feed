import logging
import datetime
import re
import html # For escaping
import markdown # Import the markdown library
# Import Pygments for code highlighting with inline styles
import pygments
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

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

def assemble_digest(news_items_data, feed_tutorials_data, generated_tutorial_html, selected_tutorial_topic, code_theme='monokai', dark_code=True):
    """Assembles the final HTML digest from the components with improved styling and overview section.
    
    Args:
        news_items_data: List of news items data
        feed_tutorials_data: List of tutorial items from feeds
        generated_tutorial_html: HTML content for the tutorial section
        selected_tutorial_topic: Topic of the tutorial
        code_theme: Pygments theme name for code highlighting (default: 'monokai')
        dark_code: Whether to use dark background for code blocks (default: True)
    """
    now = datetime.datetime.now()
    # Format like: April 3, 2025
    date_str = now.strftime("%B %d, %Y")

    # Data format from summarization: [{'url':..., 'title':..., 'type':..., 'summary':..., 'insight':..., 'angle':..., 'move':...}, ...]
    # Tutorial is HTML string: generated_tutorial_html

    # --- Process Tutorial HTML ---
    processed_tutorial_html = ""
    # Use the passed-in topic, handle None case
    tutorial_topic_display = selected_tutorial_topic if selected_tutorial_topic else "No custom tutorial today."

    if generated_tutorial_html:
        try:
            # The tutorial is already in HTML format
            # Simply use it directly
            processed_tutorial_html = generated_tutorial_html
            
            # Remove the H2 header if it exists as the section will have its own header
            processed_tutorial_html = re.sub(r'<h2(?: id="[^\"]*")?>.*?Skill Up Tutorial:.*?</h2>', '', processed_tutorial_html, count=1, flags=re.IGNORECASE | re.DOTALL).strip()
            
            # Remove any leftover Markdown code fences from the beginning/end
            processed_tutorial_html = re.sub(r'^```html\s*', '', processed_tutorial_html)
            processed_tutorial_html = re.sub(r'```\s*$', '', processed_tutorial_html)
            
            # Setup Pygments for syntax highlighting with inline styles
            lexer = PythonLexer()
            
            # VS Code / Cursor style selection
            # You can use different styles:
            # Light themes:
            # - 'vs' - Most like Visual Studio/VS Code default light theme
            # - 'xcode' - Similar to VS Code light with better contrast
            # - 'friendly' - Good readability, similar to some VS Code themes
            # Dark themes:
            # - 'monokai' - Dark theme with vibrant colors (similar to VS Code Monokai)
            # - 'dracula' - Popular dark theme with purple accents
            # - 'one-dark' - Similar to VS Code dark+ theme
            formatter = HtmlFormatter(style=code_theme, noclasses=True)
            
            # Configure background and styling based on dark_code setting
            if dark_code:
                code_bg = "#272822"
                code_border = "#181a1f"
                code_text_color = "#abb2bf"
            else:
                code_bg = "#ffffff"
                code_border = "#d4d4d4"
                code_text_color = "inherit"
            
            # Find all code blocks and replace them with syntax highlighted versions
            def highlight_code_block(match):
                # Extract the code between <code> and </code> tags
                code = match.group(2).strip()
                # Apply syntax highlighting with inline styles
                highlighted_code = pygments.highlight(code, lexer, formatter)
                # Make sure we're not using the pre/code tags that Pygments adds
                highlighted_code = re.sub(r'<pre.*?>(.*?)</pre>', r'\1', highlighted_code, flags=re.DOTALL)
                # Wrap in our own pre/code tags with proper styling
                return f'<div style="background: {code_bg}; border: 1px solid {code_border}; padding: 12px 15px; border-radius: 3px; overflow-x: auto; font-family: Consolas, \'SFMono-Regular\', \'Liberation Mono\', Menlo, monospace; font-size: 14px; margin: 1em 0; line-height: 1.45; color: {code_text_color};"><pre style="margin: 0; line-height: 125%; background: transparent; border: none;"><code class="language-python">{highlighted_code}</code></pre></div>'
            
            # Apply the highlighting to all code blocks
            processed_tutorial_html = re.sub(
                r'<(pre|div class="codehilite"><pre)><code class="language-python">(.*?)</code></pre>(</div>)?', 
                highlight_code_block, 
                processed_tutorial_html, 
                flags=re.DOTALL
            )
        except Exception as e:
            logger.error(f"Failed to process tutorial HTML: {e}")
            processed_tutorial_html = "<p><em>Error processing tutorial content.</em></p>"
            tutorial_topic_display = "Conversion Error" # Keep this error state

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
    # Use HTML H2 tag directly here, not from Markdown conversion
    # Add id for TOC (C10)
    html_parts.append(f'<h2 id="tutorial">🧑‍🏫 Skill Up: Custom Tutorial - {html.escape(tutorial_topic_display)}</h2>')
    if processed_tutorial_html:
         # Insert the HTML converted from Markdown (with H2 already removed)
         html_parts.append(processed_tutorial_html)
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


# --- Test Code Highlighting Function (For Development Only) ---
def test_code_highlighting():
    """Test function to verify the Pygments syntax highlighting is working correctly"""
    code_snippet = '''
import os
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
# Add API key setup
# os.environ["OPENAI_API_KEY"] = "your_key_here"

def example_function(param1: str, param2: int = 42) -> bool:
    """Example function with docstring."""
    if param1 == "test" and param2 > 0:
        return True
    return False
'''
    lexer = PythonLexer()
    formatter = HtmlFormatter(style='vs', noclasses=True)
    highlighted_code = pygments.highlight(code_snippet, lexer, formatter)
    
    # Example of how this would be used in the digest
    html_output = f'''
<div style="background: #ffffff; border: 1px solid #d4d4d4; padding: 12px 15px; border-radius: 3px; overflow-x: auto; font-family: Consolas, 'SFMono-Regular', 'Liberation Mono', Menlo, monospace; font-size: 14px; margin: 1em 0; line-height: 1.45;">
{highlighted_code}
</div>
'''
    return html_output

def test_multiple_styles():
    """Generate examples of different highlighting styles to compare them."""
    code_snippet = '''
import os
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
# Add API key setup
# os.environ["OPENAI_API_KEY"] = "your_key_here"

def example_function(param1: str, param2: int = 42) -> bool:
    """Example function with docstring."""
    if param1 == "test" and param2 > 0:
        return True
    return False
'''
    lexer = PythonLexer()
    
    # Light themes
    light_styles = ['vs', 'xcode', 'friendly', 'default']
    # Dark themes
    dark_styles = ['monokai', 'dracula', 'one-dark', 'nord-darker']
    
    results = ['<h2>Light Themes</h2>']
    
    # Add light themes
    for style in light_styles:
        formatter = HtmlFormatter(style=style, noclasses=True)
        highlighted_code = pygments.highlight(code_snippet, lexer, formatter)
        
        html_output = f'''
<h3>Style: {style}</h3>
<div style="background: #ffffff; border: 1px solid #d4d4d4; padding: 12px 15px; border-radius: 3px; overflow-x: auto; font-family: Consolas, 'SFMono-Regular', 'Liberation Mono', Menlo, monospace; font-size: 14px; margin: 1em 0; line-height: 1.45;">
{highlighted_code}
</div>
'''
        results.append(html_output)
    
    # Add dark themes
    results.append('<h2>Dark Themes</h2>')
    for style in dark_styles:
        formatter = HtmlFormatter(style=style, noclasses=True)
        highlighted_code = pygments.highlight(code_snippet, lexer, formatter)
        
        # For dark themes, use dark background
        html_output = f'''
<h3>Style: {style}</h3>
<div style="background: #282c34; border: 1px solid #181a1f; padding: 12px 15px; border-radius: 3px; overflow-x: auto; font-family: Consolas, 'SFMono-Regular', 'Liberation Mono', Menlo, monospace; font-size: 14px; margin: 1em 0; line-height: 1.45; color: #abb2bf;">
{highlighted_code}
</div>
'''
        results.append(html_output)
    
    with open("syntax_highlighting_comparison.html", "w", encoding="utf-8") as f:
        f.write("<html><body style='font-family: system-ui, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px;'>" + "".join(results) + "</body></html>")
    
    return "Syntax highlighting comparison (light and dark themes) saved to syntax_highlighting_comparison.html"

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
    # Generated tutorial now expected as HTML
    dummy_generated_tutorial_html = """<h2>🛠️ Skill Up Tutorial: LangGraph Basics</h2>

<p><strong>Objective:</strong> Learn to build a simple LangGraph agent.<br>
<strong>Core Concepts:</strong> Graphs for state, Nodes for functions/LLMs, Edges for control flow.<br>
<strong>Prerequisites:</strong> <code>langgraph</code>, <code>langchain_openai</code></p>

<p><strong>Step-by-Step Implementation:</strong></p>
<ol>
   <li><strong>Setup:</strong>
   <pre><code class="language-python">
import os
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
# Add API key setup
# os.environ["OPENAI_API_KEY"] = "your_key_here"
   </code></pre>
   <em>Explanation:</em> Import necessary components.</li>

   <li><strong>Define State:</strong>
   <pre><code class="language-python">
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
   </code></pre>
   <em>Explanation:</em> Define the structure to hold messages passed between nodes.</li>
</ol>
    """ # End HTML

    # Generate regular light theme digest (default)
    final_digest_html = assemble_digest(dummy_news_data, dummy_feed_tutorials_data, dummy_generated_tutorial_html, "LangGraph Basics")

    print("\n--- Assembled Light Theme HTML Digest --- ")
    # Save the light theme version 
    try:
        with open("digest_preview_light.html", "w", encoding="utf-8") as f:
            f.write(final_digest_html)
        print("\nLight theme HTML Digest saved to digest_preview_light.html")
    except Exception as e:
        print(f"\nError saving light theme HTML digest preview: {e}")
    
    # Generate a dark theme version - for example with 'one-dark' theme
    dark_theme_digest_html = assemble_digest(
        dummy_news_data, 
        dummy_feed_tutorials_data, 
        dummy_generated_tutorial_html, 
        "LangGraph Basics", 
        code_theme='one-dark',
        dark_code=True
    )

    print("\n--- Assembled Dark Theme HTML Digest --- ")
    # Save the dark theme version
    try:
        with open("digest_preview_dark.html", "w", encoding="utf-8") as f:
            f.write(dark_theme_digest_html)
        print("\nDark theme HTML Digest saved to digest_preview_dark.html")
    except Exception as e:
        print(f"\nError saving dark theme HTML digest preview: {e}")
    
    # Generate a comparison of all available code styles
    print(test_multiple_styles())

# Removed old Markdown helper functions as they are replaced by HTML parsing
# def extract_section(markdown_text, section_title): ...
# def extract_title_link(markdown_text): ... 
