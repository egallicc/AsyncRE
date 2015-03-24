ASyncRE
==============

ASynchronous Replica Exchange (ASyncRE) is an extensible Python package enabling file-based larg-scale asynchronous parallel replica exchange molecular simulations on grid computing networks consisting of heterogeneous and distributed computing environments as well as on homogeneous high performance clusters, using the job transporting of SSH or BOINC distributed network. 

Replica Exchange (RE) is a popular generalized ensemble approach for the efficient sampling of conformations of molecular systems. In RE, the system is simulated at several states differing in thermodynamic environmental parameters (temperature, for example) and/or potential energy settings (biasing potentials, etc). Multiple copies (replicas) of the system are simulated at each state in such a way that, in addition to traveling in conformational space, they also travel in state space by means of periodic reassignments of states to replicas. Traditional synchronous implementations of RE are limited in terms of robustness and scaling because all of the replicas are simulated at the same time and state reassignments require stopping all of the replicas. In Asynchronous RE replicas run independently from each other, allowing simulations involving hundreds of replicas on distributed, dynamic and/or unreliable computing resources.

The basic idea of ASyncRE is to assign all replicas to either the running or the waiting lists, and allowing a subset of replicas in the waiting list to perform exchanges independently from the other replicas on the running list. In the previous version of ASyncRE (https://github.com/saga-project/asyncre-bigjob), the BigJob framework is used for launching, monitoring, and managing replicas on NSF XSEDE high performance resources. In the new release, to hide most of the complexities of resource allocation and job scheduling on a variety of architectures from large national supercomputing clusters to local departmental resources, we have implemented two different job transport systems: SSH transport for high performance cluster resources (such as those of XSEDE), and the BOINC transport for distributed computing on campus grid networks. State exchanges are performed for idle replicas via the filesystem by extracting and modifying data on the input/output files of the MD engine while other replicas continue to run. Support for arbitrary RE approaches is provided by simple user-provided adaptor modules which in general do not require source code-level modifications of legacy simulation engines. Currently, adaptor modules exist for BEDAM binding free energy calculations with IMPACT.

The newest version of ASyncRE is by default running multi-architecture for SSH. The core strategy behind multi-architecture is copying all the required files, including lib files, bin files, and input files to a remote directory in a remote client to do the simulation. After the simulation is finished, the necessary files will be copied back to the host, and the remaining files will be deleted. The big advantage of this strategy is that no file-transfer is needed between the host and the remote client during the simulation, which greatly improve the performance, especially for the simulation running in the newest intel coprocessor(MIC) system.

For the newest ASyncRE package, there are three changes need to be pointed out.

(1) The runimpact file has been changed. Now, only the directory path of lib files and the executive command are needed
export LD_LIBRARY_PATH=.:$LD_LIBRARY_PATH
./main1m $1

(2) The nodefile is needed to be pre-set up. There should be six columns in the nodefile file. They are 'node name', 'slot number', 'number of threads', 'system architect','username', and 'name of the remote temperary folder'. 
    --'node name' represents the name of the remote client
    --'slot number' represents the initial slot number in special type architecture in the remote client. For CPU architecture, this number is irrelevant, it can be assigned to any number, but for MIC architecture, this number must be assigned as 0,1,2,3,4,5,6,7,8,9, total ten numbers for 60 cores in MIC. In case the MIC has less than 60 cores, the total numbers need to be decreased.
    --'number of threads' represents how many threads (MIC) or cores (CPU) for one job. Right now, for the CPU architecture, the number of threads can be assigned as you want. For the MIC architecture, this number can only be set to be 24. 
    --'system architect' represents which kind of architecture you want to use to run one job. The available choices are as follows:
	--'Linux-mic' for intel coprocessor(MIC) architecture
	--'Linux-x86_64_icc' for CPU architecture in which the C++ compiler is intel C++ compiler
	--'Linux-x86_64' for CPU architecture in which the C++ compiler is general gcc compiler running in ubuntu 14.0 OS
	--'Linux-x86_64_12.0' for CPU architecture in which the C++ compiler is general gcc compiler running in ubuntu 12.0 OS
    --'username' represents the username in the remote client. Right now, this column is simply set as empty ''
    --'name of the remote temperary folder" represents the name of the remote directory in the remote client. Generally it is set as '/tmp', however, it can be set to any name.
    Convenientlly, this nodefile can be automatically generated in the bedam_workflow package for running in the XSEDE clusters.

(3) In this version, if the simulation is running in the intel coprocessor(MIC), the default setup is using 24 threads (6 cores, 4 threads per core) to run the simulation, and this default setup can not be changed. The more flexible setup will be provided in the next version.

The runimpact template and nodefile template can be found in the examples.

Web Pages
---------

ASyncRE: https://github.com/ComputationalBiophysicsCollaborative/AsyncRE

Installation
------------

ASyncRE depends on few modules which are easily installed from PiP: 

    pip install numpy
    pip install configobj
    pip install scp
    pip install paramiko

ASyncRE is currently distributed only by git:

    git clone https://github.com/ComputationalBiophysicsCollaborative/AsyncRE.git
    cd asyncre
    python setup.py install

A distribution archive can be created by issuing the command:

    python setup.py sdist

after which async_re-<version>.tar.gz will be found under dist/

Installation from the distribution archive:

    cd dist
    pip install async_re-<version>.tar.gz


Test
----

To test execute the "date" application

    python date_async_re.py command.inp

which will spawn a bunch of /bin/date replicas.

Test BEDAM SyncRE
----

To execute the BEDAM SyncRE

In the folder examples/bcd_benzene_BEDAM_RE

Changing the nodefile and binding.cntl files to your setup

Then in the virtual python, run

    python ../../bedamtempt_async_re.py binding.cntl

Test Temperature SyncRE
----

To execute the Temperature SyncRE

In the folder examples/temperature_RE

Changing the nodefile and linearwt_asyncre.cnt files to your setup

Then in the virtual python, run

    python ../../tempt_async_re.py linearwt_asyncre.cntl

See additional sample application files under the examples/ subdirectory.

