This second independent audit attempt is preserved as a failed adapter attempt.
Existing validators/controls, chunk reassembly and bilateral event matching
completed. The new direct XML adapter incorrectly expected a canonical node to
carry `callCount`, although that source-fact field aggregates call sites by
instance. It failed at the first such comparison. The corrected adapter derives
the count from independently saved canonical nodes with the same instanceId.
Raw captures are preserved. These partial outputs are not a completed audit.
