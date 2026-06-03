# Handover — Stage 4 complete, ready for Stage 5

Continues from `CONTEXT.md`. Read both. This doc is the **delta** since the previous (Stage 3 → 4) handoff.

## Where the project stands

- ✅ **Stage 4 done.** Full pipeline end-to-end: wake word → VAD recording → Whisper transcription → Ollama LLM (qwen2.5:1.5b) → Piper TTS → audio out. Fully offline, working on Mac.
- ⏳ **Stage 4 committed.** committed state at handover:
  - `scripts/test_tts.py` — new file (Stage 4a, standalone Piper test)
  - `scripts/test_assistant.py` — heavily modified (Stage 4b: threading, queues, `ask()` restructure, VAD/wake-word tuning, warmups)
  - `config.py` — Piper paths added, `_checks` block added, duplicate `OLLAMA_MODEL` removed, `import os` added
  - Suggested commit: `stage 4: piper TTS wired with threaded queue pipeline`
- ▶️ **Next: Stage 5** — polish. Consolidate scripts into `assistant.py`, module split, state machine, error recovery, persistent worker threads.

## What got built this session

### `scripts/test_tts.py` (Stage 4a)
Standalone ~30-line script. Loads `PiperVoice` once, synthesizes a hardcoded sentence, plays via `sounddevice`. Used to:
- Prove Piper + sounddevice basics work
- Get user comfortable with `synthesize → bytes → numpy → play` flow
- Later (during debugging) became the experimental ground that **disproved** the boundary-click hypothesis

**API note:** the user's installed `piper-tts` version uses `voice.synthesize(text)` returning chunk objects with `.audio_int16_bytes`, NOT `voice.synthesize_stream_raw(text)` returning raw bytes. The user discovered this themselves via `help(voice)`.

### `scripts/test_assistant.py` (Stage 4b)
The big restructure. **Architecture: 3 threads, 2 queues, sentinel-based shutdown.**

```
main thread (LLM + chunker)  ──[ sentence_queue ]──>  synthesizer  ──[ audio_queue ]──>  player
       produces strings                                produces int16 arrays              writes to sd.OutputStream
```

Key implementation details:
- `VOICE` is **module-level** (loaded once at startup, ~1-2s slow load). This is the entire reason we chose Piper-as-library over subprocess: pay model load once, not per sentence (subprocess pattern from Whisper would compound here because TTS is called once per *sentence*, not once per turn).
- `ask()` takes a `sentence_queue` param. Uses `re.compile(r"(?<=[.?!])\s+")` at module level — lookbehind keeps punctuation attached to the sentence; pattern matches the whitespace *after* the terminator (so we only push complete sentences once they're fully done).
- `ask()` maintains **two strings**: `output_string` (full reply, grows forever, used for return) and `buffer` (unsent text, shrinks every time a sentence is extracted). User initially split `output_string` instead of `buffer` → caused duplicate sentence pushes. Real teaching moment on the difference between accumulators and staging buffers.
- After LLM `done` loop ends: flush remaining `buffer` to queue, then push `None` sentinel.
- `synthesizer_worker` forwards the `None` to `audio_queue` (middle workers must forward; tail workers don't).
- `player_worker` holds **one** `sd.OutputStream` open per turn, writes audio chunks into it via `stream.write()` (blocking). Before exit, writes a 300ms silence tail so the stream closes from zeros (masks the amplifier-transition click).
- `speak()` orchestrator: creates queues, spawns workers, runs `ask()` inline on the main thread, joins workers. Per-turn lifecycle.

### Tuning settings (after extensive debugging)
- `VAD_AGGRESSIVENESS = 3` in `config.py` (was 2) — filters background noise
- `SPEECH_FRAMES_NEEDED = 3` in `record_until_silence` — 90ms of sustained speech required to set `has_heard_speech` (prevents single-frame false positives)
- 15-frame warmup loop at start of `record_until_silence` — discards stale OS-buffered audio (~450ms)
- `WAKE_THRESHOLD = 0.8` — comfortably above the noise floor (~0.5–0.7 fluctuation seen in logs)
- **Wake-word warmup: 10 chunks (~800ms)** at main loop start — `oww.predict()` called but scores ignored; primes the model's internal feature buffer so first real predictions are reliable
- 200ms silence pad per sentence in `synthesizer_worker` — natural inter-sentence pacing
- 300ms drain-tail silence before `player_worker` exits — masks stream-close click

## Key decisions made this session

1. **Piper as Python library, NOT subprocess.** Different from Whisper precedent and worth understanding. Whisper is one call per turn → subprocess overhead is bounded. Piper is one call per *sentence* (2-3 per turn) → subprocess overhead would compound and add latency mid-speech (the worst possible place). Library means voice loaded once at startup, reused across all synthesis calls. User has now seen both patterns with reasoning for each.

2. **Threading (not asyncio, not multiprocessing).** Threads are right for I/O-bound work that releases the GIL — HTTP streaming, Piper C-level inference, sounddevice all qualify. Multiprocessing would add IPC overhead for no benefit (no CPU-bound *Python* code anywhere). asyncio was an alternative but threading is simpler for someone learning concurrency for the first time. `queue.Queue` + sentinel = clean coordination.

3. **`sd.OutputStream` over `sd.play()`.** Switched after the user's experiment in `test_tts.py` (three back-to-back `sd.play`/`sd.wait` calls with no crackling) **disproved my boundary-click hypothesis**. Real cause: CPU contention from concurrent Piper inference caused buffer underruns in `sd.play`'s small buffer. `OutputStream` has a real ring buffer that absorbs jitter. `latency='high'` is available as further mitigation if needed (not currently used).

4. **Sentence chunking via regex with lookbehind.** `re.split` with `(?<=[.?!])\s+` is the Pythonic way; user learned regex + lookbehinds as bonus concepts. The whitespace-after-punctuation is the key insight — it's what tells us the LLM has *moved past* the sentence, not just emitted a period.

5. **Per-turn stream lifecycle.** Currently `sd.OutputStream` opens in `speak()` and closes after each reply. Causes one close-click per reply, masked by 300ms drain tail. **Cleaner fix would be persistent worker threads** (queues + workers at module scope, started once at program start, never torn down) — deferred to Stage 5 because it requires changing `speak()`'s synchronous handoff semantics.

## Real learning moments from the session

The user experienced these directly, not just heard about them:

- **Concurrent vs parallel** — interleaved time-slicing vs literally-simultaneous execution. Distinct concepts that everyday English conflates.
- **GIL** — Python's per-process lock; released during I/O and C extension calls. So our threads ARE truly parallel in practice because every stage spends its time in I/O or C code.
- **Multithreading vs multiprocessing** — when to pick each (we use threads; multiprocessing's separate memory + pickling would only be needed if we had CPU-bound *Python* work, which we don't).
- **Producer-consumer with `queue.Queue`** — thread-safe FIFO with blocking `get()` and sentinel-based shutdown propagation. Tail workers `break` on `None`; middle workers forward `None` then `break`.
- **Buffers as a general concept** — bridges between producers and consumers operating at different granularities. The string `buffer` (token → sentence) and the queues themselves (fast → slow handoff) are both buffers, of different shapes.
- **`output_string` vs `buffer` distinction** — accumulator vs staging-pen. They look similar but have completely different lifetimes and jobs. Splitting the wrong one is a real bug that I had to walk them through.
- **`np.frombuffer` is zero-copy** — reinterprets existing bytes as int16 view, no allocation. Useful idiom.
- **CPU contention → audio buffer underruns**, not boundary clicks. The crackling correlated with the LLM streaming because that's when all three threads were active, saturating CPU and starving `sd.play`'s callback.
- **Diagnostic-first debugging.** I was wrong twice (boundary-click theory, then warmup-only theory) before the user's clean experiment + actual log evidence forced the correct diagnosis. Lesson on letting hypotheses meet reality before trusting them.
- **Model warmup matters in two places.** Both `webrtcvad` (sort of — via the warmup loop discarding stale OS buffer) and `openwakeword` (priming its internal feature buffer with real audio) needed warmup before their outputs were trustworthy. Same root cause, two places.
- **Tuning is per-environment.** No universal "right" values for `WAKE_THRESHOLD`, `VAD_AGGRESSIVENESS`, `SPEECH_FRAMES_NEEDED`. They calibrate against your mic, room, and voice. The user developed intuition for the tradeoffs through experimentation.

## Collaboration style (still in `/memory/MEMORY.md`)

**Unchanged from previous handover and still critical:**
- User writes Python code themselves. Describe structure + syntax + small inline snippets. Do NOT use Write/Edit for `.py` files.
- Markdown / shell / JSON / config files: fine to write directly.
- Explain *why* before *what*. Layered explanations (mental model → mechanics → tradeoffs).
- Discuss before implementing. Don't rush past explanation.
- One concept at a time. Don't introduce threading and regex and OutputStream all at once.
- PEP 8 gentle reminders worth giving. User mixes some habits (variable name conventions, occasional spacing).

Memory files at `/Users/harshitpratapsingh/.claude/projects/-Users-harshitpratapsingh-Desktop-private-jarvis/memory/`. No new memories needed this session — code is the artifact.

## Stage 5 preview (polish) — discuss before implementing

What's planned:

1. **Consolidate into `assistant.py`** at project root. Stage 5 makes this the real entrypoint, not `scripts/test_assistant.py`.
2. **Module split.** Each stage script currently copies its own version of helper functions. Extract into modules — probably `audio.py` (VAD recording, output stream management), `stt.py` (whisper wrapper), `llm.py` (ask + chunker), `tts.py` (synthesizer). `assistant.py` just orchestrates. Test scripts stay in `scripts/` as standalone references.
3. **Explicit state machine.** Currently the loop has implicit states (idle → recording → transcribing → thinking → speaking) hidden in nested ifs. Make states explicit (enum + match, or a small class). Enables UX hooks (LED status), interruption handling, error states.
4. **Error recovery.** Currently any failure crashes the loop. Stage 5: graceful handling of Ollama down, whisper timeout, Piper failure. Tell the user what went wrong, return to listening.
5. **Persistent worker threads.** Move queues + workers to module scope; spawn once at startup. Eliminates per-reply stream-close click without the drain-tail hack. Requires a "reply done" event (since `speak()` no longer owns the workers' lifecycle).
6. **Status indicator.** Print state machine for now on Mac. Future LED on Pi.

Things to discuss before coding:
- Module boundaries (what goes where; how minimal vs how DRY)
- State machine representation (explicit class? enum + match? simple string?)
- Persistent workers: how does `speak()` know the reply is fully played? Probably an `audio_queue.join()` or a per-turn `threading.Event`.
- Error categories: transient (retry) vs config (fail loud) vs hardware (surface to user)

## How to start the next session

1. Read this file (`HANDOVER.md`) and the original `CONTEXT.md`. Auto-memory will load from the memory dir.
2. Acknowledge briefly — don't repeat the roadmap back.
3. Ask the user whether to (a) commit Stage 4 first, or (b) dive into Stage 5 discussion, or (c) revisit anything from Stage 4.
4. If diving into Stage 5: start with the **discussion** (module boundaries first), not code.
5. Don't skip explanations. The user is learning.
