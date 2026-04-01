import glob
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sentence_transformers import SentenceTransformer

# ── Constants ──
FOLDER = "knowledge base\\out_going\\all_200k_ads"

def visualise_clusters(model):
    # ── Load all files ──
    all_paths = (glob.glob(f"{FOLDER}/*.txt") +
                 glob.glob(f"{FOLDER}/*.md"))
    print(f"Files found: {len(all_paths):,}")

    texts = []
    for fp in all_paths:
        with open(fp, encoding="utf-8", errors="ignore") as f:
            text = f.read().strip()
        if text:
            texts.append(text)

    print(f"Files loaded: {len(texts):,}")

    # ── Encode ──
    print("Encoding...")
    embeddings = model.encode(texts, batch_size=64, show_progress_bar=True)

    # ── PCA: 384D → 2D ──
    print("Running PCA...")
    pca     = PCA(n_components=2)
    reduced = pca.fit_transform(embeddings)   # shape: (N, 2)
    var     = pca.explained_variance_ratio_
    print(f"  Variance explained: {var.sum()*100:.1f}%")

    # ── Plot ──
    plt.figure(figsize=(10, 6))
    plt.scatter(reduced[:, 0], reduced[:, 1],
                alpha=0.5, c='#5B21B6', s=12)
    plt.title(
        f"Ad Clusters — PCA of 384-dim Embeddings\n"
        f"{len(texts):,} ads | Variance explained: {var.sum()*100:.1f}%"
    )
    plt.xlabel(f"PC 1 ({var[0]*100:.1f}%)")
    plt.ylabel(f"PC 2 ({var[1]*100:.1f}%)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("ad_clusters.png", dpi=150)
    print("Saved: ad_clusters.png")
    plt.show()


# ── Run ──
model = SentenceTransformer("all-MiniLM-L6-v2")
visualise_clusters(model)