# Keyterm Prompting

Scribe v2 can be biased toward specific words and phrases so brand, product, and
person names come back spelled correctly instead of mangled. This is the single
biggest accuracy win for domain content - "StoryBrand" instead of "story brand",
"Medit" instead of "meddit", "Al-Hassiny" instead of "al hassini".

## How it reaches the API

`keyterms` is sent to `scribe_v2` as repeated multipart fields (one per term).
Rules enforced client-side by `sanitize_keyterms` before sending, so a bad term
can never 400 the whole request:

- up to **1000** terms
- each **< 50 characters**
- each **≤ 5 words** (after normalisation)
- none containing `< > { } [ ] \`

Terms breaking a rule are dropped with a printed reason; the rest still go.

## Two levers - always-on vs per-video

There are two places keyterms come from, and the distinction is the whole point:

- **`transcription.keyterms` (always-on)** - a flat list applied to *every*
  transcription automatically. Convenient, but it means the +20% surcharge and
  those terms hit every run, relevant or not.
- **`transcription.keyterm_sets` (per-video)** - *named* vocabularies you activate
  only on the videos that need them, with `--keyterm-set <name>`. Nothing applies
  unless you name a set (or pass ad-hoc `--keyterms`).

**To activate keyterms only on specific videos:** put your vocabulary in
**sets**, keep the always-on `keyterms` list empty (or tiny). Then a plain
`/create-transcript video.mp4` applies no bias and no surcharge, while
`/create-transcript dental-webinar.mp4 --keyterm-set dental` applies the dental
vocabulary to that one video. Driving through Claude, you just say "this is a
dental video" and the orchestrator picks the set.

## Full precedence

Resolved by `resolve_keyterm_sets()` then `resolve_keyterms()`:

1. `--keyterms "a,b,c"` - ad-hoc per-run terms (CLI).
2. `--keyterm-set dental,agency` - terms from named sets in config.
3. `transcription.keyterms` - the always-on base list.
4. `DEFAULT_KEYTERMS` in `transcribe.py` - shipped default (empty).

All four **union** (deduped, order-preserving). `--keyterms-replace` uses only the
terms named **this run** (1 + 2), skipping the always-on base and default - the
per-video escape hatch when you keep a standing list but want none of it on a
particular video. A typo'd set name fails loud and lists the available sets;
`/create-transcript status` also lists them.

## Cost note

Using keyterms (from any source) adds a documented **+20% surcharge** on the base
transcription cost, and **more than 100 keyterms** forces a **20-second minimum
billable duration** per request. The skill prints both notes when keyterms are
active. Sets keep this contained: only the videos you tag pay the surcharge.

## Recommended config seed (sets by category)

Two businesses, two categories, so two sets. Keep the always-on `keyterms` list
empty so random downloads get no bias:

```json
{
  "elevenlabs_api_key": "sk_...",
  "transcription": {
    "keyterms": [],
    "keyterm_sets": {
      "dental": [
        "Institute of Digital Dentistry",
        "iDD",
        "Dr Ahmad Al-Hassiny",
        "Al-Hassiny",
        "intraoral scanner",
        "CAD/CAM",
        "Medit",
        "iTero",
        "3Shape",
        "Primescan",
        "TRIOS",
        "Dentsply Sirona",
        "Straumann"
      ],
      "agency": [
        "Pro Marketing",
        "Ascot",
        "Spiffy",
        "ClickUp",
        "Cloudflare",
        "WordPress"
      ]
    }
  }
}
```

Then: `--keyterm-set dental` on dental content, `--keyterm-set agency` on client
work, nothing on the rest. Keep sets to names genuinely non-obvious to a general
model - common English words gain nothing and eat the ≤ 5-word budget. Add a
one-off (a guest's name, a specific product model) with `--keyterms` on the run
rather than editing the set.
