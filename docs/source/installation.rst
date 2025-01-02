Installation
============
The most recent release can be installed from
`PyPI <https://pypi.org/project/pyobo>`_ with:

.. code-block:: shell

    python3 -m pip install pyobo

The most recent code and data can be installed directly from GitHub with:

.. code-block:: shell

    python3 -m pip install git+https://github.com/biopragmatics/pyobo.git

To install in development mode, use the following:

.. code-block:: shell

    git clone git+https://github.com/biopragmatics/pyobo.git
    cd pyobo
    UV_PREVIEW=1 python3 -m pip install -e .

Note that the ``UV_PREVIEW`` environment variable is required to be
set until the uv build backend becomes a stable feature.
