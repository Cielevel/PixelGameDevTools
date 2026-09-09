"""pipeline（管线配方）回归测试。

覆盖三块：
1. 注册表与参数（自省完整性 / 类型强转 / 校验拦截）
2. 端到端执行（图像管线 / 确定性重跑 / 门禁拦截 / dry-run 零副作用）
3. parity：与既有 CLI（video-std / standardize）逐像素一致——管线只是编排、
   不重写算法这条红线，靠这两个用例守住（改任一侧算法，这里必须仍然一致）
"""
import json
import os
import shutil
import subprocess
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pipeline as pipemod
import video as vidmod


# ------------------------------------------------------------ 合成素材 ----
GREEN = (20, 180, 40)      # 绿幕底
RED = (200, 40, 40)
DARK = (40, 40, 60)


def _grid_png(path, side=96, cell=8):
    """96x96、8px 逻辑格、少量纯色的「网格放大稿」——grid-sample 应还原成 12x12。"""
    im = Image.new("RGB", (side, side), (249, 249, 249))
    px = im.load()
    cols = [RED, DARK, (240, 200, 80)]
    cells = side // cell
    for cy in range(2, cells - 2):          # 四周留 2 格背景边
        for cx in range(2, cells - 2):
            c = cols[(cx + cy) % 3]
            for yy in range(cy * cell, (cy + 1) * cell):
                for xx in range(cx * cell, (cx + 1) * cell):
                    px[xx, yy] = c
    im.save(path)
    return path


def _green_video(tmpdir, n=6, w=160, h=120):
    """绿幕 + 横移红块的确定性合成视频（无损 h264，抽帧可精确还原）。"""
    framedir = os.path.join(tmpdir, "src")
    os.makedirs(framedir, exist_ok=True)
    for i in range(n):
        im = Image.new("RGB", (w, h), GREEN)
        px = im.load()
        x0 = 30 + i * 8
        for y in range(40, 80):
            for x in range(x0, x0 + 28):
                px[x, y] = RED
        im.save(os.path.join(framedir, "f_{:02d}.png".format(i)))
    mp4 = os.path.join(tmpdir, "synth.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-framerate", "4",
         "-i", os.path.join(framedir, "f_%02d.png"),
         "-c:v", "libx264", "-preset", "ultrafast", "-qp", "0",
         "-pix_fmt", "yuv444p", mp4],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return mp4


def _img_graph(path, out_dir, extra_stages=()):
    return {
        "version": 1,
        "name": "test-image",
        "input": {"op": "source.images", "params": {"paths": [path]}},
        "stages": [
            {"op": "grid-sample", "params": {"grid": "auto"}},
            {"op": "quantize", "params": {"colors": 16}},
            {"op": "export-frames"},
            {"op": "export-sheet", "params": {"source-route": "sampled"}},
        ] + list(extra_stages),
        "output": {"dir": out_dir},
    }


def _run(graph):
    return pipemod.run(graph)


# ------------------------------------------------------------ 注册表 ----
def test_registry_sanity():
    assert pipemod.SCHEMA_VERSION == 1
    cats = set()
    for name, d in pipemod.OPS.items():
        assert callable(d["fn"]), name
        assert d["category"] in ("source", "transform", "export", "gate"), name
        assert d["io"][0] in ("-", "frames") and d["io"][1] in ("-", "frames", "report"), name
        for prm in d["params"]:
            assert set(prm) >= {"key", "type", "default", "help", "required"}
        cats.add(d["category"])
    assert cats == {"source", "transform", "export", "gate"}
    assert {"source.video", "source.images", "quantize", "outline",
            "export-sheet", "gate-check", "gate-stability"} <= set(pipemod.OPS)


def test_coerce_types():
    d = lambda k, t: {"key": k, "type": t, "default": None, "help": "", "required": False}
    assert pipemod._coerce(d("s", "size"), [8, 6], "t") == (8, 6)
    assert pipemod._coerce(d("s", "size"), "8x6", "t") == (8, 6)
    assert pipemod._coerce(d("c", "color"), "#182b54", "t") == (24, 43, 84)
    assert pipemod._coerce(d("g", "grid"), "auto", "t") == "auto"
    assert pipemod._coerce(d("g", "grid"), 8, "t") == (8, 8)
    assert pipemod._coerce(d("m", "choice:auto|green"), "auto", "t") == "auto"
    for bad, decl in [(["a", 0], ("s", "size")), ("#xyz!", ("c", "color")),
                      (True, ("n", "int")), ("red", ("m", "choice:auto|green"))]:
        with pytest.raises(pipemod.PipelineError):
            pipemod._coerce(d(decl[0], decl[1]), bad, "t")


# ------------------------------------------------------------ 校验 ----
def _valid_graph():
    return {
        "version": 1,
        "input": {"op": "source.images", "params": {"paths": ["x.png"]}},
        "stages": [{"op": "quantize", "params": {"colors": 8}}, {"op": "export-frames"}],
        "output": {"dir": "out"},
    }


def test_validate_ok():
    assert pipemod.validate(_valid_graph()) == []


@pytest.mark.parametrize("mutate, frag", [
    (lambda g: g.update(version=2), "version"),
    (lambda g: g.update(input={"op": "quantize"}), "源节点"),
    (lambda g: g.update(input={"op": "nope"}), "未知节点"),
    (lambda g: g["stages"].__setitem__(0, {"op": "resize", "params": {"fit": "contain"}}), "必填"),
    (lambda g: g["stages"].__setitem__(0, {"op": "quantize", "params": {"colour": 8}}), "不是有效参数"),
    (lambda g: g["stages"].__setitem__(0, {"op": "source.images"}), "只能出现在 input"),
    (lambda g: g["stages"].__setitem__(1, {"op": "gate-check"}), "export-frames"),
    (lambda g: g["stages"].__setitem__(1, {"op": "export-frames", "id": "a"}), "id/from"),
    (lambda g: g.pop("output"), "output.dir"),
    (lambda g: g.update(stages=[]), "非空列表"),
])
def test_validate_catches(mutate, frag):
    g = _valid_graph()
    mutate(g)
    errors = pipemod.validate(g)
    assert errors and any(frag in e for e in errors), errors


# ------------------------------------------------------------ 执行 ----
def test_run_grid_pipeline(tmp_path):
    src = _grid_png(str(tmp_path / "grid_src.png"))
    out = str(tmp_path / "out")
    rep = _run(_img_graph(src, out))
    assert rep["ok"] and rep["frames"] == 1
    frames = sorted(f for f in os.listdir(out) if f.endswith(".png"))
    assert len(frames) == 2  # 1 帧 + sheet
    img = Image.open(os.path.join(out, "grid_src_00.png"))
    assert img.size == (12, 12)  # 96 / 8 格
    meta = json.load(open(os.path.join(out, "grid_src_sheet.json"), encoding="utf-8"))
    (fr,) = meta["frames"].values()   # 单帧
    assert fr["frame"]["w"] == 12 and fr["frame"]["h"] == 12
    assert meta["meta"]["image"] == "grid_src_sheet.png"
    assert meta["meta"]["sourceRoute"] == "sampled"


def test_run_deterministic(tmp_path):
    src = _grid_png(str(tmp_path / "grid_src.png"))
    outs = []
    for d in ("a", "b"):
        out = str(tmp_path / d)
        _run(_img_graph(src, out))
        outs.append({f: open(os.path.join(out, f), "rb").read()
                     for f in sorted(os.listdir(out))})
    assert outs[0] == outs[1]  # 逐字节一致（含 sheet 与 JSON）


def test_gate_blocks(tmp_path):
    src = _grid_png(str(tmp_path / "grid_src.png"))
    g = _img_graph(src, str(tmp_path / "out"),
                   extra_stages=[{"op": "gate-check", "params": {"max-colors": 2}}])
    rep = _run(g)
    assert not rep["ok"]
    assert any(name == "gate-check" and not ok for name, ok, _ in rep["gates"])


def test_gate_stability_pass(tmp_path):
    """两帧完全相同的合成序列：静态格多、无变色 → gate-stability 通过。"""
    framedir = tmp_path / "frames"
    framedir.mkdir()
    for i in range(3):
        im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        px = im.load()
        for y in range(4, 28):
            for x in range(4, 28):
                px[x, y] = (200, 60, 60, 255) if (x + y) % 2 else (60, 60, 200, 255)
        im.save(str(framedir / "sq_{:02d}.png".format(i)))
    g = {
        "version": 1,
        "input": {"op": "source.images", "params": {"paths": [str(framedir)]}},
        "stages": [{"op": "gate-stability", "params": {"preset": "standard"}}],
    }
    rep = _run(g)
    assert rep["ok"], rep["gates"]


def test_dry_run_no_side_effect(tmp_path):
    src = _grid_png(str(tmp_path / "grid_src.png"))
    out = str(tmp_path / "never")
    rep_dry = pipemod.run(_img_graph(src, out), dry_run=True)
    assert rep_dry["ok"] and rep_dry["dry_run"]
    assert not os.path.exists(out)   # dry-run 不建目录、不写文件


# ------------------------------------------------------------ parity ----
def test_parity_image_vs_standardize(tmp_path):
    """管线（grid-sample + quantize）与 pixcli standardize 单图路径逐像素一致。"""
    import standardize as stdmod
    src = _grid_png(str(tmp_path / "grid_src.png"))
    im = Image.open(src).convert("RGBA")
    expect, _rep = stdmod.standardize(im, grid="auto", sampling="mode", colors=16, bg="auto")
    out = str(tmp_path / "out")
    _run(_img_graph(src, out))
    got = Image.open(os.path.join(out, "grid_src_00.png")).convert("RGBA")
    assert got.size == expect.size
    assert list(got.getdata()) == list(expect.getdata())


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="需要 ffmpeg")
def test_parity_video_vs_videostd(tmp_path):
    """管线（完整视频链）与 video_standardize 逐像素一致——编排不改变算法结果。"""
    mp4 = _green_video(str(tmp_path))
    out_pipe = str(tmp_path / "pipe")
    g = {
        "version": 1,
        "input": {"op": "source.video", "params": {"path": mp4, "fps": 4}},
        "stages": [
            {"op": "chroma-key", "params": {"mode": "auto"}},
            {"op": "crop", "params": {"mode": "auto"}},
            {"op": "resize", "params": {"size": [24, 24], "fit": "contain"}},
            {"op": "remove-bg", "params": {"mode": "auto"}},
            {"op": "quantize", "params": {"colors": 8}},
            {"op": "temporal-mode", "params": {"window": 3}},
            {"op": "outline", "params": {"color": "#182b54"}},
            {"op": "export-frames"},
        ],
        "output": {"dir": out_pipe},
    }
    rep = _run(g)
    assert rep["ok"] and rep["frames"] >= 4
    out_std = str(tmp_path / "vidstd")
    vidmod.video_standardize(
        mp4, out_std, fps=4, size=(24, 24), crop="auto", colors=8,
        outline="#182b54", make_gif=False, make_html=False,
        keep_frames=True, make_sheet=False, key="auto", fit="contain", stabilize=3)
    names = sorted(f for f in os.listdir(out_pipe) if f.endswith(".png"))
    assert names, "管线未导出帧"
    assert names == sorted(f for f in os.listdir(out_std) if f.endswith(".png"))
    for n in names:
        a = Image.open(os.path.join(out_pipe, n)).convert("RGBA")
        b = Image.open(os.path.join(out_std, n)).convert("RGBA")
        assert a.size == b.size and list(a.getdata()) == list(b.getdata()), n


# ------------------------------------------------------------ CLI ----
def test_cli_ops_json(capsys):
    import pixcli
    rc = pixcli.main(["ops", "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["version"] == 1 and len(data["ops"]) == len(pipemod.OPS)
    assert all("fn" not in op for op in data["ops"])  # 可执行体不序列化


def test_cli_run_dry_run_and_exit_codes(tmp_path, capsys):
    import pixcli
    src = _grid_png(str(tmp_path / "grid_src.png"))
    g = _img_graph(src, str(tmp_path / "out"),
                   extra_stages=[{"op": "gate-check", "params": {"max-colors": 2}}])
    gp = tmp_path / "g.json"
    gp.write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")
    assert pixcli.main(["run", str(gp), "--dry-run"]) == 0
    assert not os.path.exists(str(tmp_path / "out"))
    assert pixcli.main(["run", str(gp)]) == 1       # 门禁不通过
    g["stages"][-1]["params"]["max-colors"] = 16
    gp.write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")
    assert pixcli.main(["run", str(gp)]) == 0       # 门禁通过
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"version": 9}, ensure_ascii=False), encoding="utf-8")
    assert pixcli.main(["run", str(bad)]) == 2      # 配方非法
