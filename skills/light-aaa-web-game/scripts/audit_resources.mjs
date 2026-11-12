/** Test-mode audit helpers; no Three.js dependency. Pair with project-specific audits. */
export function auditGeometry(geometries, {maxExtent = 2000, degenerateFractionMax = 0.01} = {}) {
  const result = {geometries: 0, vertices: 0, triangles: 0, nonFinite: 0,
    invalidIndices: 0, invalidNormals: 0, missingAttributes: 0, degenerate: 0, excessiveBounds: 0};
  for (const geometry of new Set(geometries)) {
    result.geometries++;
    const p = geometry.attributes.position, n = geometry.attributes.normal;
    if (!p || !n) { result.missingAttributes++; continue; }
    result.vertices += p.count;
    const low = [Infinity, Infinity, Infinity], high = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < p.count; i++) {
      const pos = [p.getX(i), p.getY(i), p.getZ(i)];
      for (let axis = 0; axis < 3; axis++) {
        if (!Number.isFinite(pos[axis])) result.nonFinite++;
        low[axis] = Math.min(low[axis], pos[axis]); high[axis] = Math.max(high[axis], pos[axis]);
      }
      const length = Math.hypot(n.getX(i), n.getY(i), n.getZ(i));
      if (!Number.isFinite(length) || Math.abs(length - 1) > .1) result.invalidNormals++;
    }
    if (low.some((v, i) => high[i] - v > maxExtent)) result.excessiveBounds++;
    const count = geometry.index ? geometry.index.count : p.count;
    if (count % 3 !== 0) result.invalidIndices++;
    for (let i = 0; i + 2 < count; i += 3) {
      result.triangles++;
      const ids = [0, 1, 2].map(j => geometry.index ? geometry.index.getX(i + j) : i + j);
      if (ids.some(id => !Number.isInteger(id) || id < 0 || id >= p.count)) {
        result.invalidIndices++; continue;
      }
      const v = ids.map(id => [p.getX(id), p.getY(id), p.getZ(id)]);
      const a = v[1].map((x, j) => x - v[0][j]), b = v[2].map((x, j) => x - v[0][j]);
      if (Math.hypot(a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]) < 1e-10)
        result.degenerate++;
    }
  }
  result.degenerateFraction = result.degenerate / Math.max(1, result.triangles);
  const invalid = result.nonFinite + result.invalidIndices + result.invalidNormals +
    result.missingAttributes + result.excessiveBounds;
  return {id:'geometry', status:!result.geometries ? 'unverified' :
    invalid || result.degenerateFraction > degenerateFractionMax ? 'failed' : 'passed', evidence:result};
}

export function auditAudio(namedBuffers, {silentAllowed = [], minRms = 1e-5} = {}) {
  const evidence = [];
  for (const [name, buffer] of Object.entries(namedBuffers)) {
    let nonFinite = 0, peak = 0, squares = 0, samples = 0;
    for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
      const data = buffer.getChannelData(channel);
      for (const value of data) {
        if (!Number.isFinite(value)) { nonFinite++; continue; }
        peak = Math.max(peak, Math.abs(value)); squares += value * value; samples++;
      }
    }
    const rms = Math.sqrt(squares / Math.max(1, samples));
    evidence.push({name, nonFinite, peak, rms, samples, sampleRate:buffer.sampleRate,
      duration:buffer.duration, bytes:buffer.length * buffer.numberOfChannels * 4,
      invalid:nonFinite > 0 || !samples || peak > 1.000001 ||
        (!silentAllowed.includes(name) && rms < minRms)});
  }
  return {id:'audio', status:!evidence.length ? 'unverified' :
    evidence.some(item => item.invalid) ? 'failed' : 'passed', evidence};
}

export async function bufferDigest(view) {
  const bytes = new Uint8Array(view.buffer, view.byteOffset, view.byteLength);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), value => value.toString(16).padStart(2, '0')).join('');
}

export async function checkDeterminism(generate, seed = 4207) {
  // generate(seed) must return an actual TypedArray; use actual assets, not seed bytes.
  const first = await bufferDigest(await generate(seed));
  const second = await bufferDigest(await generate(seed));
  return {id:'determinism', status:first === second ? 'passed' : 'failed',
    evidence:{seed, first, second}};
}
