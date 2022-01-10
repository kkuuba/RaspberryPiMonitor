import paramiko
import subprocess


class SshConnections:
    def __init__(self, address, username, password):
        self.connection = paramiko.SSHClient()
        self.connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.connection.connect(hostname=address, username=username, password=password)

    def run_cmd(self, cmd):
        stdin, stdout, stderr = self.connection.exec_command(cmd)
        output = stdout.readlines()
        if len(output) == 1:
            return output[0]
        else:
            return output


class RunCmdLocal:
    @staticmethod
    def run_cmd(cmd):
        output = subprocess.run(cmd, stdout=subprocess.PIPE).stdout.decode("utf-8").split("\n")
        if len(output) == 1:
            return output[0]
        else:
            return output
