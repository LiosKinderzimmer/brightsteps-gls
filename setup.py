from setuptools import find_packages, setup


setup(
    name="brightsteps_gls",
    version="0.3.1",
    description="Update-safe GLS ShipIT integration for ERPNext",
    author="Bright Steps",
    author_email="info@brightsteps.at",
    url="https://brightsteps.at",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
)
