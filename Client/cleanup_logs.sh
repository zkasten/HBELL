#!/bin/bash
#0 3 * * * /home/pi/cleanup_logs.sh
find /home/pi/log -name "*.log" -mtime +30 -delete
