import assert from 'node:assert/strict';
import {auditGeometry, auditAudio, checkDeterminism} from './audit_resources.mjs';

// Synthetic unit-test data verifies failure detection; it is not game acceptance.
const attribute = values => ({count:values.length / 3,
  getX:i => values[i*3], getY:i => values[i*3+1], getZ:i => values[i*3+2]});
const geometry = {attributes:{
  position:attribute([0,0,0, 1,0,0, 0,1,0]),
  normal:attribute([0,0,1, 0,0,1, 0,0,1])}};
assert.equal(auditGeometry([geometry]).status, 'passed');
geometry.attributes.position = attribute([NaN,0,0, 1,0,0, 0,1,0]);
assert.equal(auditGeometry([geometry]).status, 'failed');

const sound = data => ({numberOfChannels:1, length:data.length, sampleRate:44100,
  duration:data.length / 44100, getChannelData:() => data});
assert.equal(auditAudio({ok:sound([0,.2,-.2,0])}).status, 'passed');
assert.equal(auditAudio({clipped:sound([0,1.4,0])}).status, 'failed');
assert.equal(auditAudio({silent:sound([0,0,0])}).status, 'failed');
assert.equal((await checkDeterminism(seed => new Float32Array([seed,1]))).status, 'passed');
let count = 0;
assert.equal((await checkDeterminism(() => new Float32Array([count++]))).status, 'failed');
console.log('7 resource audit assertions passed');
