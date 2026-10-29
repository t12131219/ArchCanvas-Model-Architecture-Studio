import test from 'node:test';
import assert from 'node:assert/strict';
import { workspaceMenuPosition } from '../src/workspaceMenuPosition.ts';

test('bottom dock menus open above and stay inside a narrow viewport', () => {
  const result = workspaceMenuPosition({left:290,top:480,bottom:512}, {width:280,height:230}, {width:400,height:540}, true);
  assert.deepEqual(result, {left:112,top:242,width:280,maxHeight:464});
});
test('long header menus scroll within a short window', () => {
  const result = workspaceMenuPosition({left:180,top:18,bottom:50}, {width:280,height:700}, {width:600,height:300});
  assert.equal(result.top,58); assert.equal(result.maxHeight,234);
});
test('menus flip above a low anchor and clamp both horizontal edges', () => {
  const result = workspaceMenuPosition({left:-40,top:350,bottom:382}, {width:280,height:180}, {width:250,height:450});
  assert.deepEqual(result,{left:8,top:162,width:234,maxHeight:334});
});
