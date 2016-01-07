from plugin_common import *

class LinuxFsFull(MyProjectPlugin):
    """ Basic plugin to monitor full filesystems on Linux systems"""
    cmd_params = 'user,passwd'
    tcp_ports = '22'

    def collect_data(self,data):
        data.df = Ssh(self.host.ip,self.host.user,self.host.passwd).run('df -h')

    def parse_data(self,data):
        df = data.df.skip(1)
        data.fs_critical = df.greaterequal(98,key=cuts(r'(\d+)%')).cut(col='5,4').renderitems()
        data.fs_warning = df.inrange(95,98,key=cuts(r'(\d+)%')).cut(col='5,4').renderitems()
        data.fs_ok = df.lessthan(95,key=cuts(r'(\d+)%')).cut(col='5,4').renderitems()

    def build_response(self,data):
        self.response.add_list(CRITICAL,data.fs_critical)
        self.response.add_list(WARNING,data.fs_warning)
        self.response.add_list(OK,data.fs_ok)

if __name__ == '__main__':
   LinuxFsFull().run()
