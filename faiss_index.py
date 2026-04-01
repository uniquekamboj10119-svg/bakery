import os, glob, json, time
import numpy as np
import faiss
import matplotlib.pyplot as plt
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import PCA

# ── The only 3 constants you ever need to change ──
FOLDER  = "out_going\\all_200k_ads"   # folder holding your ad files
INDEX_F = "ad_bot.index"              # persisted FAISS binary on disk
META_F  = "ad_metadata.json"          # state tracker — dict of processed filenames

# ── Load embedding model ──
print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")
EMBED_DIM = 384
print(f"  Model ready. Dimension: {EMBED_DIM}\n")

# ── Load or create FAISS index ──
def load_or_create_index():
    if os.path.exists(INDEX_F):
        print(f"Loading existing index from '{INDEX_F}'...")
        index = faiss.read_index(INDEX_F)
        print(f"  Vectors already indexed: {index.ntotal:,}")
    else:
        print("No existing index found. Creating new IndexFlatL2...")
        index = faiss.IndexFlatL2(EMBED_DIM)
        print(f"  Created fresh index. Dimension: {EMBED_DIM}")
    return index

# ── Load or create metadata ──
def load_or_create_meta():
    if os.path.exists(META_F):
        with open(META_F, "r") as f:
            meta = json.load(f)
        print(f"  Metadata loaded. Files already tracked: {len(meta):,}")
    else:
        meta = {}
        print("  No metadata found. Starting fresh.")
    return meta

# ── Save index + metadata safely (atomic write) ──
def save_index_and_meta(index, meta):
    faiss.write_index(index, INDEX_F + ".tmp")
    with open(META_F + ".tmp", "w") as f:
        json.dump(meta, f)
    os.replace(INDEX_F + ".tmp", INDEX_F)
    os.replace(META_F  + ".tmp", META_F)
    print(f"  Saved. Total indexed: {index.ntotal:,} vectors.")

# ── Find new files not yet indexed ──
def get_new_files(meta):
    all_files = glob.glob(os.path.join(FOLDER, "*.txt"))
    new_files = [f for f in all_files
                 if os.path.basename(f) not in meta]
    return sorted(new_files)

# ── Read file safely ──
def read_file_safe(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        return ""

# ── Embed new files in batches and add to index ──
def embed_and_index(new_files, index, meta):
    total     = len(new_files)
    start_id  = index.ntotal
    processed = 0
    BATCH     = 500

    print(f"\nFiles to embed    : {total:,}")
    print(f"Batch size        : {BATCH}")
    print(f"Estimated batches : {(total // BATCH) + 1}\n")

    t0 = time.time()

    for batch_start in range(0, total, BATCH):
        batch_files = new_files[batch_start : batch_start + BATCH]

        texts       = []
        valid_files = []
        for path in batch_files:
            content = read_file_safe(path)
            if content:
                texts.append(content)
                valid_files.append(path)

        if not texts:
            continue

        vectors = model.encode(
            texts,
            batch_size=64,
            show_progress_bar=False,
            normalize_embeddings=True
        ).astype("float32")

        index.add(vectors)

        for i, path in enumerate(valid_files):
            meta[os.path.basename(path)] = start_id + processed + i

        processed += len(valid_files)
        start_id   = index.ntotal
        elapsed    = time.time() - t0
        rate       = processed / elapsed if elapsed > 0 else 1
        eta        = (total - processed) / rate

        print(f"  Batch {batch_start // BATCH + 1:4d} | "
              f"Indexed: {processed:7,}/{total:,} | "
              f"Rate: {rate:5.0f} files/s | "
              f"ETA: {eta/60:.1f} min")

        save_index_and_meta(index, meta)

    print(f"\nDone. Total indexed: {index.ntotal:,}")
    print(f"Total time: {(time.time()-t0)/60:.1f} min\n")

# ── Query: find top-k most similar ads ──
def query_similar(query_text, index, meta, top_k=5):
    vec = model.encode(
        [query_text],
        normalize_embeddings=True
    ).astype("float32")

    distances, indices = index.search(vec, top_k)
    id_to_file = {v: k for k, v in meta.items()}

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:
            continue
        fname = id_to_file.get(int(idx), f"[id:{idx}]")
        results.append((fname, float(dist)))
    return results

# ── Visualise 2D PCA map of indexed vectors ──
def visualise_index(index, meta, sample_n=2000):
    if index.ntotal == 0:
        print("Index is empty — nothing to visualise.")
        return

    n          = min(sample_n, index.ntotal)
    sample_ids = np.random.choice(index.ntotal, n, replace=False)

    all_vectors = faiss.rev_swig_ptr(
        index.get_xb(), index.ntotal * EMBED_DIM
    ).reshape(index.ntotal, EMBED_DIM)

    sample_vecs = all_vectors[sample_ids]

    print(f"Running PCA on {n:,} sample vectors...")
    pca    = PCA(n_components=2)
    coords = pca.fit_transform(sample_vecs)

    plt.figure(figsize=(10, 7))
    plt.scatter(
        coords[:, 0], coords[:, 1],
        c=sample_ids % 50,
        cmap="tab20",
        s=4, alpha=0.6
    )
    plt.title(
        f"FAISS Index — 2D PCA of {n:,} ad embeddings\n"
        f"Total indexed: {index.ntotal:,} | "
        f"Variance explained: {pca.explained_variance_ratio_.sum()*100:.1f}%"
    )
    plt.xlabel("PCA component 1")
    plt.ylabel("PCA component 2")
    plt.colorbar(label="Style group (0–49)")
    plt.tight_layout()
    plt.savefig("faiss_map.png", dpi=150)
    print("  Saved: faiss_map.png")
    plt.show()

# ── Health check ──
def check_index_health(index, meta):
    print("\n── Index Health Check ──────────────────────")
    print(f"  FAISS vectors  : {index.ntotal:,}")
    print(f"  Metadata files : {len(meta):,}")
    if index.ntotal != len(meta):
        gap = abs(index.ntotal - len(meta))
        print(f"  WARNING: Mismatch of {gap:,} entries.")
        print("  → Run again to re-sync.")
    else:
        print("  OK — index and metadata are in sync.")
    if index.ntotal > 0:
        test_vec = np.random.randn(1, EMBED_DIM).astype("float32")
        faiss.normalize_L2(test_vec)
        D, I = index.search(test_vec, 1)
        if I[0][0] >= 0:
            print("  OK — search query returned valid result.")
        else:
            print("  ERROR: Search returned -1. Index may be corrupt.")
    print("────────────────────────────────────────────\n")


# ══════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════
print("=" * 56)
print("  FAISS AD EMBEDDING PIPELINE")
print(f"  Source folder : {FOLDER}")
print(f"  Index file    : {INDEX_F}")
print(f"  Metadata file : {META_F}")
print("=" * 56 + "\n")

# Verify folder exists
if not os.path.exists(FOLDER):
    print(f"ERROR: Folder not found — {os.path.abspath(FOLDER)}")
    exit()

total_files = glob.glob(os.path.join(FOLDER, "*.txt"))
print(f"Total .txt files in folder : {len(total_files):,}")

index = load_or_create_index()
meta  = load_or_create_meta()

check_index_health(index, meta)

new_files = get_new_files(meta)
print(f"New files found : {len(new_files):,}")

if new_files:
    embed_and_index(new_files, index, meta)
else:
    print("  Nothing new to index. Index is up to date.\n")

check_index_health(index, meta)

print("── Demo Query ──────────────────────────────")
sample_query = "affordable fresh bakery bread for family in Hisar"
print(f"  Query: \"{sample_query}\"")
results = query_similar(sample_query, index, meta, top_k=5)
print("  Top 5 similar ads:")
for rank, (fname, dist) in enumerate(results, 1):
    print(f"    {rank}. {fname:<30s}  distance: {dist:.4f}")
print()

print("── Visualisation ───────────────────────────")
visualise_index(index, meta, sample_n=2000)

print("\nPipeline complete.")