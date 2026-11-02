# ccquota: quota tracking for Claude Code and Codex

[← Back to the README](../README.md) · [繁體中文](intro.zh-Hant.md)

This is a small tool I built with Claude: **ccquota**.

## Why I made it

I write code with both Claude Code and Codex, and I kept checking how much of the 5-hour and weekly limits I had used and when they would reset.

With several sessions open at once, I also wanted to see the context fill, tokens, cache hit rate, and how many sessions were actually running.

So I built a small Python tool, **ccquota**, that shows all of this inside Claude Code, plus a standalone pixel-art dashboard. Later I added a quota band for the Codex desktop app too.

## How I built it

The first problem wasn't the UI. It was working out where the quota data actually lives.

I ended up with three sources:

- **Claude Code's official figures**: the JSON the status line receives each time it runs, and what the mod reads from the engine. They carry the official limits, context, cache figures and more.
- **Local usage records**: Python parses the transcripts Claude Code already writes on your machine, and counts tokens, requests and sessions.
- **Codex's local service**: it asks Codex's app-server for live limits, and only falls back to local records when that fails.

These feed four views: the Claude Code mod, the status line, the pixel-art panel, and a floating band for the Codex desktop app.

I handed the Codex desktop band to Codex to write. My part was checking that it couldn't affect Claude Code, then bringing it into the same project. It looks up limits with ccquota's existing code instead of keeping a second copy.

Everything uses only the Python standard library. There's nothing to pip install.

## What went wrong along the way

I learned more here than from building the UI.

### 1. Data you can read isn't always current

Claude Code keeps a local cache of the quota, but it refreshes on no fixed schedule. I once saw it go eight days without an update.

Codex is the same: its local records said 13% of the weekly limit was used, while a live query showed 47%.

So a number you can read isn't the live quota. ccquota now prefers the official live figures, falls back to caches or local records only when it has to, and marks which numbers are estimates.

### 2. You can't just add up the tokens

One API response often shows up several times in the transcripts.

Adding them all up overcounted a week's usage by 136% in my tests.

ccquota now deduplicates on message ID plus request ID, and counts cache-read tokens separately so the context re-read on every turn isn't treated as new usage.

### 3. A session file doesn't mean the session is running

When a session is killed, its file stays behind.

Counting files isn't enough. ccquota also asks the operating system whether that process ID is still alive.

### 4. Working isn't the same as being cheap to run

At first, every refresh re-read all the records from the start, which got slow as they grew.

Now an incremental cache parses only what's new.

On about 326 MB of transcripts, a read went from about 0.6 s to 0.04 s.

### 5. Working on my machine doesn't mean it works for others

After making it a Claude Code mod, I found that a marketplace install copies only the mod's own folder. With the old layout, the Python script that does the counting was never installed, and the default path pointed at my own machine.

Everything worked for me, but anyone else would have lost half the figures. I restructured the project so the script installs with the mod and is found automatically.

### 6. With no extension point, you can only float on top

Claude Code has mods, so the band can sit right above the prompt. The Codex desktop app has no such extension point, so there's no way to put a UI inside it.

Instead, it's a small always-on-top window that tracks the Codex window and sits just above its prompt, hiding when you switch to another app or minimize Codex. It looks built in, but it's really a separate window.

## What I took away from it

The biggest lesson:

**AI can write the code fast, but you still have to check for yourself whether the data source is reliable and the counting is right.**

That goes double for a usage tracker: a nice-looking display doesn't mean the numbers are correct.

Three things mattered most:

- Know whether each number is an official live value, a cache, or an estimate
- Check for duplicates before adding up tokens
- Don't re-read large files over and over just to stay live

These probably apply to any monitoring tool or log analyzer.

## What it does today

- Shows the 5-hour and weekly limits and reset times for both Claude Code and Codex
- Shows context, cache hit rate, today's tokens, cost, and the number of running sessions
- Turns yellow at 70% of a limit and red at 90%
- Mod: a band above the prompt in both the Claude Code desktop app and the CLI
- A status line for the CLI
- A standalone pixel-art panel that turns quota tracking into an adventurers' guild dashboard
- Codex desktop band: follows the Codex window and sits above its prompt, showing Codex's 5-hour and weekly limits, reset countdowns and today's tokens; drag it to reposition

## How to use it

You need Python 3.7 or later.

To show it inside Claude Code (recommended, works in the desktop app too), type this in `claude` in a terminal:

```
/plugin install ccquota --marketplace Nardohsu/ccquota
```

For the pixel-art panel or the Codex desktop band, clone the repo:

```bash
git clone https://github.com/Nardohsu/ccquota.git
cd ccquota
python ccquota_panel.py
```

On Windows you can also double-click `panel.bat` to open the panel.

Codex desktop band (Windows only for now): double-click `codex-overlay/Start.bat`, then switch back to Codex. Drag to move it, right-click for options, and press `Esc` to close it.

The panel gets Claude's official quota from the status line, so use it alongside the CLI status line; otherwise the official quota may show as "—". See the [README](../README.md) for status line setup.

## Other notes

No API key is needed, and ccquota never reads your conversations. It only parses token counts and timestamps.

Everything about Claude is handled locally. For Codex limits, ccquota starts the Codex already on your machine, which asks OpenAI using its own sign-in. ccquota never reads or stores your credentials.

The Codex band doesn't change Codex's installation or settings and doesn't add itself to startup. If you don't want it, just close it.

Current limitations:

- Codex limits come from an experimental API, so they may need updating as Codex changes
- The Codex desktop band is a floating window, not truly part of the app, and Codex's layout doesn't leave room for it

I'll keep using and improving it, and the code is public for anyone who finds it useful.

MIT License, free and open source.

If you use Claude Code or Codex, give it a try.

Found a bug, have a better idea, or have thoughts on tools like this? Come talk about it in [Issues](https://github.com/Nardohsu/ccquota/issues)!
