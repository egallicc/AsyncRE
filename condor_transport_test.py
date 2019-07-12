import os
import logging
import subprocess
import pickle
import time
from transport import Transport



    def __init__(self, jobname, nreplicas):
        Transport.__init(self)

        self.logger = logging.getLogger("asyncre.condor_transport")
        self.jobname = jobname
        self.user_name = os.environ['USER']

        self.replica_to_jobid = [None for k in range(nreplicas)]

        self.replica_status = dict()

    def setupTemplateCondorSubmit(self):
        """ Template for Condor submit description file """
        self.condor_submit_file = """
Universe                = vanilla
Executable              = {executable}
Requirements            = 
Arguments               = {input_file}
should_transfer_files   = YES
transfer_input_files    = {job_input_files}
Log                     = {jobname}.log
Error                   = {jobname}.error
Queue

"""

    def restart(self):
        # read replica job id from a saved stat file
        self.logger.info("Reading from saved status file")
        status_file = "%s_condor_stat" % self.jobname
        try:
            with open(status_file, 'r') as file:
                self.replica_to_jobid = pickle.load(file)
                for jobid in self.replica_to_jobid:
                    if not jobid:
                        continue
                    self.replica_status[jobid] = False

        except:
            None

    def save_restart(self):
        # write new job id for replicas to the saved file
        status_file = "%s_condor_stat" % self.jobname
        try:
            with open(status_file, 'w'):
                pickle.dump(self.replica_to_jobid, file)
        except:
            None

    def launchJob(self, replica, job_info):

        if self.replica_to_jobid[replica] != None:
            # a job id already exists for this replica
            cycle = job_info["cycle"]
            self.isDone(replica,cycle)

        input_file = job_info["input_file"]
        executable = job_info["executable"]
        job_input_files = job_info["job_input_files"]
        cycle = job_info["cycle"]
        working_directory = job_info["working_directory"]

        condor_submit_file = self.jobname + 'submit'

        input = self.condor_submit_file.format(
            executable=executable, input_file=input_file,
            job_input_files=job_input_files,
            jobname=self.jobname)

        with open(condor_submit_file, 'w') as submit_file:
            submit_file.write(input)

        launch_command = " cd %s ; condor_submit %s" % (working_directory, condor_submit_file)

        self.logger.info(launch_command)
        launch_job = subprocess.Popen(launch_command, stdout=subprocess.PIPE, stdin=subprocess.PIPE)

        (out, err) = launch_job.communicate()

        try:
            jobid = int(out.split()[-1]) + '0'
        except:
            self.logger.warning("launchJob():Unable to retrieve JobID")
            return None

        old_jobid = self.replica_to_jobid[replica]
        if old_jobid:
            self.logger.info("No longer tracking jobId : %s" % old_jobid)
            self.replica_status.pop(old_jobid)

        self.replica_to_jobid[replica] = jobid
        self.replica_status[jobid] = False
        self.logger.info("Now tracking jobId : %s " % jobid)

        # write the status file with updated jobID
        self.save_restart()

        return 1

    def poll(self, error_wait=10, timeout=86400):

        self.logger.info("Checking from Condor queue")

        initial_jobids = self.replica_status.keys()
        if not initial_jobids:
            self.logger.info("Cannot find any jobids from Condor queue")
            return

        query_queue = "condor_q  -submitter %s -format \"%%d.\" ClusterId -format \"%%d\n\" ProcId" % self.user_name
        self.logger.info(query_queue)
        run_condor_q = subprocess.Popen(query_queue, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        (out, err) = run_condor_q.communicate()
        condor_job_ids = set(out)

        # gets a set of job ids which are not retrieved by Condor and the jobs are assumed to be done.
        # A replica which has never run is assigned a job id None. The following conditional statement and the isDone()
        # method will return that replica as True. Further checking may be needed to streamline the code for suspected
        # bugs

        done_set = set(initial_jobids) - condor_job_ids

        for id in done_set:
            self.replica_status[id] = True

        self.logger.info("Polling Condor queue is complete")

        if not jobids:
            self.logger.info("Cannot find any jobids from Condor queue")
            return

    def ProcessJobQueue(self,mintime, maxtime):
        """
        Just wait until maxtime for Condor to complete the job
        """
        time.sleep(maxtime)

    def isDone(self, replica, cycle):
        """
        Checks if a replica has completed a run. Replica which has never run anytime is also returned as True as
        isDone() looks at the condor_q output query and considers the job complete if condor_q does not return a JobId
        """
        jobid = self.replica_to_jobid[replica]

        if jobid == None:
            return True

        else:
            return self.replica_status[jobid]


if __name__ == "__main__":
    pass