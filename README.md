# Rolex Grey Market Tracker

Personal daily tracker for Rolex grey market prices in Singapore.

## Data Source

**Carousell SG** — listings from brand new to well-used.

## Usage

```bash
# Fetch latest prices (run daily)
python fetch_prices.py

# Serve dashboard locally
python -m http.server 8080
# open http://localhost:8080
```

## Files

| File | Purpose |
|------|---------|
| `fetch_prices.py` | Scrapes Carousell SG, writes `data.json` |
| `data.json` | Latest listings + 90-day history snapshots |
| `index.html` | Dashboard (reads `data.json`) |

## Automate (macOS launchd)

```xml
<!-- ~/Library/LaunchAgents/com.user.rolex-tracker.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" ...>
<plist version="1.0">
  <dict>
    <key>Label</key><string>com.user.rolex-tracker</string>
    <key>ProgramArguments</key>
    <array>
      <string>/usr/bin/python3</string>
      <string>/Users/alfredlim/Personal/rolex-tracker/fetch_prices.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
    <key>StandardOutPath</key><string>/tmp/rolex-tracker.log</string>
    <key>StandardErrorPath</key><string>/tmp/rolex-tracker.err</string>
  </dict>
</plist>
```

Then: `launchctl load ~/Library/LaunchAgents/com.user.rolex-tracker.plist`
