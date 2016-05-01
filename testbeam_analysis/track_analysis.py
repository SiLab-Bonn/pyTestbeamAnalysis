''' Track finding and fitting functions are listed here.'''
from __future__ import division

import logging
from multiprocessing import Pool, cpu_count
from math import sqrt
import os.path


import tables as tb
import numpy as np
from numba import njit
from matplotlib.backends.backend_pdf import PdfPages

from testbeam_analysis.tools import plot_utils
from testbeam_analysis.tools import analysis_utils
from testbeam_analysis.tools import geometry_utils


def find_tracks(input_tracklets_file, input_alignment_file, output_track_candidates_file, event_range=None, chunk_size=1000000):
    '''Takes first DUT track hit and tries to find matching hits in subsequent DUTs.
    The output is the same array with resorted hits into tracks. A track quality is set to
    be able to cut on good (less scattered) tracks.
    This function is uses numba to increase the speed on the inner loop (_find_tracks_loop()).

    This function can also be called on TrackCandidates arrays. That is usefull if an additional alignment step
    was done and the track finding has to be repeated.

    Parameters
    ----------
    input_tracklets_file : string
        Input file name with merged cluster hit table from all DUTs (tracklets file)
        Or track candidates file.
    input_alignment_file : string
        File containing the alignment information
    output_track_candidates_file : string
        Output file name for track candidate array
    '''
    logging.info('=== Find tracks ===')

    # Get alignment errors from file
    with tb.open_file(input_alignment_file, mode='r') as in_file_h5:
        try:
            raise tb.exceptions.NoSuchNodeError # FIXME: sigma is to small after alignment, track finding with tracks instead of correlation needed
            correlations = in_file_h5.root.Alignment[:]
            n_duts = correlations.shape[0]
            logging.info('Taking correlation cut values from alignment')
            column_sigma = correlations['correlation_x']
            row_sigma = correlations['correlation_y']
        except tb.exceptions.NoSuchNodeError:
            logging.info('Taking correlation cut values from prealignment')
            correlations = in_file_h5.root.PreAlignment[:]
            n_duts = correlations.shape[0]
            column_sigma = np.zeros(shape=n_duts)
            row_sigma = np.zeros(shape=n_duts)
            column_sigma[0], row_sigma[0] = 0., 0.  # DUT0 has no correlation error
            for index in range(1, n_duts):
                column_sigma[index] = correlations[index]['column_sigma']
                row_sigma[index] = correlations[index]['row_sigma']

    with tb.open_file(input_tracklets_file, mode='r') as in_file_h5:
        try:  # First try:  normal tracklets assumed
            tracklets_node = in_file_h5.root.Tracklets
        except tb.exceptions.NoSuchNodeError:
            try:  # Second try: normal track candidates assumed
                tracklets_node = in_file_h5.root.TrackCandidates
                output_track_candidates_file = os.path.splitext(output_track_candidates_file)[0] + '_2.h5'
                logging.info('Additional find track run on track candidates file %s', input_tracklets_file)
                logging.info('Output file with new track candidates file %s', output_track_candidates_file)
            except tb.exceptions.NoSuchNodeError:  # Last try: not used yet
                raise
        with tb.open_file(output_track_candidates_file, mode='w') as out_file_h5:
            track_candidates = out_file_h5.create_table(out_file_h5.root, name='TrackCandidates', description=tracklets_node.dtype, title='Track candidates', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))

            for tracklets_data_chunk, index in analysis_utils.data_aligned_at_events(tracklets_node, chunk_size=chunk_size):
                # Prepare hit data for track finding, create temporary arrays for x, y, z position and charge data
                # This is needed to call a numba jitted function, since the numer of DUTs is not fixed
                tr_x = tracklets_data_chunk['x_dut_0']
                tr_y = tracklets_data_chunk['y_dut_0']
                tr_z = tracklets_data_chunk['z_dut_0']
                tr_charge = tracklets_data_chunk['charge_dut_0']
                for dut_index in range(1, n_duts):
                    tr_x = np.vstack((tr_x, tracklets_data_chunk['x_dut_%d' % (dut_index)]))
                    tr_y = np.vstack((tr_y, tracklets_data_chunk['y_dut_%d' % (dut_index)]))
                    tr_z = np.vstack((tr_z, tracklets_data_chunk['z_dut_%d' % (dut_index)]))
                    tr_charge = np.vstack((tr_charge, tracklets_data_chunk['charge_dut_%d' % (dut_index)]))
                tr_x = np.transpose(tr_x)
                tr_y = np.transpose(tr_y)
                tr_z = np.transpose(tr_z)
                tr_charge = np.transpose(tr_charge)

                tracklets_data_chunk['track_quality'] = np.zeros(shape=tracklets_data_chunk.shape[0])  # If find tracks is called on already found tracks the track quality has to be reset

                # Perform the track finding with jitted loop
                tracklets_data_chunk, tr_x, tr_y, tr_z, tr_charge = _find_tracks_loop(tracklets_data_chunk, tr_x, tr_y, tr_z, tr_charge, column_sigma, row_sigma)

                # Merge result data from arrays into one recarray
                combined = np.column_stack((tracklets_data_chunk['event_number'], tr_x, tr_y, tr_z, tr_charge, tracklets_data_chunk['track_quality'], tracklets_data_chunk['n_tracks']))
                combined = np.core.records.fromarrays(combined.transpose(), dtype=tracklets_data_chunk.dtype)

                track_candidates.append(combined)


def fit_tracks(input_track_candidates_file, input_alignment_file, output_tracks_file, fit_duts=None, ignore_duts=None, include_duts=[-5, -4, -3, -2, -1, 1, 2, 3, 4, 5], track_quality=1, max_tracks=None, force_prealignment=False, output_pdf_file=None, use_correlated=False, chunk_size=1000000):
    '''Fits a line through selected DUT hits for selected DUTs. The selection criterion for the track candidates to fit is the track quality and the maximum number of hits per event.
    The fit is done for specified DUTs only (fit_duts). This DUT is then not included in the fit (include_duts). Bad DUTs can be always ignored in the fit (ignore_duts).

    Parameters
    ----------
    input_track_candidates_file : string
        file name with the track candidates table
    input_alignment_file : pytables file
        File name of the input aligment data
    output_tracks_file : string
        file name of the created track file having the track table
    fit_duts : iterable
        the duts to fit tracks for. If None all duts are used
    ignore_duts : iterable
        the duts that are not taken in a fit. Needed to exclude bad planes from track fit. Also included Duts are ignored!
    include_duts : iterable
        The relative dut positions of DUTs to use in the track fit. The position is relative to the actual dut the tracks are fitted for
        e.g. actual track fit dut = 2, include_duts = [-3, -2, -1, 1] means that duts 0, 1, 3 are used for the track fit
        If include_duts is None all available DUTs are used, besides the ignore_duts
    max_tracks : int, None
        only events with tracks <= max tracks are taken
    track_quality : int
        0: All tracks with hits in DUT and references are taken
        1: The track hits in DUT and reference are within 2-sigma of the correlation
        2: The track hits in DUT and reference are within 1-sigma of the correlation
        Track quality is saved for each DUT as boolean in binary representation. 8-bit integer for each 'quality stage', one digit per DUT.
        E.g. 0000 0101 assigns hits in DUT0 and DUT2 to the corresponding track quality.
    pixel_size : iterable, (x dimensions, y dimension)
        the size in um of the pixels, needed for chi2 calculation
    correlated_only : bool
        Use only events that are correlated. Can (at the moment) be applied only if function uses corrected Tracklets file
    '''

    logging.info('=== Fit tracks ===')

    use_prealignment = True if force_prealignment else False

    with tb.open_file(input_alignment_file, mode="r") as in_file_h5:  # Open file with alignment data
        z_positions = in_file_h5.root.PreAlignment[:]['z']
        if not use_prealignment:
            try:
                alignment = in_file_h5.root.Alignment[:]
                use_prealignment = False
            except tb.exceptions.NodeError:
                z_positions = in_file_h5.root.PreAlignment[:]['z']
                use_prealignment = True

    if use_prealignment:
        logging.info('Use prealignment data')
    else:
        logging.info('Use alignment data')

    def create_results_array(good_track_candidates, slopes, offsets, chi2s, n_duts):
        # Define description
        description = [('event_number', np.int64)]
        for index in range(n_duts):
            description.append(('x_dut_%d' % index, np.float))
        for index in range(n_duts):
            description.append(('y_dut_%d' % index, np.float))
        for index in range(n_duts):
            description.append(('z_dut_%d' % index, np.float))
        for index in range(n_duts):
            description.append(('charge_dut_%d' % index, np.float))
        for dimension in range(3):
            description.append(('offset_%d' % dimension, np.float))
        for dimension in range(3):
            description.append(('slope_%d' % dimension, np.float))
        description.extend([('track_chi2', np.uint32), ('track_quality', np.uint32), ('n_tracks', np.uint8)])

        # Define structure of track_array
        tracks_array = np.zeros((n_tracks,), dtype=description)
        tracks_array['event_number'] = good_track_candidates['event_number']
        tracks_array['track_quality'] = good_track_candidates['track_quality']
        tracks_array['n_tracks'] = good_track_candidates['n_tracks']
        for index in range(n_duts):
            tracks_array['x_dut_%d' % index] = good_track_candidates['x_dut_%d' % index]
            tracks_array['y_dut_%d' % index] = good_track_candidates['y_dut_%d' % index]
            tracks_array['z_dut_%d' % index] = good_track_candidates['z_dut_%d' % index]
            tracks_array['charge_dut_%d' % index] = good_track_candidates['charge_dut_%d' % index]
        for dimension in range(3):
            tracks_array['offset_%d' % dimension] = offsets[:, dimension]
            tracks_array['slope_%d' % dimension] = slopes[:, dimension]
        tracks_array['track_chi2'] = chi2s

        return tracks_array

    def store_track_data(fit_dut):  # Set the offset to the track intersection with the tilded plane and store the data
        if not use_prealignment:  # Deduce plane orientation in 3D for track extrapolation; not needed if rotation info is not available (e.g. only prealigned data)
            dut_position = np.array([alignment[fit_dut]['translation_x'], alignment[fit_dut]['translation_y'], alignment[fit_dut]['translation_z']])
            rotation_matrix = geometry_utils.rotation_matrix(alpha=alignment[fit_dut]['alpha'],
                                                             beta=alignment[fit_dut]['beta'],
                                                             gamma=alignment[fit_dut]['gamma'])
            basis_global = rotation_matrix.T.dot(np.eye(3))  # TODO: why transposed?
            dut_plane_normal = basis_global[2]
        else:  # Prealignment does not set any plane rotations thus plane normal = (0, 0, 1) and position = (0, 0, z)
            dut_position = np.array([0., 0., z_positions[fit_dut]])
            dut_plane_normal = np.array([0., 0., 1.])

        # Set the offset to the track intersection with the tilded plane
        actual_offsets = geometry_utils.get_line_intersections_with_plane(line_origins=offsets,
                                                                          line_directions=slopes,
                                                                          position_plane=dut_position,
                                                                          normal_plane=dut_plane_normal)

        tracks_array = create_results_array(good_track_candidates, slopes, actual_offsets, chi2s, n_duts)

        try:  # Check if table exists already, than append data
            tracklets_table = out_file_h5.get_node('/Tracks_DUT_%d' % fit_dut)
        except tb.NoSuchNodeError:  # Table does not exist, thus create new
            tracklets_table = out_file_h5.create_table(out_file_h5.root, name='Tracks_DUT_%d' % fit_dut, description=np.zeros((1,), dtype=tracks_array.dtype).dtype, title='Tracks fitted for DUT_%d' % fit_dut, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))

        tracklets_table.append(tracks_array)

        # Plot chi2 distribution
        plot_utils.plot_track_chi2(chi2s, fit_dut, output_fig)

    with PdfPages(output_tracks_file[:-3] + '.pdf') as output_fig:
        with tb.open_file(input_track_candidates_file, mode='r') as in_file_h5:
            try:  # If file exists already delete it first
                os.remove(output_tracks_file)
            except OSError:
                pass
            with tb.open_file(output_tracks_file, mode='a') as out_file_h5:  # Append mode to be able to append to existing tables; file is created here since old file is deleted
                n_duts = sum(['charge' in col for col in in_file_h5.root.TrackCandidates.dtype.names])
                fit_duts = fit_duts if fit_duts else range(n_duts)  # Std. setting: fit tracks for all DUTs
                if not include_duts:  # If include_dut is None use all DUTs in the  fit
                    all_duts = True
                else:
                    all_duts = False

                for fit_dut in fit_duts:  # Loop over the DUTs where tracks shall be fitted for
                    if not all_duts:
                        logging.info('Fit tracks for DUT %d', fit_dut)
                    else:  # Special case: use all DUTs in the fit, looping over fit_dut not needed
                        logging.info('Fit tracks for all DUTs, will lead to constrained residuals!')

                    for track_candidates_chunk, _ in analysis_utils.data_aligned_at_events(in_file_h5.root.TrackCandidates, chunk_size=chunk_size):

                        # Select track candidates
                        dut_selection = 0  # DUTs to be used in the fit
                        quality_mask = 0  # Masks DUTs to check track quality for
                        if not all_duts:
                            for include_dut in include_duts:  # Calculate relative mask to select DUT hits for fitting
                                if fit_dut + include_dut < 0 or ((ignore_duts and fit_dut + include_dut in ignore_duts) or fit_dut + include_dut >= n_duts):
                                    continue
                                if include_dut >= 0:
                                    dut_selection |= ((1 << fit_dut) << include_dut)
                                else:
                                    dut_selection |= ((1 << fit_dut) >> abs(include_dut))

                                quality_mask = dut_selection | (1 << fit_dut)  # Include the DUT where the track is fitted for in quality check
                        else:  # Special case, use all DUTs
                            for i in range(n_duts):
                                if ignore_duts and i in ignore_duts:
                                    continue
                                dut_selection |= (1 << i)
                                quality_mask |= (1 << i)

                        if bin(dut_selection).count("1") < 2:
                            logging.warning('Insufficient track hits to do fit (< 2). Omit DUT %d', fit_dut)
                            continue

                        logging.debug("Use %d DUTs in the fit", bin(dut_selection).count("1"))

                        # Select tracks based on given track_quality
                        good_track_selection = (track_candidates_chunk['track_quality'] & (dut_selection << (track_quality * 8))) == (dut_selection << (track_quality * 8))
                        if max_tracks:  # Option to neglect events with too many hits
                            good_track_selection = np.logical_and(good_track_selection, track_candidates_chunk['n_tracks'] <= max_tracks)

                        logging.info('Lost %d tracks candidates due to track quality cuts, %d percent ', good_track_selection.shape[0] - np.count_nonzero(good_track_selection), (1. - float(np.count_nonzero(good_track_selection) / float(good_track_selection.shape[0]))) * 100.)

                        if use_correlated:  # Reduce track selection to correlated DUTs only
                            good_track_selection &= (track_candidates_chunk['track_quality'] & (quality_mask << 24) == (quality_mask << 24))
                            logging.info('Lost due to correlated cuts %d', good_track_selection.shape[0] - np.sum(track_candidates_chunk['track_quality'] & (quality_mask << 24) == (quality_mask << 24)))

                        good_track_candidates = track_candidates_chunk[good_track_selection]

                        # Prepare track hits array to be fitted
                        n_fit_duts = bin(dut_selection).count("1")
                        index, n_tracks = 0, good_track_candidates['event_number'].shape[0]  # Index of tmp track hits array
                        track_hits = np.zeros((n_tracks, n_fit_duts, 3))
                        for dut_index in range(0, n_duts):  # Fill index loop of new array
                            if (1 << dut_index) & dut_selection == (1 << dut_index):  # True if DUT is used in fit
                                xyz = np.column_stack((good_track_candidates['x_dut_%s' % dut_index], good_track_candidates['y_dut_%s' % dut_index], good_track_candidates['z_dut_%s' % dut_index]))
                                track_hits[:, index, :] = xyz
                                index += 1

                        # Split data and fit on all available cores
                        n_slices = cpu_count()
                        slice_length = np.ceil(1. * n_tracks / n_slices).astype(np.int32)
                        slices = [track_hits[i:i + slice_length] for i in range(0, n_tracks, slice_length)]
                        pool = Pool(n_slices)
                        results = pool.map(_fit_tracks_loop, slices)
                        pool.close()
                        pool.join()
                        del track_hits

                        # Store results
                        offsets = np.concatenate([i[0] for i in results])  # Merge offsets from all cores in results
                        slopes = np.concatenate([i[1] for i in results])  # Merge slopes from all cores in results
                        chi2s = np.concatenate([i[2] for i in results])  # Merge chi2 from all cores in results

                        # Store the data
                        if not all_duts:  # Check if all DUTs were fitted at one
                            store_track_data(fit_dut)
                        else:
                            for fit_dut in range(n_duts):
                                store_track_data(fit_dut)
                    if all_duts:  # Stop fit Dut loop since all DUTs were fitted at once
                        break


# Helper functions that are not meant to be called during analysis
@njit
def _set_dut_track_quality(tr_column, tr_row, track_index, dut_index, actual_track, actual_track_column, actual_track_row, actual_column_sigma, actual_row_sigma):
    # Set track quality of actual DUT from actual DUT hit
    column, row = tr_column[track_index][dut_index], tr_row[track_index][dut_index]
    if row != 0:  # row = 0 is no hit
        actual_track['track_quality'] |= (1 << dut_index)  # Set track with hit
        column_distance, row_distance = abs(column - actual_track_column), abs(row - actual_track_row)
        if column_distance < 1 * actual_column_sigma and row_distance < 1 * actual_row_sigma:  # High quality track hits
            actual_track['track_quality'] |= (65793 << dut_index)
        elif column_distance < 2 * actual_column_sigma and row_distance < 2 * actual_row_sigma:  # Low quality track hits
            actual_track['track_quality'] |= (257 << dut_index)
    else:
        actual_track['track_quality'] &= (~(65793 << dut_index))  # Unset track quality


@njit
def _reset_dut_track_quality(tracklets, tr_column, tr_row, track_index, dut_index, hit_index, actual_column_sigma, actual_row_sigma):
    # Recalculate track quality of already assigned hit, needed if hits are swapped
    first_dut_index = _get_first_dut_index(tr_column, hit_index)

    actual_track_column, actual_track_row = tr_column[hit_index][first_dut_index], tr_row[hit_index][first_dut_index]
    actual_track = tracklets[hit_index]
    column, row = tr_column[hit_index][dut_index], tr_row[hit_index][dut_index]

    actual_track['track_quality'] &= ~(65793 << dut_index)  # Reset track quality to zero

    if row != 0:  # row = 0 is no hit
        actual_track['track_quality'] |= (1 << dut_index)  # Set track with hit
        column_distance, row_distance = abs(column - actual_track_column), abs(row - actual_track_row)
        if column_distance < 1 * actual_column_sigma and row_distance < 1 * actual_row_sigma:  # High quality track hits
            actual_track['track_quality'] |= (65793 << dut_index)
        elif column_distance < 2 * actual_column_sigma and row_distance < 2 * actual_row_sigma:  # Low quality track hits
            actual_track['track_quality'] |= (257 << dut_index)


@njit
def _get_first_dut_index(tr_column, index):
    ''' Returns the first DUT that has a hit for the track at index '''
    dut_index = 0
    for dut_index in range(tr_column.shape[1]):  # Loop over duts, to get first DUT hit of track
        if tr_column[index][dut_index] != 0:
            break
    return dut_index


@njit
def _swap_hits(tr_column, tr_row, tr_z, tr_charge, track_index, dut_index, hit_index, column, row, z, charge):
    #     print 'Swap hits', tr_column[track_index][dut_index], tr_column[hit_index][dut_index]
    tmp_column, tmp_row, tmp_z, tmp_charge = tr_column[track_index][dut_index], tr_row[track_index][dut_index], tr_z[track_index][dut_index], tr_charge[track_index][dut_index]
    tr_column[track_index][dut_index], tr_row[track_index][dut_index], tr_z[track_index][dut_index], tr_charge[track_index][dut_index] = column, row, z, charge
    tr_column[hit_index][dut_index], tr_row[hit_index][dut_index], tr_z[hit_index][dut_index], tr_charge[hit_index][dut_index] = tmp_column, tmp_row, tmp_z, tmp_charge


@njit
def _find_tracks_loop(tracklets, tr_column, tr_row, tr_z, tr_charge, column_sigma, row_sigma):
    ''' Complex loop to resort the tracklets array inplace to form track candidates. Each track candidate
    is given a quality identifier. Each hit is put to the best fitting track. Tracks are assued to have
    no big angle, otherwise this approach does not work.
    Optimizations included to make it compile with numba. Can be called from
    several real threads if they work on different areas of the array'''
    n_duts = tr_column.shape[1]
    actual_event_number = tracklets[0]['event_number']

    # Numba uses c scopes, thus define all used variables here
    n_actual_tracks = 0
    track_index, actual_hit_track_index = 0, 0  # Track index of table and first track index of actual event
    column, row = 0., 0.
    actual_track_column, actual_track_row = 0., 0.
    column_distance, row_distance = 0., 0.
    hit_distance = 0.

    for track_index, actual_track in enumerate(tracklets):  # Loop over all possible tracks
        #         print '== ACTUAL TRACK  ==', track_index
        # Set variables for new event
        if actual_track['event_number'] != actual_event_number:  # Detect new event
            actual_event_number = actual_track['event_number']
            for i in range(n_actual_tracks):  # Set number of tracks of previous event
                tracklets[track_index - 1 - i]['n_tracks'] = n_actual_tracks
            n_actual_tracks = 0
            actual_hit_track_index = track_index

        n_actual_tracks += 1
        reference_hit_set = False  # The first real hit (column, row != 0) is the reference hit of the actual track
        n_track_hits = 0

        for dut_index in range(n_duts):  # loop over all DUTs in the actual track
            actual_column_sigma, actual_row_sigma = column_sigma[dut_index], row_sigma[dut_index]

            # Calculate the hit distance of the actual assigned DUT hit towards the actual reference hit
            current_column_distance, current_row_distance = abs(tr_column[track_index][dut_index] - actual_track_column), abs(tr_row[track_index][dut_index] - actual_track_row)
            current_hit_distance = sqrt(current_column_distance * current_column_distance + current_row_distance * current_row_distance)  # The hit distance of the actual assigned hit
            if tr_column[track_index][dut_index] == 0:  # No hit at the actual position
                current_hit_distance = -1  # Signal no hit

#             print '== ACTUAL DUT  ==', dut_index

            if not reference_hit_set and tr_row[track_index][dut_index] != 0:  # Search for first DUT that registered a hit (row != 0)
                actual_track_column, actual_track_row = tr_column[track_index][dut_index], tr_row[track_index][dut_index]
                reference_hit_set = True
                tracklets[track_index]['track_quality'] |= (65793 << dut_index)  # First track hit has best quality by definition
                n_track_hits += 1
#                 print 'ACTUAL REFERENCE HIT', actual_track_column, actual_track_row
            elif reference_hit_set:  # First hit found, now find best (closest) DUT hit
                shortest_hit_distance = -1  # The shortest hit distance to the actual hit; -1 means not assigned
                for hit_index in range(actual_hit_track_index, tracklets.shape[0]):  # Loop over all not sorted hits of actual DUT
                    if tracklets[hit_index]['event_number'] != actual_event_number:  # Abort condition
                        break
                    column, row, z, charge = tr_column[hit_index][dut_index], tr_row[hit_index][dut_index], tr_z[hit_index][dut_index], tr_charge[hit_index][dut_index]
                    if row != 0:  # Check for hit (row != 0)
                        # Calculate the hit distance of the actual DUT hit towards the actual reference hit
                        column_distance, row_distance = abs(column - actual_track_column), abs(row - actual_track_row)
                        hit_distance = sqrt(column_distance * column_distance + row_distance * row_distance)
                        if shortest_hit_distance < 0 or hit_distance < shortest_hit_distance:  # Check if the hit is closer to reference hit
                            #                             print 'FOUND MATCHING HIT', column, row
                            if track_index != hit_index:  # Check if hit swapping is needed
                                if track_index > hit_index:  # Check if hit is already assigned to other track
                                    #                                     print 'BUT HIT ALREADY ASSIGNED TO TRACK', hit_index
                                    first_dut_index = _get_first_dut_index(tr_column, hit_index)  # Get reference DUT index of other track
                                    # Calculate hit distance to reference hit of other track
                                    column_distance_old, row_distance_old = abs(column - tr_column[hit_index][first_dut_index]), abs(row - tr_row[hit_index][first_dut_index])
                                    hit_distance_old = sqrt(column_distance_old * column_distance_old + row_distance_old * row_distance_old)
                                    if current_hit_distance > 0 and current_hit_distance < hit_distance:  # Check if actual assigned hit is better
                                        #                                         print 'CURRENT ASSIGNED HIT FITS BETTER, DO NOT SWAP', hit_index
                                        continue
                                    if hit_distance > hit_distance_old:  # Only take hit if it fits better to actual track; otherwise leave it with other track
                                        #                                         print 'IT FIT BETTER WITH OLD TRACK, DO NOT SWAP', hit_index
                                        continue
#                                 print 'SWAP HIT'
                                _swap_hits(tr_column, tr_row, tr_z, tr_charge, track_index, dut_index, hit_index, column, row, z, charge)
                                if track_index > hit_index:  # Check if hit is already assigned to other track
                                    #                                     print 'RESET DUT TRACK QUALITY'
                                    _reset_dut_track_quality(tracklets, tr_column, tr_row, track_index, dut_index, hit_index, actual_column_sigma, actual_row_sigma)
                            shortest_hit_distance = hit_distance
                            n_track_hits += 1

# if reference_dut_index == n_duts - 1:  # Special case: If there is only one hit in the last DUT, check if this hit fits better to any other track of this event
#                 pass
#             print 'SET DUT TRACK QUALITY'
            _set_dut_track_quality(tr_column, tr_row, track_index, dut_index, actual_track, actual_track_column, actual_track_row, actual_column_sigma, actual_row_sigma)

#         print 'TRACK', track_index
#         for dut_index in range(n_duts):
#             print tr_row[track_index][dut_index],
#         print
        # Set number of tracks of last event
        for i in range(n_actual_tracks):
            tracklets[track_index - i]['n_tracks'] = n_actual_tracks

    return tracklets, tr_column, tr_row, tr_z, tr_charge


def _fit_tracks_loop(track_hits):
    ''' Do 3d line fit and calculate chi2 for each fit. '''
    def line_fit_3d(hits):
        datamean = hits.mean(axis=0)
        offset, slope = datamean, np.linalg.svd(hits - datamean)[2][0]  # http://stackoverflow.com/questions/2298390/fitting-a-line-in-3d
        intersections = offset + slope / slope[2] * (hits.T[2][:, np.newaxis] - offset[2])  # Fitted line and DUT plane intersections (here: points)
        chi2 = np.sum(np.square(hits - intersections), dtype=np.uint32)  # Chi2 of the fit in um
        return datamean, slope, chi2

    slope = np.zeros((track_hits.shape[0], 3,))
    offset = np.zeros((track_hits.shape[0], 3,))
    chi2 = np.zeros((track_hits.shape[0],))

    for index, actual_hits in enumerate(track_hits):  # Loop over selected track candidate hits and fit
        try:
            offset[index], slope[index], chi2[index] = line_fit_3d(actual_hits)
        except np.linalg.linalg.LinAlgError:
            chi2[index] = 1e9

    return offset, slope, chi2


def _function_wrapper_find_tracks_loop(args):  # Needed for multiprocessing call with arguments
    return _find_tracks_loop(*args)



