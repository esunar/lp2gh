#!/bin/bash

curl -vvv \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H 'Authorization: Bearer ${GITHUB_TOKEN}' \
  https://api.github.com/repos/canonical/juju-verify/milestones \
  -d '{"title":"v1.0","state":"open","description":"Tracking milestone for version 1.0","due_on":"2012-10-09T23:39:01Z"}'