// The service uses exactly the Studio's typed operations and undo reducer.
import { createDocument, createHistory, reduceHistory, validateDocument } from '../studio/src/core/index.ts';
import { draftPresets } from '../studio/src/authoringPresets.ts';

try {
  let text = '';
  for await (const chunk of process.stdin) text += chunk;
  const input = JSON.parse(text);
  let result;
  if (input.action === 'catalog') result = { presets: draftPresets.length };
  else if (input.action === 'create') result = createHistory(createDocument(input.architecture));
  else {
    const document = validateDocument(input.document);
    const history = input.history ?? createHistory(document);
    if (JSON.stringify(history.document) !== JSON.stringify(document) || !Array.isArray(history.past) || !Array.isArray(history.future) || history.past.length > 100 || history.future.length > 100) throw new Error('Invalid canvas history envelope');
    for (const snapshot of [history.document, ...history.past, ...history.future]) {
      validateDocument(snapshot);
      if (snapshot.id !== document.id || snapshot.sourceBindingDigest !== document.sourceBindingDigest || JSON.stringify(snapshot.architecture) !== JSON.stringify(document.architecture)) throw new Error('Canvas history source binding changed');
    }
    if (input.action === 'validate') result = history;
    else if (input.action === 'apply') result = reduceHistory(history, { type: 'apply', operations: input.operations, baseRevision: input.visualRevision });
    else if (['undo', 'redo'].includes(input.action)) result = reduceHistory(history, { type: input.action });
    else throw new Error('Unknown canvas operation');
  }
  process.stdout.write(JSON.stringify(result));
} catch (error) { process.stderr.write(error.message); process.exitCode = 2; }
