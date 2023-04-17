from setuptools import setup
from dotenv import dotenv_values, find_dotenv

config = dotenv_values(find_dotenv("kernel/.conf"))

setup(
    name="cocoa_kernel",
    version=config["version"],
    description=config["name"],
    author="Matteo Provendola",
    author_email="cuoremagico93@gmail.com",
    packages=["kernel"],
    package_data={"kernel": [".conf"]},
    zip_safe=False
)
