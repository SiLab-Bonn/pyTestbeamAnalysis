import sys
import os
import logging
import unittest
from PyQt5 import QtWidgets, QtCore, QtGui

from testbeam_analysis.gui.tab_widgets.files_tab import FilesTab


class TestGui(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Make QApplication which starts event loop in order to create widgets
        cls.test_app = QtWidgets.QApplication(sys.argv)
        # Creat widgets
        cls.files_tab = FilesTab()

    @classmethod
    def tearDownClass(cls):
        pass

    def test_files_tab(self):

        # Test default settings
        self.assertEqual(self.files_tab.edit_output.toPlainText(), os.getcwd())

        test_duts = ['Tel_%i' % i for i in range(4)]
        self.files_tab._data_table.setRowCount(len(test_duts))
        self.files_tab._data_table.column_labels = ['Path', 'Name', 'Status', 'Navigation']
        self.files_tab._data_table.set_dut_names()

        self.assertListEqual(self.files_tab._data_table.dut_names, test_duts)



if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGui)
    unittest.TextTestRunner(verbosity=2).run(suite)
