import json
import os

CACHE_FILE = "query_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

# Initialize the global dictionary used by app.py
query_cache = load_cache()

def update_persistent_cache(query, response):
    global query_cache

    # 1. Update the in-memory dictionary so it's available immediately
    query_cache[query] = response

    # 2. Save the updated state to the JSON file (UTF-8 so Windows doesn't use cp1252)
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(query_cache, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving cache: {e}")