import bpy
"""
	Transfer (& Remove) Track Fcurves to Action Extras
"""
def export_anim_tracks(action):
	num_exported = 0
	fc_tracks = [fc.data_path for fc in action.fcurves if fc.data_path.startswith('["T')]
	if len(fc_tracks) == 0:
		return
	action["trackKeys"] = []
	action["constTrackKeys"] = []
	for t_datapath in fc_tracks:
		track_index = int(t_datapath.split('"')[-2][1:])
		fc = action.fcurves.find(data_path=t_datapath)
		if len(fc.keyframe_points) > 0:
			kf_vals = [kp.co[1] for kp in fc.keyframe_points]
			tmin,tmax,tavg = [min(kf_vals),max(kf_vals),sum(kf_vals) / len(kf_vals)]
			if tavg == 0 or tmin == tmax:
				#constant
				action["constTrackKeys"].append({'trackIndex':track_index, 'value': tavg, 'time': 0.0 })
				num_exported += 1
			else:
				num_exported += len(fc.keyframe_points)
				for kp in fc.keyframe_points:
					action["trackKeys"].append({'trackIndex':track_index, 'value': kp.co[1], 'time': kp.co[0] / 30.0 })
				fc.keyframe_points.clear()
		action.fcurves.remove(fc)
	# remove custom group
	group_name = "Track Keys"
	g_idx = action.groups.find("Track Keys")
	if g_idx >= 0:
		a_group = action.groups[g_idx]
		action.groups.remove(a_group)
	print(f'{num_exported} Tracks Exported')
"""
	Creates FCurves for Anim Tracks & Corrects Timing Misalignment (Inbetween Frames due to quantization precison loss)
"""
def import_anim_tracks(action):
	track_keys = action.get("trackKeys", [])
	const_track_keys = action.get("constTrackKeys", [])
	track_list = []
	const_track_list = []
	ct_data = []
	t_data = []
	num_imported = 0
	if len(track_keys) > 0:
		t_data = [[t['trackIndex'],t['value'],t['time']] for t in [trk.to_dict() for trk in track_keys]]
		t_usage = sorted(list(set([t[0] for t in t_data])))
		track_list.extend(t_usage)

	if len(const_track_keys) > 0:
		ct_data = [[t['trackIndex'],t['value'],t['time']] for t in [ct.to_dict() for ct in const_track_keys]]
		const_track_list = sorted(list(set([t[0] for t in ct_data])))
		track_list.extend(const_track_list)

	if len(track_list) == 0:
		return
	all_tracks = sorted(list(set(track_list)))
	track_unsorted = {t:[] for t in all_tracks}
	track_sorted = {t:[] for t in all_tracks}
	track_props = ['T{:02d}'.format(track_idx) for track_idx in range(max(all_tracks))]
	# property name to valid datapath
	track_fcurves = ['["{}"]'.format(t) for t in track_props]
	# uncomment to create custom props on armature
	#for t_datapath in track_props:
	#	if t_datapath not in armature:
	#		armature[t_datapath] = 0.0
	#	rna = armature.id_properties_ui(t_datapath)
	#	rna.update(min=-2.0, max=2.0, soft_min=-2.0, soft_max = 2.0, precision=9, step=0.1, default=0.0, description=t_datapath)
	#
  # INIT FCURVES
	# group tracks - collapsible section in fcurve editor
	group_name = "Track Keys"
	g_idx = action.groups.find(group_name)
	if g_idx < 0:
		a_group = action.groups.new(group_name)
	else:
		a_group = action.groups[g_idx]
	# create fcurves (clear existing)
	for track_dp in track_fcurves:
		fc = action.fcurves.find(data_path=track_dp)
		if not fc is None:
			fc.keyframe_points.clear()
			action.fcurves.remove(fc)
		fc = action.fcurves.new(data_path=track_dp)
		fc.group = a_group
		fc.update()
	# sort const keys & eliminate samples (multiple values per track)
	for trk in const_track_list:
		t_datapath = '["T{:02d}"]'.format(trk)
		key_points = [t[1] for t in ct_data if t[0] == trk]
		tmin,tmax,tavg = [min(key_points),max(key_points),sum(key_points) / len(key_points)]
		const_val = tmin if tmin == tmax else key_points[-1]
		track_sorted[trk].append([0, const_val])
		num_imported += 1
	# 
	for trk in t_usage:
		t_datapath = '["T{:02d}"]'.format(trk)
		key_points = sorted([[t[2],t[1]] for t in t_data if t[0] == trk])
		track_unsorted[trk] = key_points
		frames_aligned = []
		frames_unaligned = []
		frames_vals = []
		for p in key_points:
			t, v = p
			frame_num = f = t * 30.0
			frames_unaligned.append(f)
			if (math.ceil(f)-f) < (f - math.floor(f)):
				frame_num = math.ceil(f)
			else:
				frame_num = math.floor(f)
			frames_aligned.append(frame_num)
		# fetch fcurve & clear
		fc = action.fcurves.find(data_path=t_datapath)
		fc.keyframe_points.clear()
		fc.update()
		# insert unaligned kf
		fc.keyframe_points.add(len(key_points))
		for i in range(len(key_points)):
			fc.keyframe_points[i].co = frames_unaligned[i], key_points[i][1]
		fc.update()
		# re-evaluate fcurve at aligned frames
		for t in range(len(key_points)):
			frm = frames_aligned[t]
			v = fc.evaluate(frm)
			frames_vals.append(v)
		#
		for t in range(len(key_points)):
			frm = frames_aligned[t]
			track_sorted[trk].append([frm, frames_vals[t]])
		# clear out temp
		fc.keyframe_points.clear()
		fc.update()
	#
	for trk in all_tracks:
		t_datapath = '["T{:02d}"]'.format(trk)
		num_keys = len(track_sorted[trk])
		if num_keys > 0:
			# fetch fcurve
			fc = action.fcurves.find(data_path=t_datapath)
			fc.keyframe_points.add(num_keys)
			num_imported += num_keys 
			for i in range(num_keys):
				fc.keyframe_points[i].co = track_sorted[trk][i][0], track_sorted[trk][i][1]
			fc.update()
	print(f'{num_imported} Tracks Imported')
