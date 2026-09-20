"""Insert a table of contents into a generated markdown file."""
import re
from collections import Counter
from pathlib import Path


LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def slug(heading):
    """GitHub anchor for a heading: link text only, lowercase, no punctuation/emoji, spaces to hyphens."""
    s = re.sub(r"[^\w\s-]", "", LINK_RE.sub(r"\1", heading).strip().lower())
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
        toc.append(f"- [{LINK_RE.sub(r'\1', h)}](#{anchor})")  # a linked heading keeps only its text here
    toc.append("")
    at = next(i for i, l in enumerate(lines) if l.startswith("## "))  # keep any intro above the TOC
    Path(path).write_text("\n".join(lines[:at] + toc + lines[at:]) + "\n", encoding="utf-8")


def demo():
    p = Path("/tmp/toc_demo.md")
    p.write_text("# T\n\nintro\n\n## 📚 A B\n\nx\n\n## A B\n\ny\n\n## [A B](http://x/1)\n\nz\n", encoding="utf-8")
    add_toc(p)
    out = p.read_text(encoding="utf-8")
    assert "- [📚 A B](#-a-b)" in out, out
    assert "- [A B](#a-b)" in out and "- [A B](#a-b-1)" in out, out
    assert slug("[A B](http://x/1)") == "a-b"
    assert out.index("intro") < out.index("## Contents") < out.index("## 📚 A B")
    add_toc(p)  # already has a TOC: the Contents heading must not pile up
    assert p.read_text(encoding="utf-8").count("## Contents") == 1
    print("ok")


if __name__ == "__main__":
    demo()
