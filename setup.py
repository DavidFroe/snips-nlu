import io
import os

from setuptools import setup, find_packages

packages = [p for p in find_packages()
            if "tests" not in p and "debug" not in p]

root = os.path.abspath(os.path.dirname(__file__))

with io.open(os.path.join(root, "snips_nlu", "__about__.py"),
             encoding="utf8") as f:
    about = dict()
    exec(f.read(), about)

with io.open(os.path.join(root, "README.rst"), encoding="utf8") as f:
    readme = f.read()

required = [
    "deprecation>=2.0,<3.0",
    "num2words>=0.5.6",
    "numpy>=1.26",
    "pyaml>=17.0",
    "requests>=2.0,<3.0",
    "scikit-learn>=1.4",
    "scipy>=1.11,<2.0",
    "sklearn-crfsuite>=0.5",
    "snips-nlu-parsers>=0.3.1,<0.5",
    "snips-nlu-utils>=0.9,<0.10",
]

extras_require = {
    "doc": [
        "sphinx>=1.8,<1.9",
        "sphinxcontrib-napoleon>=0.6.1,<0.7",
        "sphinx-rtd-theme>=0.2.4,<0.3",
        "sphinx-tabs>=1.1,<1.2"
    ],
    # snips-nlu-metrics 0.15.0 runs fine on this stack, but its published
    # metadata still pins numpy<2 and scikit-learn<0.23, which would downgrade
    # the whole installation. Install it separately instead:
    #   pip install --no-deps "snips-nlu-metrics>=0.15"
    "metrics": [
    ],
    "test": [
        "coverage>=4.4.2",
        "checksumdir>=1.3",
        "pytest>=8.0",
    ]
}

setup(name=about["__title__"],
      description=about["__summary__"],
      long_description=readme,
      version=about["__version__"],
      author=about["__author__"],
      author_email=about["__email__"],
      license=about["__license__"],
      url=about["__github_url__"],
      project_urls={
          "Documentation": about["__doc_url__"],
          "Source": about["__github_url__"],
          "Tracker": about["__tracker_url__"],
      },
      install_requires=required,
      extras_require=extras_require,
      python_requires=">=3.9",
      classifiers=[
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.13",
          "Topic :: Scientific/Engineering :: Artificial Intelligence",
      ],
      keywords="nlu nlp language machine learning text processing intent",
      packages=packages,
      include_package_data=True,
      entry_points={
          "console_scripts": [
              "snips-nlu=snips_nlu.cli:main"
          ]
      },
      zip_safe=False)
