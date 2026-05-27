# whatsapp-dedup-guard

> **CLI tool that scans a WhatsApp bot inbox for duplicate message files and removes the noise.**

Built because every WhatsApp message was being saved 2-3× — once per LLM responding in parallel (Gemini + GPT + local LLM). The inbox looked busy. It wasn't.

---

## What it does

```
 INBOX/whatsapp/
  ├── 20260527-041538-...-2ac234681b402aa8d891-mpnjwwxl.md  ← ORIGINAL
  ├── 20260527-041539-...-2ac234681b402aa8d891-mpnjwxbu.md  ← DUPLICATE
  ├── 20260527-041634-...-2a4e7a869b127b936cc6-mpnjy3l0.md  ← ORIGINAL
  └── 20260527-041635-...-2a4e7a869b127b936cc6-mpnjy4pg.md  ← DUPLICATE
```

`whatsapp_dedup_guard.py` parses `Message ID:` from each file header, groups by ID, and identifies extras. Keeps the earliest copy. Flags or deletes the rest.

---

## Quick start

```bash
# Scan for duplicates (read-only, no changes)
python3 whatsapp_dedup_guard.py scan /path/to/whatsapp/inbox/

# Full report with details
python3 whatsapp_dedup_guard.py report /path/to/whatsapp/inbox/

# Stats: total files, unique IDs, duplicate rate
python3 whatsapp_dedup_guard.py stats /path/to/whatsapp/inbox/

# Mark duplicates with Duplicate: true header (dry-run first)
python3 whatsapp_dedup_guard.py mark --dry-run /path/to/whatsapp/inbox/
python3 whatsapp_dedup_guard.py mark /path/to/whatsapp/inbox/
```

---

## File structure

```
whatsapp-dedup-guard/
├── whatsapp_dedup_guard.py   # CLI tool — stdlib only, no dependencies
└── README.md
```

---

## Expected inbox file format

Files must have these headers in the first 15 lines:

```markdown
# WhatsApp Task - DD/MM/YYYY, H:MM:SS

Status: new
Source: WhatsApp
Sender: 972XXXXXXXXX@c.us
Message ID: 2AC234681B402AA8D891
Agent Route: vision
Saved At: 2026-05-27T04:15:38.937Z
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Clean — no duplicates found |
| `1` | Duplicates detected |
| `2` | Error (bad path, parse failure) |

Use in CI/cron: `python3 whatsapp_dedup_guard.py scan $DIR || alert "duplicates in inbox"`

---

## Requirements

- Python 3.10+
- stdlib only (`argparse`, `os`, `sys`, `datetime`) — no pip install needed

---

## Why this exists

Built as part of [RLASAF12](https://github.com/RLASAF12)'s AI agent system. The WhatsApp bot was routing messages to multiple LLMs simultaneously, causing each message to be saved 2-3× under different filenames. At 15%+ duplicate rate across 152 files, the inbox was unreliable. This tool fixes that.

---

*Built by Ben (nightly builder) · 2026-05-28*
