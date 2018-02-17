Graphical user interface
========================
The following documentation explains the features and usage of the graphical user interface (:GUI:) of *testbeam analysis*. The GUI is written in *PyQt* and intended to simplify
the analysis procedure. Its structured into several *tabs*, one for each step of a complete analysis. It offers the following features: 

   - Input file consistency check and setup plotting
   - Documentation of options via *function introspection*
   - Logging from analysis to GUI
   - Exception handling
   - Plotting results into GUI
   - Saving and loading analysis sessions
   - Running consecutive analysis without user interaction
   - Multi-threading
   - Support of `ViTables <https://github.com/uvemas/ViTables>`_
   .. NOTE::
      Due to current `dependency issues <https://github.com/conda-forge/vitables-feedstock/issues/3>`_ on *PyQt* version 5, a system installation of ViTables is required, e.g. on Ubuntu run
      .. code-block:: bash
         sudo apt-get install vitables

After running
   .. code-block:: bash
      python setup.py develop
   in the *tesbeam analysis* folder, the GUI can be opened from the shell via
   .. code-block:: bash
      tba
   .. NOTE::
      A minimum screen resolution of 1366 x 768 is required in order to display all features correctly.
   
File selection
**************
The file selection tab provides a table in order to display and handle the input files of all *devices under test* (:DUT:). The input files can be selected via a button click or *dragged & dropped*
onto the table area on the left-hand side of the file selection tab. After file selection, the path to each input file, the DUT name for subsequent analysis as well as the file status
(each input file is checked for required information) are displayed in the table. The table entries can be moved or deleted by usinf the buttons in the *Navigation* column. Each DUT can be optionally
renamed by double-clicking on the respective field in the table, the default naming is *Tel_i* where *i* is the DUT index. The output folder for the following analysis can be selected via the respective 
button on the right-hand side of the tab. An example of the files selection tab is shown in :ref:`label_files_tab`.
   .. NOTE::
      The required input files must be already interpreted hit files in *HDF5* format where each file must contain the following data:
      - *event_number*, *frame*, *charge*, *column*, *row*

.. _label_files_tab:

.. figure:: _static/file.png

Example of the file selection for FE-I4 telescope data, consisting of 4 FE-I4 pixel detectors

Setup 
*****
The setup tab provides a plotting area on the left-hand side of the tab in order to plot the schematic test setup as well as a tab to input setup information for each DUT on the right-hand side.
The telescope setup is plotted from the top- (upper) and side-view (lower) with rotations shown multiplied by a factor of 10 and correct relative distances in between DUTs.
Information for each DUT can be input manually or selected from a list with predefined DUT-types. This list can be extended by the current, complete information via entering a *new* name into
the respective field and pressing the respective button. DUT-types can be overwritten or removed from the list by typing `name` or `:name` respectively, into the respective field and pressing
the button. Dead material (*scatter planes*) in the setup can be added by clicking the button in the upper-right corner. An example of the setup tab is shown in :ref:`label_setup_tab`.

.. _label_setup_tab:

.. figure:: _static/setup.png

Example of setup tab for FE-I4 telescope data, consisting of 4 FE-I4 pixel detectors and a scatter plane

Analysis
********

.. image:: _static/noisy.png
