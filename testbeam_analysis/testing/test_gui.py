import sys
import os
import logging
import unittest
from PyQt5 import QtWidgets, QtCore, QtGui

from testbeam_analysis.gui.tab_widgets.files_tab import FilesTab
from testbeam_analysis.gui.tab_widgets.setup_tab import SetupTab


class TestGui(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Make QApplication which starts event loop in order to create widgets
        cls.test_app = QtWidgets.QApplication(sys.argv)

        # Create widgets
        cls.files_tab = FilesTab()
        cls.setup_tab = SetupTab()

        # Create test data
        cls.data = {'dut_names': ['Tel_%i' % i for i in range(4)]}

        # Dut types
        cls.dut_types = {'FE-I4': {'material_budget': 0.001067236, 'n_cols': 80, 'n_rows': 336, 'pitch_col': 250.0,
                                   'pitch_row': 50.0},
                         'Mimosa26': {'material_budget': 0.000797512, 'n_cols': 1152, 'n_rows': 576, 'pitch_col': 18.4,
                                      'pitch_row': 18.4}}

    @classmethod
    def tearDownClass(cls):
        pass

    def test_files_tab(self):

        self.assertEqual(self.files_tab.isFinished, False)

        # Test default settings
        self.assertEqual(self.files_tab.edit_output.toPlainText(), os.getcwd())

        self.files_tab._data_table.setRowCount(len(self.data['dut_names']))
        self.files_tab._data_table.column_labels = ['Path', 'Name', 'Status', 'Navigation']
        self.files_tab._data_table.set_dut_names()

        self.assertListEqual(self.files_tab._data_table.dut_names, self.data['dut_names'])

    def test_setup_tab(self):

        self.assertEqual(self.setup_tab.isFinished, False)

        # Inits all tabs and the setup painter
        self.setup_tab.input_data(data=self.data)

        self.setup_tab._dut_types = self.dut_types

        self.assertListEqual(sorted(self.data['dut_names']), sorted(self.setup_tab.tw.keys()))

        # Set props of tel 0
        self.setup_tab._set_properties(self.data['dut_names'][0], 'FE-I4')

        properties = {}
        for p in self.setup_tab._dut_widgets[self.data['dut_names'][0]].keys():
            if p in self.dut_types['FE-I4'].keys():
                properties[p] = self.setup_tab._dut_widgets[self.data['dut_names'][0]][p].text()

        self.assertListEqual(sorted(properties.values()), sorted([unicode(r) for r in self.dut_types['FE-I4'].values()]))

        # Add scatter plane and check if tab is created
        self.setup_tab._add_dut('Scatter_plane', scatter_plane=True)
        dut_names = self.data['dut_names'][:]
        dut_names.append('Scatter_plane')

        self.assertListEqual(sorted(dut_names), sorted(self.setup_tab.tw.keys()))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGui)
    unittest.TextTestRunner(verbosity=2).run(suite)
