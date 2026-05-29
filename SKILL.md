---
name: macos-osascript
description: "Drive macOS scriptable apps from the terminal via the bundled `bin/osa` command (AppleScript / JavaScript-for-Automation over `osascript`). `osa apps` lists scriptable apps, `osa dict <App>` dumps an app's vocabulary, `osa run '<script>'` / `osa tell <App> '<body>'` execute it. Use whenever the user wants to read or act on a local macOS app — Mail (read mail, save attachments), Calendar (read/create events), Contacts, Notes, Reminders, Messages, Finder, Safari/Chrome/Arc (active tab, URL, run JS in page), Pages/Numbers/Keynote, Preview, Music/Photos, System Events (UI scripting for non-scriptable apps). Read-only by default; destructive ops need --write. macOS only."
---

# macOS osascript bridge

Terminal access to any **scriptable** macOS application through Apple Events.
The CLI is a thin wrapper over the system `osascript` and `sdef` tools: it holds
no per-app knowledge, so the authoritative source for what an app can do is its
own dictionary, fetched live with `osa dict`.

This is the escape hatch for things the cloud connectors can't do — e.g. Gmail's
connector lists an attachment but can't download it; Mail.app **can** save it to
disk, after which `textutil`/`sips` convert it for reading.

## How to invoke

Run the bundled launcher **`bin/osa`** (PEP 723 — `uv` resolves deps inline on
first run, no install step). Resolve `bin/osa` against this skill's directory;
from elsewhere use the absolute path.

## When to use

Trigger this skill when the user mentions a local Mac app or wants to:

- read/search Mail or **save a mail attachment** to disk
- read or create **Calendar** events / **Reminders** / **Notes**
- look up **Contacts**
- read or send **Messages** (iMessage/SMS)
- get the active **Safari / Chrome / Arc** tab's URL or content, or run JS in it
- read/write **Pages / Numbers / Keynote** documents
- operate **Finder** (selection, paths, metadata)
- drive a **non-scriptable** app's UI via **System Events** (GUI scripting)

Do **not** use it for Electron apps with no dictionary (Slack, WhatsApp,
Discord, Telegram, Signal, Notion, Linear, VS Code, Cursor, Zoom) — they expose
nothing to AppleScript. Use their own CLIs/MCP connectors instead, or, as a last
resort, GUI-script them through `System Events`.

## Commands

### `osa apps [--all] [--json]`
List scriptable apps installed on this machine. `--all` also surfaces the
faceless CoreServices agents (noisy); default keeps the useful set.

### `osa dict <App> [--raw]`
Print an app's scripting vocabulary — a per-suite list of commands and classes.
**Read this before scripting an app you don't know**, instead of guessing verbs.
`--raw` emits the full `.sdef` XML. `<App>` is fuzzy (`chrome`, `mail`).

```bash
bin/osa dict Calendar          # commands + classes, summarized
bin/osa dict "Google Chrome" --raw | less
```

### `osa run '<script>' [-f FILE] [--js] [--write]`
Run an AppleScript (default) or JavaScript-for-Automation (`--js`). Script comes
from the argument, `-f FILE`, or stdin.

```bash
bin/osa run 'tell app "Calendar" to get name of every calendar'
bin/osa run --js 'Application("Finder").selection().map(f => f.name())'
bin/osa run -f /tmp/script.applescript
```

### `osa tell <App> '<body>' [-f FILE] [--write]`
Convenience: wraps BODY in `tell application "<App>" … end tell`.

```bash
bin/osa tell Mail 'get subject of every message of inbox'
```

## Safety

Read-only by default. Scripts containing **irreversible or shell-escaping**
verbs (`delete`, `empty`, `erase`, `to trash`, `do shell script`, `eject`,
`restart computer`, `shut down`) are **refused unless `--write` is passed**.
This is a coarse rail, not a sandbox: outbound actions (sending mail/messages,
posting) are not blocked by the CLI and must still be confirmed with the user
before running, per normal agent safety rules.

## Per-app cheat-sheet

Fetch the full vocabulary with `osa dict <App>`. Quick orientation for the apps
worth reaching for:

| App | What it's good for | Starter |
| --- | --- | --- |
| **Mail** | read messages, headers, bodies; **save attachments**; make drafts | `osa tell Mail 'get subject of every message of inbox'` |
| **Calendar** | list calendars, read/create events | `osa tell Calendar 'get name of every calendar'` |
| **Reminders** | read/create reminders & lists | `osa tell Reminders 'get name of every list'` |
| **Notes** | read/create notes & folders | `osa tell Notes 'get name of every folder'` |
| **Contacts** | look up people, emails, phones | `osa tell Contacts 'get name of every person'` |
| **Messages** | read chats, send iMessage/SMS *(send = confirm first)* | `osa dict Messages` |
| **Google Chrome** | active tab URL/title, list tabs, **execute JS in page** | `osa tell "Google Chrome" 'get URL of active tab of front window'` |
| **Safari** / **Arc** | same as Chrome (active tab, run JS) | `osa tell Safari 'get URL of front document'` |
| **Finder** | selection, paths, file metadata, windows | `osa tell Finder 'get selection as alias list'` |
| **Pages / Numbers / Keynote** | read/write documents, sheets, slides | `osa dict Numbers` |
| **Preview** | open PDFs/images, read open docs | `osa dict Preview` |
| **Music / Photos / TV** | now-playing, library, albums | `osa tell Music 'get name of current track'` |
| **System Events** | **GUI-script non-scriptable apps**, processes, UI tree, keystrokes, file ops | `osa tell "System Events" 'get name of every process whose visible is true'` |
| **iTerm / Terminal** | open sessions, run commands, read output | `osa dict iTerm` |
| **Image Events** | resize/convert images, read dimensions (faceless) | `osa dict "Image Events"` |

## Worked example: read a Mail attachment the Gmail connector can't download

```bash
# 1. Locate the message and save its attachment to disk.
bin/osa tell Mail '
  set out to "/tmp/att.doc"
  set msgs to (messages of inbox whose subject contains "AGREEMENT")
  save (first mail attachment of (item 1 of msgs)) in (out as POSIX file)
'
# 2. Convert for reading (system tools, not this CLI):
textutil -convert txt /tmp/att.doc -output /tmp/att.txt   # .doc/.docx → text
# sips / Read tool handle PDFs and images directly.
```

## Notes

- **Permissions (TCC).** The first time `osa` drives a given app, macOS prompts
  to allow Automation (System Settings → Privacy & Security → Automation). Some
  apps additionally need Full Disk Access to reach their data. Reading an app's
  objects via Apple Events does **not** require disk access to its container.
- **JXA vs AppleScript.** `--js` is more convenient for JSON-shaped data;
  AppleScript reads more naturally for app verbs. Both hit the same Apple Events.
- **Fuzzy app names** work for `dict`/`tell` via Launch Services; quote names
  with spaces (`"Google Chrome"`).
