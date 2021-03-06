# get_cluster_window_matrix.py

import os
import numpy as np
import pickle
import sys
import bisect

def get_clust_to_filename(filename_to_clust):
	clusts = [clust for clust in filename_to_clust.values()]
	clust_to_filename = {k:[] for k in clusts}
	for frame, clust in filename_to_clust.iteritems():
		# if clust == -1: continue
		clust_to_filename[clust].append(frame)
	return clust_to_filename

def get_embed(frame_img):
	return np.load(frame_img[:-20]+'embeddings'+frame_img[-14:-4]+'.npy')

def get_centroid(clust):
	clust_points = np.array([get_embed(frame) for frame in clust])
	centroid = np.mean(clust_points, axis=0)
	return centroid

def get_error(win, filenames):
	win_embeds = np.array([get_embed(frame) for frame in win])
	clust_embeds = np.array([get_embed(filename) for filename in filenames])
	error_sum = 0
	count = 0
	for win_embed in win_embeds:
		win_error = float('inf')
		for clust_embed in clust_embeds:
			win_error = min(win_error, np.linalg.norm(win_embed-clust_embed))
		error_sum += win_error
		count += 1
	return error_sum/count

def compute_win_clust_mat(filename_to_clust, window_size=30):
	clust_to_filename = get_clust_to_filename(filename_to_clust)
	video_filenames = sorted([img for val in clust_to_filename.values() for img in val])
	wins = [video_filenames[i:i+window_size] for i in xrange(len(video_filenames)-window_size+1)]

	win_clust_vecs = []
	for clust in clust_to_filename.keys():
		if clust == -1: continue
		filenames = clust_to_filename[clust]
		centroid = get_centroid(filenames)
		errors = np.array([get_error(win, filenames) for win in wins])
		win_clust_vecs.append(errors)
	win_clust_mat = np.vstack(np.array(win_clust_vecs))
	return (win_clust_mat, wins)

def get_best_seqs(projid, window_size=30):
	# load clustered frames
	print 'loading clustered frames...'
	with open(os.path.join('temp', projid, 'filename_to_clust.pkl'), 'rb') as stream:
		filename_to_clust = pickle.load(stream)
	embs = []
	filenames = []
	labels = []
	for vid in filename_to_clust.keys():
		for filename, label in filename_to_clust[vid].iteritems():
			embs.append(get_embed(filename))
			filenames.append(filename)
			labels.append(label)
	np.savetxt('embs.tsv', embs, delimiter='\t')
	with open('metadata.tsv', 'w') as mfile:
		mfile.write('labels\tfilename\n')
		for i in range(len(filenames)):
			mfile.write('%d\t%s\n'%(labels[i], filenames[i]))

	# contruct matrix for every video
	video_names = [os.path.join('videos', projid, v+'.m4v') for v in filename_to_clust.keys()]
	for i in range(len(video_names)):
		if not os.path.isfile(video_names[i]):
			video_names[i] = video_names[i][:video_names[i].rindex('.')]+'.mp4' # assume only mp4s and m4vs
	print 'video names: ' + ' '.join(video_names)
	mat_wins = [compute_win_clust_mat(video_clustered_frames, window_size) for video_clustered_frames in filename_to_clust.values()]
	matrices = [mat_win[0] for mat_win in mat_wins]
	wins = [[(win[0], win[-1]) for win in mat_win[1]] for mat_win in mat_wins] # contructs tuples of start and end frames
	flattened_wins = [win for vid_wins in wins for win in vid_wins]

	index = 0
	indices = [0]
	for x in xrange(len(wins)):
		index += len(wins[x])
		indices.append(index)

	# concatenate matrices & find best sequences
	print 'finding best values in matrix...'
	num_clusts = np.max([len(m) for m in matrices])
	for x in xrange(len(matrices)):
		while len(matrices[x]) != num_clusts:
			matrices[x] = np.append(matrices[x], np.full((1, matrices[x].shape[1]), np.inf), axis=0)
		matrices[x] = matrices[x].T

	mat = np.concatenate(matrices, axis=0)
	argmins = np.argmin(mat, axis=0)

	vid_indices = [bisect.bisect(indices, argmin)-1 for argmin in argmins]

	best_seqs = [(video_names[vid_indices[x]], [int(k[-13:-4]) for k in flattened_wins[argmins[x]]], x) for x in xrange(len(vid_indices))]
	# print best_seqs

	# remove overlap
	vid_seq_dict = {k:[] for k in set([seq[0] for seq in best_seqs])}
	for seq in best_seqs: vid_seq_dict[seq[0]].append(seq[1])
	# print '\n'
	for vid in vid_seq_dict.keys():
		vid_seq_dict[vid].sort(key=lambda x: x[0])
	# print vid_seq_dict

	for vid in vid_seq_dict.keys():
		vid_seq_dict[vid]
		i = 0
		while i < len(vid_seq_dict[vid]):
			j = i+1
			while j < len(vid_seq_dict[vid]):
				if vid_seq_dict[vid][i][0] <= vid_seq_dict[vid][j][1] and vid_seq_dict[vid][j][0] <= vid_seq_dict[vid][i][1]: # segments overlap
					# set vid_seq_dict[vid][i] to merged interval
					# remove vid_seq_dict[vid][j]
					vid_seq_dict[vid][i] = [min(vid_seq_dict[vid][i][0], vid_seq_dict[vid][j][0]), max(vid_seq_dict[vid][i][1], vid_seq_dict[vid][j][1])]
					del vid_seq_dict[vid][j]
					j -= 1
				j += 1
			i += 1
		vid_seq_dict[vid].sort(key=lambda x: x[0])
	print vid_seq_dict
	return vid_seq_dict
	# return best_seqs

if __name__ == "__main__":
	projid = sys.argv[1]
        window_size = 5
	seqs = get_best_seqs(projid, window_size)
	# print seqs

