import datetime
result = snapshot_patch()
name = 'td_snapshot_' + datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
out = me.parent().create(textDAT, name)
out.text = result
out.openViewer(unique=True, borders=True)
