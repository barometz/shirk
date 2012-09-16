import plugs.plugbase

class Plug(plugs.plugbase.Plug):
    def __init__(self, core):
        super(Plug, self).__init__(core)
        self.triggercmds = [('quit', self.cmd_quit)]

    def cmd_quit(self, source, target, cmd, argv):
        self.core.quit()

