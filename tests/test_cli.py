import pytest

from routereval.cli import build_parser, main


def test_defaults():
    args = build_parser().parse_args([])
    assert args.retries == 3 and args.timeout == 60.0


def test_baseline_only_needs_no_endpoint(monkeypatch, capsys):
    monkeypatch.delenv("FLOWISE_URL", raising=False)
    assert main(["--baseline-only"]) == 0
    assert "keyword baseline" in capsys.readouterr().out


def test_missing_url_is_a_usage_error(monkeypatch, capsys):
    monkeypatch.delenv("FLOWISE_URL", raising=False)
    assert main([]) == 2
    err = capsys.readouterr().err
    assert "FLOWISE_URL" in err
    assert "--baseline-only" in err


def test_in_scope_only_drops_the_out_of_scope_cases(capsys):
    main(["--baseline-only", "--in-scope-only"])
    first = capsys.readouterr().out.splitlines()[0]
    assert "/15" in first


def test_an_invalid_retry_count_is_rejected():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--retries", "many"])
