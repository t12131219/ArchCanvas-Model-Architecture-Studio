import test from 'node:test';
import assert from 'node:assert/strict';
import { moduleSymbol } from '../src/moduleSymbols.ts';
test('symbol choices distinguish multiplication semantics and never infer tensor shape from labels',()=>{
 assert.equal(moduleSymbol({operator:'mult'}).symbol,'multiply');
 assert.equal(moduleSymbol({operator:'matmul'}).symbol,'matmul');
 assert.equal(moduleSymbol({operator:'normalization'}).symbol,'norm');
 assert.equal(moduleSymbol({operator:'activation'}).symbol,'activation');
 assert.equal(moduleSymbol({semantic_type:'hadamard-product'}).symbol,'hadamard');
 assert.equal(moduleSymbol({kind:'state'}).symbol,'variable');
 assert.equal(moduleSymbol({kind:'parameter',shape:[8,16]}).symbol,'matrix');
 assert.equal(moduleSymbol({kind:'parameter',shape:[8,16,32]}).symbol,'variable');
 assert.equal(moduleSymbol({kind:'opaque'}).symbol,'unknown');
});
