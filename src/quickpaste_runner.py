# quickpaste_runner.py v1.0.0 | sha256:483271940e07bb28d1b4f896443f8b6034e5edea57ed352887f31bce7e04eb91
import datetime
result = snapshot_patch()
name = 'td_snapshot_' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
out = me.parent().create(textDAT, name)
out.text = result
out.openViewer(unique=True, borders=True)
