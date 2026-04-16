# Models

This directory is reserved for local copies of the trained model and metadata.

By default, the backend loads the artifacts stored in this directory.

`random_forest_lab_v2_metadata.json` now includes a portable runtime contract:

- the ordered input columns expected by the model;
- the runtime feature dtypes used to coerce live payloads;
- relative dataset paths for replay or offline summaries.

This means live inference no longer depends on the training parquet splits being
present locally, as long as the model and metadata stay together.
