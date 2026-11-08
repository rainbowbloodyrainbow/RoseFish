"""Prevent mixing old axle-origin firmware with new plate-center TF."""
from pathlib import Path
import json
r=Path(__file__).resolve().parent
stamp=r/'geometry-board-deployment.json'
if not stamp.exists():
    raise SystemExit('New measured geometry is prepared but matching D0WD firmware is not deployed. Do not combine plate-center laser TF with axle-origin odometry. See geometry-update.txt.')
d=json.loads(stamp.read_text())
if d.get('geometry_version')!='measured_plate_center_20261107' or d.get('verified_on_board')is not True:
    raise SystemExit('Board geometry version is not verified; see geometry-update.txt.')
