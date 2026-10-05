#!/bin/bash
# Launch a project-dedicated Blender GUI with the official MCP addon server on its own port
# (default 9878; anim uses 9877), so it never collides with another project's Blender on 9876.
PORT="${BLENDER_MCP_PORT:-9878}"
FILE="${1:-}"
EXPR="import bpy
def _start():
    from bl_ext.lab_blender_org.mcp import mcp_to_blender_server as s, execute_interactive as e
    try:
        s.start('localhost', $PORT)
        s.timer_internal_vars_calc(active=0.05, idle=1.0, idle_delay=5.0)
        bpy.app.timers.register(e.run, first_interval=0.1, persistent=True)
        print('MCP server on port $PORT')
    except Exception as ex:
        print('MCP start failed:', ex)
    return None
bpy.app.timers.register(_start, first_interval=2.0)"
LOG="${SCRATCH:-/tmp}/blender_$PORT.log"
nohup /Applications/Blender.app/Contents/MacOS/Blender --online-mode $FILE --python-expr "$EXPR" > "$LOG" 2>&1 &
echo "pid $! log $LOG"
