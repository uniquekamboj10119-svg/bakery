# 🍞 Hisar Bakery — Persona Content Generator & Eval Framework

Generates **ad_copy, tweet_post, offers, animation_prompt** for each of 1,500  
customer personas using Hugging Face Inference API, then scores every output  
against 9 evaluation metrics.

---

## Folder Structure

```
hisar_bakery_eval/
├── eval_framework.py   ← main pipeline + evaluation engine
├── prompts.py          ← all prompt templates (v1/v2/v3)
├── requirements.txt
└── README.md
```

---

## Setup

```bash
pip install -r requirements.txt
export HF_TOKEN="hf_YOUR_TOKEN_HERE"
```

Get a free token at https://huggingface.co/settings/tokens  
(read access is enough for serverless Inference API)

---

## Run

### Quick smoke test (dry run, no API calls)
```bash
python eval_framework.py --dry-run --sample 20
```

### Real generation — 50 personas
```bash
python eval_framework.py --sample 50
```

### Full 1500 personas (takes ~2-4 hours on free tier)
```bash
python eval_framework.py
```

### Change model
Edit `HF_MODEL` in `eval_framework.py`. Recommended models:
| Model | Speed | Quality |
|-------|-------|---------|
| `mistralai/Mistral-7B-Instruct-v0.3` | Fast | Good |
| `meta-llama/Meta-Llama-3-8B-Instruct` | Medium | Better |
| `Qwen/Qwen2.5-7B-Instruct` | Fast | Great for multilingual |

---

## Output Files

| File | Contents |
|------|----------|
| `generated_content.jsonl` | One JSON line per persona with all 4 outputs |
| `eval_report.json` | Aggregate + per-persona evaluation scores |

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

## Prompt Versions

Switch prompt strategy in `prompts.py`:

```python
# in eval_framework.py, change:
from prompts import get_prompt
prompt_fn = get_prompt("v2")   # v1 | v2 (CoT) | v3 (minimal)
```

| Version | Strategy | Best for |
|---------|----------|----------|
| v1 | Direct JSON | Default, balanced |
| v2 | Chain-of-Thought + JSON | Higher quality, slower |
| v3 | Minimal 1-shot | Small/fast models |

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
  "ad_copy": "Mamta ji, ताज़ा multigrain bread sirf aapke liye! Hisar Bakery now offers 
              kesar-elaichi whole wheat loaves baked fresh every morning. Order on our 
              app and get student discount — Order karo, swad lo! 🍞",
  "tweet_post": "Fresh multigrain bakes daily at Hisar Bakery! 🥖 
                 Perfect for health-conscious families in Hisar. 
                 #HisarBakery #FreshBaked #HaryanaFood",
  "offers": "Student Special: 15% off on all multigrain products on orders above ₹300. 
             Valid Mon-Fri. Show student ID on app checkout.",
  "animation_prompt": "Warm morning light streams into a cozy Hisar Bakery kitchen. 
                       Camera starts with a slow aerial pan over golden multigrain loaves 
                       cooling on a wooden rack. Close-up of steam rising as a loaf is 
                       sliced, revealing seeded texture. Warm amber and cream color palette 
                       with soft bokeh. Scene fades to a smiling family at breakfast table 
                       with Hisar Bakery packaging.",
  "parse_success": true,
  "latency_ms": 2340.5
}
```
