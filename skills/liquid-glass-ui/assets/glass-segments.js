// Analytic damped spring. Frequencies are in radians / second.
function advance(s, goal, frequency, damping, dt) {
  const offset = s.value - goal, decay = frequency * damping;
  const oscillation = frequency * Math.sqrt(1 - damping * damping);
  const cos = Math.cos(oscillation * dt), sin = Math.sin(oscillation * dt) / oscillation;
  const envelope = Math.exp(-decay * dt), speed = s.speed;
  s.value = goal + envelope * (offset * cos + (speed + decay * offset) * sin);
  s.speed = envelope * (speed * cos - (decay * speed + frequency * frequency * offset) * sin);
}

// A native radio group remains the single source of truth, including keyboard changes.
export function mountGlassSegments(group) {
  const motion = matchMedia('(prefers-reduced-motion: reduce)');
  const listeners = new AbortController(), options = {signal: listeners.signal};
  const thumb = document.createElement('span');
  thumb.className = 'lg-thumb'; thumb.hidden = true;
  thumb.setAttribute('aria-hidden', 'true');
  group.prepend(thumb);
  const x = {value:0, speed:0}, tail = {...x}, width = {...x}, lift = {...x};
  let choices = [], gesture, frame = 0, previous = 0, goalX = 0, goalWidth = 1, releaseAt = 0;
  let swallowClick = false, disposed = false;
  const selected = () => choices.find(c => c.input.checked);
  const localX = px => px - group.getBoundingClientRect().left - group.clientLeft;
  const nearest = pos => choices.reduce((a,b) => Math.abs(a.x-pos) < Math.abs(b.x-pos) ? a : b);
  function paint() {
    const w = Math.max(1, width.value), trail = w * .42 * Math.tanh((x.value - tail.value) / (w * .42));
    const p = Math.max(-.09, Math.min(1.08, lift.value)), stretch = Math.abs(trail) / w;
    thumb.style.width = w + 'px';
    thumb.style.transform = 'translate3d(' + (x.value - trail / 2 - w / 2) + 'px,0,0) scale(' +
      (1 + .50*p + stretch) + ',' + (1 + .34*p - .12*stretch) + ')';
  }
  function snap() {
    for (const [s, value] of [[x, goalX], [tail, goalX], [width, goalWidth], [lift, 0]]) {
      s.value = value; s.speed = 0;
    }
    paint();
  }
  function tick(now) {
    frame = 0;
    const dt = Math.max(.001, Math.min(.1, (now - previous) / 1000));
    previous = now;
    const pressed = gesture || now < releaseAt ? 1 : 0;
    advance(x, goalX, gesture?.dragging ? 55 : 32, .84, dt);
    advance(tail, goalX, gesture?.dragging ? 24 : 22, .89, dt);
    advance(width, goalWidth, 32, .86, dt);
    advance(lift, pressed, pressed ? 36 : 22, pressed ? .84 : .73, dt);
    paint();
    const settled = (s, goal, epsilon) => Math.abs(s.value - goal) < epsilon && Math.abs(s.speed) < epsilon*25;
    if (!settled(x, goalX, .05) || !settled(tail, goalX, .05) || !settled(width, goalWidth, .05) ||
        !settled(lift, pressed, .002) || (!gesture && pressed)) frame = requestAnimationFrame(tick);
    else if (!pressed) snap();
  }
  function wake() {
    if (motion.matches) { cancelAnimationFrame(frame); frame = 0; snap(); }
    else if (!frame) { previous = performance.now(); frame = requestAnimationFrame(tick); }
  }
  function align(animate) {
    const item = selected();
    thumb.hidden = !item || !group.clientWidth;
    group.toggleAttribute('data-lg-segments', !thumb.hidden);
    if (thumb.hidden) return;
    goalX = item.x; goalWidth = item.width;
    const h = Math.max(1, group.clientHeight * .855);
    thumb.style.height = h + 'px'; thumb.style.top = (group.clientHeight - h) / 2 + 'px';
    if (animate) wake(); else snap();
  }
  function endGrab() {
    const id = gesture?.id;
    gesture = null;
    if (id != null && group.hasPointerCapture(id)) group.releasePointerCapture(id);
  }
  function refresh() {
    if (disposed) return;
    if (gesture?.dragging) swallowClick = true;
    endGrab(); releaseAt = 0; cancelAnimationFrame(frame); frame = 0;
    choices = Array.from(group.children).filter(el => el.matches('label.lg-choice')).map(label => ({
      label, input:label.querySelector('input[type="radio"]'), width:Math.max(1, label.offsetWidth - 1),
      x:label.offsetLeft + label.offsetWidth / 2
    })).filter(c => c.input && !c.input.disabled && c.label.offsetWidth);
    align(false);
  }
  group.addEventListener('change', event => {
    if (choices.some(c => c.input === event.target)) align(true);
  }, options);
  group.addEventListener('pointerdown', event => {
    if (gesture || !event.isPrimary || event.button !== 0) return;
    swallowClick = false;
    const item = choices.find(c => c.label.contains(event.target));
    if (!item) return;
    // No checked radio yet: leave the first choice to the native control.
    if (thumb.hidden) return;
    gesture = {id:event.pointerId, x:event.clientX, y:event.clientY, grip:localX(event.clientX) - item.x, dragging:false};
    goalX = item.x; goalWidth = item.width; releaseAt = 0; wake();
  }, options);
  window.addEventListener('pointermove', event => {
    if (gesture?.id !== event.pointerId) return;
    if (!gesture.dragging) {
      const dx = Math.abs(event.clientX - gesture.x), dy = Math.abs(event.clientY - gesture.y);
      if (dy > 6 && dy > dx) { endGrab(); align(true); return; }
      if (dx < 4) return;
      gesture.dragging = true;
      group.setPointerCapture(event.pointerId);
    }
    const centers = choices.map(c => c.x);
    goalX = Math.max(Math.min(...centers), Math.min(Math.max(...centers), localX(event.clientX) - gesture.grip));
    goalWidth = nearest(goalX).width;
    wake();
  }, options);
  window.addEventListener('pointerup', event => {
    if (gesture?.id !== event.pointerId) return;
    const {dragging, grip} = gesture;
    endGrab(); releaseAt = performance.now() + 85;
    if (dragging) {
      swallowClick = true;
      const {input} = nearest(localX(event.clientX) - grip);
      input.focus({preventScroll:true});
      input.click();
    }
    align(true);
  }, options);
  function cancel(event) {
    if (!gesture || (event.pointerId != null && event.pointerId !== gesture.id)) return;
    swallowClick = gesture.dragging; endGrab(); releaseAt = 0; align(true);
  }
  window.addEventListener('pointercancel', cancel, options);
  window.addEventListener('blur', cancel, options);
  group.addEventListener('lostpointercapture', e => { if (e.target === group) cancel(e); }, options);
  group.addEventListener('click', e => {
    if (swallowClick && e.isTrusted && e.detail > 0) {
      swallowClick = false; e.preventDefault(); e.stopImmediatePropagation();
    }
  }, {...options, capture:true});
  const observer = new ResizeObserver(refresh);
  observer.observe(group);
  Array.from(group.querySelectorAll(':scope > .lg-choice')).forEach(label => observer.observe(label));
  group.closest('form')?.addEventListener('reset', () => queueMicrotask(refresh), options);
  motion.addEventListener('change', refresh, options);
  refresh();
  return {refresh, destroy() {
    disposed = true; endGrab(); listeners.abort(); observer.disconnect(); cancelAnimationFrame(frame);
    group.removeAttribute('data-lg-segments'); thumb.remove();
  }};
}
