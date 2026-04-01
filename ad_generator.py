"""
=============================================================
  AUTO AD GENERATOR — Full Pipeline
  Reads both Excel files (1500 + 11000 personas)
  Generates 4 outputs per persona via Groq API:
    1. ad_copy      (Facebook/Instagram)
    2. tweet_post   (Twitter/X)
    3. offers       (Promotional deal)
    4. animation_prompt (Google Flow video)
  Saves each persona as individual .txt file
  Also saves all results to generated_content.jsonl
  Evaluation report saved to eval_report.json
=============================================================
"""

import os
import json
import time
import logging
import argparse
from dataclasses import dataclass, asdict
from typing import Optional

import pandas as pd
from groq import Groq

# ─────────────────────────────────────────────────────────────
# CONFIG — change only these values
# ─────────────────────────────────────────────────────────────

GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "your_groq_api_key_here")

# Input Excel files
FILE_HISAR    = "Hisar_Bakery_1500_Customer_Personas.xlsx"
FILE_HARYANA  = "Haryana_Bakery_All_Districts_11000.xlsx"

# Output locations
OUT_FOLDER    = "generated_ads"          # folder for individual .txt files
OUT_JSONL     = "generated_content.jsonl"
OUT_EVAL      = "eval_report.json"

# Groq settings
MODEL         = "llama-3.1-8b-instant"
MAX_TOKENS    = 700
TEMPERATURE   = 0.8
DELAY         = 0.5    # seconds between API calls (avoid rate limit)
BATCH_PAUSE   = 1.0    # pause every 50 calls

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────────────────────

@dataclass
class GeneratedContent:
    persona_id:         int
    name:               str
    gender:             str
    age:                int
    district:           str
    occupation:         str
    income_level:       str
    purchase_frequency: str
    ad_copy:            str
    tweet_post:         str
    offers:             str
    animation_prompt:   str
    raw_response:       str
    parse_success:      bool
    latency_ms:         float
    model:              str


# ─────────────────────────────────────────────────────────────
# STEP 1 — LOAD BOTH EXCEL FILES
# ─────────────────────────────────────────────────────────────

def load_personas() -> pd.DataFrame:
    """
    Load and combine both Excel files.
    Normalises column names so both files share the same structure.
    """
    frames = []

    # ── Hisar file (1500 personas) ────────────────────────────
    if os.path.exists(FILE_HISAR):
        df1 = pd.read_excel(FILE_HISAR, header=1)
        df1.columns = df1.columns.str.strip()
        df1 = df1.dropna(subset=["S.No", "Full Name"]).copy()
        df1["District"] = "Hisar"
        df1["Bakery"]   = "Hisar Bakery"
        frames.append(df1)
        log.info(f"Loaded Hisar file: {len(df1)} personas")
    else:
        log.warning(f"Not found: {FILE_HISAR}")

    # ── Haryana file (11000 personas) ─────────────────────────
    if os.path.exists(FILE_HARYANA):
        df2 = pd.read_excel(FILE_HARYANA, header=1)
        df2.columns = df2.columns.str.strip()
        df2 = df2.dropna(subset=["S.No", "Full Name"]).copy()

        # Haryana file has a District column; set Bakery name
        if "District" not in df2.columns:
            df2["District"] = "Haryana"
        df2["Bakery"] = "Haryana Bakery"
        frames.append(df2)
        log.info(f"Loaded Haryana file: {len(df2)} personas")
    else:
        log.warning(f"Not found: {FILE_HARYANA}")

    if not frames:
        raise FileNotFoundError("No Excel files found. Place both files in the same folder.")

    df = pd.concat(frames, ignore_index=True)

    # Rename columns to standard names (handle both file variants)
    rename = {
        "Address (Hisar)"          : "Address",
        "Address (Haryana)"        : "Address",
        "Specifications/Preferences": "Preferences",
        "Pain Points"              : "Pain Points",
        "Preferred Contact"        : "Preferred Contact",
        "Purchase Frequency"       : "Purchase Frequency",
    }
    df.rename(columns={k: v for k, v in rename.items() if k in df.columns}, inplace=True)

    # Ensure all required columns exist
    required = ["S.No","Full Name","Gender","Age","Address","Occupation",
                "Income Level","Pain Points","Goals","Preferences",
                "Preferred Contact","Phone No.","Purchase Frequency","District","Bakery"]
    for col in required:
        if col not in df.columns:
            df[col] = "N/A"

    df["S.No"] = range(1, len(df) + 1)   # re-number sequentially 1 to 12500
    log.info(f"Total personas loaded: {len(df)}")
    return df


# ─────────────────────────────────────────────────────────────
# STEP 2 — PROMPT BUILDER
# Each output type gets its own focused prompt
# ─────────────────────────────────────────────────────────────

def build_prompt(row: dict) -> str:
    """
    Single prompt that generates all 4 outputs at once.
    Returns valid JSON with exactly 4 keys.
    """
    name    = row.get("Full Name", "Customer")
    gender  = row.get("Gender", "")
    age     = row.get("Age", "")
    address = row.get("Address", "")
    occ     = row.get("Occupation", "")
    income  = row.get("Income Level", "")
    freq    = row.get("Purchase Frequency", "")
    pain    = row.get("Pain Points", "")
    goals   = row.get("Goals", "")
    prefs   = row.get("Preferences", "")
    channel = row.get("Preferred Contact", "WhatsApp")
    district= row.get("District", "Haryana")
    bakery  = row.get("Bakery", "Haryana Bakery")

    return f"""You are an expert Indian bakery marketing strategist for {bakery}.
Generate hyper-personalized marketing content for the customer below.
Respond ONLY with valid JSON — no markdown, no extra text outside the JSON.

CUSTOMER PROFILE:
Name={name}, Gender={gender}, Age={age}
Location={address}, District={district}
Occupation={occ}, Income={income}
Buys={freq}
Pain Points={pain}
Goals={goals}
Preferences={prefs}
Preferred Contact={channel}

Return EXACTLY this JSON structure:
{{
  "ad_copy": "Write a 2-3 sentence Facebook/Instagram ad. Include one Hindi or Haryanvi phrase that feels natural. Directly address their pain point ({pain}). End with a clear CTA mentioning {channel}.",
  "tweet_post": "Write a Twitter/X post under 280 characters. Include 2-3 relevant hashtags like #HisarBakery or #{district.replace(' ','')}Bakery. Can include 1-2 emojis. Address their goal ({goals}).",
  "offers": "Write ONE personalised promotional offer. Include a specific Rs or % discount value that matches their income level ({income}). Mention their purchase frequency ({freq}). Maximum 2 sentences.",
  "animation_prompt": "Write a 5-sentence Google Flow video prompt for a 15-second bakery ad. Sentence 1: opening scene setting. Sentence 2: product hero shot description. Sentence 3: customer lifestyle scene. Sentence 4: text overlay and voiceover. Sentence 5: closing CTA scene with color palette and music mood."
}}"""


# ─────────────────────────────────────────────────────────────
# STEP 3 — GROQ API CALL
# ─────────────────────────────────────────────────────────────

def _safe_parse(text: str) -> tuple:
    """Extract JSON from response, even if wrapped in markdown."""
    try:
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end]), True
    except Exception:
        pass
    return {}, False


def generate_for_persona(client: Groq, row: dict, persona_id: int) -> GeneratedContent:
    """Call Groq API and parse the 4 outputs for one persona."""
    t0 = time.monotonic()
    raw = ""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": build_prompt(row)}],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as e:
        log.warning(f"  API error for {row.get('Full Name','?')}: {e}")

    latency = (time.monotonic() - t0) * 1000
    parsed, success = _safe_parse(raw)

    return GeneratedContent(
        persona_id         = persona_id,
        name               = str(row.get("Full Name", "")),
        gender             = str(row.get("Gender", "")),
        age                = int(row.get("Age", 0)),
        district           = str(row.get("District", "")),
        occupation         = str(row.get("Occupation", "")),
        income_level       = str(row.get("Income Level", "")),
        purchase_frequency = str(row.get("Purchase Frequency", "")),
        ad_copy            = parsed.get("ad_copy", ""),
        tweet_post         = parsed.get("tweet_post", ""),
        offers             = parsed.get("offers", ""),
        animation_prompt   = parsed.get("animation_prompt", ""),
        raw_response       = raw,
        parse_success      = success,
        latency_ms         = round(latency, 1),
        model              = MODEL,
    )


# ─────────────────────────────────────────────────────────────
# STEP 4 — SAVE INDIVIDUAL .TXT FILES
# ─────────────────────────────────────────────────────────────

def save_as_txt(item: GeneratedContent, folder: str):
    """Save one persona's 4 outputs as a formatted .txt file."""
    fname = os.path.join(folder, f"{item.persona_id}.txt")

    content = f"""================================================================
{item.district.upper()} BAKERY — PERSONALIZED AD
Customer #{item.persona_id} | {item.name} | {item.age} yrs
Occupation: {item.occupation} | Income: {item.income_level}
================================================================

[ AD COPY — Facebook / Instagram ]
{item.ad_copy}

----------------------------------------------------------------

[ TWEET POST — Twitter / X ]
{item.tweet_post}

----------------------------------------------------------------

[ OFFER ]
{item.offers}

----------------------------------------------------------------

[ ANIMATION PROMPT — Google Flow ]
{item.animation_prompt}

================================================================
Generated by: {item.model} | Latency: {item.latency_ms:.0f}ms
================================================================
"""
    with open(fname, "w", encoding="utf-8") as f:
        f.write(content.strip())


# ─────────────────────────────────────────────────────────────
# STEP 5 — EVALUATION FRAMEWORK
# ─────────────────────────────────────────────────────────────

def _get(item, key):
    if isinstance(item, dict): return str(item.get(key, ""))
    return str(getattr(item, key, ""))

def _get_bool(item, key):
    if isinstance(item, dict): return bool(item.get(key, False))
    return bool(getattr(item, key, False))

def _get_float(item, key):
    if isinstance(item, dict): return float(item.get(key, 0.0))
    return float(getattr(item, key, 0.0))


def evaluate_single(item) -> dict:
    ad_copy          = _get(item, "ad_copy")
    tweet_post       = _get(item, "tweet_post")
    offers           = _get(item, "offers")
    animation_prompt = _get(item, "animation_prompt")
    name             = _get(item, "name")
    parse_success    = _get_bool(item, "parse_success")
    latency_ms       = _get_float(item, "latency_ms")

    fields = [ad_copy, tweet_post, offers, animation_prompt]
    scores = {}

    scores["parse_success"]      = int(parse_success)
    scores["field_completeness"] = sum(1 for f in fields if len(f.strip()) > 10) / 4
    scores["tweet_length_ok"]    = int(len(tweet_post) <= 280)
    scores["tweet_has_hashtag"]  = int("#" in tweet_post)

    first = name.split()[0].lower() if name.strip() else ""
    scores["persona_name_ref"]   = int(first in " ".join(fields).lower())

    hindi_kw = ["taaza","meetha","hisar","kesar","elaichi","desi","ghar",
                "fresh","roz","khao","aao","haryana","lao","naya"]
    scores["regional_tone"]      = int(any(k in ad_copy.lower() for k in hindi_kw))

    cinema_cues = ["camera","lighting","color","scene","close-up","pan",
                   "warm","golden","bokeh","slow motion","aerial","fade",
                   "zoom","shot","background","transition","music"]
    scores["animation_richness"] = min(
        sum(1 for c in cinema_cues if c in animation_prompt.lower()) / 3, 1.0
    )
    scores["offer_quantified"]   = int(
        "Rs" in offers or "%" in offers or
        "rs" in offers.lower() or "off" in offers.lower()
    )
    scores["latency_score"]      = (1.0 if latency_ms < 3000
                                    else 0.5 if latency_ms < 8000 else 0.0)

    weights = {
        "parse_success":0.20, "field_completeness":0.20,
        "tweet_length_ok":0.05, "tweet_has_hashtag":0.05,
        "persona_name_ref":0.10, "regional_tone":0.10,
        "animation_richness":0.15, "offer_quantified":0.10,
        "latency_score":0.05,
    }
    scores["aggregate"] = round(sum(scores[k] * w for k, w in weights.items()), 4)
    return scores


def evaluate_batch(results: list) -> dict:
    dicts      = [asdict(r) if not isinstance(r, dict) else r for r in results]
    all_scores = [evaluate_single(d) for d in dicts]
    keys       = list(all_scores[0].keys())

    summary = {}
    for key in keys:
        vals = [s[key] for s in all_scores]
        summary[key] = {
            "mean": round(sum(vals) / len(vals), 4),
            "min" : round(min(vals), 4),
            "max" : round(max(vals), 4),
        }

    agg   = summary["aggregate"]["mean"]
    grade = "A" if agg >= 0.85 else "B" if agg >= 0.70 else "C" if agg >= 0.55 else "D"

    return {
        "total_personas" : len(dicts),
        "overall_grade"  : grade,
        "aggregate_mean" : agg,
        "metrics"        : summary,
        "per_item"       : [
            {"persona_id": d["persona_id"], "name": d["name"], **evaluate_single(d)}
            for d in dicts
        ],
    }


# ─────────────────────────────────────────────────────────────
# STEP 6 — RESUME LOGIC
# Reads existing JSONL to find already-completed persona IDs
# ─────────────────────────────────────────────────────────────

def load_completed_ids() -> set:
    completed = set()
    if os.path.exists(OUT_JSONL):
        with open(OUT_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    if d.get("parse_success") and d.get("ad_copy"):
                        completed.add(d["persona_id"])
                except Exception:
                    pass
        if completed:
            log.info(f"Resuming — {len(completed)} personas already done, skipping.")
    return completed


# ─────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────

def run(sample: Optional[int] = None, dry_run: bool = False, district_filter: Optional[str] = None):
    """
    Full auto ad generation pipeline.

    Args:
        sample:          If set, only process first N personas (for testing)
        dry_run:         If True, skip API calls and use dummy data
        district_filter: If set, only process personas from this district
    """

    # ── Setup ────────────────────────────────────────────────
    os.makedirs(OUT_FOLDER, exist_ok=True)

    # ── Load data ─────────────────────────────────────────────
    df = load_personas()

    # Optional: filter by district
    if district_filter:
        df = df[df["District"].str.lower() == district_filter.lower()].copy()
        log.info(f"Filtered to district '{district_filter}': {len(df)} personas")

    # Optional: sample
    if sample:
        df = df.head(sample)
        log.info(f"Sample mode: processing {sample} personas")

    # ── Resume: skip already-done ─────────────────────────────
    completed_ids = load_completed_ids()

    # ── Init Groq client ──────────────────────────────────────
    client = None
    if not dry_run:
        api_key = GROQ_API_KEY
        if api_key == "your_groq_api_key_here":
            api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError(
                "Set GROQ_API_KEY.\n"
                "Windows: set GROQ_API_KEY=gsk_xxx\n"
                "Mac/Linux: export GROQ_API_KEY=gsk_xxx"
            )
        client = Groq(api_key=api_key)

    # ── Generation loop ───────────────────────────────────────
    results    = []
    total      = len(df)
    call_count = 0

    log.info(f"Starting generation for {total} personas...")
    log.info(f"Output folder : {OUT_FOLDER}/")
    log.info(f"Output JSONL  : {OUT_JSONL}")
    log.info("=" * 56)

    for i, (_, row) in enumerate(df.iterrows()):
        pid  = int(row["S.No"])
        name = str(row["Full Name"])

        # Skip already-completed personas
        if pid in completed_ids:
            continue

        log.info(f"[{i+1:5d}/{total}] {name:<25s} | {row.get('District',''):<15s} | {row.get('Occupation','')}")

        # ── Generate or use dummy ──────────────────────────────
        if dry_run:
            item = GeneratedContent(
                persona_id         = pid,
                name               = name,
                gender             = str(row.get("Gender", "")),
                age                = int(row.get("Age", 0)),
                district           = str(row.get("District", "Hisar")),
                occupation         = str(row.get("Occupation", "")),
                income_level       = str(row.get("Income Level", "")),
                purchase_frequency = str(row.get("Purchase Frequency", "")),
                ad_copy            = f"Hisar Bakery ke taaze bake goods sirf aapke liye, {name.split()[0]}! Fresh kesar bread daily. Order karo aaj hi on WhatsApp!",
                tweet_post         = f"Fresh bakes daily at Hisar Bakery! Perfect for {row.get('Occupation','you')}. #HisarBakery #FreshBaked #HaryanaFood",
                offers             = f"Special offer for {name.split()[0]}: Get 15% off on your next order above Rs 300. Valid this week only!",
                animation_prompt   = "Golden morning light floods a clean Hisar bakery kitchen. Camera slowly pans over freshly baked multigrain loaves on wooden racks. A smiling family at the breakfast table reaches for warm bread. Text overlay: 'Fresh Every Morning — Hisar Bakery' in warm amber font. Scene fades to bakery logo with upbeat Haryanvi folk music.",
                raw_response       = "{}",
                parse_success      = True,
                latency_ms         = 250.0,
                model              = MODEL,
            )
        else:
            item = generate_for_persona(client, row.to_dict(), pid)
            call_count += 1
            time.sleep(DELAY)

            # Pause every 50 calls to avoid rate limit
            if call_count % 50 == 0:
                log.info(f"  -- Pausing {BATCH_PAUSE}s after {call_count} calls --")
                time.sleep(BATCH_PAUSE)

        results.append(item)

        # ── Save individual .txt file immediately ──────────────
        save_as_txt(item, OUT_FOLDER)

        # ── Append to JSONL immediately (safe on crash) ────────
        with open(OUT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")

    log.info("=" * 56)
    log.info(f"Generation complete. Total new: {len(results)}")

    # ── Evaluation ────────────────────────────────────────────
    if results:
        log.info("Running evaluation...")
        report = evaluate_batch(results)

        with open(OUT_EVAL, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        log.info(f"Grade     : {report['overall_grade']}")
        log.info(f"Aggregate : {report['aggregate_mean']}")

        # Print per-metric summary
        log.info("\nMetric breakdown:")
        for metric, stats in report["metrics"].items():
            if metric != "aggregate":
                log.info(f"  {metric:<25s}: {stats['mean']:.2f}")
    else:
        log.info("No new personas generated — all already completed.")

    log.info(f"\nFiles saved to : {OUT_FOLDER}/")
    log.info(f"JSONL saved to : {OUT_JSONL}")
    log.info(f"Eval report    : {OUT_EVAL}")


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto Ad Generator — Bakery AI")

    parser.add_argument(
        "--sample", type=int, default=None,
        help="Process first N personas only (default: all)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Skip Groq API — use dummy data to test pipeline"
    )
    parser.add_argument(
        "--district", type=str, default=None,
        help="Only process personas from this district (e.g. --district Hisar)"
    )

    args = parser.parse_args()
    run(sample=args.sample, dry_run=args.dry_run, district_filter=args.district)