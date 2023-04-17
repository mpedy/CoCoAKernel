from pexpect import replwrap

class IREPLWrapper(replwrap.REPLWrapper):
    """A subclass of REPLWrapper that gives incremental output
    specifically for cocoa_kernel.
    The parameters are the same as for REPLWrapper, except for one
    extra parameter:
    :param line_output_callback: a callback method to receive each batch
      of incremental output. It takes one string parameter.
    """
    def __init__(self, cmd_or_spawn, orig_prompt, prompt_change,
                 extra_init_cmd=None, line_output_callback=None):
        self.line_output_callback = line_output_callback
        replwrap.REPLWrapper.__init__(self, cmd_or_spawn, orig_prompt,
                                      prompt_change, extra_init_cmd=extra_init_cmd)

    def _expect_prompt(self, timeout=-1):
        if timeout == None:
            # "None" means we are executing code from a Jupyter cell by way of the run_command
            # in the do_execute() code below, so do incremental output.
            while True:
                pos = self.child.expect_exact([self.prompt, self.continuation_prompt, u'\r\n', u'\n', u'\r'],
                                              timeout=None)
                if pos == 2 or pos == 3:
                    # End of line received.
                    self.line_output_callback(self.child.before + '\n')
                elif pos == 4:
                    # Carriage return ('\r') received.
                    self.line_output_callback(self.child.before + '\r')
                else:
                    if len(self.child.before) != 0:
                        # Prompt received, but partial line precedes it.
                        self.line_output_callback(self.child.before)
                    break
        else:
            # Otherwise, use existing non-incremental code
            pos = replwrap.REPLWrapper._expect_prompt(self, timeout=timeout)

        # Prompt received, so return normally
        return pos