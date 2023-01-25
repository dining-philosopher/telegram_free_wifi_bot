# telegram_free_wifi_bot
hello world telegram bot

Shows free wi-fi networks from wigle.net on openstreetmap.

Needs api_keys.json file like this:

```
{
    "wigle_key": "your_wigle_key_here=",
    "telegram_key": "your_telegram_key_here"
}
```

Contextily library has ill-functioning `_retryer` function, so it is recommended to redefine it, e. g. as follows:

The file is somewhere like ~/.local/lib/python3.8/site-packages/contextily/tile.py

```
import sys
from requests.adapters import HTTPAdapter, Retry
def _retryer(tile_url, wait, max_retries):
    """new retry function cos original one sucks
    ignores wait, max_retries"""
    s = requests.Session()
    retries = Retry(total=4,
                backoff_factor=0.2,
                status_forcelist=[ 500, 502, 503, 504 ])
    adapter = HTTPAdapter(max_retries=retries)
    s.mount('http://', adapter)
    s.mount('https://', adapter)
    print("Trying to get url: ", tile_url, file = sys.stderr)
    request = s.get(tile_url, headers={"user-agent": USER_AGENT})
    request.raise_for_status()
    return request
```

