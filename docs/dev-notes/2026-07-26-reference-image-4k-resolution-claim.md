# Reference-image resolution claim is wrong, plus two smaller gaps - 2026-07-26

Notes captured while using /create-image to generate a four-variant quarter-fold birthday card (2x2 grid, text rendered in three of four quadrants, two subject photos as reference images for facial likeness). Four production runs, all at `--resolution 4K --aspect-ratio 3:4` with two `--reference-image` inputs.

Priority is a rough call, P1 is "actively misleading", P2 is "limits a real workflow", P3 is "polish".

---

## 1. The reference-image downscale warning is false (P1)

Observation. `generate.py` carries this in the `--reference-image` argparse help, and emits the same string as a `note` field on every reference-guided result.

```
Note: reference-guided generation returns ~1K-ish output resolution
regardless of --resolution request.
```

That is not what happens. Four consecutive runs with two reference images at `--resolution 4K` returned **3584 x 4800** every time, measured with `sips -g pixelWidth -g pixelHeight` on the written PNGs. Not one came back near 1K.

The payload is not the cause. `generate.py` correctly sets `generationConfig.imageConfig.imageSize` alongside `aspectRatio`, which is exactly the field whose omission caused the genuine downscale bug in `edit.py`. It looks like the warning was carried over from the `edit.py` behaviour and applied to the wrong script.

Why it matters. This is the single most expensive kind of wrong doc, because it tells you a workflow is impossible when it is not. Any piece that needs both a likeness reference and legible rendered text (cards, posters, covers, thumbnails with copy) reads this note and concludes it has to choose one. In this case it nearly caused a switch to a 1K-capped provider that would have made a 32-word message illegible.

Suggested fix. Delete the claim from both the argparse help and the emitted `note` field, or re-verify and restate it accurately if there is some narrower condition under which it holds (single reference? certain aspect ratios? the older model slug?). If the condition is real but narrow, name the condition. If it applies to `edit.py` only, move it there.

---

## 2. Nano Banana 2 on Replicate is 1K-capped and nothing warns you at the point of choice (P2)

Observation. `references/models/nano-banana-2.md` and `scripts/registry/models.json` both record it correctly, the Replicate provider block carries a single `1K` rate while `gemini-direct` carries `512 / 1K / 2K / 4K`. But the fact is only visible if you go looking at the pricing table. `references/providers/replicate.md` lists Nano Banana 2 under hosted models as "fallback for image generation" with no resolution caveat.

Why it matters. "Fallback" reads as "same thing, different route". For anything that renders text, it is not a like-for-like fallback, it is a 4x linear resolution drop. The failure is silent, you get a valid image with mushy text.

Suggested fix. One line in `references/providers/replicate.md` next to the Nano Banana 2 entry - "1K only, do not use as the fallback for pieces that render text, use Gemini direct". Optionally have `cost_tracker` or the router warn when a Replicate nano-banana-2 call is requested above 1K.

---

## 3. Reference-image bleed into flat graphic styles is undocumented (P3)

Observation. Of four variants generated from near-identical prompts differing only in the style and palette paragraph, the flat mid-century graphic variant pulled photographic texture out of a reference image and ghosted it into the artwork. A subject photo of a palm-print shirt appeared as a large blurred photographic overlay across a panel specified as flat cream with generous empty space, and again behind the subject's head on another panel. The painterly, watercolour, and realism variants from the same references showed no bleed at all.

Plausible mechanism is that a deliberately quiet panel in a flat style gives the model very little to synthesise, and reference texture fills the vacuum.

Why it matters. It is a style-conditional artifact, so it survives a prompt that is otherwise well behaved, and it shows up in exactly the panels you designed to be calm.

Suggested fix. A short "known quirks" line under `references/models/nano-banana-2.md` noting that flat or minimal illustration styles combined with reference images can bleed photographic texture into low-detail regions, and that the mitigation is either to drop references for those panels or to describe the empty region's material explicitly (for example "flat matte cream paper with no texture, no photographic detail").
