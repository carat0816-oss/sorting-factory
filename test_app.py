import json
import os
import tempfile
from pathlib import Path
from streamlit.testing.v1 import AppTest

# 保存先を一時ファイルにする（手元の data/runs.jsonl を汚さない）
data_file = Path(tempfile.mkdtemp()) / 'runs.jsonl'
os.environ['SORTING_FACTORY_DATA'] = str(data_file)
replay = lambda at: next(b for b in at.button if b.label == 'もう一度遊ぶ')  # noqa: E731

app = str(Path(__file__).with_name('app.py'))
at = AppTest.from_file(app).run()
assert not at.exception, at.exception
rows = []
for phase in range(3):
    for i in range(3):
        rows.append(dict(number=len(rows)+1, phase=phase, rule=['01 色で仕分け','02 形で仕分け','03 ★なら逆'][phase], color='青', shape='丸', star=False, answer='未回答' if i==2 else '左', expected='左', correct=i<2, reaction_ms=None if i==2 else 650+i*100, exposure_ms=1000, elapsed_s=phase*10+i+1, phase_elapsed_s=i+1, score=100 if i<2 else 0, combo=i+1 if i<2 else 0, reason=''))
at.session_state['result'] = dict(rows=rows, score=600, max_combo=2)
at.run()
assert not at.exception, at.exception
assert len(at.metric) == 3
assert at.metric[0].value == '600'
replay(at).click().run()
assert not at.exception, at.exception
assert 'result' not in at.session_state
at.session_state['result'] = dict(rows=[], score=0, max_combo=0)
at.run()
assert not at.exception, at.exception
print('PASS: initial screen, results/charts, replay, empty results')

rows[0].update(expected="蹴る", answer="蹴る", correct=True)
rows[1].update(expected="左", answer="蹴る", correct=False)
rows[2].update(expected="蹴る", answer="未回答", correct=False)
at.session_state['result'] = dict(rows=rows, score=600, max_combo=2, mode="ハード")
at.run()
assert not at.exception, at.exception
assert [x.value for x in at.metric][3:] == ['50%', '1', '1']
print('PASS: hard-mode success, missed targets, wrong kicks and reaction comparison')

# 記録を「みんなのデータ」に送る：同意するまで送れず、送ると1行保存される
assert at.button(key='share').disabled
at.text_input(key='player_name').input('テスト太郎')
at.checkbox(key='consent').check().run()
at.button(key='share').click().run()
assert not at.exception, at.exception
saved = [json.loads(x) for x in data_file.read_text(encoding='utf-8').splitlines()]
assert len(saved) == 1 and saved[0]['player'] == 'テスト太郎' and saved[0]['mode'] == 'ハード'
assert saved[0]['score'] == 600 and saved[0]['n_answered'] == 6 and saved[0]['kick_miss'] == 1
assert not any(b.key == 'share' for b in at.button)  # 同じ回は二度送れない
print('PASS: consent, sending a run, no double sending')

# ノーマルの回をもう1つ送り、みんなのデータ画面を開く
replay(at).click().run()
for r in rows:
    r.update(expected='左', answer='左', correct=True)
rows[2].update(answer='未回答', correct=False, reaction_ms=None)
at.session_state['result'] = dict(rows=rows, score=900, max_combo=5, mode='ノーマル')
at.run()
assert at.text_input(key='player_name').value == 'テスト太郎'  # 名前は引き継ぐ
assert at.button(key='share').disabled  # 同意はプレイごと
at.checkbox(key='consent').check().run()
at.button(key='share').click().run()
assert not at.exception, at.exception
at.sidebar.radio(key='page').set_value('📊 みんなのデータ').run()
assert not at.exception, at.exception
assert [m.value for m in at.metric][:2] == ['1 回', '1 人']
assert len(at.dataframe) >= 3
at.segmented_control(key='shared_mode').set_value('ハード').run()
assert not at.exception, at.exception
assert at.metric[0].value == '1 回'
print('PASS: shared data view (ranking, trends, rules, CSV)')
