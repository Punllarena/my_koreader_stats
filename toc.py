"""Insert a table of contents into a generated markdown file."""
import re
from collections import Counter
from pathlib import Path


def slug(heading):
    """GitHub anchor for a heading: lowercase, drop punctuation/emoji, spaces to hyphens."""
    s = re.sub(r"[^\w\s-]", "", heading.strip().lower())
    return re.sub(r"\s", "-", s)  # leading space left by a stripped emoji becomes a hyphen, as on GitHub


def add_toc(path, title="Contents"):
    """Insert a TOC of the '## ' headings after the H1. No-op below two headings."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if f"## {title}" in lines:
        return  # already has a TOC
    headings = [l[3:].strip() for l in lines if l.startswith("## ")]
    if len(headings) < 2:
        return
    seen = Counter()
    toc = [f"## {title}", ""]
    for h in headings:
        anchor = slug(h)
        seen[anchor] += 1
        if seen[anchor] > 1:
            anchor += f"-{seen[anchor] - 1}"  # GitHub suffixes repeated headings
        toc.append(f"- [{h}](#{anchor})")
    toc.append("")
    at = next(i for i, l in enumerate(lines) if l.startswith("## "))  # keep any intro above the TOC
    Path(path).write_text("\n".join(lines[:at] + toc + lines[at:]) + "\n", encoding="utf-8")


def demo():
    p = Path("/tmp/toc_demo.md")
    p.write_text("# T\n\nintro\n\n## 📚 A B\n\nx\n\n## A B\n\ny\n\n## A B\n\nz\n", encoding="utf-8")
    add_toc(p)
    out = p.read_text(encoding="utf-8")
    assert "- [📚 A B](#-a-b)" in out, out
    assert "- [A B](#a-b-1)" in out, out
    assert out.index("intro") < out.index("## Contents") < out.index("## 📚 A B")
    add_toc(p)  # already has a TOC: the Contents heading must not pile up
    assert p.read_text(encoding="utf-8").count("## Contents") == 1
    print("ok")


if __name__ == "__main__":
    demo()
