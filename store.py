"""プレイデータを保存・読み込みする（reefmother-fps の store.py と同じ仕組み）。

- Streamlit の Secrets に Google のサービスアカウントとスプレッドシートの URL があれば、Googleスプレッドシートに保存する
- なければ、手元の data/runs.jsonl に保存する（ローカルでの動作確認用。Streamlit Community Cloud ではアプリの再起動で消える）

スプレッドシートは1回＝1行。集計しやすい列（スコア・正答率・判断時間など。サーバー側でログから計算し直す）と、
荷物1個ごとのログを JSON にまとめた列（items_json）を持つ。
"""
from __future__ import annotations

import json
import math
import os
import statistics
import time
from pathlib import Path

import streamlit as st

# 荷物1個ごとのログの列（items_json には、この並びの配列として入れる）
ITEM_COLS = ["number", "phase", "rule", "color", "shape", "star", "answer", "expected", "correct",
             "reaction_ms", "exposure_ms", "limit_ms", "elapsed_s", "phase_elapsed_s", "score", "combo", "reason"]
_TEXT_COLS = {"rule", "color", "shape", "answer", "expected", "reason"}
_BOOL_COLS = {"star", "correct"}

# 1回＝1行の集計列
SUMMARY = ["score", "max_combo", "n_items", "n_answered", "n_correct", "n_unanswered", "acc", "rt_median_ms",
           "acc_r1", "acc_r2", "acc_r3", "rt_r1", "rt_r2", "rt_r3",
           "acc_after_switch", "rt_after_switch", "acc_later", "rt_later",
           "kick_rate", "kick_miss", "wrong_kick"]
HEADER = ["run_id", "received_at", "player", "played_at", "mode", *SUMMARY, "version", "items_json"]

MODES = ("ノーマル", "ハード")
MAX_NAME = 16
MAX_ITEMS = 80       # 30秒で出せる荷物の数より十分多い上限
CELL_LIMIT = 45000   # スプレッドシートの1セルの上限（5万文字）より少し余裕を持たせる
VERSION = 1


def _num(v):
    """数値ならそのまま（NaN/無限大は None）、それ以外は None。"""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)) and math.isfinite(v):
        return v
    return None


def _ratio(n, d):
    return round(n / d, 4) if d else None


def _median(values):
    values = [v for v in values if v is not None]
    return round(statistics.median(values)) if values else None


def summarize(items: list[dict], mode: str) -> dict:
    """荷物1個ごとのログから、1回分の集計を出す（リザルト画面と同じ定義）。"""
    answered = [r for r in items if r["answer"] != "未回答"]
    correct = sum(bool(r["correct"]) for r in answered)
    out = {
        "score": sum(r["score"] or 0 for r in items),
        "max_combo": max([r["combo"] or 0 for r in items], default=0),
        "n_items": len(items), "n_answered": len(answered), "n_correct": correct,
        "n_unanswered": len(items) - len(answered),
        "acc": _ratio(correct, len(answered)),
        "rt_median_ms": _median(r["reaction_ms"] for r in answered),
    }
    for p in range(3):
        rows = [r for r in answered if r["phase"] == p]
        out[f"acc_r{p + 1}"] = _ratio(sum(bool(r["correct"]) for r in rows), len(rows))
        out[f"rt_r{p + 1}"] = _median(r["reaction_ms"] for r in rows)
    # ルール変更後（2・3番目のルール）を、切り替え後3秒以内とそれ以降に分ける
    changed = [r for r in answered if (r["phase"] or 0) > 0 and r["phase_elapsed_s"] is not None]
    for name, rows in (("after_switch", [r for r in changed if r["phase_elapsed_s"] <= 3]),
                       ("later", [r for r in changed if r["phase_elapsed_s"] > 3])):
        out[f"acc_{name}"] = _ratio(sum(bool(r["correct"]) for r in rows), len(rows))
        out[f"rt_{name}"] = _median(r["reaction_ms"] for r in rows)
    if mode == "ハード":
        targets = [r for r in items if r["expected"] == "蹴る"]
        out["kick_rate"] = _ratio(sum(bool(r["correct"]) for r in targets), len(targets))
        out["kick_miss"] = sum(r["answer"] != "蹴る" for r in targets)
        out["wrong_kick"] = sum(r["answer"] == "蹴る" and r["expected"] != "蹴る" for r in items)
    else:
        out["kick_rate"] = out["kick_miss"] = out["wrong_kick"] = None
    return out


def _clean_item(row) -> dict | None:
    if not isinstance(row, dict):
        return None
    item = {}
    for k in ITEM_COLS:
        v = row.get(k)
        if k in _TEXT_COLS:
            item[k] = str(v if v is not None else "")[:20]
        elif k in _BOOL_COLS:
            item[k] = bool(v)
        else:
            item[k] = _num(v)
    if item["phase"] not in (0, 1, 2):
        return None
    item["score"] = min(max(item["score"] or 0, 0), 200)  # 1個の得点は最大200点
    return item


def clean_run(run_id: str, player: str, result: dict) -> dict | None:
    """ブラウザから届いた1回分を検査して、保存してよい形にそろえる。おかしければ None。"""
    if not isinstance(result, dict) or not isinstance(result.get("rows"), list):
        return None
    if len(result["rows"]) > MAX_ITEMS:
        return None
    items = [i for i in (_clean_item(r) for r in result["rows"]) if i]
    mode = result.get("mode") if result.get("mode") in MODES else "ノーマル"
    return {
        "id": str(run_id)[:40],
        "player": str(player or "").strip()[:MAX_NAME] or "ゲスト",
        "mode": mode,
        "items": items,
        **summarize(items, mode),
    }


def _to_row(run: dict) -> list:
    items = json.dumps([[it[k] for k in ITEM_COLS] for it in run["items"]], ensure_ascii=False, separators=(",", ":"))
    if len(items) > CELL_LIMIT:  # 長すぎたら理由の列を落とす
        items = json.dumps([[it[k] for k in ITEM_COLS[:-1]] + [""] for it in run["items"]],
                           ensure_ascii=False, separators=(",", ":"))
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    blank = lambda v: "" if v is None else v  # noqa: E731
    return [run["id"], now, run["player"], now, run["mode"], *[blank(run[k]) for k in SUMMARY], VERSION, items]


def _from_row(row: dict) -> dict | None:
    """スプレッドシートの1行 → 分析画面で使う形（集計列＋ items のリスト）。"""
    try:
        f = lambda k: _num(float(row[k])) if str(row.get(k, "")).strip() != "" else None  # noqa: E731
        items = [dict(zip(ITEM_COLS, x)) for x in json.loads(row.get("items_json") or "[]")]
        return {
            "run_id": str(row["run_id"]), "player": str(row["player"]), "played_at": str(row["played_at"]),
            "mode": str(row.get("mode") or "ノーマル"), **{k: f(k) for k in SUMMARY}, "items": items,
        }
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None


class SheetStore:
    kind = "sheet"
    label = "Googleスプレッドシート"

    def __init__(self, info: dict, url: str):
        import gspread  # Secrets があるときだけ使う

        gc = gspread.service_account_from_dict(info)
        book = gc.open_by_url(url)
        try:
            self.ws = book.worksheet("runs")
        except gspread.WorksheetNotFound:
            self.ws = book.add_worksheet("runs", rows=1000, cols=len(HEADER))
        if self.ws.row_values(1) != HEADER:
            self.ws.update([HEADER], "A1")

    def append(self, run: dict) -> None:
        self.ws.append_row(_to_row(run), value_input_option="RAW")

    def load(self, limit: int) -> list[dict]:
        rows = self.ws.get_all_records(expected_headers=HEADER, value_render_option="UNFORMATTED_VALUE")
        return [r for r in (_from_row(x) for x in rows[-limit:]) if r]


class LocalStore:
    kind = "local"
    label = "ローカルファイル（data/runs.jsonl）"

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, run: dict) -> None:
        # スプレッドシートと同じ行の形で保存しておく（読み込みの処理を共通にするため）
        row = dict(zip(HEADER, _to_row(run)))
        with self.path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")

    def load(self, limit: int) -> list[dict]:
        if not self.path.exists():
            return []
        rows = []
        for ln in self.path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                rows.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
        return [r for r in (_from_row(x) for x in rows) if r]


_NO_SECRETS = (KeyError, FileNotFoundError, getattr(st.errors, "StreamlitSecretNotFoundError", FileNotFoundError))


@st.cache_resource
def _local_store(path: str):
    return LocalStore(Path(path))


@st.cache_resource
def _sheet_store(url: str, info_json: str):
    return SheetStore(json.loads(info_json), url)


def get_store():
    # Secrets は毎回読み直し、その内容ごとに保存先をキャッシュする。
    # こうしておくと、起動後に Secrets を足したり変えたりしても再起動なしで切り替わる。
    try:
        info = dict(st.secrets["gcp_service_account"])
        url = st.secrets["sheet_url"]
    except _NO_SECRETS:
        # テストでは SORTING_FACTORY_DATA で保存先を差し替える
        default = Path(__file__).parent / "data" / "runs.jsonl"
        return _local_store(os.environ.get("SORTING_FACTORY_DATA", str(default)))
    return _sheet_store(url, json.dumps(info, sort_keys=True))
