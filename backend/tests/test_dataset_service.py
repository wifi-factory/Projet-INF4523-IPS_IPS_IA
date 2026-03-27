from __future__ import annotations


def test_dataset_summary_reads_parquet(services):
    summary = services.dataset_service.get_summary()

    assert summary.splits["train"].rows == 24796
    assert summary.splits["validation"].rows == 5313
    assert summary.splits["test"].rows == 5389
    assert summary.schema_comparison.schema_equal_train_validation is True
    assert summary.schema_comparison.schema_equal_train_test is True
