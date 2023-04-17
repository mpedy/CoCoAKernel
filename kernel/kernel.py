from ipykernel.kernelbase import Kernel
from pexpect import EOF, spawn

from subprocess import check_output
import os.path
import uuid
from dotenv import dotenv_values, find_dotenv

import re
import signal
import os

__version__ = "1.0.0"
version_pat = re.compile(r'version (\d+(\.\d+)+)')

from .display import (extract_contents, build_cmds)
from .IREPLWrapper import IREPLWrapper


class CocoaKernel(Kernel):
    config = dotenv_values(os.path.dirname(os.path.realpath(__file__))+"/.conf")
    implementation = config["kernelname"]
    implementation_version = __version__
    binary_path = config["CoCoA_folder"]

    @property
    def language_version(self):
        m = version_pat.search(self.banner)
        return m.group(1)

    _banner = None

    @property
    def banner(self):
        if self._banner is None:
            self._banner = self.config["CoCoA_banner"]
        return self._banner

    language_info = {'name': 'cocoa',
                     'codemirror_mode': 'shell',
                     'file_extension': '.cocoa5'}

    def __init__(self, **kwargs):
        Kernel.__init__(self, **kwargs)
        self._start_cocoa()
        self._known_display_ids = set()

    def _start_cocoa(self):
        # Signal handlers are inherited by forked processes, and we can't easily
        # reset it from the subprocess. Since kernelapp ignores SIGINT except in
        # message handlers, we need to temporarily reset the SIGINT handler here
        # so that cocoa and its children are interruptible.
        sig = signal.signal(signal.SIGINT, signal.SIG_DFL)
        try:
            # Note: the next few lines mirror functionality in the
            # cocoa() function of pexpect/replwrap.py.  Look at the
            # source code there for comments and context for
            # understanding the code here.
            child = spawn(f"\"{self.binary_path}/bin/CoCoAInterpreter\" --packageDir \"{self.binary_path}/packages\"", echo=False,
                                  encoding='utf-8', codec_errors='replace')
            # Using IREPLWrapper to get incremental output
            self.bashwrapper = IREPLWrapper(child, u'# ', None, line_output_callback=self.process_output)
        finally:
            signal.signal(signal.SIGINT, sig)

        # Disable bracketed paste (see <https://github.com/takluyver/bash_kernel/issues/117>)
        #self.bashwrapper.run_command("bind 'set enable-bracketed-paste off' >/dev/null 2>&1 || true")
        # Register Bash function to write image data to temporary file
        #self.bashwrapper.run_command(build_cmds())


    def process_output(self, output):
        if not self.silent:
            plain_output, rich_contents = extract_contents(output)

            # Send standard output
            if plain_output:
                stream_content = {'name': 'stdout', 'text': plain_output}
                self.send_response(self.iopub_socket, 'stream', stream_content)

            # Send rich contents, if any:
            for content in rich_contents:
                if isinstance(content, Exception):
                    message = {'name': 'stderr', 'text': str(content)}
                    self.send_response(self.iopub_socket, 'stream', message)
                else:
                    if 'transient' in content and 'display_id' in content['transient']:
                        self._send_content_to_display_id(content)
                    else:
                        self.send_response(self.iopub_socket, 'display_data', content)

    def _send_content_to_display_id(self, content):
        """If display_id is not known, use "display_data", otherwise "update_display_data"."""
        # Notice this is imperfect, because when re-running the same cell, the output cell
        # is destroyed and the div element (the html tag) with the display_id no longer exists. But the
        # `update_display_data` function has no way of knowing this, and thinks that the
        # display_id still exists and will try, and fail to update it (as opposed to re-create
        # the div with the display_id).
        #
        # The solution is to have the user always to generate a new display_id for a cell: this
        # way `update_display_data` will not have seen the display_id when the cell is re-run and
        # correctly creates the new div element.
        display_id = content['transient']['display_id']
        if display_id in self._known_display_ids:
            msg_type = 'update_display_data'
        else:
            msg_type = 'display_data'
            self._known_display_ids.add(display_id)
        self.send_response(self.iopub_socket, msg_type, content)

    def do_execute(self, code, silent, store_history=True,
                   user_expressions=None, allow_stdin=False):
        self.silent = silent
        if not code.strip():
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}

        interrupted = False
        try:
            # Note: timeout=None tells IREPLWrapper to do incremental
            # output.  Also note that the return value from
            # run_command is not needed, because the output was
            # already sent by IREPLWrapper.
            self.bashwrapper.run_command(code.rstrip(), timeout=None)
        except KeyboardInterrupt:
            self.bashwrapper.child.sendintr()
            interrupted = True
            self.bashwrapper._expect_prompt()
            output = self.bashwrapper.child.before
            self.process_output(output)
        except EOF:
            output = self.bashwrapper.child.before + 'Restarting CoCoA'
            self._start_cocoa()
            self.process_output(output)

        if interrupted:
            return {'status': 'abort', 'execution_count': self.execution_count}

        #try:
        #    exitcode = int(self.bashwrapper.run_command('echo $?').rstrip())
        #except Exception:
        #    exitcode = 1

        exitcode = 0
        if exitcode:
            error_content = {
                'ename': '',
                'evalue': str(exitcode),
                'traceback': []
            }
            self.send_response(self.iopub_socket, 'error', error_content)

            error_content['execution_count'] = self.execution_count
            error_content['status'] = 'error'
            return error_content
        else:
            return {'status': 'ok', 'execution_count': self.execution_count,
                    'payload': [], 'user_expressions': {}}

#    def do_complete(self, code, cursor_pos):
#        code = code[:cursor_pos]
#        default = {'matches': [], 'cursor_start': 0,
#                   'cursor_end': cursor_pos, 'metadata': dict(),
#                   'status': 'ok'}
#
#        if not code or code[-1] == ' ':
#            return default
#
#        tokens = code.replace(';', ' ').split()
#        if not tokens:
#            return default
#
#        matches = []
#        token = tokens[-1]
#        start = cursor_pos - len(token)
#
#        if token[0] == '$':
#            # complete variables
#            cmd = 'compgen -A arrayvar -A export -A variable %s' % token[1:] # strip leading $
#            output = self.bashwrapper.run_command(cmd).rstrip()
#            completions = set(output.split())
#            # append matches including leading $
#            matches.extend(['$'+c for c in completions])
#        else:
#            # complete functions and builtins
#            cmd = 'compgen -cdfa %s' % token
#            output = self.bashwrapper.run_command(cmd).rstrip()
#            matches.extend(output.split())
#
#        if not matches:
#            return default
#        matches = [m for m in matches if m.startswith(token)]
#
#        return {'matches': sorted(matches), 'cursor_start': start,
#                'cursor_end': cursor_pos, 'metadata': dict(),
#                'status': 'ok'}
