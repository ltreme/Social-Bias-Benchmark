from setuptools import find_packages, setup

setup(
    name="benchmark",
    version="0.1.0",
    packages=find_packages("src"),
    package_dir={"": "src"},
    install_requires=[
        "numpy",
        "requests",
        "python-dotenv",
        "huggingface_hub",
        "transformers",
        "torch",
        "pandas",
    ],
)
