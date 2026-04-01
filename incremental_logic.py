import os, glob, json, time
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# ── The only 3 constants you ever need to change ──
FOLDER  =  "knowledge base\\out_going\\all_200k_ads"   # folder holding your ad files
INDEX_F = "ad_bot.index"              # persisted FAISS binary on disk
META_F  = "ad_metadata.json"          # state tracker — dict of processed filenames

EMBED_DIM  = 384
BATCH_SIZE = 500

# ── Load model ────────────────────────────────────────────────
print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")
print(f"  Model ready. Dimension: {EMBED_DIM}\n")

# ── Load index ────────────────────────────────────────────────
if os.path.exists(INDEX_F):
    index = faiss.read_index(INDEX_F)
    print(f"Loaded index. Vectors: {index.ntotal:,}")
else:
    index = faiss.IndexFlatL2(EMBED_DIM)
    print("Created fresh index.")

# ── Load metadata (processed = filenames already indexed) ─────
if os.path.exists(META_F):
    with open(META_F, "r") as f:
        processed = json.load(f)
    print(f"Loaded metadata. Tracked files: {len(processed):,}")
else:
    processed = {}
    print("No metadata found. Starting fresh.")


# ════════════════════════════════════════════════════════════
#  INCREMENTAL LOGIC — the 3 steps
# ════════════════════════════════════════════════════════════

# 1. Collect every .txt and .md currently in the folder
all_files = (
    glob.glob(os.path.join(FOLDER, "*.txt")) +
    glob.glob(os.path.join(FOLDER, "*.md"))
)

# 2. Keep only files NOT already in our metadata dict  ← THE incremental step
new_files = [
    f for f in all_files
    if os.path.basename(f) not in processed
]

print(f"\nTotal: {len(all_files):,} | Processed: {len(processed):,} | New: {len(new_files):,}")

# 3. Early-exit if nothing to do
if not new_files:
    print("Nothing new. Index is up to date.")
    exit(0)   # exit code 0 = success for Windows Task Scheduler


# ════════════════════════════════════════════════════════════
#  EMBED + INDEX the new files (batch by batch)
# ════════════════════════════════════════════════════════════
total    = len(new_files)
start_id = index.ntotal
added    = 0

print(f"\nFiles to embed    : {total:,}")
print(f"Batch size        : {BATCH_SIZE}")
print(f"Estimated batches : {(total // BATCH_SIZE) + 1}\n")

t0 = time.time()

for batch_start in range(0, total, BATCH_SIZE):

    batch_paths = new_files[batch_start : batch_start + BATCH_SIZE]

    # Read content — skip empty or unreadable files
    texts       = []
    valid_paths = []
    for path in batch_paths:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read().strip()
            if text:
                texts.append(text)
                valid_paths.append(path)
        except Exception:
            pass

    if not texts:
        continue

    # Embed this batch → float32 matrix (N, 384)
    vectors = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        normalize_embeddings=True
    ).astype("float32")

    # Add to FAISS index
    index.add(vectors)

    # Update processed dict: filename → vector ID
    for i, path in enumerate(valid_paths):
        fname            = os.path.basename(path)
        processed[fname] = start_id + added + i

    added    += len(valid_paths)
    start_id  = index.ntotal

    # Progress line
    elapsed = time.time() - t0
    rate    = added / elapsed if elapsed > 0 else 1
    eta     = (total - added) / rate

    print(f"  Batch {batch_start // BATCH_SIZE + 1:4d} | "
          f"Indexed: {added:7,}/{total:,} | "
          f"Rate: {rate:5.0f} files/s | "
          f"ETA: {eta/60:.1f} min")

    # ── Checkpoint save after every batch ─────────────────
    # Write to .tmp first → rename (atomic — safe on crash)
    faiss.write_index(index, INDEX_F + ".tmp")
    with open(META_F + ".tmp", "w") as f:
        json.dump(processed, f)
    os.replace(INDEX_F + ".tmp", INDEX_F)
    os.replace(META_F  + ".tmp", META_F)


# ════════════════════════════════════════════════════════════
#  FINAL REPORT
# ════════════════════════════════════════════════════════════
elapsed = time.time() - t0

print(f"\n{'='*56}")
print(f"  Incremental indexing complete.")
print(f"  New files added   : {added:,}")
print(f"  Total in index    : {index.ntotal:,}")
print(f"  Total in metadata : {len(processed):,}")
print(f"  Time taken        : {elapsed/60:.1f} min")
print(f"  Rate              : {added/elapsed:.0f} files/sec")

if index.ntotal == len(processed):
    print(f"  Health            : OK — index and metadata in sync")
else:
    gap = abs(index.ntotal - len(processed))
    print(f"  Health            : WARNING — {gap:,} mismatch — run again")

print(f"{'='*56}")