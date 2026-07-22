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

## Three-tier precedence

Resolved by `resolve_keyterms(cli, replace, config)`:

1. `--keyterms "a,b,c"` - per-run terms (CLI).
2. `transcription.keyterms` in `~/.creators-studio/config.json` - your standing list.
3. `DEFAULT_KEYTERMS` in `transcribe.py` - shipped default (empty; the standing
   list belongs in your config, not in the plugin).

Tiers **union** (deduped, order-preserving) so a per-run `--keyterms` **adds** to
your standing list rather than replacing it - you almost always still want your
brand names. Use `--keyterms-replace` for the rare pure-override case.

## Cost note

Using keyterms adds a documented **+20% surcharge** on the base transcription
cost, and **more than 100 keyterms** forces a **20-second minimum billable
duration** per request. The skill prints both notes when keyterms are active.
Practically: a large standing list is free-ish on long recordings but can dominate
cost on a batch of very short clips - the run-time notes make that visible.

## Recommended standing list (config seed)

Add the names your recordings actually use to `~/.creators-studio/config.json`.
A starting point for the dental-education and agency work:

```json
{
  "elevenlabs_api_key": "sk_...",
  "transcription": {
    "keyterms": [
      "Institute of Digital Dentistry",
      "iDD",
      "Dr Ahmad Al-Hassiny",
      "Al-Hassiny",
      "Pro Marketing",
      "intraoral scanner",
      "CAD/CAM",
      "Medit",
      "iTero",
      "3Shape",
      "Primescan",
      "TRIOS",
      "Dentsply Sirona",
      "Straumann",
      "Spiffy",
      "Ascot",
      "ClickUp",
      "Cloudflare",
      "WordPress"
    ]
  }
}
```

Keep it to names that are genuinely non-obvious to a general model - common English
words gain nothing from being listed and only eat into the ≤ 5-word budget. Add
per-video one-offs (a guest's name, a specific product model) with `--keyterms` on
the run rather than bloating the standing list.
