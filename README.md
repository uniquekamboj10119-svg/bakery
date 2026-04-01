# 🍞 Hisar Bakery — Persona Content Generator & Eval Framework

Generates **ad_copy, tweet_post, offers, animation_prompt** for each of 1,500  
customer personas using **Groq API (free, fast)**, then scores every output  
against 9 evaluation metrics.

---

## Folder Structure

```
Prompt By me/
├── eval_groq.py                          ← main pipeline (Groq API)
├── prompts.py                            ← prompt templates (v1/v2/v3)
├── requirements_groq.txt                 ← dependencies
├── README_groq.md                        ← this file
├── generated_content.jsonl               ← outputs (auto-created)
├── eval_report.json                      ← evaluation scores (auto-created)
└── Hisar_Bakery_1500_Customer_Personas.xlsx
```

---

## Setup

```bash
pip install -r requirements_groq.txt
```

**Set your Groq API key** (get free key at https://console.groq.com):

Windows PowerShell:
```powershell
$env:GROQ_API_KEY = "gsk_YOUR_KEY_HERE"
```

To set it permanently (never need to set again):
```powershell
[System.Environment]::SetEnvironmentVariable("GROQ_API_KEY", "gsk_YOUR_KEY_HERE", "User")
```
Then close and reopen VS Code.

---

## Run

### Quick smoke test (no API calls)
```powershell
python eval_groq.py --dry-run --sample 20
```

### Real generation — 5 personas to test
```powershell
python eval_groq.py --sample 5
```

### Full 1500 personas
```powershell
python eval_groq.py
```

### Resume after interruption
Just run the same command again — it automatically skips already completed personas:
```powershell
python eval_groq.py
```

---

## Output Files

| File | Contents |
|------|----------|
| `generated_content.jsonl` | One JSON line per persona with all 4 outputs |
| `eval_report.json` | Aggregate + per-persona evaluation scores |

---

## Groq Rate Limits (Free Tier)

| Limit | Value |
|-------|-------|
| Tokens per day | 500,000 |
| Requests per minute | ~30 |
| Cost | FREE |

At ~600 tokens per persona, you can process ~800 personas per day.  
If you hit the daily limit, just run again the next day — resume is automatic.

---

## Evaluation Metrics (9 dimensions)

| Metric | Weight | What it checks |
|--------|--------|---------------|
| `parse_success` | 20% | Valid JSON returned |
| `field_completeness` | 20% | All 4 fields non-empty |
| `regional_tone` | 10% | Hindi/Haryanvi keywords in ad |
| `persona_name_ref` | 10% | First name appears in content |
| `animation_richness` | 15% | ≥3 cinematic cues in prompt |
| `offer_quantified` | 10% | ₹ or % in offer |
| `tweet_length_ok` | 5% | Tweet ≤ 280 chars |
| `tweet_has_hashtag` | 5% | # present in tweet |
| `latency_score` | 5% | Response time |

**Grade scale:** A ≥ 0.85 · B ≥ 0.70 · C ≥ 0.55 · D < 0.55

---

## Animation Prompt Usage (Google Veo / Flow)

The `animation_prompt` field is ready to paste directly into:
- **Google Veo 2** (via VideoFX / Vertex AI)
- **Google Flow** (AI filmmaking tool)
- **Runway Gen-3**, **Kling**, **Pika**

Each prompt specifies: setting · mood · product · camera movement · color palette  
for a 6-10 second bakery advertisement scene.

---

## Example Output

```json
{
  "persona_id": 1,
  "name": "Mamta Antil",
  "ad_copy": "Mamta ji, ताज़ा multigrain bread sirf aapke liye! Hisar Bakery now offers kesar-elaichi whole wheat loaves baked fresh every morning. Order on our app and get student discount — Order karo, swad lo! 🍞",
  "tweet_post": "Fresh multigrain bakes daily at Hisar Bakery! 🥖 Perfect for health-conscious families in Hisar. #HisarBakery #FreshBaked #HaryanaFood",
  "offers": "Student Special: 15% off on all multigrain products on orders above ₹300. Valid Mon-Fri.",
  "animation_prompt": "Warm morning light streams into a cozy Hisar Bakery kitchen. Camera starts with a slow aerial pan over golden multigrain loaves cooling on a wooden rack. Close-up of steam rising as a loaf is sliced. Warm amber and cream color palette with soft bokeh. Scene fades to a smiling family at breakfast table with Hisar Bakery packaging.",
  "parse_success": true,
  "latency_ms": 1166.8
}
```
