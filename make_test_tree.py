"""Generate a synthetic directory tree for file-search benchmarks.

Runs unchanged on Windows 11 and Ubuntu so both VMs index identical trees.

Example:
    python make_test_tree.py C:\\bench\\tree_10k --files 10000
"""
import argparse
import csv
import os
import random

NEEDLE_PREFIX = "target_needle"
CONTENT_KEYWORD = "zebracorn"  # unusual word for full-text (content) searches
WORDS = ["kernel", "process", "thread", "memory", "page", "frame", "scheduler",
         "mutex", "semaphore", "deadlock", "inode", "journal", "cache", "swap"]


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("root", help="output folder (must not already contain a tree)")
    p.add_argument("--files", type=int, required=True, help="total number of files")
    p.add_argument("--per-dir", type=int, default=100, help="files per leaf folder")
    p.add_argument("--dirs-per-level", type=int, default=10, help="fan-out of the folder tree")
    p.add_argument("--targets", type=int, default=10, help="number of needle files to plant")
    p.add_argument("--seed", type=int, default=42, help="random seed (keep identical across OSes)")
    args = p.parse_args()

    if os.path.exists(args.root) and os.listdir(args.root):
        p.error(f"{args.root} is not empty; pick a new folder")

    rng = random.Random(args.seed)
    needle_slots = set(rng.sample(range(args.files), args.targets))
    manifest = []

    for i in range(args.files):
        leaf = i // args.per_dir
        # Spread leaf folders over a 3-level tree, e.g. d03/d07/d01
        parts = []
        n = leaf
        for _ in range(3):
            parts.append(f"d{n % args.dirs_per_level:02d}")
            n //= args.dirs_per_level
        folder = os.path.join(args.root, *reversed(parts), f"leaf{leaf:05d}")
        os.makedirs(folder, exist_ok=True)

        body = " ".join(rng.choice(WORDS) for _ in range(40))
        if i in needle_slots:
            name = f"{NEEDLE_PREFIX}_{len(manifest):03d}.txt"
            body += f" {CONTENT_KEYWORD}"
        else:
            name = f"file_{i:06d}.txt"

        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body + "\n")
        if i in needle_slots:
            manifest.append(path)

    manifest_path = os.path.join(args.root, "_manifest.csv")
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["needle_path"])
        w.writerows([m] for m in manifest)

    print(f"Created {args.files} files under {args.root}")
    print(f"Planted {len(manifest)} needles; list in {manifest_path}")


if __name__ == "__main__":
    main()
