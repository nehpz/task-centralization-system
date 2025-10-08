# Task Centralization System - Granola Integration

Automatically sync meeting notes from Granola to Obsidian vault.

**Status**: Week 1 Complete (Day 5) - Automation Ready
**Version**: 0.1.0
**Owner**: Stephen Mangrum

---

## Quick Start

### 1. Install Dependencies

This project uses [uv](https://github.com/astral-sh/uv) for fast, reliable dependency management.

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

The `.venv` virtual environment will be created automatically.

### 2. Set Up API Keys

**Required** for LLM enrichment:
```bash
export PERPLEXITY_API_KEY="your-perplexity-api-key"
```

Add to your shell profile (~/.zshrc or ~/.bashrc) to make permanent:
```bash
echo 'export PERPLEXITY_API_KEY="pplx-..."' >> ~/.zshrc
```

### 3. Test Manual Sync

The scripts use `uv run` shebang for automatic dependency management:

```bash
./granola_sync.py
# OR
uv run granola_sync.py
```

This will:
1. Fetch new meetings from Granola
2. Create markdown notes in `00_Inbox/Meetings/`
3. Enrich with LLM-extracted action items and decisions
4. Add [[WikiLinks]] for people, projects, and entities

### 4. Install Automated Sync (Optional)

To automatically sync every 15 minutes:

```bash
./install_cron.sh
```

This adds a cron job that runs the sync script every 15 minutes.

---

## Features

✅ **Automatic Meeting Capture**
- Fetches meetings from Granola API
- Converts ProseMirror content to clean Markdown
- Writes to Obsidian with YAML frontmatter
- Incremental sync (only new meetings)

✅ **LLM-Powered Action Item Extraction** 🆕
- Automatically extracts action items with assignees
- Identifies decisions with rationale
- Extracts entities (people, projects, companies)
- Creates [[WikiLinks]] for vault integration
- Obsidian Tasks plugin format (emoji priorities)
- Powered by Perplexity Sonar Pro

✅ **Rich Metadata**
- Meeting title, date, time
- Attendee list with wikilinks
- Calendar event integration
- Granola recording links

✅ **Robust & Reliable**
- Duplicate detection
- Error handling and retry logic
- Status tracking
- Comprehensive logging

---

## Usage

### Manual Sync

Run sync once:
```bash
./granola_sync.py
```

### Backfill Historical Meetings

Process last 7 days:
```bash
python3 src/processor.py --backfill 7
```

Process specific meeting:
```bash
python3 src/processor.py --doc-id <granola-document-id>
```

### Monitor Sync Status

Check last sync results:
```bash
cat .sync_status.json
```

View logs:
```bash
tail -f logs/granola_sync.log
tail -f logs/cron.log
```

### Manage Cron Job

View current cron jobs:
```bash
crontab -l
```

Remove sync cron job:
```bash
crontab -l | grep -v 'run_sync.sh' | crontab -
```

---

## Project Structure

```
task-centralization-system/
├── src/
│   ├── credential_manager.py    # Loads Granola credentials
│   ├── granola_fetcher.py       # Fetches from Granola API
│   ├── format_converter.py      # ProseMirror → Markdown
│   ├── obsidian_writer.py       # Writes notes to Obsidian
│   └── processor.py             # End-to-end orchestration
├── config/
│   └── credentials.example.json # Example configuration
├── logs/
│   ├── granola_sync.log         # Detailed sync logs
│   └── cron.log                 # Cron execution logs
├── granola_sync.py              # Main sync script
├── run_sync.sh                  # Cron wrapper
├── install_cron.sh              # Cron installer
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## Configuration

### Automatic (Default)

The system automatically loads Granola credentials from:
```
~/Library/Application Support/Granola/supabase.json
```

No configuration required if you have Granola installed and logged in.

### Manual (Optional)

Create `~/.config/task-centralization/credentials.json`:

```json
{
  "granola": {
    "access_token": "your_token_here",
    "refresh_token": "your_refresh_token_here"
  },
  "user": {
    "name": "Your Name",
    "email": "your@email.com"
  },
  "vault": {
    "path": "~/Obsidian/your-vault",
    "inbox_meetings_path": "00_Inbox/Meetings"
  }
}
```

---

## Output Format

Meeting notes are created in `00_Inbox/Meetings/` with this format:

**Filename**: `YYYY-MM-DD - Meeting Title.md`

**Content**:
```markdown
---
date: '2025-10-07'
time: '14:00'
meeting: 'Weekly Team Sync'
source: granola-api
granola_id: abc123...
type: meeting-note
status: auto-generated
attendees:
- '[[Person 1]]'
- '[[Person 2]]'
---

# Weekly Team Sync

**Monday, October 07, 2025 at 02:00 PM** · 45 minutes
**Attendees**: [[Person 1]], [[Person 2]]

## Notes

[Converted meeting content from Granola]

---

**Generated**: 2025-10-07T14:45:00 via Task Centralization System
**Source**: Granola API (automatic capture)
**Granola ID**: `abc123...`
```

---

## Troubleshooting

### No meetings syncing

1. Check Granola credentials:
   ```bash
   ls -la ~/Library/Application\ Support/Granola/supabase.json
   ```

2. Test API access:
   ```bash
   python3 src/granola_fetcher.py
   ```

3. Check logs:
   ```bash
   tail -20 logs/granola_sync.log
   ```

### Duplicate notes

The system automatically skips notes that already exist (checks Granola ID in existing notes).

To reprocess a meeting, delete the note and run sync again.

### Cron not running

1. Verify cron job exists:
   ```bash
   crontab -l
   ```

2. Check cron logs:
   ```bash
   tail -f logs/cron.log
   ```

3. Test script manually:
   ```bash
   ./run_sync.sh
   ```

---

## Development

### Run Tests

```bash
# Test credential loading
python3 src/credential_manager.py

# Test API access
python3 src/granola_fetcher.py

# Test format conversion
python3 src/format_converter.py

# Test full pipeline
python3 src/processor.py --backfill 1
```

### Logging Levels

Edit `granola_sync.py` to change log verbosity:
- `DEBUG`: Everything
- `INFO`: Standard operations (default)
- `WARNING`: Issues only
- `ERROR`: Failures only

---

## Roadmap

### Week 2 (Planned)
- [ ] LLM parsing for action items
- [ ] Entity linking to vault notes
- [ ] Enhanced meeting note template

### Week 3 (Planned)
- [ ] Notion backup integration
- [ ] Validation engine
- [ ] Weekly validation reports

### Week 4 (Planned)
- [ ] Production deployment
- [ ] Monitoring dashboard
- [ ] Documentation finalization

---

## Credits

**Built by**: Stephen Mangrum
**Based on**: [Joseph Thacker's Granola API reverse engineering](https://josephthacker.com/hacking/2025/05/08/reverse-engineering-granola-notes.html)
**Part of**: Task Centralization System project

---

## License

Personal use only.
