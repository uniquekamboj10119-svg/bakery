"""
Hisar Bakery — Persona-Driven AI Content Generator & Evaluation Framework
Uses: Groq API (free, fast)
Generates: ad_copy, tweet_post, offers, animation_prompt
"""

import os
import json
import time
import random
import logging
import argparse
from dataclasses import dataclass, asdict
from typing import Optional

import pandas as pd
from groq import Groq

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

MODEL          = "llama-3.1-8b-instant"   # free, very fast on Groq
MAX_TOKENS     = 700
TEMPERATURE    = 0.8
BATCH_SIZE     = 50
OUTPUT_JSONL   = "generated_content.jsonl"
EVAL_REPORT    = "eval_report.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────

@dataclass
class GeneratedContent:
    persona_id: int
    name: str
    gender: str
    age: int
    occupation: str
    income_level: str
    purchase_frequency: str
    ad_copy: str
    tweet_post: str
    offers: str
    animation_prompt: str
    raw_response: str
    parse_success: bool
    latency_ms: float
    model: str


# ─────────────────────────────────────────────
# PROMPT
# ─────────────────────────────────────────────

def build_prompt(row: dict) -> str:
    return f"""You are an expert Indian bakery marketing strategist for Hisar Bakery,
a premium local bakery in Hisar, Haryana. Generate hyper-personalized marketing content.
Respond ONLY with valid JSON — no markdown, no extra text.

PERSONA:
Name={row['Full Name']}, Gender={row['Gender']}, Age={row['Age']}
Location={row['Address (Hisar)']}, Occupation={row['Occupation']}
Income={row['Income Level']}, Buys={row['Purchase Frequency']}
Pain Points={row['Pain Points']}
Goals={row['Goals']}
Preferences={row['Specifications/Preferences']}
Contact Preference={row['Preferred Contact']}

Return this exact JSON:
{{
  "ad_copy": "2-3 sentence Facebook/Instagram ad. Include a Hindi/Haryanvi phrase. End with CTA.",
  "tweet_post": "Max 280 chars. 2-3 hashtags like #HisarBakery. Emoji ok.",
  "offers": "One personalized offer with Rs or % value suited to their income and frequency.",
  "animation_prompt": "5-sentence Google Veo/Flow video prompt: setting, mood, product, camera movement, color palette."
}}"""


# ─────────────────────────────────────────────
# GENERATION
# ─────────────────────────────────────────────

def generate_content(client: Groq, row: dict) -> GeneratedContent:
    prompt = build_prompt(row)
    t0 = time.monotonic()

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as e:
        log.warning(f"[ID {row['S.No']}] API error: {e}")
        raw = ""

    latency = (time.monotonic() - t0) * 1000
    parsed, success = _safe_parse(raw)

    return GeneratedContent(
        persona_id        = int(row["S.No"]),
        name              = str(row["Full Name"]),
        gender            = str(row["Gender"]),
        age               = int(row["Age"]),
        occupation        = str(row["Occupation"]),
        income_level      = str(row["Income Level"]),
        purchase_frequency= str(row["Purchase Frequency"]),
        ad_copy           = parsed.get("ad_copy", ""),
        tweet_post        = parsed.get("tweet_post", ""),
        offers            = parsed.get("offers", ""),
        animation_prompt  = parsed.get("animation_prompt", ""),
        raw_response      = raw,
        parse_success     = success,
        latency_ms        = round(latency, 1),
        model             = MODEL,
    )


def _safe_parse(text: str) -> tuple:
    try:
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end]), True
    except Exception:
        pass
    return {}, False


# ─────────────────────────────────────────────
# EVALUATION
# FIX: accepts BOTH dataclass and dict via helper
# ─────────────────────────────────────────────

def _get(item, key: str) -> str:
    """
    Safely get a field from either a GeneratedContent dataclass
    or a plain dict (after asdict() conversion).
    This is the root fix for the AttributeError.
    """
    if isinstance(item, dict):
        return str(item.get(key, ""))
    return str(getattr(item, key, ""))


def _get_bool(item, key: str) -> bool:
    if isinstance(item, dict):
        return bool(item.get(key, False))
    return bool(getattr(item, key, False))


def _get_float(item, key: str) -> float:
    if isinstance(item, dict):
        return float(item.get(key, 0.0))
    return float(getattr(item, key, 0.0))


def evaluate_single(item) -> dict:
    """
    Evaluate one GeneratedContent — works with both
    dataclass instances and plain dicts.
    """
    scores = {}

    ad_copy          = _get(item, "ad_copy")
    tweet_post       = _get(item, "tweet_post")
    offers           = _get(item, "offers")
    animation_prompt = _get(item, "animation_prompt")
    name             = _get(item, "name")
    parse_success    = _get_bool(item, "parse_success")
    latency_ms       = _get_float(item, "latency_ms")

    fields = [ad_copy, tweet_post, offers, animation_prompt]

    scores["parse_success"]      = int(parse_success)
    scores["field_completeness"] = sum(1 for f in fields if len(f.strip()) > 10) / 4
    scores["tweet_length_ok"]    = int(len(tweet_post) <= 280)
    scores["tweet_has_hashtag"]  = int("#" in tweet_post)

    first_name = name.split()[0].lower() if name.strip() else ""
    scores["persona_name_ref"]   = int(first_name in " ".join(fields).lower())

    hindi_keywords = ["taaza","meetha","khaas","swaad","dil","aao","lao","khao",
                      "haryana","hisar","kesar","elaichi","desi","ghar",
                      "fresh","roz","naya","khushbu"]
    scores["regional_tone"]      = int(any(kw in ad_copy.lower() for kw in hindi_keywords))

    cinema_cues = ["camera","lighting","color","scene","close-up","pan",
                   "warm","golden","bokeh","slow motion","aerial","fade",
                   "zoom","shot","background","foreground","transition"]
    scores["animation_richness"] = min(
        sum(1 for cue in cinema_cues if cue in animation_prompt.lower()) / 3,
        1.0
    )
    scores["offer_quantified"]   = int("Rs" in offers or "%" in offers or
                                       "rs" in offers.lower() or "off" in offers.lower())
    scores["latency_score"]      = (1.0 if latency_ms < 3000
                                    else 0.5 if latency_ms < 8000
                                    else 0.0)

    weights = {
        "parse_success"      : 0.20,
        "field_completeness" : 0.20,
        "tweet_length_ok"    : 0.05,
        "tweet_has_hashtag"  : 0.05,
        "persona_name_ref"   : 0.10,
        "regional_tone"      : 0.10,
        "animation_richness" : 0.15,
        "offer_quantified"   : 0.10,
        "latency_score"      : 0.05,
    }
    scores["aggregate"] = round(
        sum(scores[k] * w for k, w in weights.items()), 4
    )
    return scores


def evaluate_batch(results: list) -> dict:
    """
    results is a list of GeneratedContent dataclass objects.
    Convert each to dict first so evaluate_single always
    receives the same type.
    """
    # Normalise — convert dataclass → dict if needed
    dicts = [asdict(r) if not isinstance(r, dict) else r for r in results]

    all_scores  = [evaluate_single(d) for d in dicts]
    metric_keys = list(all_scores[0].keys())

    summary = {}
    for key in metric_keys:
        vals = [s[key] for s in all_scores]
        summary[key] = {
            "mean": round(sum(vals) / len(vals), 4),
            "min" : round(min(vals), 4),
            "max" : round(max(vals), 4),
        }

    agg   = summary["aggregate"]["mean"]
    grade = ("A" if agg >= 0.85 else
             "B" if agg >= 0.70 else
             "C" if agg >= 0.55 else "D")

    return {
        "total_personas" : len(dicts),
        "overall_grade"  : grade,
        "aggregate_mean" : agg,
        "metrics"        : summary,
        "per_item"       : [
            {
                "persona_id": d["persona_id"],
                "name"      : d["name"],
                **evaluate_single(d)
            }
            for d in dicts
        ],
    }


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run(csv_path: str, sample: Optional[int] = None, dry_run: bool = False):

    # Support both .xlsx and .csv input files
    if csv_path.endswith(".xlsx"):
        df = pd.read_excel(csv_path, header=1)
    else:
        df = pd.read_csv(csv_path)

    df = df.dropna(subset=["S.No", "Full Name"])

    if sample:
        df = df.head(sample)
        log.info(f"Running on {sample} personas (sample mode)")
    else:
        log.info(f"Running on all {len(df)} personas")

    # Resume logic — skip already completed personas
    completed_ids = set()
    if os.path.exists(OUTPUT_JSONL):
        with open(OUTPUT_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if data.get("parse_success") and data.get("ad_copy"):
                        completed_ids.add(data["persona_id"])
                except Exception:
                    pass
        if completed_ids:
            log.info(f"Resuming — {len(completed_ids)} personas already done, skipping.")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key and not dry_run:
        raise ValueError(
            "GROQ_API_KEY environment variable not set.\n"
            "Run:  set GROQ_API_KEY=your_key_here   (Windows)\n"
            "  or  export GROQ_API_KEY=your_key_here (Mac/Linux)"
        )

    client  = Groq(api_key=api_key) if not dry_run else None
    results = []

    for i, (_, row) in enumerate(df.iterrows()):
        pid = int(row["S.No"])
        if pid in completed_ids:
            continue

        log.info(f"[{i+1}/{len(df)}] Generating for: {row['Full Name']}")

        if dry_run:
            item = GeneratedContent(
                persona_id        = pid,
                name              = str(row["Full Name"]),
                gender            = str(row["Gender"]),
                age               = int(row["Age"]),
                occupation        = str(row["Occupation"]),
                income_level      = str(row["Income Level"]),
                purchase_frequency= str(row["Purchase Frequency"]),
                ad_copy           = "Hisar Bakery ke taaze bake goods sirf aapke liye! Fresh kesar bread daily. Order karo aaj hi!",
                tweet_post        = "Fresh bakes daily at Hisar Bakery! #HisarBakery #FreshBaked #HaryanaFood",
                offers            = "Get 20% off on orders above Rs 500 this week!",
                animation_prompt  = "Warm golden morning light in Hisar Bakery. Camera pans over fresh loaves. Close-up of steam rising. Amber color palette with soft bokeh. Fade to bakery logo.",
                raw_response      = "{}",
                parse_success     = True,
                latency_ms        = round(random.uniform(200, 800), 1),
                model             = MODEL,
            )
        else:
            item = generate_content(client, row)

        results.append(item)

        # Write to JSONL immediately (safe on crash)
        with open(OUTPUT_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")

        # Small pause every BATCH_SIZE calls to avoid rate limit
        if (i + 1) % BATCH_SIZE == 0:
            log.info(f"Batch of {BATCH_SIZE} complete. Pausing 1s...")
            time.sleep(1)

    log.info("Running evaluation...")
    report = (evaluate_batch(results)
              if results
              else {"note": "No new personas generated — all already completed."})

    with open(EVAL_REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    if results:
        log.info(f"Done! Grade: {report['overall_grade']} | "
                 f"Aggregate: {report['aggregate_mean']}")
    log.info(f"Output : {OUTPUT_JSONL}")
    log.info(f"Report : {EVAL_REPORT}")

    return report


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hisar Bakery Groq Content Generator")
    parser.add_argument("--csv",
                        default="Hisar_Bakery_1500_Customer_Personas.xlsx",
                        help="Path to personas file (.xlsx or .csv)")
    parser.add_argument("--sample",
                        type=int,
                        default=None,
                        help="Run on first N personas only (for testing)")
    parser.add_argument("--dry-run",
                        action="store_true",
                        help="Skip API calls, use dummy data to test pipeline")
    args = parser.parse_args()

    run(csv_path=args.csv, sample=args.sample, dry_run=args.dry_run)
