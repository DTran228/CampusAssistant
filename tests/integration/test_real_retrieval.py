import os
import pytest


@pytest.mark.real_retrieval
@pytest.mark.skipif(os.getenv("CAMPUS_REAL_RETRIEVAL") != "1", reason="Explicit optional model download; separate from offline checks")
def test_real_mpnet_index_search():
    from eval.smoke_retrieval import run_smoke
    assert run_smoke()["status"] == "passed"
