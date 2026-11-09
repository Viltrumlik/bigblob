#!/usr/bin/env python3
"""bigblob - find what is making the git repository big.

A fresh clone takes four minutes and the working tree is 30 MB. The
weight is in history: a 200 MB dump someone committed in 2023 and deleted
in the next commit is still in every clone, forever, and `du` will never
show it to you.

    $ bigblob
      212.4 MB  data/dump.sql            gone from HEAD
       48.0 MB  assets/intro.mov
        3.1 MB  package-lock.json

`gone from HEAD` is the important column: those files are not in your
working tree at all. They are pure weight.

Exit codes: 0 ok, 1 not a git repository, 2 usage.

Zero dependencies. Python 3.9+.
"""

import argparse
import heapq
import json
import os
import subprocess
import sys

VERSION = "0.1.0"
EXIT_OK, EXIT_ERROR, EXIT_USAGE = 0, 1, 2


def git(root, *args, **kw):
    return subprocess.Popen(["git", *args], cwd=root, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, universal_newlines=True,
                            errors="replace", **kw)


def repo_root(start):
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         universal_newlines=True)
    if out.returncode != 0 or not out.stdout.strip():
        return None
    return os.path.realpath(out.stdout.strip())


def human(size):
    for unit, step in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if size >= step:
            return "%.1f %s" % (size / float(step), unit)
    return "%d B" % size


def biggest_blobs(root, keep):
    """Eng katta blob'lar. Xotira chegaralangan: faqat `keep` ta saqlanadi.

    Katta repoda millionlab obyekt bo'lishi mumkin, shuning uchun hammasi
    lug'atga yig'ilmaydi -- oqim bo'ylab o'qib, uyum (heap) ushlab turiladi.
    """
    top = []
    proc = git(root, "cat-file", "--batch-all-objects",
               "--batch-check=%(objectname) %(objecttype) %(objectsize)")
    with proc:
        for line in proc.stdout:
            parts = line.split()
            if len(parts) != 3 or parts[1] != "blob":
                continue
            size = int(parts[2])
            if len(top) < keep:
                heapq.heappush(top, (size, parts[0]))
            elif size > top[0][0]:
                heapq.heapreplace(top, (size, parts[0]))
    return {sha: size for size, sha in top}


def paths_for(root, shas):
    """Blob'larning tarixda ko'ringan nomlari.

    Bitta blob bir necha nom ostida uchrashi mumkin (ko'chirilgan yoki
    nusxalangan), shuning uchun eng ko'p uchragani olinadi.
    """
    seen = {}
    proc = git(root, "rev-list", "--objects", "--all")
    with proc:
        for line in proc.stdout:
            sha, _, path = line.rstrip("\n").partition(" ")
            if path and sha in shas:
                seen.setdefault(sha, {})
                seen[sha][path] = seen[sha].get(path, 0) + 1
    return {sha: max(names, key=names.get) for sha, names in seen.items()}


def head_paths(root):
    proc = git(root, "ls-tree", "-r", "--name-only", "HEAD")
    with proc:
        return {line.rstrip("\n") for line in proc.stdout if line.strip()}


def repo_size(root):
    out = subprocess.run(["git", "count-objects", "-v"], cwd=root,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                         universal_newlines=True)
    total = 0
    for line in out.stdout.splitlines():
        if line.startswith(("size:", "size-pack:")):
            total += int(line.split(":")[1].strip()) * 1024   # KiB da beriladi
    return total


def collect(root, limit, only_gone):
    sizes = biggest_blobs(root, max(limit * 4, 50))
    names = paths_for(root, set(sizes))
    in_head = head_paths(root)
    rows = []
    for sha, size in sizes.items():
        path = names.get(sha)
        if path is None:
            continue              # faqat tag/commit ichidagi blob; nomi yo'q
        gone = path not in in_head
        if only_gone and not gone:
            continue
        rows.append({"sha": sha, "size": size, "path": path, "gone": gone})
    rows.sort(key=lambda r: -r["size"])
    return rows[:limit]


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="bigblob",
        description="Find what is making the git repository big.",
        epilog="example: bigblob --only-gone   # pure weight, not in your tree")
    p.add_argument("path", nargs="?", default=".", metavar="PATH")
    p.add_argument("-n", type=int, default=20, metavar="N",
                   help="how many to show (default 20)")
    p.add_argument("--only-gone", action="store_true",
                   help="only blobs that are no longer in HEAD")
    p.add_argument("--json", action="store_true")
    p.add_argument("--version", action="version", version="bigblob " + VERSION)
    args = p.parse_args(argv)

    if args.n < 1:
        print("error: -n must be at least 1", file=sys.stderr)
        return EXIT_USAGE
    start = os.path.abspath(args.path)
    if not os.path.isdir(start):
        print("error: not a folder: %s" % args.path, file=sys.stderr)
        return EXIT_USAGE
    root = repo_root(start)
    if root is None:
        print("error: not a git repository", file=sys.stderr)
        return EXIT_ERROR

    rows = collect(root, args.n, args.only_gone)
    total = repo_size(root)

    if args.json:
        print(json.dumps({"ok": True, "repository_bytes": total, "blobs": rows},
                         indent=2, sort_keys=True))
        return EXIT_OK
    if not rows:
        print("nothing to report")
        return EXIT_OK

    width = min(48, max(len(r["path"]) for r in rows))
    for r in rows:
        note = "  gone from HEAD" if r["gone"] else ""
        print("%10s  %s%s" % (human(r["size"]), r["path"].ljust(width), note))

    weight = sum(r["size"] for r in rows if r["gone"])
    print("\nrepository on disk: %s" % human(total))
    if weight:
        print("%s of the above is no longer in HEAD" % human(weight))
        print("it stays in every clone until the history is rewritten "
              "(git filter-repo)")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
