# Handover — Stage 3 complete, ready for Stage 4

Continues from `CONTEXT.md`. Read both. This doc is the **delta** since the original handoff.

## Where the project stands

- ✅ **Stage 3 done.** Full pipeline working end-to-end: wake word → VAD recording → Whisper transcription → Ollama LLM (qwen2.5:1.5b) → streamed reply printed live.
- ⏳ **Stage 3 NOT yet committed.** User skipped the commit at end of session. Uncommitted state at handover:
  - `scripts/test_llm_v2.py` — modified (added `SYSTEM_PROMPT` + few-shot example, added `"system"` field to JSON body)
  - `scripts/test_assistant.py` — new file, the wired pipeline
  - Both ready to commit. Suggested message: `stage 3: llm brain wired into pipeline with voice system prompt`
- ▶️ **Next: Stage 4** — Piper TTS. Take the LLM reply and *speak* it through the speakers.

## What got built this session

### `scripts/test_llm_v1.py`
Non-streaming. Hardcoded prompt → `requests.post` to `/api/generate` → `response.json()["response"]`. Built first to make the user *feel* the wait, so streaming would land harder.

### `scripts/test_llm_v2.py`
Streaming version. Uses `iter_lines()`, parses each NDJSON line with `json.loads`, prints with `end="", flush=True` for the typewriter effect, accumulates into a return string. Also now has `SYSTEM_PROMPT` constant and sends it via the `"system"` field. The system prompt uses **few-shot prompting** (an example exchange) — this was a real lesson, see below.

### `scripts/test_assistant.py`
Full pipeline. Copied from `test_stt.py`, then the LLM pieces (imports, `OLLAMA_URL`, `SYSTEM_PROMPT`, `ask()`) added in, and `ask()` wired into the main loop right after `transcribe_with_whisper`. Includes `if text.strip():` guard before sending to LLM. Working end-to-end — confirmed by user.

## Key decisions made this session

1. **`/api/generate` + `"system"` field, not `/api/chat` + messages.** Decided to add system prompt as the smallest possible change. Switching to `/api/chat` is deferred to Stage 6 when we want multi-turn conversation (the messages/roles model pays off there, not now).

2. **Streaming from v2 onward, not just for v1.** The user asked about streaming early. We chose to build v1 *without* streaming first so the contrast would be felt, then v2 with it. Worked great pedagogically.

3. **Few-shot system prompt over emphasis/repetition.** Tried Technique 1 (emphatic rules: "CRITICAL: max 2 sentences") then Technique 2 (concrete example exchange). Technique 2 won decisively for qwen2.5:1.5b. **The lesson: small models obey examples, not rules.** This generalizes across all LLM work.

4. **Copy code across scripts, don't refactor into modules yet.** `test_assistant.py` has its own copy of `ask()` rather than importing from `test_llm_v2.py`. Module organization is Stage 5 work.

## Real learning moments from the session

The user understood these *through experiencing them*, not just being told:

- **Application caching vs. OS caching.** Whisper subprocess pattern was supposed to pay model-reload cost every call, but user observed 9s → 0.6s improvement. This is OS-level caching (page cache + macOS Gatekeeper verdict cache) on top of the app-level absence of caching. Two layers of caching.
- **Cold daemon vs. warm daemon.** Felt the Ollama warm-up timing directly with `ollama run` from the terminal. Layer 4 of the original streaming explanation landed.
- **`sys.path.insert(0, dirname(dirname(abspath(__file__))))`** — walked through this idiom innermost-out. User can now read/write it confidently.
- **System prompt as the highest-leverage thing for voice.** Same question, one `"system"` field added → markdown-with-bullets becomes conversational prose. Demonstrated visibly.
- **`raise_for_status()` before `.json()`.** User correctly explained why.
- **`end="", flush=True`** — needed together for the typewriter effect. Flush is the subtle one.

## Collaboration style (also in `/memory/MEMORY.md`)

**Critical:** the user writes Python code themselves to learn syntax. Do NOT use Write/Edit to produce `.py` files for them. Instead:
- Describe structure + syntax pieces + small inline snippets.
- Let them type the file.
- Review what they wrote, ask "why" questions to verify understanding.

Shell commands, configs, JSON, markdown — fine to write directly. Constraint is specifically about Python authorship.

Other style notes:
- Explain *why* before *what*. Layered explanations (mental model → mechanics → tradeoffs) work well.
- Discuss before implementing. The user prefers to talk through approaches and make decisions consciously.
- New things one at a time. Don't introduce streaming and system prompts and refactoring all at once.
- Don't refactor working stage scripts into "production architecture" yet — that's Stage 5.
- Style points worth gentle reminders: PEP 8 (`x = y` not `x=y`), 4-space indentation everywhere (user mixed 2/4-space in v2, fine but worth fixing habit), triple-double-quote docstrings (`"""`).

Memory files are at `/Users/harshitpratapsingh/.claude/projects/-Users-harshitpratapsingh-Desktop-private-jarvis/memory/`. Index in `MEMORY.md`. Five memories: user profile, pedagogy, python-self-write, voice-assistant project, MEMORY.md index.

## Stage 4 preview (Piper TTS) — discuss before implementing

What we'll build: take the LLM's reply string and produce audio through the speaker.

The interesting parts for Stage 4:
1. **Audio output pipeline.** Mirror of Stage 0/2's input. How raw audio bytes come out of Piper, get fed into `sounddevice`, become sound.
2. **Cashing in the streaming setup.** Right now `ask()` returns the full string after generation completes. The whole reason we did streaming in v2 was Stage 4: feed tokens into TTS *as they arrive*, sentence by sentence, so the user hears speech start in ~500ms instead of ~3s. This will require restructuring `ask()` — instead of returning a string, it'll yield chunks (generator), or take a callback for each sentence. **This is a design discussion to have before coding.**
3. **Sentence chunking.** Naive token-by-token streaming to TTS sounds awful. We need to buffer until a sentence boundary (`.` `?` `!` followed by space) and *then* synthesize. There's a real tradeoff: short chunks = faster first-audio but choppier prosody; long chunks = better prosody but more latency.
4. **Piper install.** Probably `pip install piper-tts` plus a voice model download. User has a 3.5mm headset (output only, output works on Pi 4 too) so audio output is testable on both Mac and Pi.

Things to discuss before writing code:
- Generator-based `ask()` vs callback-based vs background thread + queue.
- Which Piper voice to use (English voice, sized for Pi).
- Where to add `INPUT_DEVICE` / `OUTPUT_DEVICE` logic in `config.py`.

## How to start the next session

1. Read this file (`HANDOVER.md`) and the original `CONTEXT.md`. Auto-memory will already load from the memory dir.
2. Acknowledge briefly — don't repeat the whole roadmap back.
3. Ask the user whether to (a) commit Stage 3 first, or (b) dive into Stage 4 discussion, or (c) revisit anything from Stage 3.
4. If diving into Stage 4: start with the *discussion* (point 2 above — the streaming/chunking design), not code.

Don't skip explanations. The user is learning.
