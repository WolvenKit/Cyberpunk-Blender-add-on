import bpy
from math import *
from collections import Counter
"""
	Transfer (& Remove) Track Fcurves to Action Extras
"""
def export_anim_tracks(action):
	obj = {"trackKeys": [], "constTrackKeys": []}
	num_exported = 0
	fc_tracks = [fc.data_path for fc in action.fcurves if fc.data_path.startswith('["T')]
	for t_datapath in fc_tracks:
		track_index = int(t_datapath.split('"')[-2][1:])
		fc = action.fcurves.find(data_path=t_datapath)
		if len(fc.keyframe_points) > 0:
			kf_vals = [kp.co[1] for kp in fc.keyframe_points]
			tmin,tmax,tavg = [min(kf_vals),max(kf_vals),sum(kf_vals) / len(kf_vals)]
			if tavg == 0 or tmin == tmax:
				#constant
				obj["constTrackKeys"].append({'trackIndex':track_index, 'value': tavg, 'time': 0.0 })
				num_exported += 1
			else:
				num_exported += len(fc.keyframe_points)
				for kp in fc.keyframe_points:
					obj["trackKeys"].append({'trackIndex':track_index, 'value': kp.co[1], 'time': kp.co[0] / 30.0 })
			fc.keyframe_points.clear()
			fc.update()
		action.fcurves.remove(fc)
	#
	action['trackKeys'] = obj["trackKeys"]
	action['constTrackKeys'] = obj["constTrackKeys"]
	action["optimizationHints"] = { "preferSIMD": False, "maxRotationCompression": 0}
	# remove custom group
	remove_track_action_group(action)
	print(f'{num_exported} Tracks Exported')

"""
	Create Custom Properties for Tracks on all Armatures
"""
def add_track_properties(track_properties=[]):
	armature_list = [obj for obj in bpy.data.objects if obj.type == 'ARMATURE']
	for armature in armature_list:
		for prop_name in track_properties:
			try:
				if prop_name not in armature:
					armature[prop_name] = 0.0
				rna = armature.id_properties_ui(prop_name)
				rna.update(property_type='FLOAT', is_overridable_library=True, description="", use_soft_limits=False, default_float=(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0), min_float=-3.40282e+38, max_float=3.40282e+38, soft_min_float=-3.40282e+38, soft_max_float=3.40282e+38, precision=8, step_float=0.01, subtype='NONE', eval_string="0.0")
			except Exception as e:
				print(f"Error creating custom track property ({prop_name}) on Armature [{armature.name}]: {e}")
"""
	Track Action Group Name
"""
def get_track_action_group_name():
	return "Track Keys"
"""
	Remove Custom Action Group for Tracks  - collapsible section in fcurve editor
"""
def remove_track_action_group(action):
	try:
		group_name = get_track_action_group_name()
		group_id = action.groups.find(group_name)
		if group_id >= 0:
			action_group = action.groups[group_id]
			action.groups.remove(action_group)
	except Exception as e:
		print(f"Error removing custom track action group: {e}")
"""
	Create Custom Action Group for Tracks  - collapsible section in fcurve editor
"""
def add_track_action_group(action):
	try:
		group_name = get_track_action_group_name()
		group_id = action.groups.find(group_name)
		if group_id < 0:
			action_group = action.groups.new(group_name)
			return action_group
		else:
			action_group = action.groups[group_id]
			return action_group
	except Exception as e:
		print(f"Error adding custom track action group: {e}")
"""
	Creates FCurves for Anim Tracks & Corrects Timing Misalignment (Inbetween Frames due to quantisation precison loss)
"""
def import_anim_tracks(action):
	track_keys = action.get("trackKeys", [])
	const_track_keys = action.get("constTrackKeys", [])
	track_list = []
	const_track_list = []
	ct_data = []
	t_data = []
	t_usage = []
	num_imported = 0
	if len(track_keys) > 0:
		t_data = [[t['trackIndex'],t['value'],t['time']] for t in [trk.to_dict() for trk in track_keys]]
		t_usage = sorted(list(set([t[0] for t in t_data])))
		track_list.extend(t_usage)
		#print("tracks")

	if len(const_track_keys) > 0:
		ct_data = [[t['trackIndex'],t['value'],t['time']] for t in [ct.to_dict() for ct in const_track_keys]]
		const_track_list = sorted(list(set([t[0] for t in ct_data])))
		track_list.extend(const_track_list)
		#print("consttracks")

	if len(track_list) == 0:
		#print("NoTracks")
		return
	#print('tracklist')
	#print(track_list)
	all_tracks = sorted(list(set(track_list)))
	#print('all tracks')
	#print(all_tracks)
	track_unsorted = {t:[] for t in all_tracks}
	track_sorted = {t:[] for t in all_tracks}
	track_props = ['T{:02d}'.format(t) for t in all_tracks]
	# property name to valid datapath
	track_fcurves = ['["{}"]'.format(t) for t in track_props]
	track_property_idx = {t:'T{:02d}'.format(t) for t in all_tracks}
	track_fcurve_idx = {t:'["T{:02d}"]'.format(t) for t in all_tracks}

	add_track_properties(track_props)
	# group tracks - collapsible section in fcurve editor
	action_group = add_track_action_group(action)

	"""
		create fcurves (clear existing)
	"""
	for track_dp in track_fcurve_idx.values():
		fc = action.fcurves.find(data_path=track_dp)
		if not fc is None:
			fc.keyframe_points.clear()
			action.fcurves.remove(fc)
		fc = action.fcurves.new(data_path=track_dp)
		fc.group = action_group
		fc.update()
	"""
		sort const keys & eliminate samples (multiple values per track)
	"""
	for trk in const_track_list:
		t_datapath = track_fcurve_idx[trk]
		key_points = [t[1] for t in ct_data if t[0] == trk]
		tmin,tmax,tavg = [min(key_points),max(key_points),sum(key_points) / len(key_points)]
		const_val = tmin if tmin == tmax else key_points[-1]
		track_sorted[trk].append([0, const_val])
		num_imported += 1
	#
	for trk in t_usage:
		t_datapath = track_fcurve_idx[trk]
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
		t_datapath = track_fcurve_idx[trk]
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

"""
	POSE BONES - Corrects Timing Misalignment (Inbetween Frames due to quantisation precison loss)
"""
def fix_anim_frame_alignment(action):
	#from collections import Counter
	fc_keys = dict(Counter([fc.data_path for fc in action.fcurves if fc.data_path.startswith('pose.bones[')]))
	#fc_cached_bones = {bn: {n:[] for n in ['location','rotation_quaternion','scale','rotation_axis_angle','rotation_euler']} for bn in fc_bones}
	for dp in fc_keys.keys():
		bn = dp.split('"')[-2]
		channel = dp.split('.')[-1]
		array_len = fc_keys[dp]
		sorted_fc = {}
		num_fixed = 0
		for i in range(array_len):
			fc = action.fcurves.find(data_path=dp, index=i)
			if not fc is None:
				if len(fc.keyframe_points) > 0:
					num_fixed = 0
					num_org_keys = len(fc.keyframe_points)
					frames_unaligned = [kp.co[0] for kp in fc.keyframe_points]
					frames_aligned = []
					frame_values = [kp.co[1] for kp in fc.keyframe_points]
					frame_values_aligned = []
					for f in frames_unaligned:
						frame_num = f
						if (ceil(f)-f) < (f - floor(f)):
							frame_num = ceil(f)
						else:
							frame_num = floor(f)
						if frame_num != f:
							num_fixed += 1
						frames_aligned.append(frame_num)
					frames_aligned = sorted(list(set(frames_aligned)))
					num_keys = len(frames_aligned)
					# re-evaluate fcurve at aligned frames
					for kfp in range(num_keys):
						frame_num = frames_aligned[kfp]
						frame_val = fc.evaluate(frame_num)
						frame_values_aligned.append(frame_val)
					# check for constants
					omin,omax,oavg = [min(frame_values),max(frame_values),sum(frame_values) / len(frame_values)]
					vmin,vmax,vavg = [min(frame_values_aligned),max(frame_values_aligned),sum(frame_values_aligned) / len(frame_values_aligned)]
					if omin == omax:
						print(f'{bn}-{channel}[{i}] constant org {omin} -> {num_keys} dupes')
						if vmin != vmax:
							print(f'org {omin} == {omax} but {vmin} != {vmax} Re-Aligned')
					if vmin == vmax:
						print(f'{bn}-{channel}[{i}] constant realiglned  {vmin} -> {num_keys} dupes')
						if omin != omax:
							print(f'org {omin} != {omax} but {vmin} == {vmax} Re-Aligned')
					if num_keys == 1:
						print(f'{bn}-{channel}[{i}] single const {frame_values_aligned[0]} org({frame_values[0]} @ frame {frames_aligned[0]} org({frames_unaligned[0]})')
					fc.keyframe_points.clear()
					fc.update()
					fc.keyframe_points.add(num_keys)
					for kfp in range(num_keys):
						fc.keyframe_points[kfp].co = frames_aligned[kfp], frame_values_aligned[kfp]
					fc.update()
			#
		if num_fixed > 0:
			print(f'{dp} Re-Aligned Timing for {num_fixed} Frames')
#
