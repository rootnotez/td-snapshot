result = snapshot_patch()
out = me.parent().create(textDAT, 'td_snapshot_out')
out.text = result
out.openViewer(unique=True, borders=True)
