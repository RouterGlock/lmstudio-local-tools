#!/bin/bash
# Ensures the LM Studio local server (localhost:1234) is up.
# Called at login and periodically by com.lmstudio.server-autostart LaunchAgent.
/Users/ai/.lmstudio/bin/lms server start >/dev/null 2>&1
