#!/usr/bin/env bash
exec python3 -c "import json,os,sys; open(os.path.expanduser('~/.claude/.busy'),'w').write(json.load(sys.stdin).get('tool_name','tool'))"
