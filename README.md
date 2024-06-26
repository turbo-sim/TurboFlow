
# TurboFlow: Meanline Modelling of Turbomachinery

**TurboFlow** is a Python package for mean-line modelling of turbomachinery. It aims to offer flexible and reliable simulations for both performance prediction and design optimization, and should present a valuable resource for engineers and researchers working in the field of turbomachinery.

[![PyPI](https://img.shields.io/pypi/v/turboflow.svg)](https://pypi.org/project/turboflow/)
[![Documentation](https://img.shields.io/badge/docs-latest-blue.svg)](https://turbo-sim.github.io/TurboFlow/)

## Core features

- **Performance Prediction:** Accurately predict the performance of turbomachinery based on various input parameters.
- **Design Optimization:** Optimize preliminary turbomachinery design to achieve optimal performance metrics.
- **Equation-oriented problem formulation:** Equation-oriented problem formulation for performance analysis and design optimization.
- **Model consistency:** The model is consistent for both performance prediction and design optimization.
- **Efficient solution:** The model adopts gradient-based root-finding and optimization solver
- **Real gas fluid property analysis:** Use CoolProp to determine thermohpysical properties.
- **Flexible model:** The model offers options for submodels for loss, deviation and choking calculations
- **General geometry:** Geometrical variables are defined to cover a wide range of designs, including multistage configurations.  
- **Easy-to-use:** Intuitive and easy setup of input parameters for rapid development and analysis. 
- **Extensive Documentation:** Comprehensive guides and examples to help you get started quickly.


## Quick Installation Guide

This guide will walk you through the process of installing `Turboflow` via `pip`. To isolate the Turboflow installation and avoid conflicts with other Python packages, it is recommended to create a dedicated Conda virtual environment.

1. [Install Miniconda](https://docs.anaconda.com/free/miniconda/miniconda-install/) if you don't have it already.

2. Open a terminal or command prompt and create a new virtual environment named `turboflow_env` with Python 3.11:
   ```
   conda create --name turboflow_env python=3.11
   ```

3. Activate the newly created virtual environment:
   ```
   conda activate turboflow_env
   ```

4. Install Turboflow using pip within the activated virtual environment:
   ```
   pip install turboflow
   ```

5. Verify the installation by running the following command in your terminal:
   ```
   python -c "import turboflow; turboflow.print_package_info()"
   ```

   If the installation was successful, you should see the Turboflow banner and package information displayed in the console output.

Congratulations! You have now successfully installed Turboflow in its own Conda virtual environment using pip. You're ready to start using Turboflow in your Python projects.




