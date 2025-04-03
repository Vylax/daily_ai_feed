import feedparser
import logging
import time
import datetime # Add datetime
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
            # Return items and etag separately from cache if needed
            cached_items = cached_data.get('items', [])
            return cached_items, feed_url

    logger.info(f"Fetching feed: {feed_url}")
    items = []
    feed_etag = _fetch_cache.get(feed_url, (0, {}))[1].get('etag') if feed_url in _fetch_cache else None
    try:
        # Add a user-agent to potentially avoid blocking
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        feed_data = feedparser.parse(feed_url, request_headers=headers, etag=feed_etag)

        # Check for bozo flag for malformed feeds
        if feed_data.bozo:
            logger.warning(f"Feed at {feed_url} may be malformed: {feed_data.bozo_exception}")
            # Still try to process entries if possible

        # Check for HTTP status
        status = feed_data.get('status')
        if status == 304: # Not Modified
            logger.info(f"Feed not modified (304): {feed_url}")
            # Return previously cached items
            if feed_url in _fetch_cache:
                 return _fetch_cache[feed_url][1].get('items', []), feed_url
            else:
                 return [], feed_url # No previous cache, return empty
        # Allow other 2xx status codes as potentially successful
        elif not (status and 200 <= status < 300):
            logger.error(f"Failed to fetch feed {feed_url}. Status code: {status}")
            # Remove from cache if it failed
            if feed_url in _fetch_cache: del _fetch_cache[feed_url]
            return None, feed_url # Indicate failure

        for entry in feed_data.entries:
            # Prioritize published_parsed, then updated_parsed
            published_time = entry.get('published_parsed') or entry.get('updated_parsed')

            item = {
                'title': entry.get('title', 'No Title'),
                'link': entry.get('link', 'No Link'),
                 # Keep published as struct_time for now, handle conversion in filtering
                'published': published_time,
                'summary': entry.get('summary') or entry.get('description', 'No Summary'), # Some feeds use description
                'source_feed': feed_url,
                'id': entry.get('id', entry.get('link')) # Unique ID for deduplication
            }
            items.append(item)

        # Update cache
        new_etag = feed_data.get('etag')
        cache_data = {'items': items, 'etag': new_etag}
        _fetch_cache[feed_url] = (current_time, cache_data)
        logger.info(f"Successfully fetched and parsed {len(items)} items from {feed_url}")
        return items, feed_url

    except Exception as e:
        logger.error(f"Error fetching or parsing feed {feed_url}: {e}", exc_info=True)
        # Remove from cache on error
        if feed_url in _fetch_cache: del _fetch_cache[feed_url]
        return None, feed_url # Indicate failure


def _filter_items(items, feed_url, ingestion_config):
    """Applies filtering rules (date, keyword, limit) to items from a single feed."""
    if not items:
        return []

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    max_hours = ingestion_config.get('max_hours_since_published', 48)
    feed_limits = ingestion_config.get('feed_limits', {})
    default_limit = feed_limits.get('default', 25)
    # Ensure keywords are lowercase for case-insensitive comparison
    keywords = [k.lower() for k in ingestion_config.get('required_keywords', [])]

    initial_count = len(items)
    filtered_items = items
    skipped_date = 0
    skipped_keyword = 0
    skipped_limit = 0

    # 1. Date Filter
    if max_hours is not None and max_hours > 0:
        try:
            cutoff_time_utc = now_utc - datetime.timedelta(hours=float(max_hours))
            items_after_date_filter = []
            for item in filtered_items:
                published_struct = item.get('published')
                if published_struct:
                    try:
                        # Convert struct_time to timezone-aware UTC datetime
                        published_dt_utc = datetime.datetime.fromtimestamp(time.mktime(published_struct), datetime.timezone.utc)
                        if published_dt_utc >= cutoff_time_utc:
                            items_after_date_filter.append(item)
                        else:
                            skipped_date += 1
                    except OverflowError: # Handle potential mktime errors for very old dates
                        logger.debug(f"[{feed_url}] Skipping item due to OverflowError converting date: {item.get('title')}")
                        skipped_date += 1
                    except Exception as e: # Catch other potential time conversion issues
                        logger.warning(f"[{feed_url}] Could not parse/convert date for item '{item.get('title')}': {e}. Keeping item.", exc_info=False)
                        items_after_date_filter.append(item) # Keep if date parse fails
                else:
                    # Keep items with no published date (treat as recent)
                    items_after_date_filter.append(item)
            filtered_items = items_after_date_filter
        except Exception as e:
            logger.error(f"[{feed_url}] Error applying date filter (max_hours={max_hours}): {e}. Skipping date filter.", exc_info=True)
            # Don't filter if the setting itself causes an error

    if skipped_date > 0:
        logger.info(f"[{feed_url}] Date filter: Skipped {skipped_date} items older than {max_hours} hours.")

    # 2. Keyword Filter
    if keywords:
        items_after_keyword_filter = []
        for item in filtered_items:
            title = item.get('title', '').lower()
            summary = item.get('summary', '').lower()
            found = False
            for keyword in keywords:
                # Check for whole word match might be better, but simple 'in' check for now
                if keyword in title or keyword in summary:
                    items_after_keyword_filter.append(item)
                    found = True
                    break
            if not found:
                skipped_keyword += 1
        filtered_items = items_after_keyword_filter
    if skipped_keyword > 0:
        logger.info(f"[{feed_url}] Keyword filter: Skipped {skipped_keyword} items not matching required keywords.")

    # 3. Per-Feed Limit (Apply after sorting by date)
    # Sort by published date, newest first. Put items with no date or invalid date last.
    def get_sort_key(item):
        published_struct = item.get('published')
        if published_struct:
            try:
                # Use epoch seconds for sorting, handle potential errors
                return time.mktime(published_struct)
            except (OverflowError, ValueError): # Handle invalid date tuples
                return float('-inf') # Treat as very old/low priority
            except Exception:
                return float('-inf') # Treat other errors as low priority
        return float('-inf') # Items without dates also low priority

    filtered_items.sort(key=get_sort_key, reverse=True) # Newest first

    # Determine limit for this specific feed
    limit = default_limit
    # Simple approach: direct URL match in config keys
    if feed_url in feed_limits:
         limit = feed_limits[feed_url]
    # More robust: could normalize URLs or use feed titles if available/consistent
    # Ensure limit is a non-negative integer
    try:
        limit = int(limit)
        if limit < 0:
            logger.warning(f"[{feed_url}] Negative limit specified ({limit}), using default {default_limit}.")
            limit = default_limit
    except (ValueError, TypeError):
        logger.warning(f"[{feed_url}] Invalid limit specified ('{limit}'), using default {default_limit}.")
        limit = default_limit

    if len(filtered_items) > limit:
        skipped_limit = len(filtered_items) - limit
        filtered_items = filtered_items[:limit]
    if skipped_limit > 0:
        logger.info(f"[{feed_url}] Limit filter: Kept newest {limit} items, skipped {skipped_limit}.")

    final_count = len(filtered_items)
    if initial_count > final_count:
         logger.info(f"[{feed_url}] Filtered down from {initial_count} to {final_count} items.")

    return filtered_items

# Modified function signature to accept config
def fetch_all_feeds(feed_list, config, max_workers=5):
    """Fetches all feeds, applies pre-filtering based on config, and returns unique items."""
    all_items = []
    processed_ids = set() # For basic deduplication across feeds
    ingestion_config = config.get('ingestion', {}) # Get ingestion settings
    skip_feeds = ingestion_config.get('skip_feeds', [])

    logger.info(f"Starting feed ingestion. Max hours: {ingestion_config.get('max_hours_since_published')}, Keywords: {ingestion_config.get('required_keywords')}, Default Limit: {ingestion_config.get('feed_limits', {}).get('default')}")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all feed fetch tasks, skipping those in the skip list
        future_to_url = {}
        skipped_count = 0
        valid_feed_urls = []
        for url in feed_list:
            if url in skip_feeds:
                logger.warning(f"Skipping feed URL explicitly listed in config skip_feeds: {url}")
                skipped_count += 1
                continue
            # Rudimentary check for placeholder/invalid YouTube URLs if no channel ID
            # You might want a more robust check or rely on fetch errors / skip_feeds
            if "youtube.com/feeds/videos.xml?channel_id=PLACEHOLDER" in url:
                 logger.warning(f"Skipping placeholder YouTube URL: {url}. Add to skip_feeds or provide valid ID.")
                 skipped_count += 1
                 continue
            valid_feed_urls.append(url)

        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} feeds based on config 'skip_feeds' or placeholder patterns.")

        if not valid_feed_urls:
            logger.warning("No valid feed URLs remaining after checking skip_feeds.")
            return []

        future_to_url = {executor.submit(_fetch_single_feed, url): url for url in valid_feed_urls}

        items_processed_before_dedup = 0
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                # items will be None if _fetch_single_feed failed
                items, fetched_url = future.result()

                if items is None:
                    logger.warning(f"Fetching failed for URL (result was None): {url}")
                    # Consider adding to a dynamic skip list for future runs?
                    continue # Skip processing for this failed feed

                # Apply Filters (Date, Keyword, Limit) using the helper function
                filtered_single_feed_items = _filter_items(items, fetched_url, ingestion_config)
                items_processed_before_dedup += len(filtered_single_feed_items)

                # Add filtered items to the main list, handling deduplication
                added_count = 0
                for item in filtered_single_feed_items:
                    item_id = item.get('id') or item.get('link') # Use ID or link for dedup
                    if item_id and item_id not in processed_ids:
                        all_items.append(item)
                        processed_ids.add(item_id)
                        added_count += 1
                    elif not item_id:
                         # Add if no ID available, might be duplicate but can't tell
                         logger.debug(f"Adding item without unique ID from {fetched_url}: {item.get('title')}")
                         all_items.append(item)
                         added_count += 1
                    # else: skip duplicate based on ID/link

                if added_count > 0:
                    logger.debug(f"Added {added_count} new, unique, filtered items from {fetched_url}")
                elif len(items) > 0 and len(filtered_single_feed_items) == 0:
                    logger.info(f"All {len(items)} fetched items from {fetched_url} were filtered out.")
                elif len(items) == 0:
                     logger.debug(f"No items returned from fetch for {fetched_url}")


            except Exception as exc:
                logger.error(f'{url} generated an exception during processing/filtering: {exc}', exc_info=True)

    # Log final counts
    logger.info(f"Total items collected after filtering & pre-deduplication: {items_processed_before_dedup}")
    logger.info(f"Total unique items added to digest after final deduplication: {len(all_items)}")

    # Optional: Manual review/logging for specific feeds mentioned by user
    # These should ideally be managed via the 'skip_feeds' config setting
    feeds_to_monitor = [
        "https://openai.com/blog/rss.xml", # Check logs for this if not skipped
        # Add others like Facebook, DeepMind, SyncedReview, WandB if they were in the original list
    ]
    for feed_url in feed_list:
        if feed_url in feeds_to_monitor and feed_url not in skip_feeds:
            # Check if any items from this feed made it through
            has_items = any(item['source_feed'] == feed_url for item in all_items)
            if not has_items:
                logger.warning(f"Monitored feed {feed_url} had 0 items in the final list. Check fetch logs or consider adding to 'skip_feeds' if it consistently fails or returns irrelevant content.")

    # Remove YouTube placeholder - redundant if check above is done
    # all_items = [item for item in all_items if "youtube.com/feeds/videos.xml?channel_id=PLACEHOLDER" not in item.get('source_feed','')]


    return all_items

if __name__ == '__main__':
    # Example Usage - Update to pass a dummy config
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Example list, replace with loading from config in real use
    test_feeds = [
        "https://research.google/blog/rss/",
        # "https://openai.com/blog/rss.xml", # Often fails/empty, good candidate for skip_feeds
        "https://huggingface.co/blog/feed.xml",
        "http://feeds.feedburner.com/TechCrunch/artificial-intelligence", # Example non-https
        "invalid-url-example",
        "https://www.youtube.com/feeds/videos.xml?channel_id=PLACEHOLDER_ID"
    ]

    # Dummy config for testing the filtering logic
    dummy_config = {
        'ingestion': {
            'max_hours_since_published': 72, # 3 days
            'feed_limits': {
                'default': 5,
                'https://huggingface.co/blog/feed.xml': 3 # Specific limit example
            },
            'required_keywords': ['AI', 'Model'],
            'skip_feeds': ["invalid-url-example"]
        }
    }

    # Pass the dummy config to the function
    fetched_items = fetch_all_feeds(test_feeds, dummy_config) # Pass config

    if fetched_items:
        print(f"\n--- Fetched {len(fetched_items)} items after filtering ---")
        # Print details of the first few items
        for i, item in enumerate(fetched_items[:5]):
            print(f"\nItem {i+1}:")
            print(f"  Title: {item.get('title')}")
            print(f"  Link: {item.get('link')}")
            # Safely format time
            pub_time_str = 'N/A'
            if item.get('published'):
                try:
                    pub_time_str = time.strftime('%Y-%m-%d %H:%M:%S', item['published'])
                except TypeError: # Handle potential issues with the struct_time
                    pub_time_str = str(item['published']) # Fallback to string representation
            print(f"  Published: {pub_time_str}")
            print(f"  Source: {item.get('source_feed')}")
            # print(f"  Summary: {item.get('summary', '')[:100]}...") # Keep output clean
    else:
        print("\nNo items fetched or all items were filtered out.")

# Ensure any necessary imports are at the top

# Ensure any necessary imports are at the top 