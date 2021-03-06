"""
SSH job transport for AsyncRE
"""
import os
import re
import sys
import time
import random
import paramiko
import multiprocessing as mp
import logging
import Queue
import subprocess
# import scp

from transport import Transport  # WFF - 2/18/15


class ssh_transport(Transport):
    """
    Class to launch and monitor jobs on a set of nodes via ssh (paramiko)
    """

    def __init__(self, jobname, compute_nodes, replicas):  # changed on 12/1/14
        # jobname: identifies current asyncRE job
        # compute_nodes: list of names of nodes in the pool
        # nreplicas: number of replicas, 0 ... nreplicas-1
        Transport.__init__(self)  # WFF - 2/18/15
        self.logger = logging.getLogger("async_re.ssh_transport")  # WFF - 3/2/15

        # names of compute nodes (slots)
        self.compute_nodes = compute_nodes  # changed on 12/1/14
        self.nprocs = len(self.compute_nodes)

        # node status = None if idle
        # Otherwise a structure containing:
        #    replica number being executed
        #    process id
        #    process name
        #    ...
        self.node_status = [None for k in range(self.nprocs)]

        # contains the nodeid of the node running a replica
        # None = no information about where the replica is running
        self.replica_to_job = [None for k in replicas]

        # implements a queue of jobs from which to draw the next job
        # to launch
        self.jobqueue = Queue.Queue()

    def _clear_resource(self, replica):
        # frees up the node running a replica identified by replica id
        job = None
        try:
            job = self.replica_to_job[replica]
        except:
            self.logger.warning("clear_resource(): unknown replica id %d",
                                replica)

        if job == None:
            return None

        try:
            nodeid = job['nodeid']
        except:
            self.logger.warning("clear_resource(): unable to query nodeid")
            return None

        try:
            self.node_status[nodeid] = None
        except:
            self.logger.warning("clear_resource(): unknown nodeid %", nodeid)
            return None

        return nodeid

    def _availableNode(self):
        # returns a node at random among available nodes
        available = [node for node in range(self.nprocs)
                     if self.node_status[node] == None]
        if available == None or len(available) == 0:
            return None
        random.shuffle(available)
        return available[0]

    # utility to repeat a scp put command
    def _RepeatSCPput(self, transport, local_file, remote_file, num_tries=10, sleep_time=10):
        ntries = 0
        # self.logger.info("scp %s %s", local_file, remote_file) #can print out here to check the scp
        while True:
            # retry a number of times
            if ntries < num_tries:
                try:
                    transport.put(local_file, remote_file)
                except:
                    self.logger.info("Warning: unable to transfer file %s. Retrying ..." % local_file)
                    time.sleep(sleep_time)  # waits few seconds and try again
                    ntries += 1
                    continue
                else:
                    # success
                    break
            else:
                # retry one last time, letting it fail in case
                transport.put(local_file, remote_file)
                break

    # utility to repeat a scp get command
    def _RepeatSCPget(self, transport, remote_file, local_file, num_tries=10, sleep_time=10):
        ntries = 0
        # self.logger.info("scp %s %s", remote_file, local_file) #can print out here to check the scp
        while True:
            # retry a number of times
            if ntries < num_tries:
                try:
                    transport.get(remote_file, local_file)
                except:
                    self.logger.info("Warning: unable to copy back file %s. Retrying ..." % local_file)
                    time.sleep(sleep_time)  # waits few seconds and try again
                    ntries += 1
                    continue
                else:
                    # success
                    break
            else:
                # retry one last time, letting it fail in case
                transport.get(remote_file, local_file)
                break

    def _checkSSHconnection(self, ssh, scpt, job):
        # try to reopen ssh connection if it has closed
        try:
            transport = ssh.get_transport()
            transport.send_ignore()
        except:
            # connection is probably closed, try to reconnect
            ssh.close()
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if job['username'] != None:
                ssh.connect(job['nodename'], username=job['username'])
            else:
                ssh.connect(job['nodename'])
            scpt = scp.SCPClient(ssh.get_transport())
            self.logger.info("Restablished SSH connection to %s", job['nodename'])
        return (ssh, scpt)

    def _launchCmd(self, command, job):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        if job['username'] != None:
            ssh.connect(job['nodename'], username=job['username'])
        else:
            ssh.connect(job['nodename'])

        self.logger.info("SSH connection established to %s", job['nodename'])

        if job["remote_working_directory"]:
            mkdir_command = "mkdir -p %s" % job['remote_working_directory']
            stdin, stdout, stderr = ssh.exec_command(mkdir_command)
            output = stdout.read()
            error = stderr.read()
            stdin.close()
            stdout.close()
            stderr.close()

            send_files_command = "scp "
            for filename in job["exec_files"]:
                send_files_command += filename + " "
            for filename in job["job_input_files"]:
                send_files_command += job["working_directory"] + "/" + filename + " "
            if job['username'] != None:
                send_files_command += job['username'] + "@"
            send_files_command += job['nodename'] + ":" + job["remote_working_directory"] + "/"
            subprocess.call(send_files_command + " > /dev/null 2>&1 ", shell=True)

            chmod_command = "chmod -R 777 %s" % job['remote_working_directory']
            stdin, stdout, stderr = ssh.exec_command(chmod_command)
            output = stdout.read()
            error = stderr.read()
            stdin.close()
            stdout.close()
            stderr.close()
            

        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read()
        error = stderr.read()
        stdin.close()
        stdout.close()
        stderr.close()

        if job["remote_working_directory"]:
            get_files_command = "scp "
            if job['username'] != None:
                get_files_command += job['username'] + "@"
            get_files_command += job['nodename'] + ":" + job["remote_working_directory"] + "/"
            files = "{"
            for n in range(0, len(job["job_output_files"])):
                filename = job["job_output_files"][n]
                if n == 0:
                    files += filename
                else:
                    files += "," + filename
            files += "}"
            get_files_command += files + " " + job["working_directory"] + "/"
            subprocess.call(get_files_command + " > /dev/null 2>&1 ", shell=True)
            rmdir_command = "rm -rf %s" % job['remote_working_directory']
            stdin, stdout, stderr = ssh.exec_command(rmdir_command)
            stdin.close()
            stdout.close()
            stderr.close()

        job['output_queue'].put(output)
        job['error_queue'].put(error)

        ssh.close()

    def launchJob(self, replica, job_info):
        """
        Enqueues a job based on provided job info.
        """
        input_file = job_info["input_file"]
        output_file = job_info["output_file"]
        error_file = job_info["error_file"]
        executable = job_info["executable"]

        command = "%s %s > %s 2> %s " % (executable, input_file, output_file, error_file)
        

        output_queue = mp.Queue()
        error_queue = mp.Queue()

        job = job_info
        job['replica'] = replica
        job['output_queue'] = output_queue
        job['error_queue'] = error_queue
        job['command'] = command
        job['process_handle'] = None

        self.replica_to_job[replica] = job

        self.jobqueue.put(replica)

        return self.jobqueue.qsize()

    # intel coprocessor setup
    def ModifyCommand(self, job, command):
        nodename = job['nodename']
        nthreads = job['nthreads']
        slotN = job['nslots']
        arch = job['arch']

        # add command to go to remote working directory
        cd_to_command = "cd %s ; " % job["remote_working_directory"]

        mic_pattern_supermic = re.compile(r'-knc')
        mic_pattern_stampede2 = re.compile(r'-knl')

        if re.search(mic_pattern_supermic, arch):
            ncores = nthreads / 4
            offset = slotN * ncores
            add_to_command = "export KMP_PLACE_THREADS=%dC,4T,%dO ; " % (ncores, offset)
            new_command = add_to_command + cd_to_command + command
        elif re.search(mic_pattern_stampede2, arch):
            start = slotN * nthreads
            end = ((slotN + 1)* nthreads) - 1
            add_to_command = "numactl -C %d-%d " % (start, end)
            new_command = cd_to_command + add_to_command + command
        else:
            add_to_command = "export OMP_NUM_THREADS=%d;" % nthreads
            new_command = cd_to_command + add_to_command + command

        # self.logger.info(new_command) #can print new_command here to check the command
        return new_command

    def ProcessJobQueue(self, mintime, maxtime):
        """
        Launches jobs waiting in the queue.
        It will scan free nodes and job queue up to maxtime.
        If the queue becomes empty, it will still block until maxtime is elapsed.
        """
        njobs_launched = 0
        usetime = 0
        nreplicas = len(self.replica_to_job)

        while usetime < maxtime:

            # find an available node
            node = self._availableNode()

            while (not self.jobqueue.empty()) and (not node == None):

                # grabs job on top of the queue
                replica = self.jobqueue.get()
                job = self.replica_to_job[replica]

                # assign job to available node
                job['nodeid'] = node
                job['nodename'] = self.compute_nodes[node]["node_name"]
                job['nthreads'] = int(self.compute_nodes[node]["threads_number"])
                job['nslots'] = int(self.compute_nodes[node]["slot_number"])
                job['username'] = self.compute_nodes[node]["user_name"]
                job['arch'] = self.compute_nodes[node]["arch"]
                # get the shell command
                command = job['command']
                # retrieve remote working directory of node
                job["remote_working_directory"] = self.compute_nodes[node]["tmp_folder"] + "/" + job[
                    "remote_replica_dir"]

                command = self.ModifyCommand(job, command)

                if job["remote_working_directory"] and job['job_input_files']:
                    for filename in job['job_input_files']:
                        local_file = job["working_directory"] + "/" + filename
                        remote_file = job["remote_working_directory"] + "/" + filename
                        # self.logger.info("%s %s", local_file, remote_file) #can print out here to verify files

                if self.compute_nodes[node]["arch"]:
                    architecture = self.compute_nodes[node]["arch"]
                else:
                    architecture = ""

                exec_directory = job["exec_directory"]
                lib_directory = exec_directory + "/lib/" + architecture
                bin_directory = exec_directory + "/bin/" + architecture

                job["exec_files"] = []
                for filename in os.listdir(lib_directory):
                    job["exec_files"].append(lib_directory + "/" + filename)
                for filename in os.listdir(bin_directory):
                    job["exec_files"].append(bin_directory + "/" + filename)

                # launches job
                processid = mp.Process(target=self._launchCmd, args=(command, job))
                processid.start()

                job['process_handle'] = processid

                # connects node to replica
                self.replica_to_job[replica] = job
                self.node_status[node] = replica

                # updates number of jobs launched
                njobs_launched += 1
                node = self._availableNode()

            # waits mintime second and rescans job queue
            time.sleep(mintime)

            # updates set of free nodes by checking for replicas that have exited
            for repl in range(nreplicas):
                self.isDone(repl, 0)

            usetime += mintime

        return njobs_launched

    def isDone(self, replica, cycle):
        """
        Checks if a replica completed a run.

        If a replica is done it clears the corresponding node.
        Note that cycle is ignored by job transport. It is assumed that it is
        the latest cycle.  it's kept for argument compatibility with
        hasCompleted() elsewhere.
        """
        job = self.replica_to_job[replica]
        if job == None:
            # if job has been removed we assume that the replica is done
            return True
        else:
            process = job['process_handle']
            if process == None:
                done = False
            else:
                done = not process.is_alive()
            if done:
                # disconnects replica from job and node
                self._clear_resource(replica)

                # attempt to remove item from queues
                try:
                    # wait 30sec, if not raise Queue.Empty exception
                    # this could also be modified to use .get(block=False)
                    # which is equivalent to timeout=0
                    self.logger.info("%s", job['output_queue'].get(timeout=30))
                    self.logger.info("%s", job['error_queue'].get(timeout=30))
                # if the queues timeout, raises a Queue.Empty Exception
                # note this is not a mp.Queue exception; it's from the Queue lib
                except Queue.Empty:
                    self.logger.warn("Error removing items from ssh process communication queues for r%s", replica)

                job['output_queue'].close()
                job['error_queue'].close()
                self.replica_to_job[replica] = None
            return done
