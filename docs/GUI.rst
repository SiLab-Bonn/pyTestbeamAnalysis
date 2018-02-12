Graphical user interface
========================
The following documentation explains the features and usage of the graphical user interface (:GUI:) of *testbeam analysis*. The GUI is written in *PyQt* and intended to simplify
the analysis procedure. It offers the offers the following features: 

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
   
File selection
**************

.. image:: _static/file.png

Setup 
*****

.. image:: _static/setup.png

Analysis
********

.. image:: _static/noisy.png
