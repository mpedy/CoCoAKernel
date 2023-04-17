from ipykernel.kernelapp import IPKernelApp
from .kernel import CocoaKernel
IPKernelApp.launch_instance(kernel_class=CocoaKernel)
