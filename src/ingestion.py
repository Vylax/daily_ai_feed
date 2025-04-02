import feedparser
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# Simple cache to avoid refetching the same URL immediately
# In a production system, consider a more robust cache (e.g., Redis, disk cache)
_fetch_cache = {}
_CACHE_EXPIRY_SECONDS = 60 * 5 # 5 minutes

def _fetch_single_feed(feed_url):
    """Fetches and parses a single RSS feed with basic error handling."""
    current_time = time.time()

    # Check cache
    if feed_url in _fetch_cache:
        last_fetch_time, cached_data = _fetch_cache[feed_url]
        if current_time - last_fetch_time < _CACHE_EXPIRY_SECONDS:
            logger.debug(f"Using cached data for {feed_url}")
            return cached_data, feed_url

    logger.info(f"Fetching feed: {feed_url}")
    items = []
    try:
        # Add a user-agent to potentially avoid blocking
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        feed_data = feedparser.parse(feed_url, request_headers=headers, etag=_fetch_cache.get(feed_url, (0, None))[1].get('etag') if feed_url in _fetch_cache else None)

        # Check for bozo flag for malformed feeds
        if feed_data.bozo:
            logger.warning(f"Feed at {feed_url} may be malformed: {feed_data.bozo_exception}")
            # Still try to process entries if possible

        # Check for HTTP status (feedparser often handles this internally, but good practice)
        if feed_data.status == 304: # Not Modified
             logger.info(f"Feed not modified (304): {feed_url}")
             # Return previously cached data if available
             if feed_url in _fetch_cache:
                 return _fetch_cache[feed_url][1]['items'], feed_url
             else:
                 return [], feed_url # No previous cache, return empty
        elif feed_data.status != 200:
            logger.error(f"Failed to fetch feed {feed_url}. Status code: {feed_data.status}")
            # Remove from cache if it failed
            if feed_url in _fetch_cache: del _fetch_cache[feed_url]
            return None, feed_url # Indicate failure

        for entry in feed_data.entries:
            item = {
                'title': entry.get('title', 'No Title'),
                'link': entry.get('link', 'No Link'),
                'published': entry.get('published_parsed') or entry.get('updated_parsed'), # Prefer structured time
                'summary': entry.get('summary') or entry.get('description', 'No Summary'), # Some feeds use description
                'source_feed': feed_url,
                'id': entry.get('id', entry.get('link')) # Unique ID for deduplication
            }
            items.append(item)

        # Update cache
        cache_data = {'items': items, 'etag': feed_data.get('etag')}
        _fetch_cache[feed_url] = (current_time, cache_data)
        logger.info(f"Successfully fetched and parsed {len(items)} items from {feed_url}")
        return items, feed_url

    except Exception as e:
        logger.error(f"Error fetching or parsing feed {feed_url}: {e}", exc_info=True)
        # Remove from cache on error
        if feed_url in _fetch_cache: del _fetch_cache[feed_url]
        return None, feed_url # Indicate failure

def fetch_all_feeds(feed_list, max_workers=5):
    """Fetches all feeds from the list concurrently and returns a list of item dicts."""
    all_items = []
    processed_ids = set() # For basic deduplication across feeds

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all feed fetch tasks
        future_to_url = {executor.submit(_fetch_single_feed, url): url for url in feed_list}

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                items, fetched_url = future.result()
                if items is not None:
                    added_count = 0
                    for item in items:
                        item_id = item.get('id') or item.get('link') # Use ID or link for dedup
                        if item_id and item_id not in processed_ids:
                            all_items.append(item)
                            processed_ids.add(item_id)
                            added_count += 1
                        elif not item_id:
                             all_items.append(item) # Add if no ID available, might be duplicate
                             added_count += 1
                        else:
                            logger.debug(f"Duplicate item skipped: {item.get('title', '')} ({item_id})")
                    logger.debug(f"Added {added_count} new items from {fetched_url}")
                else:
                    logger.warning(f"Fetching failed for URL: {url}")
            except Exception as exc:
                logger.error(f'{url} generated an exception during fetch: {exc}', exc_info=True)

    logger.info(f"Total unique items fetched across all feeds: {len(all_items)}")
    return all_items

if __name__ == '__main__':
    # Example Usage
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Example list, replace with loading from config in real use
    test_feeds = [
        "https://research.google/blog/rss/",
        "https://openai.com/news/rss.xml",
        "https://huggingface.co/blog/feed.xml",
        "http://feeds.feedburner.com/TechCrunch/artificial-intelligence", # Example non-https
        "invalid-url-example"
    ]

    fetched_items = fetch_all_feeds(test_feeds)

    if fetched_items:
        print(f"\n--- Fetched {len(fetched_items)} items ---")
        # Print details of the first few items
        for i, item in enumerate(fetched_items[:3]):
            print(f"\nItem {i+1}:")
            print(f"  Title: {item.get('title')}")
            print(f"  Link: {item.get('link')}")
            print(f"  Published: {time.strftime('%Y-%m-%d %H:%M:%S', item['published']) if item.get('published') else 'N/A'}")
            print(f"  Source: {item.get('source_feed')}")
            # print(f"  Summary: {item.get('summary', '')[:100]}...") # Keep output clean
    else:
        print("\nNo items fetched.") 