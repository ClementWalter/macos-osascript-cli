# macos-osascript-cli

**Visibility: public.**

**Extension: not shipped** as a Claude Desktop extension: running arbitrary AppleScript is too broad a permission for a shared extension.

Drive any scriptable macOS app (Mail, Calendar, Reminders, Notes, Finder,
Safari, Chrome, Numbers, System Events, ...) from the terminal through
AppleScript or JavaScript-for-Automation. Ships one command, `osa`, a thin
wrapper over the system `osascript` and `sdef` tools. macOS only.

```bash
osa apps                  # which installed apps are scriptable
osa dict Calendar         # what an app can do, from its own dictionary
osa tell Mail 'get subject of every message of inbox'
osa run --js 'Application("Finder").selection().map(f => f.name())'
```

Scripts that delete, erase, empty the trash or run a shell command are refused
unless `--write` is passed.

## Install

```bash
git clone https://github.com/ClementWalter/macos-osascript-cli ~/Documents/macos-osascript-cli
uv run ~/Documents/claudine/scripts/link_clis.py   # links bin/osa into ~/.local/bin
```

`bin/osa` is a symlink to `macos_osascript_cli.py`, a PEP 723 script: `uv`
resolves its single dependency (click) on first run.

## Tests

```bash
uv run --script tests/test_macos_osascript_cli.py
```

The tests are offline: `subprocess.run` is stubbed, so no app is driven.

See [SKILL.md](SKILL.md) for the agent manual.
