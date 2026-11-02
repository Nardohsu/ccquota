# Codex Quota

**English** · [繁體中文](README.zh-Hant.md)

A Codex-only usage band for Windows. Python 3 standard library only; nothing to pip install.
It follows the look of the ccquota band and reads Codex data only.

Double-click `Start.bat` to start it, or run `python codex_quota.py`.
By default it follows the Codex / ChatGPT desktop window in the foreground and sits centred
above the prompt at the bottom (the band's lower edge 135px above the window's bottom).
The prompt's height changes with its content and the zoom level, so drag the band to fine-tune it;
it remembers its distance from the window's bottom.
This is a separate floating window, not an official built-in UI extension, so Codex leaves no room
for it in the conversation.
If Codex isn't found at launch, the band stays on its own; once you switch back to Codex it starts
following. After that, it hides when you switch to another app or minimize Codex.

- Drag the band to move it; in follow mode it saves its position relative to the window.
- Right-click to toggle following, refresh now, reset the position, or quit.
- `Esc` quits. `python codex_quota.py --detached` keeps it visible on its own.
- It doesn't change Codex's installation, launch settings or global settings, and doesn't add
  itself to startup.

## The numbers and where they come from

- **5h / week**: the percentage of each limit used, each with its reset countdown.
  Read every 60 seconds from `account/rateLimits/read` on the local `codex.exe app-server`.
  It uses your existing Codex sign-in; it never reads or prints credentials and sends no model
  requests.
  If that fails, it reads the token_count events in `.codex/sessions` and
  `.codex/archived_sessions`.
  A green dot means a live query; yellow means local records or no limit available. A limit
  whose reset time has passed shows `—`.
- **Today**: today's Codex tokens in your system's local time zone, updated every 15 seconds.
  It adds up the increases of each log file's cumulative token counter, so a repeated counter is
  not counted twice.
  Input already includes cached input and output already includes reasoning, so neither is added
  again.
  If separate branches each replay the same history, that usage may be counted twice; missing
  records can't be recovered.
  The first run scans every record, then only new content is read; no conversation text is
  stored.
- **Colours**: under 70% used is green, 70–89% yellow, 90% and over red.
- It doesn't show Claude Code usage, process counts, estimated cost, or context that can't be
  tied to the current conversation.
  Subscription limit percentages and token totals are different measures and can't be converted
  into each other.

`CODEX_HOME` sets where the records are read from, and `CODEX_CLI_PATH` points at a native
`codex.exe`.
By default it looks for `%LOCALAPPDATA%\OpenAI\Codex\bin\*\codex.exe`.
`python codex_quota.py --json` prints the bare numbers for diagnosis.

The app-server reader comes from `ccquota.py` in the folder above, so run it from inside the
ccquota repo.
