"""Run the routing evaluation against a deployed flow, or offline."""

from __future__ import annotations

import argparse
import sys

from routereval import baseline
from routereval.cases import CASES, IN_SCOPE
from routereval.client import AuthError, FlowiseClient
from routereval.evaluate import compare, evaluate_client, evaluate_function


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="routereval",
        description=(
            "Measure whether a Flowise router sends each question to the right branch."
        ),
    )
    parser.add_argument("--url", help="prediction endpoint (default: $FLOWISE_URL)")
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="score the keyword router only; needs no endpoint and no credential",
    )
    parser.add_argument(
        "--in-scope-only",
        action="store_true",
        help="drop the out-of-scope cases, which most flows have no branch for",
    )
    parser.add_argument(
        "--session",
        help="session id sent with every call, so cases cannot contaminate each other",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--retries", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cases = IN_SCOPE if args.in_scope_only else CASES

    reports = [evaluate_function(baseline.route, cases, name="keyword baseline")]

    if not args.baseline_only:
        try:
            client = FlowiseClient.from_env(
                url=args.url,
                timeout=args.timeout,
                retries=args.retries,
                session_id=args.session,
            )
        except AuthError as exc:
            print(str(exc), file=sys.stderr)
            print(
                "(run with --baseline-only to score the keyword router alone)",
                file=sys.stderr,
            )
            return 2
        reports.append(evaluate_client(client, cases, name="flowise router"))

    print(compare(reports))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
