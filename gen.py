from __future__ import annotations

import argparse
from datetime import datetime

from ids import generate_sbp_id, generate_op_number


def _parse_when(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc))


def main() -> None:
    parser = argparse.ArgumentParser(prog="gen")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    sbp_p = subparsers.add_parser("sbp", help="generate SBP ID")
    sbp_p.add_argument("--when", required=True, type=_parse_when)
    sbp_p.add_argument("--prefix", default="B")
    sbp_p.add_argument("--node", default="7310")
    sbp_p.add_argument("--route", default="K")
    sbp_p.add_argument("--code4", default="2001")
    sbp_p.add_argument("--tail7", default="1571101")

    opn_p = subparsers.add_parser("opn", help="generate operation number")
    opn_p.add_argument("--when", required=True, type=_parse_when)
    opn_p.add_argument("--pp", default="42")

    args = parser.parse_args()

    if args.cmd == "sbp":
        print(
            generate_sbp_id(
                args.when,
                prefix=args.prefix,
                node=args.node,
                route=args.route,
                code4=args.code4,
                tail7=args.tail7,
            )
        )
    else:
        print(generate_op_number(args.when, pp=args.pp))


if __name__ == "__main__":
    main()
