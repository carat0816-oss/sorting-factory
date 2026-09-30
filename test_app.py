from pathlib import Path
from streamlit.testing.v1 import AppTest

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
at.button[0].click().run()
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
