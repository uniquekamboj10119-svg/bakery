import os, glob, json
import faiss
from sentence_transformers import SentenceTransformer

# ── Constants ──
FOLDER  = "knowledge base\\out_going\\all_200k_ads"   # your ads folder
INDEX_F = "ad_bot.index"
META_F  = "ad_metadata.json"
EMBED_DIM = 384

# ── Load model ──
print("Loading model...")
model = SentenceTransformer("all-MiniLM-L6-v2")
print("  Model ready.\n")

# ── Load existing index ──
if os.path.exists(INDEX_F):
    index = faiss.read_index(INDEX_F)
    print(f"Index loaded  : {index.ntotal:,} vectors")
else:
    index = faiss.IndexFlatL2(EMBED_DIM)
    print("Fresh index created.")

# ── Load existing metadata ──
if os.path.exists(META_F):
    with open(META_F, "r") as f:
        processed = json.load(f)
    print(f"Metadata loaded: {len(processed):,} files")
else:
    processed = {}
    print("No metadata. Starting fresh.")

# ════════════════════════════════════════════
#  INCREMENTAL — find only new files
# ════════════════════════════════════════════
all_files = (
    glob.glob(os.path.join(FOLDER, "*.txt")) +
    glob.glob(os.path.join(FOLDER, "*.md"))
)
new_files = [f for f in all_files if os.path.basename(f) not in processed]

print(f"\nTotal files : {len(all_files):,}")
print(f"Already done: {len(processed):,}")
print(f"New to index: {len(new_files):,}")

if not new_files:
    print("\nNothing new to index. Exiting.")
    exit(0)

# ════════════════════════════════════════════
#  STEP 1 — Read new files into memory
# ════════════════════════════════════════════
new_texts, new_names = [], []

for fp in new_files:
    try:
        with open(fp, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read().strip()
        if text:
            new_texts.append(text)
            new_names.append(os.path.basename(fp))
    except Exception as e:
        print(f"  SKIP: {fp} — {e}")

print(f"\nFiles to encode: {len(new_texts):,}")

# ════════════════════════════════════════════
#  STEP 2 — Encode → float32 numpy (N, 384)
# ════════════════════════════════════════════
print("Encoding...")
vectors = model.encode(
    new_texts,
    batch_size=32,
    show_progress_bar=True,
    convert_to_numpy=True,
    normalize_embeddings=True
).astype("float32")

print(f"Encoded shape : {vectors.shape}")

# ════════════════════════════════════════════
#  STEP 3 — Add to FAISS index
# ════════════════════════════════════════════
start_id = index.ntotal                  # capture BEFORE add()
index.add(vectors)
print(f"Added {len(new_texts):,} vectors. Index total: {index.ntotal:,}")

# ════════════════════════════════════════════
#  STEP 4 — Update metadata
# ════════════════════════════════════════════
for i, name in enumerate(new_names):
    processed[name] = {
        "faiss_id": start_id + i,
        "status":   "indexed"
    }

# ════════════════════════════════════════════
#  STEP 5 — Atomic save (crash-safe)
# ════════════════════════════════════════════
faiss.write_index(index, INDEX_F + ".tmp")
with open(META_F + ".tmp", "w") as f:
    json.dump(processed, f, indent=4)

os.replace(INDEX_F + ".tmp", INDEX_F)
os.replace(META_F  + ".tmp", META_F)

print(f"\n✅ Saved.")
print(f"   Index   : {index.ntotal:,} vectors  →  {INDEX_F}")
print(f"   Metadata: {len(processed):,} entries →  {META_F}")

if index.ntotal == len(processed):
    print("   Health  : OK — index and metadata in sync ✓")
else:
    print(f"   Health  : WARNING — {abs(index.ntotal - len(processed)):,} mismatch")