# Copyright (c) 2026 inovex GmbH
#
# SPDX-License-Identifier: Apache-2.0


import twister_reader as tw
from conftest import FIXTURES

XML_PATH = FIXTURES / "twister" / "twister_report.xml"
TWISTER_JSON = FIXTURES / "twister" / "twister.json"
NEEDS_JSON = FIXTURES / "needs" / "needs.json"
HANDLER_LOG_BASE = FIXTURES / "twister"


# ---------------------------------------------------------------------------
# parse_twister_results
# ---------------------------------------------------------------------------


def test_parse_results_returns_list():
    results = tw.parse_twister_results(XML_PATH)
    assert isinstance(results, list)
    assert len(results) == 4


def test_parse_results_fields():
    results = tw.parse_twister_results(XML_PATH)
    r = results[0]
    for field in ("platform", "suite", "function", "status", "time"):
        assert field in r


def test_parse_results_module_filter_prefix():
    results = tw.parse_twister_results(XML_PATH, module_filter="kernel.queue")
    assert len(results) == 4


def test_parse_results_module_filter_exact():
    results = tw.parse_twister_results(XML_PATH, module_filter="kernel.queue", exact=True)
    assert len(results) == 2
    assert all(r["scenario"] == "kernel.queue" for r in results)


def test_parse_results_failed_status():
    results = tw.parse_twister_results(
        XML_PATH, module_filter="kernel.queue.minimallibc", exact=True
    )
    failed = [r for r in results if r["status"] == "failed"]
    assert len(failed) == 1
    assert "expected 1 got 0" in failed[0]["reason"]


def test_parse_results_skipped_status(tmp_path):
    xml = (
        '<?xml version="1.0"?>'
        "<testsuites>"
        '<testsuite name="plat">'
        '<testcase classname="kernel.test" name="kernel.test.kernel.test.test_skip" time="0">'
        '<skipped message="not supported"/>'
        "</testcase>"
        "</testsuite>"
        "</testsuites>"
    )
    p = tmp_path / "report.xml"
    p.write_text(xml)
    results = tw.parse_twister_results(p)
    assert results[0]["status"] == "skipped"


def test_parse_results_strips_test_prefix():
    results = tw.parse_twister_results(XML_PATH, module_filter="kernel.queue", exact=True)
    for r in results:
        assert not r["function"].startswith("test_")


# ---------------------------------------------------------------------------
# load_spec_lookup
# ---------------------------------------------------------------------------


def test_load_spec_lookup_keys_are_functions():
    lookup = tw.load_spec_lookup(NEEDS_JSON)
    assert "test_queue_put" in lookup
    assert "test_queue_get" in lookup


def test_load_spec_lookup_req_ids():
    lookup = tw.load_spec_lookup(NEEDS_JSON)
    assert lookup["test_queue_put"]["req_ids"] == ["zep-srs-20-1"]


def test_load_spec_lookup_suite_title():
    lookup = tw.load_spec_lookup(NEEDS_JSON)
    assert lookup["test_queue_put"]["suite_title"] == "Queue API Tests"


# ---------------------------------------------------------------------------
# find_handler_log
# ---------------------------------------------------------------------------


def test_find_handler_log_exact():
    result = tw.find_handler_log(
        HANDLER_LOG_BASE,
        "qemu_cortex_m3/ti_lm3s6965",
        "zephyr_gnu",
        "tests/kernel/queue",
        "kernel.queue",
    )
    assert result is not None
    assert result.name == "handler.log"
    assert result.exists()


def test_find_handler_log_stale_single_candidate(tmp_path):
    base = tmp_path / "qemu" / "zephyr_gnu" / "tests" / "queue"
    stale = base / "kernel.queue.old"
    stale.mkdir(parents=True)
    (stale / "handler.log").write_text("log data")

    result = tw.find_handler_log(tmp_path, "qemu", "zephyr_gnu", "tests/queue", "kernel.queue")
    assert result is not None
    assert result.exists()


def test_find_handler_log_stale_prefix_match(tmp_path):
    base = tmp_path / "qemu" / "gnu" / "tests" / "queue"
    for name in ["kernel.queue", "kernel.queue.minimallibc"]:
        d = base / name
        d.mkdir(parents=True)
        (d / "handler.log").write_text("log")

    result = tw.find_handler_log(tmp_path, "qemu", "gnu", "tests/queue", "kernel.queue")
    assert result is not None
    assert result.parent.name == "kernel.queue"


def test_find_handler_log_not_found(tmp_path):
    result = tw.find_handler_log(tmp_path, "noplatform", "notoolchain", "notests", "noscenario")
    assert result is None


def test_find_handler_log_keeps_only_after_last_pardir(tmp_path):
    """Twister keeps the part after the LAST `../`, so more than one is stripped."""
    d = tmp_path / "qemu" / "gnu" / "proj" / "tests" / "unit" / "kernel.queue"
    d.mkdir(parents=True)
    (d / "handler.log").write_text("log")

    result = tw.find_handler_log(tmp_path, "qemu", "gnu", "../../proj/tests/unit", "kernel.queue")
    assert result is not None
    assert result.parent.name == "kernel.queue"


def test_find_handler_log_detailed_test_id_layout(tmp_path):
    """`--detailed-test-id` omits the path segment; the name carries it instead."""
    d = tmp_path / "qemu" / "gnu" / "tests" / "queue" / "kernel.queue"
    d.mkdir(parents=True)
    (d / "handler.log").write_text("log")

    result = tw.find_handler_log(
        tmp_path, "qemu", "gnu", "../tests/queue", "tests/queue/kernel.queue"
    )
    assert result is not None
    assert result.parent.name == "kernel.queue"


def test_find_handler_log_pardir_does_not_shortcut_a_present_path(tmp_path):
    """A path with no `../` is unchanged — the control for the two tests above."""
    d = tmp_path / "qemu" / "gnu" / "tests" / "queue" / "kernel.queue"
    d.mkdir(parents=True)
    (d / "handler.log").write_text("log")

    assert tw.find_handler_log(tmp_path, "qemu", "gnu", "tests/queue", "kernel.queue") is not None
    # ...and a path that does NOT exist is still not found, so the new flat
    # fallback cannot mask a genuinely missing log.
    assert tw.find_handler_log(tmp_path, "qemu", "gnu", "tests/other", "kernel.queue") is None


# ---------------------------------------------------------------------------
# load_twister_meta
# ---------------------------------------------------------------------------


def test_load_twister_meta_environment_keys():
    data = tw.load_twister_meta(TWISTER_JSON)
    env = data["environment"]
    assert "run_date" in env
    assert "zephyr_version" in env
    assert "toolchain" in env


def test_load_twister_meta_testsuites_list():
    data = tw.load_twister_meta(TWISTER_JSON)
    assert isinstance(data["testsuites"], list)
    assert len(data["testsuites"]) > 0
