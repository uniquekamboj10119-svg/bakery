"""
prompts.py — Prompt templates for Hisar Bakery content generation
Swap or extend these without touching the main pipeline.
"""

# ─────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────

SYSTEM = """You are an expert Indian bakery marketing strategist for Hisar Bakery,
a premium local bakery in Hisar, Haryana. You write hyper-personalized, 
culturally warm marketing content. Respond ONLY in valid JSON — no markdown."""


# ─────────────────────────────────────────────────────────────
# V1 — Full JSON  (default)
# ─────────────────────────────────────────────────────────────

def v1_full_json(row: dict) -> str:
    return f"""{SYSTEM}

Generate 4 marketing assets for this persona. Return ONLY valid JSON.

PERSONA:
Name={row['Full Name']}, Gender={row['Gender']}, Age={row['Age']}
Location={row['Address (Hisar)']}, Occupation={row['Occupation']}
Income={row['Income Level']}, Buys={row['Purchase Frequency']}
Pain Points={row['Pain Points']}
Goals={row['Goals']}
Preferences={row['Specifications/Preferences']}
Contact Preference={row['Preferred Contact']}

{{
  "ad_copy": "2-3 sentences. Include a Hindi/Haryanvi phrase. End with CTA.",
  "tweet_post": "Max 280 chars. 2-3 hashtags (#HisarBakery etc). Emoji ok.",
  "offers": "One personalized promo with ₹ or % value, suited to their income/frequency.",
  "animation_prompt": "5-sentence Google Veo/Flow video prompt: setting, mood, product, camera, palette."
}}"""


# ─────────────────────────────────────────────────────────────
# V2 — Chain-of-Thought before JSON  (better quality, slower)
# ─────────────────────────────────────────────────────────────

def v2_cot(row: dict) -> str:
    return f"""{SYSTEM}

Step 1 — Think briefly (2 sentences) about what matters most to this customer.
Step 2 — Output valid JSON with the 4 marketing assets.

PERSONA:
Name={row['Full Name']}, Age={row['Age']}, Occupation={row['Occupation']}
Income={row['Income Level']}, Pain Points={row['Pain Points']}
Goals={row['Goals']}, Frequency={row['Purchase Frequency']}

FORMAT:
{{
  "thinking": "brief reasoning",
  "ad_copy": "...",
  "tweet_post": "...",
  "offers": "...",
  "animation_prompt": "..."
}}"""


# ─────────────────────────────────────────────────────────────
# V3 — Minimal / fast  (for high-throughput, small models)
# ─────────────────────────────────────────────────────────────

def v3_minimal(row: dict) -> str:
    return f"""Bakery marketer. Customer: {row['Full Name']}, {row['Age']}yr {row['Occupation']}, 
{row['Income Level']}, buys {row['Purchase Frequency']}. 
Pain: {row['Pain Points'][:80]}. Goal: {row['Goals'][:80]}.

Return JSON:
{{"ad_copy":"...","tweet_post":"...","offers":"...","animation_prompt":"..."}}"""


# ─────────────────────────────────────────────────────────────
# REGISTRY — pick by name
# ─────────────────────────────────────────────────────────────

REGISTRY = {
    "v1": v1_full_json,
    "v2": v2_cot,
    "v3": v3_minimal,
}

def get_prompt(version: str = "v1"):
    if version not in REGISTRY:
        raise ValueError(f"Unknown prompt version '{version}'. Choose: {list(REGISTRY)}")
    return REGISTRY[version]
