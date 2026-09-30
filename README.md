# 仕分け工場

Streamlitで遊べる、データ分析リザルト付きの仕分けゲームです。実プレイ30秒、10秒ごとのルール変更で2秒ずつ休憩し、全体約34秒で終了します。

## 起動

Windowsでは「起動.bat」をダブルクリックします。初回は専用仮想環境と依存ライブラリをセットアップします。Pythonと、初回セットアップ時のインターネット接続が必要です。

手動で起動する場合：

```sh
python -m venv .venv
# Windows
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py --server.address localhost --browser.gatherUsageStats false
# macOS / Linux
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py --server.address localhost --browser.gatherUsageStats false
```

## 遊び方

クリックとキー操作（←・→、ハードではSpaceで蹴る）に対応します。長押しによる連打は無効です。

### ノーマル

| 実プレイ時間 | ルール |
|---|---|
| 0–10秒 | 青は左、オレンジは右 |
| 10–20秒 | 丸は左、四角は右 |
| 20–30秒 | 青は左、オレンジは右。ただし★付きは逆 |

### ハード（色固定・形キック）

**左＝オレンジ、右＝青で固定**。蹴る対象は色に関係なく、以下の形です。

| 実プレイ時間 | 蹴る形 |
|---|---|
| 0–10秒 | 四角 |
| 10–20秒 | 丸 |
| 20–30秒 | 三角 |

3種類の形は同確率で出現し、★は出ません。蹴る対象は1.5秒以内、それ以外は3秒以内に仕分けます。蹴るボタンは左右ボタンの下にあります。

各ルール変更時は2秒間タイマーと入力が停止し、新しいルールと再開カウントを表示します。正解100点＋コンボボーナス（2連続から10点刻み、最大100点）。誤答・未回答でコンボがリセットされます。切り替え・終了時に残った荷物も未回答として記録します。

## リザルトとデータ

- スコア、回答正答率、最大コンボ、ルール別成績
- 判断時間の散布図、切り替え後3秒以内とそれ以降の比較
- ハードでは蹴り成功率、見逃し、誤キック、操作別判断時間
- 全ログをUTF-8 BOM付きCSVでダウンロード

未回答は回答正答率と判断時間集計から除外し、別に数えます。蹴る対象の見逃しには左右への誤仕分けと未回答を含みます。ログのelapsed_sとphase_elapsed_sは休憩を除いた時間で、比較区間は荷物の提示時刻に基づきます。

ゲーム中はブラウザ内のperformance.now()で測定し、終了時にStreamlitへ一括送信します。研究用の反応時間測定ではなく、画面の描画遅延などを含むゲーム用途の計測です。タブを離れても時計は止まらず、戻った際に終了を判定します。

データはセッション内だけに保持します。再プレイやブラウザ再読み込みで以前の結果は消えるため、必要なら先にCSVを保存してください。

## 検証

```sh
node test_game.mjs
.venv\Scripts\python test_app.py
```

ゲームテストにはNode.jsが必要です。ゲームの通常起動にNode.jsは不要です。ルール判定、制限時間、休憩、クリック・キー入力、得点、リザルト集計を検証します。

実装：[Streamlit Components v2](https://docs.streamlit.io/develop/api-reference/custom-components/st.components.v2.component)
