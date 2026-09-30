export default function(component) {
  const { parentElement: root, setStateValue } = component;
  const $ = id => root.querySelector('#' + id);
  const duration = 30000, phaseDuration = 10000, itemDuration = 3000, pauseDuration = 2000;
  let hard = false;
  let ruleNames = ['01 色で仕分け', '02 形で仕分け', '03 ★なら逆'];
  let running = false, started = 0, phase = 0, item = null, shown = 0;
  let score = 0, combo = 0, maxCombo = 0, rows = [], frame = 0, nextAt = 0;
  const choose = () => Math.random() < .5;

  function activeElapsed(now) {
    const wall = Math.max(0, now - started);
    return Math.min(duration, wall - Math.min(pauseDuration, Math.max(0, wall - 10000))
      - Math.min(pauseDuration, Math.max(0, wall - 22000)));
  }
  function correctSide(p, phaseNumber) {
    if (hard) return p.shape === ['square', 'circle', 'triangle'][phaseNumber] ? '蹴る' : p.blue ? '右' : '左';
    if (phaseNumber === 1) return p.circle ? '左' : '右';
    let left = p.blue;
    if (!hard && phaseNumber === 2 && p.star) left = !left;
    return left ? '左' : '右';
  }
  function setRule() {
    $('phase').textContent = `RULE ${phase + 1} / 3 ・ ${phase * 10}–${(phase + 1) * 10}秒`;
    $('rule').textContent = ['色で仕分けよう', 'ルール変更！ 今度は形', 'ルール変更！ ★付きは色の逆'][phase];
    $('mapping').textContent = [
      '青 → 左 ／ オレンジ → 右（形・★は無視）',
      '丸 → 左 ／ 四角 → 右（色・★は無視）',
      '青 → 左 ／ オレンジ → 右。ただし★付きは左右を逆に！'
    ][phase];
    if (hard) {
      $('rule').textContent = ['■ 四角は蹴る！', '● 丸は蹴る！', '▲ 三角は蹴る！'][phase];
      $('mapping').textContent = '左＝オレンジ ／ 右＝青（ずっと固定）。指定の形だけ1.5秒以内に蹴る！';
    }
    $('rulebox').classList.remove('flash');
    void $('rulebox').offsetWidth;
    $('rulebox').classList.add('flash');
  }
  function spawn(now) {
    item = {blue: choose(), circle: choose(), star: choose()};
    item.shape = hard ? ['square', 'circle', 'triangle'][Math.floor(Math.random() * 3)] : item.circle ? 'circle' : 'square';
    if (hard) item.star = false;
    shown = now;
    $('symbol').className = `${item.blue ? 'blue' : 'orange'} ${item.shape}`;
    $('star').textContent = item.star ? '★' : '';
    $('label').textContent = `${item.blue ? '青' : 'オレンジ'}・${{circle:'丸',square:'四角',triangle:'三角'}[item.shape]}${item.star ? '・★' : ''}`;
    $('parcel').style.visibility = 'visible';
    $('feedback').textContent = '仕分け再開！';
    $('kick').disabled = $('left').disabled = $('right').disabled = false;
  }
  function record(answer, now, reason = '') {
    if (!item) return;
    const expected = correctSide(item, phase);
    const correct = answer === expected;
    combo = correct ? combo + 1 : 0;
    maxCombo = Math.max(maxCombo, combo);
    const earned = correct ? 100 + Math.min((combo - 1) * 10, 100) : 0;
    score += earned;
    rows.push({number: rows.length + 1, mode: hard ? 'ハード' : 'ノーマル', limit_ms: correctSide(item, phase) === '蹴る' ? 1500 : itemDuration, phase, rule: ruleNames[phase],
      color: item.blue ? '青' : 'オレンジ', shape: {circle:'丸',square:'四角',triangle:'三角'}[item.shape], star: item.star,
      answer, expected, correct, reaction_ms: answer === '未回答' ? null : Math.round(now - shown),
      exposure_ms: Math.round(now - shown), elapsed_s: +(activeElapsed(now) / 1000).toFixed(3),
      phase_elapsed_s: +((activeElapsed(shown) - phase * phaseDuration) / 1000).toFixed(3),
      score: earned, combo, reason});
    $('score').textContent = score;
    $('combo').textContent = combo;
    $('feedback').textContent = correct ? `✓ 正解！ +${earned}` : answer === '未回答' ? '時間切れ！ 次の荷物へ' : `× 正解は「${expected}」`;
    $('feedback').style.color = correct ? '#5be0ba' : '#ffc28a';
    item = null;
    $('parcel').style.visibility = 'hidden';
    $('kick').disabled = $('left').disabled = $('right').disabled = true;
    nextAt = now + 180;
  }
  function finish(now) {
    if (!running) return;
    if (item) record('未回答', Math.min(now, started + duration + 2 * pauseDuration), 'プレイ終了');
    running = false;
    cancelAnimationFrame(frame);
    $('play').hidden = true;
    $('done').hidden = false;
    setStateValue('finished', {rows, mode: hard ? 'ハード' : 'ノーマル', score, max_combo: maxCombo, duration_seconds: 30});
  }
  function advance(now) {
    if (!running) return false;
    const wall = now - started;
    const elapsed = activeElapsed(now);
    const newPhase = wall >= 22000 ? 2 : wall >= 10000 ? 1 : 0;
    if (item) {
      const deadline = shown + (correctSide(item, phase) === '蹴る' ? 1500 : itemDuration);
      const boundary = started + phase * (phaseDuration + pauseDuration) + phaseDuration;
      if (now >= deadline && deadline <= boundary) record('未回答', deadline, '荷物の制限時間');
    }
    if (newPhase !== phase) {
      if (item) record('未回答', started + phase * (phaseDuration + pauseDuration) + phaseDuration, 'ルール変更');
      phase = newPhase;
      setRule();
      nextAt = now;
    }
    if (elapsed >= duration) { finish(now); return false; }
    const pauseEnd = wall >= 10000 && wall < 12000 ? 12000
      : wall >= 22000 && wall < 24000 ? 24000 : 0;
    $('remaining').textContent = ((duration - elapsed) / 1000).toFixed(1);
    $('progress').style.width = `${100 * (1 - elapsed / duration)}%`;
    $('pause').hidden = !pauseEnd;
    if (pauseEnd) {
      $('parcel').style.visibility = 'hidden';
      $('kick').disabled = $('left').disabled = $('right').disabled = true;
      $('pause-count').textContent = Math.ceil((pauseEnd - wall) / 1000);
      $('feedback').textContent = 'タイマー停止中 — 上の新しいルールを確認しよう';
      $('feedback').style.color = '#5be0ba';
      nextAt = now;
      return true;
    }

    if (!item && now >= nextAt) spawn(now);
    $('item-progress').style.width = item ? `${100 * Math.max(0, 1 - (now - shown) / (correctSide(item, phase) === '蹴る' ? 1500 : itemDuration))}%` : '0%';
    $('remaining').textContent = ((duration - elapsed) / 1000).toFixed(1);
    $('progress').style.width = `${100 * (1 - elapsed / duration)}%`;
    return true;
  }
  function tick(now) { if (advance(now)) frame = requestAnimationFrame(tick); }
  function answer(side) {
    const now = performance.now();
    // Ignore a click aimed at an expired parcel or the old rule.
    const previous = item;
    if (!advance(now) || !item || item !== previous) return;
    record(side, now);
    root.querySelector('.factory').focus({preventScroll: true});
  }
  $('mode').onchange = () => {
    $('normal-rules').hidden = $('mode').value === 'hard';
    $('hard-rules').hidden = $('mode').value !== 'hard';
  };
  $('start').onclick = () => {
    if (running) return;
    hard = $('mode').value === 'hard';
    if (hard) ruleNames = ['01 四角を蹴る', '02 丸を蹴る', '03 三角を蹴る'];
    $('kick').hidden = !hard;
    $('left').textContent = hard ? '← オレンジ' : '← 左へ';
    $('right').textContent = hard ? '青 →' : '右へ →';
    $('control-hint').textContent = hard ? '← 左 ／ → 右 ／ Space 蹴る ・ ボタンでも操作できます' : '← 左 ／ → 右 ・ ボタンでも操作できます';
    $('intro').hidden = true;
    $('play').hidden = false;
    running = true;
    started = performance.now();
    setRule();
    spawn(started);
    root.querySelector('.factory').focus();
    root.querySelector('.factory').scrollIntoView({block: 'start'});
    frame = requestAnimationFrame(tick);
  };
  $('left').onclick = () => answer('左');
  $('right').onclick = () => answer('右');
  $('kick').onclick = () => { if (hard) answer('蹴る'); };
  const keyHandler = e => {
    if (!running || e.repeat || !['ArrowLeft', 'ArrowRight', ...(hard ? [' '] : [])].includes(e.key)) return;
    e.preventDefault();
    answer(e.key === ' ' ? '蹴る' : e.key === 'ArrowLeft' ? '左' : '右');
  };
  root.addEventListener('keydown', keyHandler);
  // A background tab does not extend the shift. Check the deadline on return.
  const visibleHandler = () => { if (running && !document.hidden) advance(performance.now()); };
  document.addEventListener('visibilitychange', visibleHandler);
  return () => {
    running = false;
    cancelAnimationFrame(frame);
    root.removeEventListener('keydown', keyHandler);
    document.removeEventListener('visibilitychange', visibleHandler);
  };
}
