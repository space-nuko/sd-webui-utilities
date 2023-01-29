import os
import os.path
import sys
import bisect
import shutil

path = sys.argv[1]
if not os.path.isdir(path):
    print(f"Invalid path {path}")
    exit(1)


def closest(haystack, needle):
    if len(haystack) == 0: return None, None

    index = bisect.bisect_left(haystack, needle)
    if index == 0:
        return None, haystack[0]
    if index == len(haystack):
        return haystack[index-1], None
    if haystack[index] == needle:
        return haystack[index], haystack[index]
    return haystack[index-1], haystack[index]


# Return the longest prefix of all list elements.
def commonprefix(m):
    "Given a list of pathnames, returns the longest common leading component"
    if not m: return ''
    s1 = min(m)
    s2 = max(m)
    for i, c in enumerate(s1):
        if c != s2[i]:
            return s1[:i]
    return s1


for root, dirs, files in os.walk(path):
    files = list(files)

    safetensors = [f for f in files if os.path.splitext(f)[1] == ".safetensors"]
    if not safetensors:
        continue

    previews = [f for f in files if f.endswith(".preview.png")]
    if not previews:
        continue

    missing = []
    for s in safetensors:
        preview_path = os.path.splitext(s)[0] + ".preview.png"
        fullpath = os.path.join(root, preview_path)
        if not os.path.exists(fullpath):
            missing.append(fullpath)

    if not missing:
        continue

    for image_path in missing:
        bn = os.path.basename(image_path)
        p = [p for p in previews if len(commonprefix([bn, p])) > 6]
        if not p:
            continue
        found = closest(p, bn)
        found = found[0] or found[1]
        print(f"{bn} <- {os.path.basename(found)}")
        shutil.copyfile(os.path.join(root, found), image_path)
