from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from archcanvas_cli.persistence import encode_envelope, decode_envelope, ARCHITECTURE_REF
from archcanvas_cli.server import DocumentStore
from tests.test_source_authoring_bridge import source_view

class CanvasPersistenceTests(unittest.TestCase):
    def test_history_shares_source_once_and_recovers_exact_snapshots(self):
        document = source_view('mlp')['document']
        history = {'document':deepcopy(document),'past':[deepcopy(document) for i in range(6)],'future':[]}
        for index,snapshot in enumerate(history['past']): snapshot['revision']=index
        value={'document':document,'history':history,'revision':1}
        original=deepcopy(value); compact=encode_envelope(value)
        self.assertEqual(value,original)
        self.assertLess(len(json.dumps(compact)),len(json.dumps(value))//2)
        self.assertEqual(decode_envelope(compact),value)
        with tempfile.TemporaryDirectory() as directory:
            store=DocumentStore(Path(directory))
            store.put(document['id'],document,0,history=history)
            actual=json.loads(store.path(document['id']).read_text())
            self.assertEqual(actual['history']['past'][0]['architecture'],ARCHITECTURE_REF)
            self.assertEqual(store.get(document['id'])['history'],history)
            poisoned=deepcopy(history); poisoned['past'][0]['architecture']['nodes'][0]['kind']='Forged'
            with self.assertRaisesRegex(ValueError,'source binding'): store.put(document['id'],document,1,history=poisoned)
            self.assertEqual(store.get(document['id'])['revision'],1)

    def test_invalid_or_foreign_architecture_is_not_replaced_with_a_valid_fact(self):
        document=source_view('mlp')['document']
        poisoned=deepcopy(document);poisoned['architecture']['irDigest']='foreign'
        value={'document':document,'history':{'document':document,'past':[poisoned],'future':[]}}
        compact=encode_envelope(value)
        self.assertEqual(compact['history']['past'][0]['architecture'],poisoned['architecture'])
        self.assertEqual(decode_envelope(compact),value)
        for bad in ([],{}, {'document':document,'history':{'past':3}}): decode_envelope(bad)
