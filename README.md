# Local AI toolkit (LM Studio) — offline fallback

Purpose: if hosted Claude/all cloud AI goes down again (like 2026-09-03), you can
still get terminal + browser-driven work done using a fully local model in
LM Studio. This mirrors two of the tools used in Claude Code sessions:
Bash/file-editing and Chrome browser control.

## What was installed

Both are configured as MCP servers in `~/.lmstudio/mcp.json` (already edited):

- **terminal** → `@wonderwhy-er/desktop-commander` — shell command execution,
  file read/write/edit/search, directory listing. Local equivalent of the
  Bash/Read/Edit/Write tools.
- **browser** → `@playwright/mcp --extension` — controls your *actual* running
  Chrome (real tabs, real logins/cookies) via a bridge extension, instead of a
  disconnected automation profile. This is the closest local equivalent to
  claude-in-chrome.

Both run via `npx`, already pre-warmed into the local npm cache
(`~/.npm/_npx`), so they should still launch even with a flaky/offline
connection — no first-run download needed.

## One-time setup (do this once)

1. **Install the browser bridge extension.**
   A Chrome tab is open to the Playwright Extension page on the Chrome Web
   Store. Click **Add to Chrome** → **Add extension**. Pin it to the toolbar
   if you want easy access.
   (Direct link: https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm)

   The extension will show a pairing token on install — that token is already
   saved into `~/.lmstudio/mcp.json` under the `browser` server's `env` block
   (`PLAYWRIGHT_MCP_EXTENSION_TOKEN`), so the extension and the MCP server
   auto-pair without a manual "approve connection" step each time.

2. **Reload MCP servers in LM Studio.**
   Open LM Studio → left sidebar → **Program** (or the plug/MCP icon) →
   you should see `mempalace`, `terminal`, and `browser` listed. If they don't
   show up, hit the refresh/reload icon in that panel, or fully quit and
   reopen LM Studio.

3. **Load a tool-calling capable model.**
   You already have `Qwen3.8-27B-MLX-4bit` downloaded — it supports tool/function
   calling well. Load it from the model picker.

4. **Start a chat, enable tools.**
   In the chat, make sure the `terminal` and `browser` MCP tools are toggled on
   for that conversation (LM Studio shows a tool-picker/toggle near the chat
   input). Ask it to do something simple to confirm, e.g.:
   - "List the files in ~/Desktop" (tests **terminal**)
   - "Open google.com and tell me the page title" (tests **browser** — the
     extension will prompt you once per browser-launch to connect the current
     tab/window to the bridge)

## Running Qwen from the terminal (with tools)

`lms chat` (LM Studio's built-in CLI chat) does **not** support MCP tools — it's
plain text only. Instead, use the script at `~/lmstudio-local-tools/qwen-chat.py`,
which talks to LM Studio's local server API (`http://localhost:1234/api/v1/chat`)
the same way the GUI chat does, including MCP tool calls. It's stdlib-only
Python (no pip installs needed), so it still works if package registries are
unreachable during an outage.

**One-time setup required** (security gate, on by default = off) — this has
two dependent parts, both in LM Studio's **Developer** tab → **Local Server**
→ **Server Settings**:

1. Enable **"Require Authentication"** first. This is a hard prerequisite —
   **"Allow calling servers from mcp.json" silently does nothing without it**,
   which is exactly the trap this setup hit: toggling only the mcp.json
   switch, restarting the server, and still getting "Permission denied" no
   matter what.
2. Click **"Manage Tokens"** → **Create Token**, name it (e.g.
   `qwen-chat-local`), and copy the value shown — it's only displayed once.
3. Now enable **"Allow calling servers from mcp.json"** — it will actually
   take effect this time.
4. Export the token so the script can send it:
   `export LM_API_TOKEN="<paste token>"` (add to `~/.zshrc` to persist it
   across terminal sessions).

Once authentication is required, every request — including `qwen-chat.py`'s —
must carry `Authorization: Bearer <token>`, or it's rejected outright, tool
calls or not.

Then, from any terminal:

```
cd ~/lmstudio-local-tools
export LM_API_TOKEN="<your token>"      # or set it once in ~/.zshrc
python3 qwen-chat.py                    # interactive REPL, both tools on
python3 qwen-chat.py --no-browser       # terminal tool only
python3 qwen-chat.py --no-terminal      # browser tool only
python3 qwen-chat.py --show-reasoning   # show the model's reasoning blocks
python3 qwen-chat.py -p "list files in ~/Desktop"   # one-shot, non-interactive
```

It keeps the conversation stateful across turns (via LM Studio's
`response_id`/`previous_response_id`), prints each tool call it makes and a
truncated preview of the tool's output, then the model's final reply. Type
`exit` or Ctrl-D to quit.

Consider making it a shell alias for fast access during an actual outage:
`alias qwen="python3 ~/lmstudio-local-tools/qwen-chat.py"` in `~/.zshrc`.

Note: unlike this Claude Code session, there's no per-tool-call confirmation
prompt in this terminal script — the API executes tool calls immediately once
the server setting above is on. Keep that in mind before asking it to do
anything destructive; see Safety notes below.

## Using the browser tool day-to-day

Unlike claude-in-chrome (always-on), the Playwright bridge extension needs you
to click its toolbar icon once per Chrome session to connect a tab/window to
the MCP bridge before the model can drive it. After that, the model can
navigate, click, type, read page text, take screenshots, and read console/network
info in that window, using your real logged-in sessions.

If you'd rather not install the extension at all, an isolated fallback is
available by editing `~/.lmstudio/mcp.json`: change the `browser` args to
`["-y", "@playwright/mcp@latest", "--browser", "chrome", "--user-data-dir",
"~/.lmstudio-browser-profile"]`. This launches a separate, persistent Chrome
profile instead of connecting to your real one (no logins carried over
initially, but persists across sessions once you log in inside it).

## Auto-start (server no longer depends on remembering to open the app)

A LaunchAgent (`~/Library/LaunchAgents/com.lmstudio.server-autostart.plist`,
wrapper script `~/.local/bin/ensure-lmstudio-server.sh`) runs `lms server start`
at login and every 5 minutes thereafter. Per LM Studio's docs this is the
documented "programmatic" way to bring the local server (localhost:1234) up on
service launch — it's already loaded and confirmed working. If, on a fresh
reboot with LM Studio fully quit, this turns out to need the app itself
running in the background first, fall back to: LM Studio → Settings (Cmd+,)
→ enable "run LLM server on login" (this also minimizes the app to the system
tray on quit instead of fully exiting).

Check it any time with:
```
launchctl list | grep lmstudio
cat ~/.local/bin/ensure-lmstudio-server.launchd.log
```

## Coding model: Qwen3-Coder-30B-A3B

Downloaded via `lms get "qwen/qwen3-coder-30b" --mlx -y` — a MoE model (30B
total / ~3B active params) tuned for code, noticeably better than the general
Qwen3.8-27B for multi-file edits and diff-accuracy, and fast on this machine's
64GB RAM since only ~3B params activate per token. Load it in LM Studio's
model picker, or pass it to the terminal script:

```
python3 qwen-chat.py --model "qwen/qwen3-coder-30b"
```

Keep the general Qwen3.8-27B for non-coding chat/reasoning; switch to the
coder model specifically for app/website-building tasks.

## VS Code integration (Cline) — tried, then removed

Installed VS Code + the Cline extension as the closest local equivalent to
Claude Code's in-editor agentic loop. Removed the same night
(`brew uninstall --cask --zap visual-studio-code`, plus `brew cleanup
--prune=all` for the download cache) — decided it wasn't worth keeping
installed just for occasional use. `--zap` took the app, CLI symlinks,
Cline's extension data, caches, preferences, and saved state with it; nothing
left behind. Terminal-based access (`qwen-chat.py`, or LM Studio's own chat)
covers the same need without a standing editor install. Revisit if in-editor
diffs become worth the footprint again — the LM Studio side (models, MCP
tools) is already there for it to plug into.

## Web search: rg/websearch (replaces delan/web-search)

`rg_websearch_mcp.py` — a self-authored, keyless MCP server exposing one tool,
`web_search(query, max_results=5)`, replacing the third-party `delan/web-search`
Hub plugin (which has been removed from the auto-confirm list; disable/remove
it in LM Studio's Program panel if you want it fully gone).

**Why it scrapes Bing, not DuckDuckGo:** DuckDuckGo was the obvious first
choice, but both `html.duckduckgo.com` and `lite.duckduckgo.com` were tested
live and both return an anti-bot CAPTCHA challenge page ("Select all squares
containing a duck") for a bare scripted request — verified by actually
fetching them, not assumed. Bing's plain HTML results page
(`www.bing.com/search?q=...`) currently returns clean, uncaptcha'd results for
a single low-frequency request, so that's the backend. If Bing ever starts
blocking this too, the fix is the same shape: fetch the page yourself in a
browser dev tools tab, check for a challenge page, and adjust the regex to
match whatever markup it's actually serving that day — scraping a search
engine's HTML is inherently a "verify it still works" kind of integration,
not "write once, forget."

Registered in `~/.lmstudio/mcp.json` as the `websearch` server, launched via
`uv run --with mcp python3 rg_websearch_mcp.py` (no persistent pip install —
`uv` resolves the `mcp` package into its cache on first run and reuses it
after). LM Studio shows it internally as `mcp/websearch` — the mcp.json-based
integration id is always `mcp/<key>`, so a literal `rg/websearch`-prefixed id
isn't available without publishing an actual LM Studio Hub plugin under an
`rg` Hub account (a materially bigger project: Hub login, `lms create`
scaffolding, `lms push`). `rg/websearch` is this project's own name/branding;
`mcp/websearch` is what LM Studio's tool list will show.

Test it standalone any time with:
```
python3 rg_websearch_mcp.py --self-test "your query here"
```

## Vision model: Qwen3-VL-30B-A3B (abliterated, Q8_0)

Downloaded via:
```
lms get "https://huggingface.co/noctrex/Huihui-Qwen3-VL-30B-A3B-Instruct-abliterated-GGUF@Q8_0" --gguf -y
```
GGUF (not MLX) so it runs on LM Studio's llama.cpp backend with full Metal GPU
offload. Vision-capable (drop images into a chat) + abliterated (uncensored,
for testing — note research shows abliteration costs roughly ~9% general
reasoning quality, it's not a free unlock) + true 8-bit, per explicit request.
32.5GB on disk; comfortable alone in 64GB RAM but not alongside much else.

**First attempt got the wrong quant**: passing the repo as a short name
(`owner/repo@Q8_0`) failed to resolve at all (not in LM Studio's known
catalog), and passing the plain HF URL without a quant suffix silently
auto-picked LM Studio's hardware-recommended default (Q4_K_S, 4-bit) instead
of what was asked for. The fix was appending `@Q8_0` to the full URL. Worth
checking `du -sh` on the model folder after any non-interactive `lms get` to
confirm you got the file you actually asked for, not a silent substitute.

## A real memory lesson from tonight

Two chat models (`qwen3-coder-30b` + `qwen3.8-27b`, ~33GB combined) had been
loaded via `lms load` (manual, not through the API), which — unlike JIT-loaded
models — **has no TTL by default and never auto-unloads**. That left only
~8GB free, which would have made the 32.5GB vision model (or a ComfyUI
image/video generation) impossible to run without swapping. Fixed by
unloading both manually and going back to letting API calls JIT-load models
on demand.

**Rule going forward: don't use `lms load` for casual use.** Just hit the API
(`qwen-chat.py`, LM Studio's own chat, etc.) and let JIT loading +
Auto-Evict (both on by default) manage memory — only one JIT-loaded model
stays resident at a time, and it auto-unloads after 60 minutes idle
(configurable in Developer tab → Server Settings if you want it shorter).
`lms load` is fine for a deliberate one-off (like the coder-model test
earlier), just remember to `lms unload` when done, or don't use it at all.

## OpenClaw (tried, then removed)

Evaluated OpenClaw (github.com/openclaw/openclaw) as a more full-featured
local terminal agent than `qwen-chat.py` — installed, configured against
`lmstudio/qwen/qwen3-coder-30b`, set `exec-policy preset cautious` for
command-approval gating. Fully uninstalled the same night
(`openclaw uninstall --all`, then `npm uninstall -g openclaw`) once remote
control of this actual Claude Code session from a phone covered the
"terminal agent access away from my desk" need. Worth revisiting on the
Mac Mini if a dedicated always-on local agent becomes useful again — the
LM Studio side (models, MCP servers) is already in place for it to plug into.

## Safety notes

- **terminal** gives the model the same real shell access as this Claude Code
  session's Bash tool — full read/write/delete on your filesystem and the
  ability to run any command. LM Studio will pop a confirmation dialog per
  tool call by default (`neverAskForToolConfirmation: false` in
  `~/.lmstudio/settings.json`) — leave that on. Don't approve a command you
  don't understand, especially from a smaller/weaker local model that may
  misinterpret a task.
- **browser** with `--extension` can act in your real, logged-in browser
  (email, banking tabs, etc. if open). Same caution as with claude-in-chrome:
  don't approve actions on sensitive tabs you haven't reviewed.
- Local models (even a good 27B one) are much more likely than Claude to
  misread instructions, hallucinate file paths, or run a destructive command
  by mistake. Treat this as an emergency-capability toolkit, not a full
  replacement — review before approving anything destructive.

## Repo layout

```
qwen-chat.py                                    terminal chat client
rg_websearch_mcp.py                             rg/websearch MCP server
mcp.json.example                                redacted template for ~/.lmstudio/mcp.json
scripts/ensure-lmstudio-server.sh                LaunchAgent wrapper script
launchagents/com.lmstudio.server-autostart.plist LaunchAgent definition
```

`~/.lmstudio/mcp.json` and `~/.lmstudio/settings.json` on this machine are
the real, live copies (with the actual Playwright pairing token) and are
**not** in this repo — see `mcp.json.example` for the structure to copy in.

## Files touched on this machine (not all are in this repo)

- `~/.lmstudio/mcp.json` — `terminal`, `browser`, `websearch` server entries
  (kept the existing `mempalace` entry).
- `~/.lmstudio/settings.json` — swapped `delan/web-search:*` for
  `mcp/websearch:*` in the auto-confirm list.
- `~/.local/bin/ensure-lmstudio-server.sh` +
  `~/Library/LaunchAgents/com.lmstudio.server-autostart.plist` — server
  auto-start (copies live in this repo under `scripts/` and `launchagents/`).
- Models: `qwen/qwen3.8-27b` (general chat), `qwen/qwen3-coder-30b` (coding),
  and the Qwen3-VL-30B-A3B abliterated Q8_0 GGUF (vision).
- OpenClaw: installed, configured, then fully removed (`openclaw uninstall
  --all` + `npm uninstall -g openclaw`) — see the OpenClaw section above.
- VS Code + Cline: installed, then fully removed (`brew uninstall --cask
  --zap visual-studio-code` + `brew cleanup --prune=all`) — see that section
  above.
