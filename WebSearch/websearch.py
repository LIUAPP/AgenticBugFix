import requests

YOUR_GOOGLE_API_KEY = "AIzaSyDbmAkXL0n5OL8aGgSWp6Bgl-eCjlNQlrY"
YOUR_CUSTOM_SEARCH_ENGINE_ID = "1575da05955d24f76"

def simple_web_search_api(query, api_key, cx_id, num_results=5):
    """
    Performs a simple web search using the Google Custom Search JSON API.

    Args:
        query (str): The search query.
        api_key (str): Your Google API Key with Custom Search API enabled.
        cx_id (str): Your Custom Search Engine ID (CX).
        num_results (int): The number of search results to retrieve (max 10 per request).

    Returns:
        list: A list of dictionaries, each representing a search result (title, link, snippet).
              Returns an empty list if an error occurs or no results are found.
    """
    search_url = "https://www.googleapis.com/customsearch/v1"

    if api_key == "":
        api_key = YOUR_GOOGLE_API_KEY
    
    if cx_id == "":
        cx_id = YOUR_CUSTOM_SEARCH_ENGINE_ID

    params = {
        "key": api_key,
        "cx": cx_id,
        "q": query,
        "num": min(num_results, 10) # Max 10 results per request for this API
    }

    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()

        results = []
        if 'items' in data:
            for item in data['items']:
                results.append({
                    'title': item.get('title'),
                    'link': item.get('link'),
                    'snippet': item.get('snippet')
                })
        return results
    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        return []
    except ValueError as e:
        print(f"Error parsing JSON response: {e}")
        return []




def WebSearchTest(search_query):
    search_results = simple_web_search_api(search_query, YOUR_GOOGLE_API_KEY, YOUR_CUSTOM_SEARCH_ENGINE_ID, num_results=3)

    if search_results:
        print(f"\nSearch results for '{search_query}':")
        for i, result in enumerate(search_results):
            print(f"\n{i+1}. Title: {result['title']}")
            print(f"   Link: {result['link']}")
            print(f"   Snippet: {result['snippet']}")
    else:
        print("No search results found or an error occurred.")


WebSearchTest("Can you figure out why the there is a bug in the Agent code?")

