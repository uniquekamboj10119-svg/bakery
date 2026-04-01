import os, zipfile, glob, time

FOLDER   = "out_going\\all_200k_ads"
ZIP_PATH = os.path.join(FOLDER, "All_246500_Ads_Complete.zip")

# ── Step 1: Check zip exists ──────────────────────────────────
if not os.path.exists(ZIP_PATH):
    print(f"ERROR: ZIP not found at {ZIP_PATH}")
    exit()

zip_size_mb = os.path.getsize(ZIP_PATH) / (1024 * 1024)
print(f"Found ZIP: {ZIP_PATH}")
print(f"ZIP size : {zip_size_mb:.1f} MB")

# ── Step 2: Count files inside ZIP before extracting ─────────
print("\nChecking contents of ZIP...")
with zipfile.ZipFile(ZIP_PATH, 'r') as z:
    all_names = z.namelist()
    txt_files = [f for f in all_names if f.endswith('.txt')]
    print(f"  Total entries in ZIP : {len(all_names):,}")
    print(f"  .txt files inside    : {len(txt_files):,}")
    print(f"  Sample entries       : {all_names[:3]}")

# ── Step 3: Extract all files ─────────────────────────────────
print(f"\nExtracting to '{FOLDER}/'...")
print("This may take 2-5 minutes for 246,500 files. Please wait...")

t0 = time.time()
with zipfile.ZipFile(ZIP_PATH, 'r') as z:
    z.extractall(FOLDER)

elapsed = time.time() - t0
print(f"Extraction complete in {elapsed:.1f} seconds.")

# ── Step 4: Verify extracted files ───────────────────────────
# The ZIP may have extracted into a subfolder — find where files landed
txt_direct = glob.glob(os.path.join(FOLDER, "*.txt"))
txt_sub    = glob.glob(os.path.join(FOLDER, "**", "*.txt"), recursive=True)

print(f"\nVerification:")
print(f"  .txt files directly in out_going/  : {len(txt_direct):,}")
print(f"  .txt files anywhere inside out_going: {len(txt_sub):,}")

if txt_sub:
    print(f"  Sample file paths:")
    for f in txt_sub[:3]:
        print(f"    {f}")

# ── Step 5: Tell user what FOLDER to use in faiss_pipeline.py ─
if txt_direct:
    print(f"\nSETTING FOR faiss_pipeline.py:")
    print(f'  FOLDER = "out_going"')
elif txt_sub:
    # Files are inside a subfolder
    subfolder = os.path.dirname(txt_sub[0])
    rel_path  = os.path.relpath(subfolder)
    print(f"\nFiles extracted into subfolder: {subfolder}")
    print(f"\nSETTING FOR faiss_pipeline.py:")
    print(f'  FOLDER = "{rel_path}"')
else:
    print("\nWARNING: No .txt files found after extraction.")
    print("Check if files have a different extension:")
    all_after = glob.glob(os.path.join(FOLDER, "**", "*"), recursive=True)
    exts = set(os.path.splitext(f)[1] for f in all_after if os.path.isfile(f))
    print(f"  Extensions found: {exts}")

print("\nDone. Now run faiss_pipeline.py")