#!/usr/bin/env bash
exec python3 -c "import json,sys; open('/Users/noah/.claude/.busy','w').write(json.load(sys.stdin).get('tool_name','tool'))"
