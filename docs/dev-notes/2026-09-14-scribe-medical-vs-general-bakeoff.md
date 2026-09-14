# Scribe v2 Medical vs Scribe v2, on real iDD course audio

Date: 2026-09-14. Prompted by the ElevenLabs changelog entry of 2026-09-11
announcing `scribe_v2_medical` as GA. Run while adding the `--model` flag in
v4.6.0, so the flag and the finding land together.

> **Correction, same day, after Julian reviewed this note.** The first version of
> this file ran a third "Descript" arm and claimed Descript beat bare Scribe.
> Both halves of that were wrong and the claim is withdrawn.
>
> 1. **Descript's transcription engine IS ElevenLabs Scribe v2.** It is a
>    user-selectable setting in Descript (Settings > AI models > Transcription:
>    Automatic / ElevenLabs Scribe v2 / Rev AI v2 / Rev AI v3), and the iDD
>    workspace is set to Scribe v2. There is no separate "Descript engine" to
>    benchmark against, so "Descript vs Scribe" was never a model comparison.
> 2. **The Descript transcript used was not raw engine output.** Descript carries
>    its own glossary (the same job keyterms do), and that lesson had already been
>    reviewed and corrected by the iDD team. Scoring human-QA'd, glossary-assisted
>    text against raw API output measures the review process, not the model.
>
> The corrected reading is in "What the Descript arm actually showed" below. The
> `scribe_v2` vs `scribe_v2_medical` comparison is unaffected: both ran on
> identical audio through identical pipeline settings with the identical keyterm
> set, with the model as the only variable.

## Verdict up front

**The model is not the lever. Keyterms are.** Switching from `scribe_v2` to
`scribe_v2_medical` changed no proper noun on this sample. Adding six clinician
surnames as keyterms fixed every remaining error and produced the only perfect
score in the test.

Do not adopt `scribe_v2_medical` as the default for dental content on the
strength of its name. Adopt it, if at all, for the register normalisation
described below, and treat the keyterm set as the accuracy control.

## Sample

`02 - 02 - Facial Analysis for Smile Design - Jameel Gardee.mp4`, 4:46, single
speaker, from the Avant Garde / ASDE course. Chosen because it is dense with
clinician proper nouns and because a Descript transcript of the same audio
already existed at `~/code/idd-world/transcripts/Avant Garde/`. That transcript
turned out NOT to be a usable control (see the correction at the top); it is kept
in the table for context, marked as such.

One lesson is not a corpus. Treat everything here as a strong signal on
single-speaker lecture audio with named clinicians, not a settled result.

## Proper-noun accuracy

The `dental` keyterm set (184 terms) was active on all three Scribe runs. It is
brand-and-clinical-term only; clinician surnames were deliberately left out of it
when it was built, to be supplied ad hoc. That decision is exactly what this test
measures.

| Proper noun | Descript (not a control) | Scribe v2 | Medical | Medical + keyterms |
|---|---|---|---|---|
| Frank Spear | OK | OK | OK | OK |
| John Kois | OK | OK | OK | OK |
| Gerard Chiche | "Jared Chiche" | "Jared Kische" | "Jared Kische" | OK |
| Christian Coachman | OK | OK | OK | OK |
| Galip Gurel | OK | OK | OK | OK |
| Eric Van Dooren | OK | "Eric van Durante" | "Eric van Duren" | OK |
| **Score** | **5/6** | **4/6** | **4/6** | **6/6** |

The columns that constitute a controlled test are the three Scribe runs. The
Descript column is struck as an engine comparison, for the reasons in the
correction above, and is read separately below.

**Medical's only accuracy movement was a closer miss**, "Duren" against
"Durante" for Van Dooren. Closer, still wrong, still needed the keyterm.

## What the Descript arm actually showed

Reading it correctly makes it evidence **for** the conclusion rather than against
it. Descript is running the same `scribe_v2` this skill calls by default. So the
gap between the Descript column (5/6) and the bare `scribe_v2` column (4/6) on
identical audio cannot be a model difference, because there is no model
difference. It can only come from the two things layered on top:

- Descript's **glossary**, which does the same job as `keyterms` here, and
- the iDD team's **human review** of that lesson.

That is the same lever, applied twice, arriving at the same place: the run that
reached 6/6 got there by supplying names, not by changing models. Two pipelines
around one engine, and both times the names were what mattered.

It does raise a question this note cannot answer: **where does the Descript
glossary and the `dental` keyterm set diverge?** They are two separately
maintained vocabularies feeding the same engine. If a name is in one and not the
other, transcripts drift depending on which path produced them. Worth an audit.

A genuinely raw Descript baseline would need a file the team has never reviewed.
Not run here, and not needed for the model question.

## What the medical model actually changed

97.31% word-level similarity between the two models on the full transcript, 20
differing spans. Sixteen were punctuation only. The rest:

| Measure | Scribe v2 | Medical |
|---|---|---|
| Informal contractions (gonna, wanna, gotta) | 5 | 0 |
| Commas | 65 | 55 |
| Sentences | 41 | 43 |
| Average sentence length (words) | 22.6 | 21.7 |

The medical model **normalises register**: every "gonna" became "going to". It
also punctuates into slightly shorter, cleaner sentences. For a published course
transcript that a student reads, that is a genuine editorial benefit and the only
real reason found here to prefer it. For a verbatim record of what was said, it
is a mild fidelity loss.

## Actions this suggests

1. **Add clinician surnames to a keyterm set.** The accuracy win is entirely
   here. Either extend `dental` with the recurring iDD faculty names (Chiche,
   Van Dooren, Gurel, Coachman, Kois, Spear, Gardee, Hughes, Bhatt, Shadrooh,
   Roscoe) or add a sibling `faculty` set so the +20% keyterm surcharge stays
   opt-in per video. A sibling set matches how `agency` was scoped.
2. **Consider medical for published course transcripts**, not for verbatim or
   legal-grade records, and not on the assumption that it is more accurate.
3. **Re-run this comparison on a multi-speaker interview** before generalising.
   Diarisation behaviour was untested here (single speaker).

## Reproducing

Both caches are kept under `/tmp/scribe-test/{general,medical,medical-kt}/` for
this session only. To redo it:

```bash
src="<lesson>.mp4"
python3 scripts/transcribe.py transcribe "$src" --model scribe_v2 \
  --keyterm-set dental --formats md,json --output-dir /tmp/out-general
python3 scripts/transcribe.py transcribe "$src" --model scribe_v2_medical \
  --keyterm-set dental --formats md,json --output-dir /tmp/out-medical
```

Then diff the two `.json` caches' `text` fields. Re-rendering other formats from
those caches is free, so capture `json` on every comparison run.

## Ledger note

`transcribe_file` logs every real run to `~/.creators-studio/costs.json`. This
bake-off wrote four entries (three `scribe-v2-medical`, one `scribe-v2`), all at
0.0 marginal cost because both models are registered subscription-mode, but they
do inflate the entry count. A backup was taken first at
`~/.creators-studio/costs.json.bak-20260914`. The standing advice in
`2026-07-23-transcript-titles-and-dash-sweep.md` still applies: point `HOME` at a
temp dir for throwaway runs.
