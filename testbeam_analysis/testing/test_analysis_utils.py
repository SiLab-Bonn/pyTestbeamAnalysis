''' Script to check the correctness of the analysis utils that are written in C++.
'''
import os

import unittest

import tables as tb
import numpy as np

from hypothesis import given, seed
import hypothesis.extra.numpy as nps
import hypothesis.strategies as st
from hypothesis.extra.numpy import unsigned_integer_dtypes

from testbeam_analysis.cpp import data_struct
from testbeam_analysis.tools import analysis_utils, test_tools

testing_path = os.path.dirname(__file__)


class TestAnalysisUtils(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):  # remove created files
        pass

    @given(nps.arrays(np.int64,
                      shape=nps.array_shapes(max_dims=1, max_side=32000),
                      elements=st.integers(0, 2 ** 16 - 1)))
    def test_get_events_in_both_arrays_fuzzing(self, arr):
        ''' Check get_events_in_both_arrays function'''

        event_numbers = np.sort(arr)

        result = analysis_utils.get_events_in_both_arrays(event_numbers,
                                                          event_numbers)

        def numpy_solution(event_numbers, event_numbers_2):
            ''' Slow numpy solution to check against '''
            return np.unique(event_numbers[np.in1d(event_numbers, event_numbers_2)])

        self.assertListEqual(numpy_solution(event_numbers,
                                            event_numbers).tolist(),
                             result.tolist())

    def test_analysis_utils_get_max_events_in_both_arrays(self):
        ''' Check compiled get_max_events_in_both_arrays function'''
        # Test 1
        event_numbers = np.array([[0, 0, 1, 1, 2],
                                  [0, 0, 0, 0, 0]],
                                 dtype=np.int64)
        event_numbers_2 = np.array([0, 3, 3, 4], dtype=np.int64)
        result = analysis_utils.get_max_events_in_both_arrays(event_numbers[0],
                                                              event_numbers_2)
        self.assertListEqual([0, 0, 1, 1, 2, 3, 3, 4], result.tolist())
        # Test 2
        event_numbers = np.array([1, 1, 2, 4, 5, 6, 7], dtype=np.int64)
        event_numbers_2 = np.array([0, 3, 3, 4], dtype=np.int64)
        result = analysis_utils.get_max_events_in_both_arrays(event_numbers,
                                                              event_numbers_2)
        self.assertListEqual([0, 1, 1, 2, 3, 3, 4, 5, 6, 7], result.tolist())
        # Test 3
        event_numbers = np.array([1, 1, 2, 4, 5, 6, 7], dtype=np.int64)
        event_numbers_2 = np.array([6, 7, 9, 10], dtype=np.int64)
        result = analysis_utils.get_max_events_in_both_arrays(event_numbers,
                                                              event_numbers_2)
        self.assertListEqual([1, 1, 2, 4, 5, 6, 7, 9, 10], result.tolist())
        # Test 4
        event_numbers = np.array([1, 1, 2, 4, 5, 6, 7, 10, 10], dtype=np.int64)
        event_numbers_2 = np.array([1, 6, 7, 9, 10], dtype=np.int64)
        result = analysis_utils.get_max_events_in_both_arrays(
            event_numbers, event_numbers_2)
        self.assertListEqual([1, 1, 2, 4, 5, 6, 7, 9, 10, 10], result.tolist())
        # Test 5
        event_numbers = np.array([1, 1, 2, 4, 5, 6, 7, 10, 10], dtype=np.int64)
        event_numbers_2 = np.array([1, 1, 1, 6, 7, 9, 10], dtype=np.int64)
        result = analysis_utils.get_max_events_in_both_arrays(event_numbers,
                                                              event_numbers_2)
        self.assertListEqual([1, 1, 1, 2, 4, 5, 6, 7, 9, 10, 10],
                             result.tolist())

    def test_map_cluster(self):
        ''' Check the compiled function against result '''
        # Create result
        result = np.zeros(
            (20, ),
            dtype=tb.dtype_from_descr(data_struct.ClusterInfoTable))
        result["mean_column"] = np.nan
        result["mean_row"] = np.nan
        result["charge"] = np.nan
        (result[1]["event_number"], result[3]["event_number"], result[7]["event_number"],
         result[8]["event_number"], result[9]["event_number"]) = (1, 2, 4, 4, 19)

        (result[0]["mean_column"], result[1]["mean_column"],
         result[3]["mean_column"], result[7]["mean_column"],
         result[8]["mean_column"], result[9]["mean_column"]) = (1, 2, 3, 5, 6, 20)

        (result[0]["mean_row"], result[1]["mean_row"],
         result[3]["mean_row"], result[7]["mean_row"],
         result[8]["mean_row"], result[9]["mean_row"]) = (0, 0, 0, 0, 0, 0)

        (result[0]["charge"], result[1]["charge"], result[3]["charge"],
         result[7]["charge"], result[8]["charge"], result[9]["charge"]) = (0, 0, 0, 0, 0, 0)

        # Create data
        clusters = np.zeros(
            (20, ),
            dtype=tb.dtype_from_descr(data_struct.ClusterInfoTable))
        for index, cluster in enumerate(clusters):
            cluster['mean_column'] = index + 1
            cluster["event_number"] = index
        clusters[3]["event_number"] = 2
        clusters[5]["event_number"] = 4

        common_event_number = np.array([0, 1, 1, 2, 3, 3, 3, 4, 4],
                                       dtype=np.int64)

        data_equal = test_tools.nan_equal(
            first_array=analysis_utils.map_cluster(
                common_event_number, clusters),
            second_array=result[:common_event_number.shape[0]])
        self.assertTrue(data_equal)

    def test_analysis_utils_in1d_events(self):
        ''' Check compiled get_in1d_sorted function '''
        event_numbers = np.array([[0, 0, 2, 2, 2, 4, 5, 5, 6, 7, 7, 7, 8],
                                  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]],
                                 dtype=np.int64)
        event_numbers_2 = np.array([1, 1, 1, 2, 2, 2, 4, 4, 4, 7],
                                   dtype=np.int64)
        result = event_numbers[0][analysis_utils.in1d_events(event_numbers[0],
                                                             event_numbers_2)]
        self.assertListEqual([2, 2, 2, 4, 7, 7, 7], result.tolist())

    def test_1d_index_histograming(self):
        ''' Check jitted hist_1D_index function '''

        # Shape that is too small for the indices to trigger exception
        x = np.linspace(0, 100, 100)
        shape = (5, )
        with self.assertRaises(IndexError):
            analysis_utils.hist_1d_index(x, shape=shape)

    @given(nps.arrays(unsigned_integer_dtypes(),
                      shape=nps.array_shapes(max_dims=1, max_side=32000),
                      elements=st.integers(0, 2 ** 16 - 1)))
    def test_1d_index_hist_fuzzing(self, x):
        # Set maximum shape from maximum value
        shape = (np.max(x) + 1, )
        # Cast to uint32 needed since python
        # does sometimes upcast to int64 or float64
        shape_numpy = ((shape[0]).astype(np.uint32), )

        array_fast = analysis_utils.hist_1d_index(x, shape=shape_numpy)

        
        array = np.histogram(x.astype(np.uint32),
                             bins=shape_numpy[0],
                             range=(0, shape_numpy[0]))[0]
        self.assertTrue(np.all(array == array_fast))

    @given(nps.arrays(unsigned_integer_dtypes(),
                      shape=(2, 32000),
                      elements=st.integers(0, 2 ** 8)))
    def test_2d_index_hist_fuzzing(self, arr):
        # Set maximum shape from maximum value
        x, y = arr[0, :], arr[1, :]
        shape = (x.max() + 1, y.max() + 1)
        # Cast to uint32 needed since python
        # does sometimes upcast to int64 or float64
        shape_numpy = ((shape[0]).astype(np.uint32),
                       (shape[1]).astype(np.uint32))

        array_fast = analysis_utils.hist_2d_index(x, y,
                                                  shape=shape_numpy)

        array = np.histogram2d(x, y, bins=shape,
                               range=[[0, shape[0]], [0, shape[1]]])[0]
        self.assertTrue(np.all(array == array_fast))

    def test_2d_index_histograming(self):
        ''' Check jitted hist_2D_index exception '''
        x, y = np.linspace(0, 100, 100), np.linspace(0, 100, 100)

        with self.assertRaises(IndexError):
            analysis_utils.hist_2d_index(x, y, shape=(5, 200))
        with self.assertRaises(IndexError):
            analysis_utils.hist_2d_index(x, y, shape=(200, 5))

    @given(nps.arrays(unsigned_integer_dtypes(),
                      shape=(3, 32000),
                      elements=st.integers(0, 2 ** 8)))
    def test_3d_index_hist_fuzzing(self, arr):
        ''' Fuzzing jitted hist_2D_index function '''
        x, y, z = arr[0, :], arr[1, :], arr[2, :]
        shape = (x.max() + 1, y.max() + 1, z.max() + 1)
        # Cast to uint32 needed since python
        # does sometimes upcast to int64 or float64
        shape_numpy = ((shape[0]).astype(np.uint32),
                       (shape[1]).astype(np.uint32),
                       (shape[2]).astype(np.uint32))

        array_fast = analysis_utils.hist_3d_index(x, y, z,
                                                  shape=shape_numpy)

        array = np.histogramdd(np.column_stack((x, y, z)), bins=shape,
                               range=[[0, shape_numpy[0] - 1],
                                      [0, shape_numpy[1] - 1],
                                      [0, shape_numpy[2] - 1]])[0]
        self.assertTrue(np.all(array == array_fast))

    def test_3d_index_histograming(self):
        ''' Check jitted hist_3D_index exceptions '''
        # Shape that is too small for the indices to trigger exception
        x = y = z = np.linspace(0, 100, 100)

        with self.assertRaises(IndexError):
            analysis_utils.hist_3d_index(x, y, z, shape=(200, 200, 99))

        with self.assertRaises(IndexError):
            analysis_utils.hist_3d_index(x, y, z, shape=(99, 200, 200))

        with self.assertRaises(IndexError):
            analysis_utils.hist_3d_index(x, y, z, shape=(200, 99, 200))

if __name__ == '__main__':
    import logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAnalysisUtils)
    unittest.TextTestRunner(verbosity=2).run(suite)
