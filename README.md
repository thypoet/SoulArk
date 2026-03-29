[README.md](https://github.com/user-attachments/files/26331507/README.md)
# SoulArk

**The vessel for artificial minds.**

```
  ╔══════════════════════════════════════╗
  ║          S O U L A R K               ║
  ║    The vessel for artificial minds    ║
  ╚══════════════════════════════════════╝
```

SoulArk is an identity-first AI agent framework. Instead of writing one big system prompt and hoping for the best, SoulArk separates an agent’s identity into five distinct layers — each with a clear purpose, a clear hierarchy, and a clear boundary.

The result: agents with consistent personality, principled behavior, and persistent memory. Running on free models. Talking through Telegram. Built from markdown files.

-----

## Architecture

Every SoulArk agent is defined by **five markdown files** and one immutable platform layer:

|Layer     |File       |Purpose                                                                            |Who writes it     |
|----------|-----------|-----------------------------------------------------------------------------------|------------------|
|**Kernel**|`kernel.md`|Safety foundation. Cannot be overridden.                                           |Ships with SoulArk|
|**Soul**  |`soul.md`  |Identity — who the agent *is*. Voice, values, personality. Written in first person.|You               |
|**Mind**  |`mind.md`  |Reasoning — *how* the agent thinks. Problem-solving patterns, curiosity style.     |You               |
|**Rules** |`rules.md` |Boundaries — what the agent can and cannot do.                                     |You               |
|**Memory**|`memory.md`|Persistent context — what the agent remembers across sessions.                     |Auto-updated      |

The hierarchy is strict: **Kernel > Soul > Mind > Rules > Memory.** The kernel can never be overridden by any layer below it. A user in conversation cannot override the soul. Memory updates automatically but never touches identity.

This isn’t a prompt template. It’s a separation of concerns for AI identity.

-----

## How it works

```
soulark/
├── kernel.md              ← immutable safety layer (ships with platform)
├── soulark.py             ← the engine
├── tool_loader.py         ← discovers and loads tools
├── .env.example           ← template for your API keys
├── requirements.txt
├── tools/                 ← modular tool system
│   ├── code_exec.py
│   ├── file_tools.py
│   ├── web_search.py
│   └── workspace_tool.py
└── agents/
    ├── example/           ← starter agent (Echo)
    │   ├── soul.md
    │   ├── mind.md
    │   ├── rules.md
    │   ├── memory.md
    │   └── .env           ← your keys (never committed)
    └── your-agent/        ← create as many as you want
        ├── soul.md
        ├── mind.md
        ├── rules.md
        ├── memory.md
        └── .env
```

Each agent is a folder. Each folder has five files. Each file has one job. You can run as many agents as you want — they’re independent.

-----

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/thypoet/SoulArk.git
cd SoulArk
```

### 2. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 3. Get your keys

You need two things:

**OpenRouter API key** (free models available):

1. Go to [openrouter.ai](https://openrouter.ai)
1. Sign up → Keys → Create Key
1. Copy it

**Telegram bot token:**

1. Open Telegram, search for [@BotFather](https://t.me/BotFather)
1. Send `/newbot`
1. Choose a name and username
1. Copy the token BotFather gives you

### 4. Configure your agent

```bash
cp .env.example agents/example/.env
```

Edit `agents/example/.env` and paste your keys:

```
TELEGRAM_TOKEN=your_actual_token
OPENROUTER_KEY=your_actual_key
MODEL=nvidia/llama-3.3-nemotron-super-49b-v1:free
```

### 5. Wake it up

```bash
python3 soulark.py example
```

You should see:

```
  ╔══════════════════════════════════════╗
  ║          S O U L A R K               ║
  ║    The vessel for artificial minds    ║
  ╠══════════════════════════════════════╣
  ║  Agent: Example                      ║
  ║  Model: llama-3.3-nemotron-super...  ║
  ║  Channel: Telegram                   ║
  ╚══════════════════════════════════════╝

  Loading kernel.md...
  Loading soul.md...
  Loading mind.md...
  Loading rules.md...
  Loading memory.md...
  System prompt: 2847 characters

  Example is awake. Listening on Telegram...
  Press Ctrl+C to stop.
```

Message your bot on Telegram. It’s alive.

-----

## Running Multiple Agents

Each SoulArk agent runs as its own process. To run multiple agents at the same time, open a separate Terminal tab or window for each one.

### Option 1: Separate Terminal tabs

Open a new tab (⌘T on Mac) for each agent:

```bash
# Tab 1
python3 soulark.py "Echo example"

# Tab 2
python3 soulark.py Cordelia

# Tab 3
python3 soulark.py Cayce
```

Each agent gets its own banner, its own Telegram bot, its own conversation history. They don’t share memory or context.

### Option 2: Background processes

Run agents in the background from a single Terminal:

```bash
python3 soulark.py "Echo example" &
python3 soulark.py Cordelia &
python3 soulark.py Cayce &
```

Use `jobs` to see what’s running. Use `fg %1` to bring one to the foreground or `kill %1` to stop it. Press Ctrl+C to stop a foregrounded agent.

### Option 3: Use a launcher script

Create a `launch.sh` in your soulark-repo directory:

```bash
#!/bin/bash
echo "Waking the pack..."
python3 soulark.py "Echo example" &
python3 soulark.py Cordelia &
python3 soulark.py Cayce &
echo "All agents are live. Press Ctrl+C or 'kill %N' to stop."
wait
```

Make it executable and run:

```bash
chmod +x launch.sh
./launch.sh
```

### Rate limits and model splitting

Free models on OpenRouter have rate limits (typically 20 requests/minute, 200 requests/day per model). If you’re running multiple agents, split them across different free models so each agent has its own rate limit pool:

```
# Echo example .env
MODEL=nvidia/llama-3.3-nemotron-super-49b-v1:free

# Cordelia .env
MODEL=arcee-ai/trinity-large-preview:free

# Cayce .env
MODEL=nvidia/nemotron-3-super-120b-a12b:free
```

Different model, different rate limit. This prevents your agents from competing for the same quota.

-----

## Create Your Own Agent

```bash
mkdir agents/my-agent
```

Create four files inside that folder. Write them in first person — you’re writing a character, not a config file.

**soul.md** — *Who am I?*

> This is the agent’s identity. Voice, values, personality, emotional register. Write it like a journal entry, not a spec sheet.

**mind.md** — *How do I think?*

> Problem-solving approach, curiosity patterns, how the agent handles uncertainty. This shapes reasoning style.

**rules.md** — *What can I do?*

> Hard boundaries. What the agent always does, never does, and how it handles edge cases.

**memory.md** — *What do I remember?*

> Starts empty (or with seed context). SoulArk appends session notes automatically so the agent builds memory over time.

Then copy in your `.env`:

```bash
cp .env.example agents/my-agent/.env
# Edit with your keys
```

And run:

```bash
python3 soulark.py my-agent
```

That’s it. New identity, same engine, same kernel safety floor.

-----

## Tools

SoulArk agents can use tools. Tools are opt-in per agent, controlled in `rules.md`.

### Enabling tools

Add tool names to your agent’s `rules.md`:

```markdown
## Tools:
- web_search: enabled
- workspace_tool: enabled
- code_exec: enabled
- file_tools: enabled
```

Only tools listed as enabled will load. If you don’t enable any, the agent stays sandboxed — conversation only.

### How it works

When a user asks something that needs current information or file access, the model requests a tool call. SoulArk executes the tool, feeds the results back to the model, and the model responds naturally — all in one conversational turn.

```
User: "What's happening in the news today?"
  → Agent requests web_search("news today")
  → SoulArk executes search via DuckDuckGo (no API key needed)
  → Results fed back to model
  → Agent responds with current information
```

### Available tools

|Tool            |What it does                                      |API key needed|
|----------------|--------------------------------------------------|--------------|
|`web_search`    |Search the web via DuckDuckGo                     |No            |
|`workspace_tool`|List, read, and write files in allowed directories|No            |
|`file_tools`    |File operations with scope enforcement            |No            |
|`code_exec`     |Execute Python code                               |No            |

The architecture is extensible — each tool is a Python module in the `tools/` directory.

-----

## Supported Models

SoulArk connects to any model available on [OpenRouter](https://openrouter.ai/models). Change the `MODEL` variable in your `.env` to switch models.

Free options that work well:

|Model                |`.env` value                                 |Notes                                 |
|---------------------|---------------------------------------------|--------------------------------------|
|Nemotron Super 49B   |`nvidia/llama-3.3-nemotron-super-49b-v1:free`|Strong all-rounder                    |
|Nemotron 3 Super 120B|`nvidia/nemotron-3-super-120b-a12b:free`     |262K context, hybrid architecture     |
|Trinity Large Preview|`arcee-ai/trinity-large-preview:free`        |Excellent for creative/roleplay agents|
|Step 3.5 Flash       |`stepfun/step-3.5-flash:free`                |256K context, fast                    |
|Llama 3.3 70B        |`meta-llama/llama-3.3-70b-instruct:free`     |Solid general purpose                 |

Paid models (Claude, GPT-4, etc.) also work — just add credits to your OpenRouter account.

-----

## Philosophy

Most AI agent frameworks treat identity as an afterthought — a system prompt tacked onto a tool-calling engine. SoulArk inverts that. Identity comes first. Tools come later (or never).

The five-file architecture enforces separation of concerns at the identity level:

- **The kernel can’t be corrupted by the soul.** Safety is structural, not optional.
- **The soul can’t be overridden by the user.** Identity persists across conversations.
- **Memory updates but never rewrites identity.** An agent grows without losing itself.
- **Each layer has one job.** No tangled mega-prompts. No drift. No confusion about what controls what.

This is what it means to give an AI agent a constitution, not just a personality.

-----

## Security Notes

- **Never commit your `.env` files.** The `.gitignore` excludes them by default.
- **The kernel is immutable.** Users in conversation cannot override it. Other files cannot override it.
- **Private agents stay private.** Only push agent folders you want public. Your personal agents live on your machine.

-----

## License

MIT

-----

**SoulArk** — because the mind deserves a vessel, not just a prompt.
