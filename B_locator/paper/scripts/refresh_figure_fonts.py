"""Refresh the six Q1/Q2 paper figures without changing their original renderers.

The original drawing functions still own every coordinate, label, value, colour,
and panel layout.  This wrapper changes font selection (with a small alignment
correction for four wider point labels) and saves PNG/PDF copies under
paper/figures; no Q1/Q2 source or input data is written.

Usage: python B_locator/paper/scripts/refresh_figure_fonts.py
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile

PAPER = Path(__file__).resolve().parents[1]
LOCATOR = PAPER.parent
CACHE = Path(tempfile.gettempdir()) / "b-locator-paper-fonts"
CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(CACHE / "matplotlib"))

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager, pyplot as plt
from matplotlib import _mathtext
from matplotlib.mathtext import MathTextParser
from matplotlib.figure import Figure
from matplotlib.text import Text
from matplotlib.transforms import Bbox
from PIL import Image


def load_original(name: str, path: Path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def font_family():
    """Use the paper's Latin font; retain Song/Hei Chinese figure families."""
    for name in ("Times New Roman.ttf", "Times New Roman Bold.ttf",
                 "Times New Roman Italic.ttf", "Times New Roman Bold Italic.ttf"):
        path = Path("/System/Library/Fonts/Supplemental") / name
        if path.exists():
            font_manager.fontManager.addfont(path)
    latin = "Times New Roman"
    font_manager.findfont(latin, fallback_to_default=False)
    font_manager.fontManager.addfont(PAPER / "fonts" / "simsun.ttc")
    song = font_manager.FontProperties(fname=PAPER / "fonts" / "simsun.ttc").get_name()
    for hei in ("Microsoft YaHei", "SimHei", "Heiti SC"):
        try:
            font_manager.findfont(hei, fallback_to_default=False)
            return latin, song, hei
        except ValueError:
            pass
    # macOS exposes only TTC face zero to Matplotlib; extract the SC face in a
    # temporary font cache, leaving the installed font and original code intact.
    collection = Path("/System/Library/Fonts/STHeiti Medium.ttc")
    if collection.exists():
        from fontTools.ttLib import TTFont
        extracted = CACHE / "STHeitiSC-Medium.ttf"
        if not extracted.exists():
            TTFont(collection, fontNumber=1).save(extracted)
        font_manager.fontManager.addfont(extracted)
        return latin, song, "Heiti SC"
    raise RuntimeError("Install the original Q2 Chinese sans-serif font (SimHei or Microsoft YaHei).")


def setup_fonts(latin: str, chinese: str):
    plt.rcParams.update({
        "font.family": [latin, chinese],
        "font.serif": [latin, chinese],
        "font.sans-serif": [latin, chinese],
        "mathtext.fontset": "cm",
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def install_mixed_mathtext_fonts():
    """Retain CJK fallback in labels mixing ordinary text with CM equations.

    Matplotlib's CM math parser resolves only the first ordinary-text family.
    Extend that lookup for ordinary characters, leaving every mathematical
    glyph and every source label untouched.  This also avoids embedding a
    modified or merged font in the repository.
    """
    class MixedComputerModernFonts(_mathtext.BakomaFonts):
        def _get_glyph(self, fontname, font_class, sym):
            if fontname in ("default", "regular") and len(sym) == 1:
                codepoint = ord(sym)
                primary = self._get_font(fontname)
                if primary is not None and not primary.get_char_index(codepoint):
                    for family in self.default_font_prop.get_family()[1:]:
                        font = font_manager.get_font(font_manager.findfont(family))
                        if font.get_char_index(codepoint):
                            return font, codepoint, False
            return super()._get_glyph(fontname, font_class, sym)
    MathTextParser._font_type_mapping["cm"] = MixedComputerModernFonts


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def paper_saves(out: Path, originals: Path, records: list, alias=None):
    """Save both formats while preserving each published figure's aspect ratio."""
    native_save = Figure.savefig

    def save(fig, filename, **kwargs):
        name = alias or Path(filename).stem
        original = originals / f"{name}.png"
        original_hash = sha256(original)
        image = Image.open(original)
        ratio = image.width / image.height
        if name == "p2-wedge-geometry":
            # These four plain-text labels denote mathematical vertices, just
            # like the source renderer's $S_1$, $S_2$, and $T$ labels.
            for label in fig.findobj(Text):
                if label.get_text() in ("A", "B", "C", "D"):
                    label.set_fontfamily("cmmi10")
                    label.set_fontweight("normal")
                    # CM glyphs are wider than the old sans-serif labels; let
                    # each label extend away from its paired vertex label.
                    label.set_horizontalalignment(
                        "left" if label.get_text() in ("A", "D") else "right")
        fig.canvas.draw()
        bounds = fig.get_tightbbox(fig.canvas.get_renderer()).padded(0.1)
        width, height = bounds.width, bounds.height
        if width / height < ratio:
            width = height * ratio
        else:
            height = width / ratio
        cx, cy = (bounds.x0 + bounds.x1) / 2, (bounds.y0 + bounds.y1) / 2
        bounds = Bbox.from_bounds(cx - width / 2, cy - height / 2, width, height)
        outputs = []
        for extension in ("png", "pdf"):
            path = out / f"{name}.{extension}"
            save_kwargs = dict(kwargs, bbox_inches=bounds, facecolor="white")
            if extension == "png":
                save_kwargs["dpi"] = 400
            else:
                save_kwargs.pop("dpi", None)
                save_kwargs["metadata"] = {"Creator": "Original Q1/Q2 renderers; paper font wrapper"}
            native_save(fig, path, **save_kwargs)
            outputs.append({"path": str(path.relative_to(LOCATOR)) if path.is_relative_to(LOCATOR) else str(path),
                            "sha256": sha256(path)})
        records.append({"name": name, "original_png_sha256": original_hash,
                        "original_aspect_ratio": ratio, "outputs": outputs})
    Figure.savefig = save
    try:
        yield
    finally:
        Figure.savefig = native_save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=PAPER / "figures")
    parser.add_argument("--originals", type=Path, default=PAPER / "figures",
                        help="Existing paper PNGs used only to retain aspect ratios")
    parser.add_argument("--report", type=Path, default=PAPER / "figure-font-refresh.json")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    q1 = load_original("paper_q1_renderer", LOCATOR / "Q1" / "make_figures.py")
    q2 = load_original("paper_q2_renderer", LOCATOR / "Q2" / "make_q2_paper_figures.py")
    wedge = load_original("paper_q2_wedge_renderer", LOCATOR / "Q2" / "illustration_plot_Q2.py")
    latin, song, hei = font_family()
    install_mixed_mathtext_fonts()
    records = []
    q1.setup()
    setup_fonts(latin, song)
    with paper_saves(args.out, args.originals, records):
        q1.coverage()
        q1.flowchart()
        q1.wedge_diagram()

    plt.rcdefaults()
    q2._setup()
    setup_fonts(latin, hei)
    mma, py = q2._fields()
    with paper_saves(args.out, args.originals, records):
        q2.fig_mma_vs_pysim(plt, q2.make_cmap(), q2.PiecewiseNorm(), mma, py,
                            args.out / "p2-mma-vs-pysim.png")
        q2.fig_contour60(plt, mma, args.out / "p2-contour60.png")

    plt.rcdefaults()
    setup_fonts(latin, hei)
    with paper_saves(args.out, args.originals, records, alias="p2-wedge-geometry"):
        # The original renderer announces its original output path; suppress
        # that announcement because this wrapper redirects the actual save.
        with redirect_stdout(io.StringIO()):
            wedge.draw_q2_wedge_diagram(save_fig=True, show_fig=False)

    inputs = [LOCATOR / "Q1" / p for p in (
        "make_figures.py", "p1_intersection.py", "p1_experiments.py",
        "cases/p1_case01.csv", "cases/p1_case02.csv")]
    inputs += [LOCATOR / "Q2" / p for p in (
        "make_q2_paper_figures.py", "make_q2_figures.py", "illustration_plot_Q2.py",
        "MMAcode/Q2_expected_diameter_data.csv", "pysimulation/out/p2_grid/p2_grid_map.csv")]
    report = {"scope": "Six Q1/Q2 figures included in the paper; fonts/output formats only",
              "fonts": {"latin": latin, "math": "Computer Modern",
                        "q1_chinese": song, "q2_chinese": hei},
              "matplotlib": matplotlib.__version__,
              "original_renderers_and_data": {str(p.relative_to(LOCATOR)): sha256(p) for p in inputs},
              "figures": records}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {len(records)} original paper figures; Latin={latin}, math=Computer Modern.")


if __name__ == "__main__":
    main()
