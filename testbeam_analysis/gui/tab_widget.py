''' Defines all analysis tabs

    Each tab is for one analysis function and has function
    gui options and plotting outputs
'''

from subprocess import call
from PyQt5 import QtCore, QtWidgets, QtGui
from testbeam_analysis.gui.analysis_widgets import AnalysisWidget, ParallelAnalysisWidget
from testbeam_analysis.hit_analysis import generate_pixel_mask, cluster_hits
from testbeam_analysis.dut_alignment import correlate_cluster, prealignment, merge_cluster_data, apply_alignment, alignment
from testbeam_analysis.track_analysis import find_tracks, fit_tracks
from testbeam_analysis.result_analysis import calculate_efficiency, calculate_residuals

# Plot related import
from testbeam_analysis.tools import plot_utils


class NoisyPixelsTab(ParallelAnalysisWidget):
    """ Implements the noisy pixel analysis gui"""

    proceedAnalysis = QtCore.pyqtSignal(list)

    def __init__(self, parent, setup, options, tab_list):
        super(NoisyPixelsTab, self).__init__(parent, setup, options, tab_list)

        self.output_mask_file = [options['output_path'] + '/' + dut + options['noisy_suffix']
                                 for dut in setup['dut_names']]

        self.add_parallel_function(func=generate_pixel_mask)

        self.add_parallel_option(option='input_hits_file',
                                 default_value=options['input_files'],
                                 func=generate_pixel_mask,
                                 fixed=True)
        self.add_parallel_option(option='output_mask_file',
                                 default_value=self.output_mask_file,
                                 func=generate_pixel_mask,
                                 fixed=True)
        self.add_parallel_option(option='n_pixel',
                                 default_value=setup['n_pixels'],
                                 func=generate_pixel_mask,
                                 fixed=True)
        self.add_parallel_option(option='dut_name',
                                 default_value=setup['dut_names'],
                                 func=generate_pixel_mask,
                                 fixed=False)

        self.parallelAnalysisDone.connect(lambda _tab_list: self.proceedAnalysis.emit(_tab_list))
        self.parallelAnalysisDone.connect(lambda: self._connect_vitables(files=self.output_mask_file))
        self.parallelAnalysisDone.connect(lambda: self.parallel_plot(input_files=self.output_mask_file,
                                                                     plot_func=plot_utils.plot_masked_pixels,
                                                                     dut_names=setup['dut_names'],
                                                                     gui=True))


class ClusterPixelsTab(ParallelAnalysisWidget):
    ''' Implements the pixel clustering gui'''

    proceedAnalysis = QtCore.pyqtSignal(list)

    def __init__(self, parent, setup, options, tab_list):
        super(ClusterPixelsTab, self).__init__(parent, setup, options, tab_list)

        self.output_cluster_file = [options['output_path'] + '/' + dut + options['cluster_suffix']
                                    for dut in setup['dut_names']]

        self.add_parallel_function(func=cluster_hits)

        self.add_parallel_option(option='input_hits_file',
                                 default_value=options['input_files'],
                                 func=cluster_hits,
                                 fixed=True)

        self.add_parallel_option(option='input_noisy_pixel_mask_file',
                                 default_value=[options['output_path'] + '/' + dut + options['noisy_suffix'] for dut in setup['dut_names']],
                                 func=cluster_hits,
                                 fixed=True)

        self.add_parallel_option(option='output_cluster_file',
                                 default_value=[options['output_path'] + '/' + dut + options['cluster_suffix'] for dut in setup['dut_names']],
                                 func=cluster_hits,
                                 fixed=True)

        self.add_parallel_option(option='dut_name',
                                 default_value=setup['dut_names'],
                                 func=cluster_hits,
                                 fixed=False)

        self.parallelAnalysisDone.connect(lambda _tab_list: self.proceedAnalysis.emit(_tab_list))
        self.parallelAnalysisDone.connect(lambda: self._connect_vitables(files=self.output_cluster_file))
        self.parallelAnalysisDone.connect(lambda: self.parallel_plot(input_files=self.output_cluster_file,
                                                                     plot_func=plot_utils.plot_cluster_size,
                                                                     dut_names=setup['dut_names'],
                                                                     gui=True))


class PrealignmentTab(AnalysisWidget):
    ''' Implements the prealignment gui. Prealignment uses
        4 functions of test beam analysis:
        - correlate cluster
        - fit correlations (prealignment)
        - merge cluster data of duts
        - apply prealignment
    '''

    proceedAnalysis = QtCore.pyqtSignal(list)

    def __init__(self, parent, setup, options, tab_list):
        super(PrealignmentTab, self).__init__(parent, setup, options, tab_list)

        self.add_function(func=correlate_cluster)
        self.add_function(func=prealignment)
        self.add_function(func=merge_cluster_data)
        self.add_function(func=apply_alignment)

        self.add_option(option='input_cluster_files',
                        default_value=[options['output_path'] + '/' + dut + options['cluster_suffix'] for dut in setup['dut_names']],
                        func=correlate_cluster,
                        fixed=True)

        self.add_option(option='output_correlation_file',
                        default_value=options['output_path'] + '/Correlation.h5',
                        func=correlate_cluster,
                        fixed=True)

        self.add_option(option='input_correlation_file',
                        default_value=options['output_path'] + '/Correlation.h5',
                        func=prealignment,
                        fixed=True)

        self.add_option(option='output_alignment_file',
                        default_value=options['output_path'] + '/Alignment.h5',
                        func=prealignment,
                        fixed=True)

        self.add_option(option='input_cluster_files',
                        default_value=[options['output_path'] + '/' + dut + options['cluster_suffix'] for dut in setup['dut_names']],
                        func=merge_cluster_data,
                        fixed=True)

        self.add_option(option='output_merged_file',
                        default_value=options['output_path'] + '/Merged.h5',
                        func=merge_cluster_data,
                        fixed=True)

        self.add_option(option='input_hit_file',
                        default_value=options['output_path'] + '/Merged.h5',
                        func=apply_alignment,
                        fixed=True)

        self.add_option(option='input_alignment_file',
                        default_value=options['output_path'] + '/Alignment.h5',
                        func=apply_alignment,
                        fixed=True)

        self.add_option(option='output_hit_file',
                        default_value=options['output_path'] + '/Tracklets_prealigned.h5',
                        func=apply_alignment,
                        fixed=True)

        self.output_files = [options['output_path'] + '/Correlation.h5',
                             options['output_path'] + '/Alignment.h5',
                             options['output_path'] + '/Merged.h5',
                             options['output_path'] + '/Tracklets_prealigned.h5']

        # Fix options that should not be changed
        self.add_option(option='use_duts', func=apply_alignment,
                        default_value=[1] * setup['n_duts'], fixed=True)
        self.add_option(option='inverse', func=apply_alignment, fixed=True)
        self.add_option(option='force_prealignment', func=apply_alignment,
                        default_value=True, fixed=True)
        self.add_option(option='no_z', func=apply_alignment, fixed=True)

        self.analysisDone.connect(lambda _tab_list: self.proceedAnalysis.emit(_tab_list))
        self.analysisDone.connect(lambda: self._connect_vitables(files=self.output_files))
        self.analysisDone.connect(lambda: self.plot(input_file=self.output_files[0],
                                                    plot_func=plot_utils.plot_correlations,
                                                    dut_names=setup['dut_names'],
                                                    gui=True))


class TrackFindingTab(AnalysisWidget):
    ''' Implements the track finding gui'''

    proceedAnalysis = QtCore.pyqtSignal(list)

    def __init__(self, parent, setup, options, tab_list):
        super(TrackFindingTab, self).__init__(parent, setup, options, tab_list)

        self.add_function(func=find_tracks)

        self.add_option(option='input_tracklets_file',
                        default_value=options['output_path'] + '/Tracklets_prealigned.h5',
                        func=find_tracks,
                        fixed=True)

        self.add_option(option='input_alignment_file',
                        default_value=options['output_path'] + '/Alignment.h5',
                        func=find_tracks,
                        fixed=True)

        self.add_option(option='output_track_candidates_file',
                        default_value=options['output_path'] + '/TrackCandidates_prealignment.h5',
                        func=find_tracks,
                        fixed=True)

        self.output_files = [options['output_path'] + '/TrackCandidates_prealignment.h5']

        self.analysisDone.connect(lambda _tab_list: self.proceedAnalysis.emit(_tab_list))
        self.analysisDone.connect(lambda: self._connect_vitables(files=self.output_files))


class AlignmentTab(AnalysisWidget):
    ''' Implements the alignment gui'''

    proceedAnalysis = QtCore.pyqtSignal(list)
    skipAlignment = QtCore.pyqtSignal()

    def __init__(self, parent, setup, options, tab_list):
        super(AlignmentTab, self).__init__(parent, setup, options, tab_list)

        if isinstance(tab_list, list):
            self.tl = tab_list
        else:
            self.tl = [tab_list]

        self.add_function(func=alignment)
        self.add_function(func=apply_alignment)

        self.add_option(option='input_track_candidates_file',
                        default_value=options['output_path'] + '/TrackCandidates_prealignment.h5',
                        func=alignment,
                        fixed=True)

        self.add_option(option='input_alignment_file',
                        default_value=options['output_path'] + '/Alignment.h5',
                        func=alignment,
                        fixed=True)

        self.add_option(option='initial_translation',
                        default_value=False,
                        func=alignment,
                        fixed=True)

        self.add_option(option='initial_rotation',
                        default_value=setup['rotations'],
                        func=alignment,
                        fixed=True)

        self.add_option(option='input_hit_file',
                        default_value=options['output_path'] + '/Merged.h5',
                        func=apply_alignment,
                        fixed=True)

        self.add_option(option='input_alignment_file',
                        default_value=options['output_path'] + '/Alignment.h5',
                        func=apply_alignment,
                        fixed=True)

        self.add_option(option='output_hit_file',
                        default_value=options['output_path'] + '/Tracklets.h5',
                        func=apply_alignment,
                        fixed=True)

        self.output_files = [options['output_path'] + '/Tracklets.h5']

        self.analysisDone.connect(lambda _tab_list: self.proceedAnalysis.emit(_tab_list))
        self.analysisDone.connect(lambda: self._connect_vitables(files=self.output_files))
        self.analysisDone.connect(lambda: self.btn_skip.deleteLater())

        self.btn_skip = QtWidgets.QPushButton('Skip')
        self.btn_skip.setToolTip('Skip alignment and use pre-alignment for further analysis')
        self.btn_skip.clicked.connect(lambda: self._skip_alignment())
        self.layout_options.addWidget(self.btn_skip)

        # When global settings are updated, recreate state of alignment tab
        if options['skip_alignment']:
            self._skip_alignment(ask=False)

    def _skip_alignment(self, ask=True):

        if ask:
            msg = 'Do you want to skip alignment and use pre-alignment for further analysis?'
            reply = QtWidgets.QMessageBox.question(self, 'Skip alignment', msg, QtWidgets.QMessageBox.Yes,
                                                   QtWidgets.QMessageBox.Cancel)
        else:
            reply = QtWidgets.QMessageBox.Yes

        if reply == QtWidgets.QMessageBox.Yes:

            self.btn_skip.setText('Alignment skipped')
            self.btn_ok.deleteLater()
            self.right_widget.setDisabled(True)

            if ask:
                self.skipAlignment.emit()
                self.proceedAnalysis.emit(self.tl)

        else:
            pass


class TrackFittingTab(AnalysisWidget):
    ''' Implements the track fitting gui'''

    proceedAnalysis = QtCore.pyqtSignal(list)

    def __init__(self, parent, setup, options, tab_list):
        super(TrackFittingTab, self).__init__(parent, setup, options, tab_list)

        self.add_function(func=find_tracks)
        self.add_function(func=fit_tracks)

        if options['skip_alignment']:
            input_tracks = options['output_path'] + '/TrackCandidates_prealignment.h5'
        else:
            input_tracks = options['output_path'] + '/Tracklets.h5'

        self.add_option(option='input_tracklets_file',
                        default_value=input_tracks,
                        func=find_tracks,
                        fixed=True)

        self.add_option(option='input_alignment_file',
                        default_value=options['output_path'] + '/Alignment.h5',
                        func=find_tracks,
                        fixed=True)

        self.add_option(option='output_track_candidates_file',
                        default_value=options['output_path'] + '/TrackCandidates.h5',
                        func=find_tracks,
                        fixed=True)

        self.output_files = [options['output_path'] + '/TrackCandidates.h5']

        # Set and fix options
        self.add_option(option='fit_duts', func=fit_tracks,
                        default_value=[0] * setup['n_duts'], optional=True)
        self.add_option(option='force_prealignment', func=fit_tracks,
                        default_value=False, fixed=True)
        self.add_option(option='exclude_dut_hit', func=fit_tracks,
                        default_value=False, fixed=True)
        self.add_option(option='use_correlated', func=fit_tracks,
                        default_value=False, fixed=True)
        self.add_option(option='min_track_distance', func=fit_tracks,
                        default_value=[200] * setup['n_duts'], optional=False)

        self.analysisDone.connect(lambda _tab_list: self.proceedAnalysis.emit(_tab_list))
        self.analysisDone.connect(lambda: self._connect_vitables(files=self.output_files))


class ResultTab(AnalysisWidget):
    ''' Implements the result analysis gui'''

    def __init__(self, parent, setup, options):
        super(ResultTab, self).__init__(parent, setup, options)

        self.add_function(func=calculate_efficiency)
        self.add_function(func=calculate_residuals)
