''' Conversion of raw data with trigger time stamps taken with pymosa and pyBar.

    Read out hardware is USBpix3 based MMC3 board for 6 Mimosa26 planes that are
    read out triggerless and 1 FE-I4 plane for time reference is read out with trigger from the TLU
    with seperate hardware.

    The correlation between the two data streams is done using a trigger time
    stamp feature of the readout system.

    Note:
    -----
    So far only working with:
      - pyBAR_fei4_interpreter development branch
      - pyBAR_mimosa26_interpreter development branch
'''

import shutil
import logging

import tables as tb
from tqdm import tqdm

import pyBAR_mimosa26_interpreter.simple_converter_combined as m26_cv
from testbeam_analysis.converter import pybar_fei4_converter as pyfei4_cv
from bdaq53.analysis import bdaq53_converter as bdaq53_cv
from bdaq53.analysis.plotting import Plotting


def interpret_fei4_data(data):
    ''' Analyse telescope time reference raw data recorded with pybar and plot.

    Parameters
    ----------
    data : string, iterable of strings
        File name of the raw data or several raw data files of one run.
    '''

    pyfei4_cv.process_dut(data,
                          # Data format has trigger time stamp
                          trigger_data_format=2)


def interpret_anemone_data(data, fei4_data):
    ''' Analyse telescope Mimosa26 raw data recorded with pymosa.

        Use FE-I4 data for event alignment with trigger numbers (?)

    Parameters
    ----------
    data : string, iterable of strings
        File name of the Mimosa 26 raw data or several raw data files of one run.
    fei4_data : string, iterable of strings
        File name of the Fe-I4 raw data or several raw data files of one run.
    '''

    # Step 1: Combine several files if needed
    # to allow Mimosa26 interpreter to work
    if isinstance(data, list):
        data = combine_raw_data(data)
        fe_event_aligned = fei4_data[0][:-3] + '_event_aligned.h5'
    else:
        data = data
        fe_event_aligned = fei4_data[:-3] + '_event_aligned.h5'

    # Step 2: Interpret MIMOSA26 planes
    # Output: file with _aligned.h5 suffix with plane number
    for plane in range(1, 7):
        m26_cv.m26_converter(fin=data,  # Input file
                             fout=data[:-3] + \
                             '_frame_aligned_%d.h5' % plane,  # Output file
                             plane=plane)  # Plane number
        # Step 3: Combine FE with Mimosa data
        # Output: file with
        m26_cv.align_event_number(
            fin=data[:-3] + '_frame_aligned_%d.h5' % plane,  # Mimosa
            fe_fin=fe_event_aligned,
            fout=data[:-3] + '_run_aligned_%d.h5' % plane,
            tr=True,  # Switch column / row (transpose)
            frame=False)  # Add frame info (not working?)


def combine_raw_data(raw_data_files, chunksize=10000000):
    file_combined = raw_data_files[0][:-3] + '_combined.h5'
    # Use first tmp file as result file
    shutil.move(raw_data_files[0], file_combined)
    with tb.open_file(raw_data_files[0][:-3] + '_combined.h5', 'r+') as in_f:
        combined_data = in_f.root.raw_data
        status = 0
        for raw_data_file in tqdm(raw_data_files[1:]):
            with tb.open_file(raw_data_file) as in_f:
                for chunk in range(0, in_f.root.raw_data.shape[0], chunksize):
                    data = in_f.root.raw_data[chunk:chunk + chunksize]
                    combined_data.append(data)
                    status += chunksize
    return file_combined


def interpret_rd53a_data(data):
    ''' Interpret, convert and plot RD53A data.

        Parameters
        ----------
        data : string
            File name of the RD53A raw data
    '''
    bdaq53_cv.process_raw_data(data, n_trg_num_bits=16)
    analyzed_data_file = data[:-3] + '_interpreted.h5'
    with Plotting(analyzed_data_file=analyzed_data_file) as p:
        p.create_standard_plots()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

    interpret_fei4_data(r'H:\tmp\CERN TB\raw\45_fei4_tel_mod2_ext_trigger_scan.h5')
    interpret_anemone_data(r'H:\tmp\CERN TB\raw\20180504-164215_M26_TELESCOPE.h5',
                           fei4_data=r'H:\tmp\CERN TB\raw\45_fei4_tel_mod2_ext_trigger_scan.h5')
    interpret_rd53a_data(r'H:\tmp\CERN TB\raw\20180504_164158_ext_trigger_scan.h5')
