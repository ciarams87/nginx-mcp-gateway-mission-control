#!/bin/sh
set -eu
# Keep nginx as the normal daemon; supervisor handles demo-only config changes.
if [ ! -f /demo-control/original ]; then cp /etc/nginx/nginx.conf /demo-control/original; fi
nginx
trap 'nginx -s quit >/dev/null 2>&1 || true; exit 0' TERM INT
while :; do
  if [ -f /demo-control/request ]; then
    action=$(cat /demo-control/request 2>/dev/null || true)
    rm -f /demo-control/request
    if [ "$action" = "apply" ] && [ -f /demo-control/candidate ]; then
      cp /etc/nginx/nginx.conf /demo-control/previous
      if ! cat /demo-control/candidate > /etc/nginx/nginx.conf 2> /demo-control/test-log; then
        printf 'error: could not write nginx.conf (see details)\n' > /demo-control/status
        rm -f /demo-control/candidate
        continue
      fi
      if nginx -t > /demo-control/test-log 2>&1; then
        if nginx -s reload >> /demo-control/test-log 2>&1; then
          printf 'ok: configuration validated and reload requested\n' > /demo-control/status
        else
          cat /demo-control/previous > /etc/nginx/nginx.conf
          nginx -s reload >/dev/null 2>&1 || true
          printf 'error: reload failed; previous configuration restored (see validation details)\n' > /demo-control/status
        fi
      else
        cat /demo-control/previous > /etc/nginx/nginx.conf
        printf 'error: invalid configuration; previous configuration restored (see validation details)\n' > /demo-control/status
      fi
      rm -f /demo-control/candidate
    elif [ "$action" = "restore" ]; then
      if [ -f /demo-control/original ]; then
        cp /etc/nginx/nginx.conf /demo-control/previous
        cat /demo-control/original > /etc/nginx/nginx.conf
        if nginx -t > /demo-control/test-log 2>&1 && nginx -s reload >> /demo-control/test-log 2>&1; then
          printf 'ok: original configuration restored and reloaded\n' > /demo-control/status
        else
          cat /demo-control/previous > /etc/nginx/nginx.conf
          printf 'error: restore failed; previous configuration restored\n' > /demo-control/status
        fi
      else
        printf 'error: no original snapshot found\n' > /demo-control/status
      fi
    else
      printf 'error: invalid request\n' > /demo-control/status
    fi
  fi
  sleep 0.25
 done
