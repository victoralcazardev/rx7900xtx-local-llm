#!/bin/sh
cd "/home/victor/IA/Motores/Strata/terminal"
exec "/home/victor/IA/Motores/Strata/terminal/.venv/bin/python" "/home/victor/IA/Motores/Strata/terminal/serve/server.py" "--engine" "strata" "--config" "/home/victor/IA/Motores/Strata/terminal/strata-iq2_xs.json" "--port" "8080"
