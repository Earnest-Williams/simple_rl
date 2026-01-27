#!/usr/bin/env bash
# Delegates to the canonical formatting & linting script.
exec "$(git rev-parse --show-toplevel)/tools/style/format_and_lint.sh" "${PWD}"
