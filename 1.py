import os, csv, json, time, re
import pandas as pd
import requests
from datetime import datetime

# ── Auto-fix working directory to script location ──────────
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ── The only 3 constants you ever need to change ───────────
CSV_PATH   = "all_12500_personas.csv"
OUTPUT_CSV = "generated_ads.csv"
EVAL_CSV   = "evaluation_scores.csv"

# HuggingFace token — get free at huggingface.co/settings/tokens
HF_TOKEN   = "hf_YOUR_TOKEN_HERE"
HF_MODEL   = "mistralai/Mistral-7B-Instruct-v0.3"

BATCH_SIZE   = 10
MAX_NEW_TOK  = 600
TEMPERATURE  = 0.7

HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
HEADERS    = {"Authorization": f"Bearer {HF_TOKEN}"}


# ══════════════════════════════════════════════════════════
#  STEP 1 — BUILD PROMPT
# ══════════════════════════════════════════════════════════

def build_prompt(row):
    name    = str(row['Name']).strip()
    gender  = str(row['Gender']).strip()
    age     = str(row['Age']).strip()
    dist    = str(row['District']).strip()
    occ     = str(row['Occupation']).strip()
    income  = str(row['Income']).strip()
    pain    = str(row['PainPoints']).strip().split(';')[0].strip()
    goal    = str(row['Goals']).strip().split(';')[0].strip()
    pref    = str(row['Preferences']).strip().split(';')[0].strip()
    channel = str(row['PreferredContact']).strip()
    freq    = str(row['PurchaseFrequency']).strip()
    adtype  = str(row['AdType']).strip()
    bakery  = str(row['BakeryName']).strip()
    sal     = "Ms." if gender == "Female" else "Mr."

    type_desc = {
        "PREMIUM":  "premium gift boxes, corporate orders, wedding cakes",
        "HEALTH":   "multigrain bread, sugar-free biscuits, protein cookies",
        "FESTIVE":  "festival hampers, mithai, prasad packs",
        "DAILY":    "fresh daily bread, rusks, consistent morning bakes",
    }.get(adtype, "fresh bakery products")

    prompt = f"""<s>[INST]
You are an expert advertising copywriter for an Indian bakery.
Generate 4 personalised outputs for this customer. Reply ONLY with a valid JSON object.

CUSTOMER:
Name: {sal} {name} | Age: {age} | Location: {dist}, Haryana
Job: {occ} | Income: {income}
Pain Point: {pain}
Goal: {goal}
Preference: {pref}
Contact: {channel} | Visits: {freq}
Ad Type: {adtype} ({type_desc})
Bakery: {bakery}

Return this exact JSON structure:
{{
  "ad_copy": "80-100 word personalised ad. Address {sal} {name} directly. Mention their pain point, goal, and {bakery}. End with CTA via {channel}.",
  "tweet_post": "Under 240 chars. Catchy tweet for {bakery}. Add 2-3 hashtags like #{dist}Bakery #FreshBaked #HaryanaBakery.",
  "offer": "30-40 word promo offer for {sal} {name}. Give specific deal like 15% off or free delivery. Mention {bakery}.",
  "animation_prompt": "50-60 word Google Flow video prompt. Describe 5-10 sec bakery animation. Include: product, motion, colours, mood, text overlay. Match {adtype} theme."
}}[/INST]"""
    return prompt


# ══════════════════════════════════════════════════════════
#  STEP 2 — CALL HUGGINGFACE API
# ══════════════════════════════════════════════════════════

def call_hf(prompt, retries=3):
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens":   MAX_NEW_TOK,
            "temperature":      TEMPERATURE,
            "return_full_text": False,
            "do_sample":        True,
        }
    }
    for attempt in range(retries):
        try:
            r = requests.post(HF_API_URL, headers=HEADERS,
                              json=payload, timeout=60)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and data:
                    return data[0].get("generated_text", "")
            elif r.status_code == 503:
                wait = 20 * (attempt + 1)
                print(f"    Model loading — waiting {wait}s...")
                time.sleep(wait)
            elif r.status_code == 429:
                print("    Rate limited — waiting 30s...")
                time.sleep(30)
            else:
                print(f"    API error {r.status_code}: {r.text[:80]}")
                time.sleep(5)
        except requests.exceptions.Timeout:
            print(f"    Timeout (attempt {attempt+1})")
            time.sleep(10)
        except Exception as e:
            print(f"    Error: {e}")
            time.sleep(5)
    return None


# ══════════════════════════════════════════════════════════
#  STEP 3 — PARSE JSON RESPONSE
# ══════════════════════════════════════════════════════════

def parse_response(raw):
    empty = {"ad_copy":"","tweet_post":"","offer":"",
             "animation_prompt":"","parse_error":""}
    if not raw:
        empty["parse_error"] = "empty_response"
        return empty

    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            data = json.loads(match.group())
            for k in ["ad_copy","tweet_post","offer","animation_prompt"]:
                if k not in data:
                    data[k] = ""
            data["parse_error"] = ""
            return data
        except json.JSONDecodeError:
            pass

    result = {"parse_error": "json_failed"}
    for k in ["ad_copy","tweet_post","offer","animation_prompt"]:
        m = re.search(rf'"{k}"\s*:\s*"([^"]+)"', raw, re.IGNORECASE)
        result[k] = m.group(1) if m else ""
    return result


# ══════════════════════════════════════════════════════════
#  STEP 4 — EVALUATION (5 metrics, no external model)
# ══════════════════════════════════════════════════════════

def evaluate(row, outputs):
    name   = str(row['Name']).strip()
    dist   = str(row['District']).strip()
    bakery = str(row['BakeryName']).strip()
    pain   = str(row['PainPoints']).strip().split(';')[0].lower()
    goal   = str(row['Goals']).strip().split(';')[0].lower()

    scores  = {}
    targets = {
        "ad_copy":          (70, 120),
        "tweet_post":       (15,  45),
        "offer":            (20,  50),
        "animation_prompt": (40,  80),
    }
    cta_words    = ["call","whatsapp","order","visit","contact","message",
                    "book","buy","grab","claim","get","dial"]
    bakery_words = ["bakery","bread","bake","fresh","rusk","biscuit","cake",
                    "mithai","hamper","offer","discount","order","sweet"]

    for ot in ["ad_copy","tweet_post","offer","animation_prompt"]:
        text  = outputs.get(ot, "")
        tlow  = text.lower()
        words = text.split()

        # 1. Personalisation
        hits = sum([
            name.split()[0].lower() in tlow,
            dist.lower()   in tlow,
            bakery.lower() in tlow,
            any(w in tlow for w in pain.split()[:3]),
            any(w in tlow for w in goal.split()[:3]),
        ])
        p = round(hits / 5, 2)

        # 2. Relevance
        r = round(min(sum(1 for w in bakery_words if w in tlow) / 4, 1.0), 2)

        # 3. Length
        lo, hi = targets[ot]
        wc = len(words)
        if lo <= wc <= hi:  l = 1.0
        elif wc < lo:       l = round(wc / lo, 2)
        else:               l = round(hi / wc, 2)

        # 4. CTA
        c = 1.0 if any(w in tlow for w in cta_words) else 0.0

        # 5. Fluency
        f = round(min((len(set(words)) / len(words)) * 1.5, 1.0), 2) \
            if words else 0.0

        overall = round(0.30*p + 0.25*r + 0.20*l + 0.15*c + 0.10*f, 2)

        scores[f"{ot}_personalisation"] = p
        scores[f"{ot}_relevance"]        = r
        scores[f"{ot}_length"]           = l
        scores[f"{ot}_cta"]              = c
        scores[f"{ot}_fluency"]          = f
        scores[f"{ot}_overall"]          = overall

    scores["mean_overall"] = round(
        sum(scores[f"{k}_overall"]
            for k in ["ad_copy","tweet_post","offer","animation_prompt"]) / 4, 2)
    return scores


# ══════════════════════════════════════════════════════════
#  STEP 5 — MAIN PIPELINE
# ══════════════════════════════════════════════════════════

def run_pipeline():
    print("=" * 60)
    print("  BAKERY PROMPT ENGINEERING PIPELINE")
    print(f"  Model  : {HF_MODEL}")
    print(f"  CSV    : {CSV_PATH}")
    print(f"  Folder : {os.getcwd()}")
    print(f"  Batch  : {BATCH_SIZE} personas")
    print("=" * 60 + "\n")

    # Verify CSV exists
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: CSV not found at:")
        print(f"  {os.path.abspath(CSV_PATH)}")
        print(f"\nFiles in this folder:")
        for f in os.listdir("."):
            print(f"  {f}")
        exit(1)

    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    print(f"Loaded {len(df):,} personas.\n")

    # Resume support
    done_ids = set()
    if os.path.exists(OUTPUT_CSV):
        try:
            done_df  = pd.read_csv(OUTPUT_CSV, encoding="utf-8-sig")
            done_ids = set(done_df["PersonaID"].astype(str).tolist())
            print(f"Resuming — {len(done_ids):,} already processed.\n")
        except Exception:
            pass

    out_fields = ["PersonaID","Name","District","AdType",
                  "ad_copy","tweet_post","offer","animation_prompt",
                  "parse_error","generated_at"]

    eval_fields = ["PersonaID","Name","AdType","mean_overall"] + [
        f"{ot}_{m}"
        for ot in ["ad_copy","tweet_post","offer","animation_prompt"]
        for m  in ["personalisation","relevance","length","cta","fluency","overall"]
    ]

    write_header = not os.path.exists(OUTPUT_CSV) or len(done_ids) == 0

    out_f  = open(OUTPUT_CSV, "a", newline="", encoding="utf-8-sig")
    eval_f = open(EVAL_CSV,   "a", newline="", encoding="utf-8-sig")
    out_w  = csv.DictWriter(out_f,  fieldnames=out_fields,  extrasaction="ignore")
    eval_w = csv.DictWriter(eval_f, fieldnames=eval_fields, extrasaction="ignore")

    if write_header:
        out_w.writeheader()
        eval_w.writeheader()

    processed   = 0
    total_score = 0.0

    for _, row in df.iterrows():
        pid = str(row["PersonaID"])
        if pid in done_ids:
            continue
        if processed >= BATCH_SIZE:
            print(f"\nBatch of {BATCH_SIZE} complete. Run again to continue.")
            break

        print(f"[{processed+1:3d}/{BATCH_SIZE}] {pid} — "
              f"{row['Name']} ({row['AdType']})")

        prompt  = build_prompt(row)
        raw     = call_hf(prompt)
        outputs = parse_response(raw)
        scores  = evaluate(row, outputs)
        total_score += scores["mean_overall"]

        print(f"  Score: {scores['mean_overall']:.2f} | "
              f"ad:{scores['ad_copy_overall']:.2f} | "
              f"tweet:{scores['tweet_post_overall']:.2f} | "
              f"offer:{scores['offer_overall']:.2f} | "
              f"anim:{scores['animation_prompt_overall']:.2f}")

        if outputs.get("parse_error"):
            print(f"  Parse note: {outputs['parse_error']}")

        out_row = {
            "PersonaID":        pid,
            "Name":             row["Name"],
            "District":         row["District"],
            "AdType":           row["AdType"],
            "ad_copy":          outputs.get("ad_copy",""),
            "tweet_post":       outputs.get("tweet_post",""),
            "offer":            outputs.get("offer",""),
            "animation_prompt": outputs.get("animation_prompt",""),
            "parse_error":      outputs.get("parse_error",""),
            "generated_at":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        eval_row = {
            "PersonaID": pid,
            "Name":      row["Name"],
            "AdType":    row["AdType"],
        }
        eval_row.update(scores)

        out_w.writerow(out_row)
        eval_w.writerow(eval_row)
        out_f.flush()
        eval_f.flush()

        processed += 1
        time.sleep(1)

    out_f.close()
    eval_f.close()

    if processed > 0:
        avg = total_score / processed
        print(f"\n{'='*60}")
        print(f"  Done.")
        print(f"  Processed        : {processed}")
        print(f"  Avg score        : {avg:.2f} / 1.00")
        print(f"  Results saved to : {os.path.abspath(OUTPUT_CSV)}")
        print(f"  Scores saved to  : {os.path.abspath(EVAL_CSV)}")
        print(f"{'='*60}")
    else:
        print("Nothing new to process.")


# ══════════════════════════════════════════════════════════
#  STEP 6 — EVALUATION REPORT
# ══════════════════════════════════════════════════════════

def print_report():
    if not os.path.exists(EVAL_CSV):
        print("No evaluation file yet. Run pipeline first.")
        return

    df = pd.read_csv(EVAL_CSV, encoding="utf-8-sig")
    print(f"\n{'='*60}")
    print(f"  EVALUATION REPORT — {len(df)} personas scored")
    print(f"{'='*60}")

    for ot in ["ad_copy","tweet_post","offer","animation_prompt"]:
        print(f"\n  {ot.upper()}")
        for m in ["personalisation","relevance","length","cta","fluency","overall"]:
            col = f"{ot}_{m}"
            if col in df.columns:
                print(f"    {m:20s}: {df[col].mean():.3f}")

    print(f"\n  MEAN OVERALL : {df['mean_overall'].mean():.3f}")
    print(f"\n  BY AD TYPE:")
    for at, grp in df.groupby("AdType"):
        print(f"    {at:10s}: {grp['mean_overall'].mean():.3f} "
              f"({len(grp)} personas)")
    print(f"{'='*60}\n")


# ══════════════════════════════════════════════════════════
#  STEP 7 — SHOW SAMPLE OUTPUTS
# ══════════════════════════════════════════════════════════

def show_sample(n=2):
    if not os.path.exists(OUTPUT_CSV):
        print("No output file yet.")
        return
    df = pd.read_csv(OUTPUT_CSV, encoding="utf-8-sig")
    df = df.dropna(subset=["ad_copy"])
    df = df[df["ad_copy"].str.strip() != ""]
    if df.empty:
        print("No generated ads found.")
        return
    for _, row in df.sample(min(n, len(df))).iterrows():
        print(f"\n{'─'*56}")
        print(f"  {row['PersonaID']} | {row['Name']} | "
              f"{row['AdType']} | {row['District']}")
        print(f"{'─'*56}")
        print(f"AD COPY:\n{row['ad_copy']}\n")
        print(f"TWEET:\n{row['tweet_post']}\n")
        print(f"OFFER:\n{row['offer']}\n")
        print(f"ANIMATION PROMPT:\n{row['animation_prompt']}\n")


# ══════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":

    if "YOUR_TOKEN" in HF_TOKEN:
        print("=" * 60)
        print("  ERROR: HuggingFace token not set.")
        print("  1. Go to: https://huggingface.co/settings/tokens")
        print("  2. Click New token > Role: Read > Copy it")
        print("  3. Replace hf_YOUR_TOKEN_HERE with your token")
        print("=" * 60)
        exit(1)

    run_pipeline()
    print_report()
    show_sample(n=2)