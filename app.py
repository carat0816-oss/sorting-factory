from pathlib import Path
import uuid

import pandas as pd
import streamlit as st
import streamlit.components.v2 as components

from shared_view import show_shared
from store import clean_run, get_store

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="仕分け工場 | 30秒チャレンジ", page_icon="📦", layout="centered")

MAX_SHARED = 600        # 読み込む「みんなのデータ」の最大回数（新しい順）
MAX_PER_SESSION = 40    # 1回の接続で受け付ける最大回数（いたずら対策）

store = get_store()


@st.cache_data(ttl=60, show_spinner=False)
def load_shared() -> list[dict]:
    return store.load(MAX_SHARED)


with st.sidebar:
    st.header("📦 仕分け工場")
    page = st.radio("画面", ["🎮 遊ぶ", "📊 みんなのデータ"], key="page", label_visibility="collapsed")
    st.caption("※ プレイ中に画面を切り替えると、そのプレイは中断されます")
    try:
        n_shared = len(load_shared())
    except Exception as e:  # 保存先に一時的につながらなくてもゲームは遊べるようにする
        n_shared = None
        st.warning(f"データの読み込みに失敗しました：{e}")
    st.caption(f"保存先：{store.label}" + (f" ／ 集まった記録：{n_shared} 回" if n_shared is not None else ""))
    if store.kind == "local":
        st.caption("※ Secrets にスプレッドシートの設定がないため、手元のファイルに保存しています")

if page == "📊 みんなのデータ":
    show_shared(load_shared, store)
    st.stop()

st.markdown("# 📦 仕分け工場")
st.caption("実プレイ30秒 ・ 10秒ごとにルール変更＆2秒休憩")


@st.cache_resource
def load_game(asset_version):
    return components.component(
        "sorting_factory",
        html=(ROOT / "game.html").read_text(encoding="utf-8"),
        css=(ROOT / "game.css").read_text(encoding="utf-8"),
        js=(ROOT / "game.js").read_text(encoding="utf-8"),
    )


def share_run(result):
    """このプレイを「みんなのデータ」に送る。同意した人の分だけ、1回につき1度だけ保存する。"""
    play_id = st.session_state.play_id
    saved = st.session_state.setdefault("saved_ids", set())
    with st.container(border=True):
        if play_id in saved:
            st.success("この記録は「みんなのデータ」に送りました。サイドバーから全員分の分析を見られます。")
            return
        st.markdown("**📤 この記録を「みんなのデータ」に送る**")
        # 名前は次のプレイでも使えるように覚えておく（同意はプレイごとに取り直す）
        if "player_name" not in st.session_state:
            st.session_state.player_name = st.session_state.get("last_player", "")
        player = st.text_input("プレイヤー名（ニックネームにしてください）", max_chars=16, key="player_name",
                               placeholder="例：しわけ名人")
        consent = st.checkbox("データ提供に同意する（名前・スコア・荷物ごとの回答と判断時間が保存され、"
                              "このアプリを使う全員が見られます）", key="consent")
        if st.button("送る", disabled=not consent, key="share"):
            if len(saved) >= MAX_PER_SESSION:
                st.warning("この接続で送れる回数の上限に達しました。ページを読み込み直してください。")
                return
            run = clean_run(play_id, player, result)
            if not run:
                st.error("記録の形式がおかしいため、送れませんでした。")
                return
            try:
                store.append(run)
            except Exception as e:
                st.error(f"データの保存に失敗しました：{e}")
                return
            saved.add(play_id)
            st.session_state.last_player = player
            load_shared.clear()
            st.rerun()


if "play_id" not in st.session_state:
    st.session_state.play_id = str(uuid.uuid4())

if "result" not in st.session_state:
    game = load_game(tuple((ROOT / name).stat().st_mtime_ns for name in ("game.html", "game.css", "game.js")))
    response = game(key=st.session_state.play_id, on_finished_change=lambda: None)
    if response.finished:
        st.session_state.result = response.finished
        st.rerun()
else:
    result = st.session_state.result
    rows = result["rows"]
    st.caption(f"モード：{result.get('mode', 'ノーマル')}")
    st.subheader("シフト終了！ おつかれさまでした")
    score, accuracy, combo = st.columns(3)
    score.metric("スコア", f'{result["score"]:,}')
    answered = [r for r in rows if r["answer"] != "未回答"]
    correct = sum(r["correct"] for r in answered)
    accuracy.metric("回答した荷物の正答率", f"{correct / len(answered):.0%}" if answered else "—")
    combo.metric("最大コンボ", f'{result["max_combo"]} 連続')
    st.caption(f"回答数 {len(answered)} 個 ／ 正解 {correct} 個 ／ 未回答 {len(rows) - len(answered)} 個")
    share_run(result)
    if result.get("mode") == "ハード":
        targets = [r for r in rows if r["expected"] == "蹴る"]
        successes = sum(r["correct"] for r in targets)
        misses = sum(r["answer"] != "蹴る" for r in targets)
        wrong_kicks = sum(r["answer"] == "蹴る" and r["expected"] != "蹴る" for r in rows)
        k1, k2, k3 = st.columns(3)
        k1.metric("蹴り成功率", f"{successes / len(targets):.0%}" if targets else "—")
        k2.metric("蹴る対象の見逃し", misses)
        k3.metric("誤キック", wrong_kicks)
        st.caption("見逃しは、蹴る対象を左右へ送った場合と未回答の場合（切り替え・終了を含む）。")
    if answered:
        df = pd.DataFrame(rows)
        adf = df[df["answer"] != "未回答"].copy()
        adf["判断時間（秒）"] = adf["reaction_ms"] / 1000
        if result.get("mode") == "ハード":
            compare = adf.copy()
            compare["操作"] = compare["answer"].map(lambda x: "蹴る" if x == "蹴る" else "左右仕分け")
            st.dataframe(compare.groupby("操作").agg(回答数=("correct", "size"), 判断時間中央値秒=("判断時間（秒）", "median")).round(2), width="stretch")
        median = adf["判断時間（秒）"].median()
        st.info(f"今回の中央値は **{median:.2f}秒／個**。再挑戦して、速さと正確さの両方を伸ばそう！")
        overview, detail = st.tabs(["📊 プレイを分析", "📋 全ログ・CSV"])
        with overview:
            st.markdown("#### ルールごとの成績")
            summary = df.groupby("rule", sort=True).agg(
                荷物数=("correct", "size"), 正解数=("correct", "sum")
            )
            answered_by_rule = adf.groupby("rule").size()
            summary["回答数"] = answered_by_rule.reindex(summary.index, fill_value=0)
            summary["未回答数"] = summary["荷物数"] - summary["回答数"]
            summary["正答率（%）"] = (summary["正解数"] / summary["回答数"].replace(0, float("nan")) * 100).round(1)
            summary["判断時間中央値（秒）"] = adf.groupby("rule")["判断時間（秒）"].median().round(2)
            st.dataframe(summary, width="stretch")
            st.bar_chart(summary[["正答率（%）"]], color="#16a085")
            st.markdown("#### 判断時間の推移")
            st.caption("横軸は休憩を除いたプレイ経過秒。10秒・20秒でルールが切り替わります。誤答も含みます。")
            st.scatter_chart(adf, x="elapsed_s", y="判断時間（秒）", color="rule")
            st.markdown("#### 切り替え直後はどうだった？")
            changed = adf[adf["phase"] > 0].copy()
            if not changed.empty:
                changed["区間"] = changed["phase_elapsed_s"].map(
                    lambda seconds: "切り替え後3秒以内" if seconds <= 3 else "それ以降"
                )
                switch = changed.groupby("区間").agg(
                    回答数=("correct", "size"), 正答率=("correct", "mean"), 判断時間中央値秒=("判断時間（秒）", "median")
                )
                switch["正答率"] = (switch["正答率"] * 100).round(1).astype(str) + "%"
                st.dataframe(switch.round(2), width="stretch")
            else:
                st.caption("ルール変更後の回答があると表示されます。")
            st.caption("今回のプレイの記録です。後半ほどルールが難しくなるため、時間帯の差を疲労や能力の差とは断定できません。")
        with detail:
            st.dataframe(df, width="stretch", hide_index=True)
            st.download_button("全ログをCSVで保存", df.to_csv(index=False).encode("utf-8-sig"),
                               "sorting_factory_log.csv", "text/csv")
    else:
        st.info("今回は回答がありませんでした。左右のボタンで荷物を仕分けてみましょう。")
        if rows:
            st.download_button("全ログをCSVで保存", pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig"),
                               "sorting_factory_log.csv", "text/csv")
    st.caption("正解100点＋コンボボーナス（1連続目0点、以降10点ずつ増加、最大100点）。誤答・未回答は0点でコンボが途切れます。")
    if st.button("もう一度遊ぶ", type="primary", width="stretch"):
        del st.session_state.result
        st.session_state.play_id = str(uuid.uuid4())
        st.rerun()

