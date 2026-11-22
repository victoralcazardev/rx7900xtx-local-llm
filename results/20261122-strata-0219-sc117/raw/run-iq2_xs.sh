#!/bin/sh
cd "~/IA/Motores/Strata/terminal"
exec "~/IA/Motores/Strata/terminal/.venv/bin/python" "~/IA/Motores/Strata/terminal/serve/server.py" "--engine" "strata" "--config" "~/IA/Motores/Strata/terminal/strata-iq2_xs.json" "--port" "8080"
