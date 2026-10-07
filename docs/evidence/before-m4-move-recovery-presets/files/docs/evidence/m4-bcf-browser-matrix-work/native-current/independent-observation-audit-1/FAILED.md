This first independent audit attempt is preserved as a failed attempt. The two
existing validators and oracle controls executed with exit 0. The new audit
adapter then failed with KeyError `length` when reading raw-chunk-index.json;
the actual field is `actualTextareaLength`. No raw inputs were changed. A fresh
audit directory is used after the adapter correction; these partial outputs do
not constitute a completed audit.
