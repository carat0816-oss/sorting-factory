"""「みんなのデータ」画面：保存された全員分のプレイをまとめて見る・比べる・書き出す。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from store import ITEM_COLS, SUMMARY


def _frames(runs: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """1回＝1行の表と、荷物1個＝1行の表を作る。"""
    if not runs:
        return pd.DataFrame(columns=["run_id", "player", "played_at", "mode", *SUMMARY]), pd.DataFrame()
    per_run = pd.DataFrame([{k: v for k, v in r.items() if k != "items"} for r in runs])
    per_run = per_run.sort_values("played_at", kind="stable").reset_index(drop=True)
    per_run["何回目"] = per_run.groupby(["player", "mode"]).cumcount() + 1
    items = [{"run_id": r["run_id"], "player": r["player"], "mode": r["mode"], **it} for r in runs for it in r["items"]]
    per_item = pd.DataFrame(items, columns=["run_id", "player", "mode", *ITEM_COLS])
    return per_run, per_item


def _pct(v):
    return "—" if pd.isna(v) else f"{v:.0%}"


def show_shared(load_shared, store):
    st.markdown("# 📊 みんなのデータ")
    st.caption("「データ提供に同意」して送られたプレイの記録です。最大600回（新しい順）まで、1分ごとに読み直します。")
    try:
        runs = load_shared()
    except Exception as e:
        st.error(f"データの読み込みに失敗しました：{e}")
        return
    if st.button("🔄 最新のデータを読み込む"):
        load_shared.clear()
        st.rerun()
    per_run, per_item = _frames(runs)
    if per_run.empty:
        st.info("まだ記録がありません。遊んだあとのリザルト画面で「みんなのデータに送る」と、ここに集まります。")
        return

    mode = st.segmented_control("モード", ["ノーマル", "ハード"], default="ノーマル", key="shared_mode")
    mode = mode or "ノーマル"
    players = sorted(per_run["player"].unique())
    chosen = st.multiselect("プレイヤーで絞り込む（空なら全員）", players, key="shared_players")
    df = per_run[per_run["mode"] == mode]
    items = per_item[per_item["mode"] == mode] if not per_item.empty else per_item
    if chosen:
        df = df[df["player"].isin(chosen)]
        items = items[items["player"].isin(chosen)]
    if df.empty:
        st.info(f"{mode}の記録はまだありません。")
        return

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("記録", f"{len(df)} 回")
    m2.metric("プレイヤー", f"{df['player'].nunique()} 人")
    m3.metric("平均スコア", f"{df['score'].mean():,.0f}")
    m4.metric("正答率（全体）", _pct(df["n_correct"].sum() / df["n_answered"].sum() if df["n_answered"].sum() else None))

    ranking, trend, rules, data = st.tabs(["🏆 ランキング", "📈 伸び・速さと正確さ", "🔀 ルール別", "📋 データ・CSV"])

    with ranking:
        agg = dict(回数=("score", "size"), ベスト=("score", "max"), 平均スコア=("score", "mean"),
                   平均正答率=("acc", "mean"), 判断時間中央値ms=("rt_median_ms", "median"), 最大コンボ=("max_combo", "max"))
        if mode == "ハード":
            agg.update(蹴り成功率=("kick_rate", "mean"), 誤キック平均=("wrong_kick", "mean"))
        table = df.groupby("player").agg(**agg).sort_values("ベスト", ascending=False)
        table.insert(0, "順位", range(1, len(table) + 1))
        for col in ("平均正答率", "蹴り成功率"):
            if col in table:
                table[col] = (table[col] * 100).round(1)
        st.dataframe(table.round(1).rename(columns={"平均正答率": "平均正答率（%）", "蹴り成功率": "蹴り成功率（%）"}),
                     width="stretch")
        st.caption("ベストスコア順。正答率は未回答を除いた回答のうち正解した割合を、1回ごとに出して平均しています。")

    with trend:
        st.markdown("#### 回数を重ねるとスコアは伸びる？")
        st.scatter_chart(df, x="何回目", y="score", color="player")
        first = df[df["何回目"] == 1]["score"].mean()
        later = df[df["何回目"] > 1]["score"].mean()
        if pd.notna(later):
            st.caption(f"1回目の平均 {first:,.0f} 点 ／ 2回目以降の平均 {later:,.0f} 点。"
                       "何度も遊ぶ人ほど上手な可能性もあるため、慣れの効果とは断定できません。")
        st.markdown("#### 速さと正確さ")
        st.caption("1点＝1回のプレイ。右上ほど、判断に時間をかけて正確に答えた回です。")
        sc = df.dropna(subset=["rt_median_ms", "acc"]).assign(正答率=lambda d: d["acc"] * 100)
        if not sc.empty:
            st.scatter_chart(sc, x="rt_median_ms", y="正答率", color="player")
            if len(sc) >= 3:
                r = sc["rt_median_ms"].corr(sc["正答率"])
                if pd.notna(r):
                    st.caption(f"判断時間と正答率の相関 r = {r:.2f}（{len(sc)} 回分）")

    with rules:
        answered = items[items["answer"] != "未回答"] if not items.empty else items
        if answered.empty:
            st.caption("回答の記録があると表示されます。")
        else:
            st.markdown("#### ルールごとの成績（全員分の荷物を合算）")
            by_rule = items.groupby("rule").agg(荷物数=("correct", "size"))
            by_rule["回答数"] = answered.groupby("rule").size().reindex(by_rule.index, fill_value=0)
            by_rule["正答率（%）"] = (answered.groupby("rule")["correct"].mean() * 100).round(1)
            by_rule["判断時間中央値（秒）"] = (answered.groupby("rule")["reaction_ms"].median() / 1000).round(2)
            by_rule["未回答率（%）"] = ((1 - by_rule["回答数"] / by_rule["荷物数"]) * 100).round(1)
            st.dataframe(by_rule, width="stretch")
            st.bar_chart(by_rule[["正答率（%）"]], color="#16a085")
            st.markdown("#### 切り替え直後はどうだった？")
            changed = answered[(answered["phase"] > 0) & answered["phase_elapsed_s"].notna()].copy()
            if not changed.empty:
                changed["区間"] = changed["phase_elapsed_s"].map(lambda s: "切り替え後3秒以内" if s <= 3 else "それ以降")
                switch = changed.groupby("区間").agg(回答数=("correct", "size"), 正答率=("correct", "mean"),
                                                   判断時間中央値ms=("reaction_ms", "median"))
                switch["正答率"] = (switch["正答率"] * 100).round(1).astype(str) + "%"
                st.dataframe(switch, width="stretch")
            if mode == "ノーマル":
                st.markdown("#### ★付きの荷物（ルール3）")
                r3 = answered[answered["phase"] == 2]
                if not r3.empty:
                    star = r3.groupby("star").agg(回答数=("correct", "size"), 正答率=("correct", "mean"),
                                                 判断時間中央値ms=("reaction_ms", "median"))
                    star.index = star.index.map({True: "★あり（逆）", False: "★なし"})
                    star["正答率"] = (star["正答率"] * 100).round(1).astype(str) + "%"
                    st.dataframe(star, width="stretch")

    with data:
        st.dataframe(df.drop(columns=["何回目"]), width="stretch", hide_index=True)
        c1, c2 = st.columns(2)
        c1.download_button("回ごとのCSV", df.to_csv(index=False).encode("utf-8-sig"),
                           "sorting_factory_runs.csv", "text/csv", width="stretch")
        c2.download_button("荷物1個ごとのCSV", items.to_csv(index=False).encode("utf-8-sig"),
                           "sorting_factory_items.csv", "text/csv", width="stretch")
        if store.kind == "sheet":
            st.caption("不適切な名前や消してほしい記録は、スプレッドシートの行を消すと1分ほどでここからも消えます。")
        else:
            st.caption("不適切な名前や消してほしい記録は、data/runs.jsonl の該当行を消してください。")
