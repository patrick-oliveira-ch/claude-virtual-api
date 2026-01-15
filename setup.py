from setuptools import setup, find_packages

setup(
    name="claude-virtual-api",
    version="1.0.0",
    packages=find_packages(),
    py_modules=["client"],
    install_requires=["httpx>=0.26.0"],
    author="Patapps",
    description="Client pour Claude Virtual API",
    python_requires=">=3.10",
)
