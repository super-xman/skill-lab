function createGlassRenderer(canvas) {
  const gl = canvas.getContext('webgl', {alpha: true, antialias: false, depth: false, stencil: false});
  if (!gl) return null;

  const vertex = `
    attribute vec2 position;
    varying vec2 uv;
    void main() {
      uv = vec2(.5 + .5 * position.x, .5 - .5 * position.y);
      gl_Position = vec4(position, 0., 1.);
    }`;
  const fragment = `
    precision highp float;
    varying vec2 uv;
    uniform sampler2D scene;
    uniform sampler2D diffuseScene;
    uniform vec2 cropSize;
    uniform vec2 railSize;
    uniform float corner;
    uniform vec4 tint;
    uniform vec4 sampleBounds;

    const vec3 luma = vec3(.2126, .7152, .0722);
    void main() {
      vec2 p = (uv - .5) * railSize;
      vec2 sceneUV = .5 + p / cropSize;
      float radius = min(corner, min(railSize.x, railSize.y) * .5);
      vec2 q = abs(p) - .5 * railSize + radius;
      vec2 outer = max(q, 0.);
      float len = length(outer);
      float depth = radius - len - min(max(q.x, q.y), 0.);
      if (depth < -.65) { gl_FragColor = vec4(0.); return; }

      vec2 face = q.x > q.y ? vec2(sign(p.x), 0.) : vec2(0., sign(p.y));
      vec2 normal = len > .001 ? sign(p) * outer / len : face;
      float curvatureRadius = max(radius, 1.);
      float d = max(depth, 0.);
      float bevel = curvatureRadius * .51;
      float roll = 1. - smoothstep(0., bevel, d);
      float angle = 1.30 * roll;
      vec3 surface = vec3(normal * sin(angle), cos(angle));
      // Gently magnify the live image and concentrate the bend at the outer edge.
      float edge = 1. - smoothstep(0., railSize.y * .18, d);
      float bend = railSize.y * 1.25 * (.067 * edge + .205 * pow(edge, 10.));
      vec2 mapped = .5 + (p / 1.03 + normal * bend) / cropSize;
      vec2 at = clamp(mapped, sampleBounds.xy, sampleBounds.zw);
      vec3 detail = texture2D(scene, at).rgb;
      vec3 diffuse = texture2D(diffuseScene, at).rgb;
      vec3 color = mix(detail, diffuse, mix(.15, .085, roll));
      color = mix(vec3(dot(color, luma)), color, 1.08);
      color = mix(color, tint.rgb, tint.a * .45);
      color *= 1. - .18 * smoothstep(.38, .84, dot(diffuse, luma));

      // Grazing rays pick up a second, compressed strip of scenery from outside the
      // capsule. A pale wave and a dark stone joint produce different edge reflections.
      vec2 outside = clamp(sceneUV + normal * (bevel * (.45 + 1.1 * roll)) / cropSize,
                           sampleBounds.xy, sampleBounds.zw);
      vec3 environment = mix(texture2D(scene, outside).rgb, texture2D(diffuseScene, outside).rgb, .35);
      float grazing = pow(1. - surface.z, 5.);
      color = mix(color, environment, .09 * roll * roll + .70 * grazing);
      float upper = max(dot(normal, vec2(-.32, -.947)), 0.);
      float lower = max(dot(normal, vec2(.25, .968)), 0.);
      float lip = exp(-.95 * (d - .95) * (d - .95));
      float shoulderDistance = (d - .32 * bevel) / (.20 * bevel);
      float shoulder = exp(-shoulderDistance * shoulderDistance);
      float light = .54 + .46 * smoothstep(.10, .78, dot(environment, luma));
      vec3 glint = mix(vec3(.98, .99, 1.), environment, .19);
      color *= 1. - lip * (.035 + .15 * (1. - abs(normal.y)));
      color = mix(color, glint, lip * (.045 + light * (.46 * upper + .31 * lower))
                        + shoulder * light * (.14 * upper * upper + .085 * lower * lower));
      float coverage = smoothstep(-.65, .80, depth);
      color = clamp(color, 0., 1.);
      gl_FragColor = vec4(color * coverage, coverage);
    }`;

  function compile(type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    return shader;
  }
  const program = gl.createProgram();
  const vs = compile(gl.VERTEX_SHADER, vertex), fs = compile(gl.FRAGMENT_SHADER, fragment);
  gl.attachShader(program, vs);
  gl.attachShader(program, fs);
  gl.linkProgram(program);
  gl.deleteShader(vs);
  gl.deleteShader(fs);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    gl.deleteProgram(program);
    return null;
  }
  gl.useProgram(program);
  const triangle = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, triangle);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const position = gl.getAttribLocation(program, 'position');
  gl.enableVertexAttribArray(position);
  gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
  function makeTexture(uniform, unit) {
    const texture = gl.createTexture();
    gl.activeTexture(gl.TEXTURE0 + unit);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.uniform1i(gl.getUniformLocation(program, uniform), unit);
    return texture;
  }
  const texture = makeTexture('scene', 0), diffuseTexture = makeTexture('diffuseScene', 1);
  const cropSize = gl.getUniformLocation(program, 'cropSize');
  const railSize = gl.getUniformLocation(program, 'railSize');
  const corner = gl.getUniformLocation(program, 'corner');
  const tint = gl.getUniformLocation(program, 'tint');
  const sampleBounds = gl.getUniformLocation(program, 'sampleBounds');
  let lowWidth = 0, lowHeight = 0, allocatedWidth = 0, allocatedHeight = 0;

  function render(source, low, w, h, railW, railH, radius, color, bounds) {
    if (gl.isContextLost()) return false;
    const outputW = Math.max(1, Math.round(source.width * railW / w));
    const outputH = Math.max(1, Math.round(source.height * railH / h));
    if (canvas.width !== outputW || canvas.height !== outputH) {
      canvas.width = outputW; canvas.height = outputH;
      gl.viewport(0, 0, outputW, outputH);
    }
    if (source.width !== allocatedWidth || source.height !== allocatedHeight) {
      allocatedWidth = source.width; allocatedHeight = source.height;
      gl.activeTexture(gl.TEXTURE0);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, allocatedWidth, allocatedHeight, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    }
    gl.activeTexture(gl.TEXTURE1);
    if (lowWidth !== low.width || lowHeight !== low.height) {
      lowWidth = low.width;
      lowHeight = low.height;
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, lowWidth, lowHeight, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    }
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, gl.RGBA, gl.UNSIGNED_BYTE, low);
    gl.activeTexture(gl.TEXTURE0);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, gl.RGBA, gl.UNSIGNED_BYTE, source);
    gl.uniform2f(cropSize, w, h);
    gl.uniform2f(railSize, railW, railH);
    gl.uniform1f(corner, radius);
    gl.uniform4fv(tint, color);
    gl.uniform4fv(sampleBounds, bounds);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    return true;
  }

  function destroy() {
    gl.deleteTexture(texture);
    gl.deleteTexture(diffuseTexture);
    gl.deleteBuffer(triangle);
    gl.deleteProgram(program);
    gl.getExtension('WEBGL_lose_context')?.loseContext();
  }
  return {render, destroy, maxSize: gl.getParameter(gl.MAX_TEXTURE_SIZE)};
}

// Match an unrotated CSS object-fit: cover / object-position: center image or video.
export function drawCover(ctx, media, box) {
  const w = media.naturalWidth ?? media.videoWidth ?? media.width;
  const h = media.naturalHeight ?? media.videoHeight ?? media.height;
  if (!(w > 0 && h > 0 && box.width > 0 && box.height > 0) || media.readyState < 2) return false;
  const scale = Math.max(box.width / w, box.height / h);
  const sw = box.width / scale, sh = box.height / scale;
  ctx.drawImage(media, (w - sw) / 2, (h - sh) / 2, sw, sh, box.left, box.top, box.width, box.height);
  return true;
}

// paintBackdrop draws in viewport CSS pixels. Return false until the media is ready.
export function mountGlassLens(surface, paintBackdrop) {
  const canvas = document.createElement('canvas');
  canvas.className = 'lg-glass-pixels';
  canvas.setAttribute('aria-hidden', 'true');
  const crop = document.createElement('canvas'), low = document.createElement('canvas');
  const ctx = crop.getContext('2d'), small = low.getContext('2d');
  const solid = matchMedia('(prefers-reduced-transparency: reduce), (forced-colors: active)');
  const events = new AbortController();
  const options = {signal: events.signal};
  let renderer, frame = 0, blocked = false, lost = false, disposed = false;
  surface.prepend(canvas);

  function render() {
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    if (disposed || document.hidden) return false;
    const box = surface.getBoundingClientRect();
    const viewportWidth = document.documentElement.clientWidth;
    const viewportHeight = document.documentElement.clientHeight;
    if (solid.matches || lost || blocked || !box.width || !box.height ||
        box.right <= 0 || box.left >= viewportWidth || box.bottom <= 0 || box.top >= viewportHeight) {
      surface.removeAttribute('data-lg-rendered');
      return false;
    }
    renderer ??= createGlassRenderer(canvas);
    if (!renderer) { blocked = true; return false; }
    // The reference rails use 44px. Taller surfaces need up to 0.34 heights for
    // refraction and just under 0.40 for the outer highlight, plus a pixel of padding.
    const pad = Math.max(44, Math.ceil(box.height * .40) + 1);
    const w = box.width + 2 * pad, h = box.height + 2 * pad;
    const dpr = Math.min(devicePixelRatio || 1, 2, Math.sqrt(1200000 / (w * h)), renderer.maxSize / Math.max(w, h));
    const pw = Math.max(1, Math.round(w * dpr)), ph = Math.max(1, Math.round(h * dpr));
    if (crop.width !== pw || crop.height !== ph) {
      crop.width = pw; crop.height = ph;
    }
    const lw = Math.max(1, Math.ceil(w / 5)), lh = Math.max(1, Math.ceil(h / 5));
    if (low.width !== lw || low.height !== lh) {
      low.width = lw; low.height = lh;
      small.imageSmoothingQuality = 'high';
    }
    const area = {left: box.left - pad, top: box.top - pad, width: w, height: h};
    const sx = pw / w, sy = ph / h;
    ctx.save();
    ctx.setTransform(sx, 0, 0, sy, -area.left * sx, -area.top * sy);
    ctx.clearRect(area.left, area.top, w, h);
    let ready;
    try { ready = paintBackdrop(ctx, area); }
    finally { ctx.restore(); }
    if (ready === false) { surface.removeAttribute('data-lg-rendered'); return false; }
    small.clearRect(0, 0, lw, lh);
    small.drawImage(crop, 0, 0, lw, lh);
    const style = getComputedStyle(surface);
    const radius = parseFloat(style.borderTopLeftRadius);
    const rgb = style.getPropertyValue('--lg-tint-rgb').trim().split(/\s+/).map(v => Number(v) / 255);
    const tint = [...rgb, Number(style.getPropertyValue('--lg-opacity'))];
    try {
      // A dock's padded crop often extends below the viewport. Reflect its last visible texel.
      const bounds = [
        Math.max(0, -area.left / w) + .5 / pw,
        Math.max(0, -area.top / h) + .5 / ph,
        Math.min(1, (viewportWidth - area.left) / w) - .5 / pw,
        Math.min(1, (viewportHeight - area.top) / h) - .5 / ph
      ];
      ready = renderer.render(crop, low, w, h, box.width, box.height, radius, tint, bounds);
    } catch (error) {
      if (error.name !== 'SecurityError') throw error;
      blocked = true; ready = false;
    }
    surface.toggleAttribute('data-lg-rendered', ready);
    return ready;
  }
  function invalidate() {
    if (!disposed && !frame) frame = requestAnimationFrame(render);
  }
  canvas.addEventListener('webglcontextlost', event => {
    event.preventDefault(); lost = true; renderer = null;
    surface.removeAttribute('data-lg-rendered');
  }, options);
  canvas.addEventListener('webglcontextrestored', () => { lost = false; invalidate(); }, options);
  const observer = new ResizeObserver(invalidate);
  observer.observe(surface);
  window.addEventListener('scroll', invalidate, {...options, capture:true, passive:true});
  window.addEventListener('resize', invalidate, options);
  document.addEventListener('visibilitychange', invalidate, options);
  solid.addEventListener('change', invalidate, options);
  invalidate();
  return {render, invalidate, destroy() {
    disposed = true;
    cancelAnimationFrame(frame); events.abort(); observer.disconnect();
    renderer?.destroy(); canvas.remove(); surface.removeAttribute('data-lg-rendered');
  }};
}
