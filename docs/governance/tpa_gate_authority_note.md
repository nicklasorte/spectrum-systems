# TPA gate authority note

TPA gate authority for fix execution now requires verified `tpa_slice_artifact.authenticity` issuance (`issuer=TPA`) bound to payload and request context.

`artifacts/tpa_authority/<id>.json` and deterministic integrity tokens may still be emitted for audit/debug retrieve paths, but they are not authoritative for execution admission.
