#!/bin/bash
# Runs xcodebuild with the given arguments. If it fails, the compiler and test
# errors are posted as a GitHub annotation, because a job's logs can only be
# read when signed in, while annotations are public (even through the API).
log=$(mktemp)
xcodebuild "$@" >"$log" 2>&1
status=$?
if [ $status -eq 0 ]; then
  tail -n 5 "$log"
  exit 0
fi

errors=$(grep -E "error: |: error|Test Case .* failed|Testing failed|is unavailable" "$log" \
  | sed -E 's#^.*/ios/##' | awk '!seen[$0]++' | head -n 40)
[ -z "$errors" ] && errors=$(tail -n 40 "$log")
# Annotation messages are one line; %0A is how a workflow command encodes a newline.
message=$(printf '%s\n' "$errors" | sed 's/%/%25/g' | awk 'BEGIN { ORS = "%0A" } 1')
echo "::error title=xcodebuild failed (exit $status)::$message"
tail -n 120 "$log"
exit $status
