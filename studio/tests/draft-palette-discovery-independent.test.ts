import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import type { DraftCatalog } from '../src/authoring.ts';
import { draftPresets } from '../src/authoringPresets.ts';
import { draftPaletteCategories, draftPaletteCategoryLabel, draftPresetMatches, filterDraftModules } from '../src/draftPalette.ts';

const project = fileURLToPath(new URL('../../', import.meta.url));
const result = await promisify(execFile)(`${project}.venv/bin/python`, ['-I', '-S', '-B', '-c',
  'import sys,json;sys.path.insert(0,sys.argv[1]+"/src");from archcanvas_authoring import module_catalog;print(json.dumps(module_catalog()))', project]);
const catalog = JSON.parse(result.stdout) as DraftCatalog;
const kinds = (query: string, category = '') => filterDraftModules(catalog, query, category).map(module => module.kind);
const starters = (query: string) => draftPresets.filter(preset => draftPresetMatches(preset, catalog, query)).map(preset => preset.id);

test('category browser inventories every actual runtime module once, and never invents absent categories', () => {
  const inventory = draftPaletteCategories(catalog);
  assert.equal(inventory.reduce((count, category) => count + category.count, 0), 17);
  assert.equal(new Set(inventory.map(category => category.id)).size, 11);
  assert.deepEqual(inventory.filter(category => category.id === 'activation'), [{ id: 'activation', label: '激活函数', count: 3 }]);
  for (const category of inventory) {
    const expected = catalog.modules.filter(module => module.category === category.id);
    assert.equal(category.count, expected.length);
    assert.deepEqual(filterDraftModules(catalog, '', category.id), expected);
  }
  assert.deepEqual(draftPaletteCategories(null), []);
  assert.deepEqual(filterDraftModules(null, 'fc'), []);
  const reduced = structuredClone(catalog); reduced.modules = reduced.modules.filter(module => module.category !== 'pooling');
  assert.ok(!draftPaletteCategories(reduced).some(category => category.id === 'pooling'));
  const custom = structuredClone(catalog); custom.modules[0].category = 'external-category';
  assert.deepEqual(draftPaletteCategories(custom)[0], { id: 'external-category', label: 'external-category', count: 1 });
  assert.equal(draftPaletteCategoryLabel('external-category'), 'external-category');
});

test('novice aliases and common framework spelling resolve to the registered operator contract', () => {
  for (const [query, expected] of [
    ['ＦＣ', ['Linear']], ['fully connected', ['Linear']], ['nn.Linear', ['Linear']],
    ['Swish', ['SiLU']], ['BN', ['BatchNorm2d']], ['layer norm', ['LayerNorm']],
    ['词向量', ['Embedding']], ['max pool', ['MaxPool2d']], ['GAP', ['AdaptiveAvgPool2d']],
    ['skip connection', ['Add']], ['concatenate', ['Concat']], ['拉平', ['Flatten']],
  ] as const) assert.deepEqual(kinds(`  ${query}  `), expected, query);
  assert.deepEqual(kinds('激活函数'), ['ReLU', 'GELU', 'SiLU']);
  assert.deepEqual(kinds('normalization'), ['BatchNorm2d', 'LayerNorm']);
});

test('parameter search and multiword searches intersect the selected actual category', () => {
  assert.deepEqual(kinds('in_features'), ['Linear']);
  assert.deepEqual(kinds('kernel_size'), ['Conv2d', 'MaxPool2d']);
  assert.deepEqual(kinds('kernel_size', 'convolution'), ['Conv2d']);
  assert.deepEqual(kinds('kernel_size', 'pooling'), ['MaxPool2d']);
  assert.deepEqual(kinds('normalization eps'), ['BatchNorm2d', 'LayerNorm']);
  assert.deepEqual(kinds('normalization num_features'), ['BatchNorm2d']);
  assert.deepEqual(kinds('fc', 'activation'), []);
  assert.deepEqual(kinds('relu nonexistent'), []);
  assert.deepEqual(kinds('', 'invented-category'), []);
});

test('exact unsupported names cannot silently return a different operation or a starter that lacks it', () => {
  for (const name of ['Sigmoid', 'Tanh', 'Softmax', 'Conv1d', 'AvgPool2d', 'BatchNorm1d', 'Attention', 'MultiheadAttention', 'LSTM', 'GRU']) {
    assert.deepEqual(kinds(name), [], name);
    assert.deepEqual(kinds(`nn.${name}`), [], name);
    assert.deepEqual(starters(name), [], name);
  }
  const future = structuredClone(catalog); future.modules.push({ ...future.modules.find(module => module.kind === 'ReLU')!, kind: 'Tanh', label: 'Tanh' });
  assert.deepEqual(filterDraftModules(future, 'Tanh').map(module => module.kind), ['Tanh'], 'actual catalog support overrides historical absence');
});

test('transparent starters are searchable by their real editable components and declared I/O', () => {
  assert.deepEqual(starters('FC'), ['mlp', 'cnn', 'residual-mlp']);
  assert.deepEqual(starters('Conv2d'), ['cnn']);
  assert.deepEqual(starters('MaxPool2d'), ['cnn']);
  assert.deepEqual(starters('Add'), ['residual-mlp']);
  assert.deepEqual(starters('multilayer perceptron'), ['mlp']);
  assert.deepEqual(starters('图像分类'), ['cnn']);
  assert.deepEqual(starters('residual network'), ['residual-mlp']);
  assert.deepEqual(starters('Conv2d padding'), ['cnn']);
  assert.deepEqual(starters('32, 32'), ['cnn']);
  assert.deepEqual(starters('Embedding'), []);
  assert.ok(draftPresetMatches(draftPresets[1], null, 'Conv2d'), 'visible composition remains factual while catalog loads');
});

test('search and filtering preserve all catalog bytes and starter graph identities/parameters', () => {
  const before = JSON.stringify([catalog, draftPresets]);
  for (const query of ['', 'fc', 'padding', 'tanh', 'Conv2d', '输入', 'normalization eps', '残差']) {
    for (const category of ['', ...draftPaletteCategories(catalog).map(item => item.id)]) {
      const found = filterDraftModules(catalog, query, category);
      for (const module of found) assert.ok(catalog.modules.includes(module), 'results retain the active contract objects');
    }
    for (const preset of draftPresets) draftPresetMatches(preset, catalog, query);
  }
  assert.equal(JSON.stringify([catalog, draftPresets]), before);
});
