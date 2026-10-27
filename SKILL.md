---
name: macos-osascript-cli
description:
  "Drive macOS scriptable apps from the terminal via the `osa`
  command (AppleScript / JavaScript-for-Automation over `osascript`). `osa apps`
  lists scriptable apps, `osa dict <App>` dumps an app's vocabulary, `osa run
  '<script>'` / `osa tell <App> '<body>'` execute it. Use whenever the user
  wants to read or act on a local macOS app — Mail (read mail, save
  attachments), Calendar (read/create events), Contacts, Notes, Reminders,
  Messages, Finder, Safari/Chrome/Arc (active tab, URL, run JS in page),
  Pages/Numbers/Keynote, Preview, Music/Photos, System Events (UI scripting for
  non-scriptable apps). Read-only by default; destructive ops need --write.
  macOS only."
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

`osa` is on `$PATH` once `uv run ~/Documents/claudine/scripts/link_clis.py`
has linked `<skill-dir>/bin/osa` into `~/.local/bin`. Without the link, run
`<skill-dir>/bin/osa` (`~/.claude/skills/macos-osascript-cli/bin/osa`). It is
a PEP 723 script: `uv` resolves its dependencies on first run, no install step.

## Authentication

None. macOS asks once per target app for the Automation permission (see
Gotchas).

## Output conventions

- stdout carries only the script's result (`osascript`'s own output, newline
  trimmed); `osa apps --json` emits a JSON array of app names.
- `osa dict` prints a compact per-suite summary; `--raw` prints the app's full
  `.sdef` XML.
- A failing script's `osascript` error goes to stderr and `osa` exits with its
  exit code; CLI diagnostics go to stderr through `logging`.

## Commands

Read: `apps`, `dict`, and `run`/`tell` with read-only scripts. Write: `run`/`tell`
with a destructive verb need `--write` (see Gotchas).

```bash
# Read
osa apps                                   # scriptable apps on this Mac
osa apps --all --json                      # include CoreServices agents, as JSON
osa dict Calendar                          # an app's commands and classes
osa run 'tell app "Finder" to get name of every disk'
osa run --js 'Application("Finder").selection().map(f => f.name())'
osa tell Mail 'get subject of every message of inbox'
# Write (refused without --write when the script deletes or shells out)
osa tell Finder --write 'delete (every item of folder "Old" of desktop)'
```

### `osa apps [--all] [--json]`

List scriptable apps installed on this machine. `--all` also surfaces the
faceless CoreServices agents (noisy); default keeps the useful set.

### `osa dict <App> [--raw]`

Print an app's scripting vocabulary — a per-suite list of commands and classes.
**Read this before scripting an app you don't know**, instead of guessing verbs.
`--raw` emits the full `.sdef` XML. `<App>` is fuzzy (`chrome`, `mail`).

```bash
osa dict Calendar          # commands + classes, summarized
osa dict "Google Chrome" --raw | less
```

### `osa run '<script>' [-f FILE] [--js] [--write]`

Run an AppleScript (default) or JavaScript-for-Automation (`--js`). Script comes
from the argument, `-f FILE`, or stdin.

```bash
osa run 'tell app "Calendar" to get name of every calendar'
osa run --js 'Application("Finder").selection().map(f => f.name())'
osa run -f /tmp/script.applescript
```

### `osa tell <App> '<body>' [-f FILE] [--write]`

Convenience: wraps BODY in `tell application "<App>" … end tell`.

```bash
osa tell Mail 'get subject of every message of inbox'
```

## Recipes

### Per-app cheat-sheet

Fetch the full vocabulary with `osa dict <App>`. Quick orientation for the apps
worth reaching for:

| App                           | What it's good for                                                           | Starter                                                                      |
| ----------------------------- | ---------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **Mail**                      | read messages, headers, bodies; **save attachments**; make drafts            | `osa tell Mail 'get subject of every message of inbox'`                      |
| **Calendar**                  | list calendars, read/create events                                           | `osa tell Calendar 'get name of every calendar'`                             |
| **Reminders**                 | read/create reminders & lists                                                | `osa tell Reminders 'get name of every list'`                                |
| **Notes**                     | read/create notes & folders                                                  | `osa tell Notes 'get name of every folder'`                                  |
| **Contacts**                  | look up people, emails, phones                                               | `osa tell Contacts 'get name of every person'`                               |
| **Messages**                  | read chats, send iMessage/SMS _(send = confirm first)_                       | `osa dict Messages`                                                          |
| **Google Chrome**             | active tab URL/title, list tabs, **execute JS in page**                      | `osa tell "Google Chrome" 'get URL of active tab of front window'`           |
| **Safari** / **Arc**          | same as Chrome (active tab, run JS)                                          | `osa tell Safari 'get URL of front document'`                                |
| **Finder**                    | selection, paths, file metadata, windows                                     | `osa tell Finder 'get selection as alias list'`                              |
| **Pages / Numbers / Keynote** | read/write documents, sheets, slides                                         | `osa dict Numbers`                                                           |
| **Preview**                   | open PDFs/images, read open docs                                             | `osa dict Preview`                                                           |
| **Music / Photos / TV**       | now-playing, library, albums                                                 | `osa tell Music 'get name of current track'`                                 |
| **System Events**             | **GUI-script non-scriptable apps**, processes, UI tree, keystrokes, file ops | `osa tell "System Events" 'get name of every process whose visible is true'` |
| **iTerm / Terminal**          | open sessions, run commands, read output                                     | `osa dict iTerm`                                                             |
| **Image Events**              | resize/convert images, read dimensions (faceless)                            | `osa dict "Image Events"`                                                    |

### Worked example: read a Mail attachment the Gmail connector can't download

```bash
# 1. Locate the message and save its attachment to disk.
osa tell Mail '
  set out to "/tmp/att.doc"
  set msgs to (messages of inbox whose subject contains "AGREEMENT")
  save (first mail attachment of (item 1 of msgs)) in (out as POSIX file)
'
# 2. Convert for reading (system tools, not this CLI):
textutil -convert txt /tmp/att.doc -output /tmp/att.txt   # .doc/.docx → text
# sips / Read tool handle PDFs and images directly.
```

### Reminders.app en AppleScript : recettes et pièges

Reminders.app se pilote en AppleScript via `osascript` (ou
`osa tell Reminders`). Les propriétés exposées sur un `reminder` : `name`,
`body` (notes), `due date`, `allday due date`, `remind me date`, `priority` (0 =
aucune, 1–4 = haute, 5 = moyenne, 6–9 = basse), `completed`, `completion date`,
`flagged`, `creation date`, `modification date`, `id`.

> Limite connue : AppleScript n'expose **ni les sous-tâches ni la récurrence**.
> Un rappel récurrent apparaît comme une occurrence simple ; ne pas tenter de
> gérer la répétition par script.

#### Lire — toutes les listes et leur nombre de rappels ouverts

```bash
osascript <<'EOF'
tell application "Reminders"
  set out to ""
  repeat with l in lists
    set n to count of (reminders of l whose completed is false)
    set out to out & (name of l) & " | " & n & linefeed
  end repeat
  return out
end tell
EOF
```

> Piège de syntaxe : le `whose` doit être **parenthésé** dans un
> `count of (… whose …)`, sinon AppleScript lève
> `-1700 / Impossible de convertir … en type Unicode text`.

#### Lire — tous les rappels ouverts avec échéance ET note

On émet une ligne par rappel, champs séparés par `||`. **Lecture en lot** : on
récupère `name`, `due date` puis `body` de l'ensemble filtré en une requête
chacun, au lieu d'accéder propriété par propriété rappel par rappel. La note
(`body`) est lue ici parce que c'est la mémoire persistante de la tâche.

```bash
osascript <<'EOF'
tell application "Reminders"
  set out to ""
  repeat with l in lists
    set lname to name of l
    set ns to name of (reminders of l whose completed is false)
    set ds to due date of (reminders of l whose completed is false)
    set bs to body of (reminders of l whose completed is false)
    repeat with i from 1 to count of ns
      set dd to item i of ds
      if dd is missing value then
        set dd to "(sans échéance)"
      else
        set dd to dd as string
      end if
      set bb to item i of bs
      if bb is missing value then set bb to ""
      set out to out & lname & " || " & (item i of ns) & " || " & dd & " || " & bb & linefeed
    end repeat
  end repeat
  return out
end tell
EOF
```

> **Perf — c'est lent (~1-2 min), c'est normal.** Reminders.app fait un
> aller-retour Apple event coûteux par accès de propriété, et le filtre `whose`
> est évalué côté app. La lecture en lot ci-dessus (trois requêtes par liste)
> est la plus rapide _fiable_. **Ne pas** « tout lire d'un coup sans `whose` » :
> ça ramène tout l'historique des rappels complétés (encore plus lent).
>
> **Piège à éviter** : un `whose completed is false and due date ≤ <date>` pour
> filtrer les échéances côté serveur **renvoie zéro résultat** dès qu'un rappel
> a une `due date` à `missing value`. Toujours filtrer les dates **dans la
> boucle**, jamais dans le `whose`.

#### Modifier — compléter la note (mémoire persistante)

C'est l'écriture la plus fréquente : à chaque cycle, on **append** à la note
l'avancement daté (ce qui a été fait / trouvé / ce qui bloque), sans écraser
l'existant. Si le `body` est `missing value`, on part d'une chaîne vide.

```bash
osascript <<'EOF'
tell application "Reminders"
  set r to (first reminder of list "Famille" whose name is "Appeler le plombier")
  set old to body of r
  if old is missing value then set old to ""
  if old is not "" then set old to old & linefeed
  set body of r to old & "[2026-06-25] Devis demandé, en attente de réponse. Numéro : 06 12 34 56 78"
end tell
EOF
```

#### Modifier — cocher un rappel comme fait (tâche terminée)

```bash
osascript <<'EOF'
tell application "Reminders"
  set completed of (first reminder of list "Travail" whose name is "Préparer la revue") to true
end tell
EOF
```

#### Modifier — reprogrammer l'échéance (tâche reportée)

```bash
osascript <<'EOF'
tell application "Reminders"
  set due date of (first reminder of list "Famille" whose name is "Appeler le plombier") to (current date) + 1 * days
end tell
EOF
```

#### Ajouter — créer un nouveau rappel (sous-tâche issue de l'action)

```bash
osascript <<'EOF'
tell application "Reminders"
  tell list "Rappels"
    make new reminder with properties {name:"Relancer le plombier", body:"si pas de réponse au devis", due date:(current date) + 2 * days, priority:1}
  end tell
end tell
EOF
```

#### Fail-loud

Si un appel `osascript` échoue (app Rappels non lancée, permission
d'automatisation refusée, liste introuvable, conversion ratée), **arrête-toi,
n'invente rien, et signale l'erreur brute** (la commande et le message
d'erreur). Ne jamais combler un trou par une supposition sur le contenu d'un
rappel.

> Si l'erreur est `-1743` / _"n'est pas autorisé à envoyer des événements
> Apple"_, c'est la permission d'automatisation : demander à l'utilisateur de
> l'accorder dans Réglages Système → Confidentialité & sécurité →
> Automatisation, puis s'arrêter.

Ne jamais `delete` un rappel : c'est la donnée de l'utilisateur ; cocher ou
reprogrammer.

## Gotchas

**Safety.** Read-only by default. Scripts containing **irreversible or shell-escaping**
verbs (`delete`, `empty`, `erase`, `to trash`, `do shell script`, `eject`,
`restart computer`, `shut down`) are **refused unless `--write` is passed**.
This is a coarse rail, not a sandbox: outbound actions (sending mail/messages,
posting) are not blocked by the CLI and must still be confirmed with the user
before running, per normal agent safety rules.

- **Permissions (TCC).** The first time `osa` drives a given app, macOS prompts
  to allow Automation (System Settings → Privacy & Security → Automation). Some
  apps additionally need Full Disk Access to reach their data. Reading an app's
  objects via Apple Events does **not** require disk access to its container.
- **JXA vs AppleScript.** `--js` is more convenient for JSON-shaped data;
  AppleScript reads more naturally for app verbs. Both hit the same Apple
  Events.
- **Fuzzy app names** work for `dict`/`tell` via Launch Services; quote names
  with spaces (`"Google Chrome"`).

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
