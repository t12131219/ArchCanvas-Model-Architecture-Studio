// A saved preview may still differ from its original source layout. Keep the
// saved-state indicator separate from that engine's "edited from original" flag.
type Identity = { id: string; sourceBindingDigest: string; architecture: { irDigest: string } };
type Store = Pick<Storage, 'getItem' | 'setItem'>;
const key = (document: Identity) => `archcanvas.preview-saved.v1:${document.id}`;
async function digest(graph: unknown) {
  const bytes = new TextEncoder().encode(JSON.stringify(graph));
  const result = await crypto.subtle.digest('SHA-256', bytes);
  return [...new Uint8Array(result)].map(value => value.toString(16).padStart(2, '0')).join('');
}
export async function rememberPreviewSave(store: Store, document: Identity, graph: unknown) {
  try { store.setItem(key(document), JSON.stringify({ source: document.sourceBindingDigest, ir: document.architecture.irDigest, graph: await digest(graph) })); }
  catch { /* The saved document and browser graph remain available without this optional UI marker. */ }
}
export async function matchesPreviewSave(store: Store, document: Identity, graph: unknown) {
  try { const marker = JSON.parse(store.getItem(key(document)) ?? 'null');
    return marker?.source === document.sourceBindingDigest && marker.ir === document.architecture.irDigest && marker.graph === await digest(graph);
  } catch { return false; }
}
