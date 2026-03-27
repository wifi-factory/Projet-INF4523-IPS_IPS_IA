# Data

This directory is reserved for local copies or generated flow-level datasets.

By default, the backend reads the parquet artifacts from the absolute paths
provided in `random_forest_v1_metadata.json`, unless `IPS_TRAIN_PATH`,
`IPS_VALIDATION_PATH`, and `IPS_TEST_PATH` override them.
