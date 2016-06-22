#!/usr/bin/env python
#-*- coding:utf-8 -*-
#  Copyright (C) 2010-2013  CEA/DEN
#
#  This library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 2.1 of the License.
#
#  This library is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307 USA

import os
import datetime
import time
import paramiko

import src

STYLESHEET_GLOBAL = "jobs_global_report.xsl"
STYLESHEET_TABLE = "jobs_table_report.xsl"

parser = src.options.Options()

parser.add_option('j', 'jobs_config', 'string', 'jobs_cfg', 
                  _('The name of the config file that contains'
                  ' the jobs configuration'))
parser.add_option('o', 'only_jobs', 'list2', 'only_jobs',
                  _('The list of jobs to launch, by their name. '))
parser.add_option('l', 'list', 'boolean', 'list', 
                  _('list all available config files.'))
parser.add_option('n', 'no_label', 'boolean', 'no_label',
                  _("do not print labels, Works only with --list."), False)
parser.add_option('t', 'test_connection', 'boolean', 'test_connection',
                  _("Try to connect to the machines. Not executing the jobs."),
                  False)
parser.add_option('p', 'publish', 'boolean', 'publish',
                  _("Generate an xml file that can be read in a browser to "
                    "display the jobs status."),
                  False)

class Machine(object):
    '''Class to manage a ssh connection on a machine
    '''
    def __init__(self,
                 name,
                 host,
                 user,
                 port=22,
                 passwd=None,
                 sat_path="salomeTools"):
        self.name = name
        self.host = host
        self.port = port
        self.user = user
        self.password = passwd
        self.sat_path = sat_path
        self.ssh = paramiko.SSHClient()
        self._connection_successful = None
    
    def connect(self, logger):
        '''Initiate the ssh connection to the remote machine
        
        :param logger src.logger.Logger: The logger instance 
        :return: Nothing
        :rtype: N\A
        '''

        self._connection_successful = False
        self.ssh.load_system_host_keys()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.ssh.connect(self.host,
                             port=self.port,
                             username=self.user,
                             password = self.password)
        except paramiko.AuthenticationException:
            message = src.KO_STATUS + _("Authentication failed")
        except paramiko.BadHostKeyException:
            message = (src.KO_STATUS + 
                       _("The server's host key could not be verified"))
        except paramiko.SSHException:
            message = ( _("SSHException error connecting or "
                          "establishing an SSH session"))            
        except:
            message = ( _("Error connecting or establishing an SSH session"))
        else:
            self._connection_successful = True
            message = ""
        return message
    
    def successfully_connected(self, logger):
        '''Verify if the connection to the remote machine has succeed
        
        :param logger src.logger.Logger: The logger instance 
        :return: True if the connection has succeed, False if not
        :rtype: bool
        '''
        if self._connection_successful == None:
            message = _("Warning : trying to ask if the connection to "
            "(name: %s host: %s, port: %s, user: %s) is OK whereas there were"
            " no connection request" % 
                        (self.name, self.host, self.port, self.user))
            logger.write( src.printcolors.printcWarning(message))
        return self._connection_successful

    def copy_sat(self, sat_local_path, job_file):
        '''Copy salomeTools to the remote machine in self.sat_path
        '''
        res = 0
        try:
            self.sftp = self.ssh.open_sftp()
            self.mkdir(self.sat_path, ignore_existing=True)
            self.put_dir(sat_local_path, self.sat_path, filters = ['.git'])
            job_file_name = os.path.basename(job_file)
            self.sftp.put(job_file, os.path.join(self.sat_path,
                                                 "data",
                                                 "jobs",
                                                 job_file_name))
        except Exception as e:
            res = str(e)
            self._connection_successful = False
        
        return res
        
    def put_dir(self, source, target, filters = []):
        ''' Uploads the contents of the source directory to the target path. The
            target directory needs to exists. All subdirectories in source are 
            created under target.
        '''
        for item in os.listdir(source):
            if item in filters:
                continue
            source_path = os.path.join(source, item)
            destination_path = os.path.join(target, item)
            if os.path.islink(source_path):
                linkto = os.readlink(source_path)
                try:
                    self.sftp.symlink(linkto, destination_path)
                    self.sftp.chmod(destination_path,
                                    os.stat(source_path).st_mode)
                except IOError:
                    pass
            else:
                if os.path.isfile(source_path):
                    self.sftp.put(source_path, destination_path)
                    self.sftp.chmod(destination_path,
                                    os.stat(source_path).st_mode)
                else:
                    self.mkdir(destination_path, ignore_existing=True)
                    self.put_dir(source_path, destination_path)

    def mkdir(self, path, mode=511, ignore_existing=False):
        ''' Augments mkdir by adding an option to not fail 
            if the folder exists 
        '''
        try:
            self.sftp.mkdir(path, mode)
        except IOError:
            if ignore_existing:
                pass
            else:
                raise       
    
    def exec_command(self, command, logger):
        '''Execute the command on the remote machine
        
        :param command str: The command to be run
        :param logger src.logger.Logger: The logger instance 
        :return: the stdin, stdout, and stderr of the executing command,
                 as a 3-tuple
        :rtype: (paramiko.channel.ChannelFile, paramiko.channel.ChannelFile,
                paramiko.channel.ChannelFile)
        '''
        try:        
            # Does not wait the end of the command
            (stdin, stdout, stderr) = self.ssh.exec_command(command)
        except paramiko.SSHException:
            message = src.KO_STATUS + _(
                            ": the server failed to execute the command\n")
            logger.write( src.printcolors.printcError(message))
            return (None, None, None)
        except:
            logger.write( src.printcolors.printcError(src.KO_STATUS + '\n'))
            return (None, None, None)
        else:
            return (stdin, stdout, stderr)

    def close(self):
        '''Close the ssh connection
        
        :rtype: N\A
        '''
        self.ssh.close()
     
    def write_info(self, logger):
        '''Prints the informations relative to the machine in the logger 
           (terminal traces and log file)
        
        :param logger src.logger.Logger: The logger instance
        :return: Nothing
        :rtype: N\A
        '''
        logger.write("host : " + self.host + "\n")
        logger.write("port : " + str(self.port) + "\n")
        logger.write("user : " + str(self.user) + "\n")
        if self.successfully_connected(logger):
            status = src.OK_STATUS
        else:
            status = src.KO_STATUS
        logger.write("Connection : " + status + "\n\n") 


class Job(object):
    '''Class to manage one job
    '''
    def __init__(self, name, machine, application, distribution, table, 
                 commands, timeout, config, logger, job_file, after=None):

        self.name = name
        self.machine = machine
        self.after = after
        self.timeout = timeout
        self.application = application
        self.distribution = distribution
        self.table = table
        self.config = config
        self.logger = logger
        # The list of log files to download from the remote machine 
        self.remote_log_files = []
        
        # The remote command status
        # -1 means that it has not been launched, 
        # 0 means success and 1 means fail
        self.res_job = "-1"
        self.cancelled = False
        
        self._T0 = -1
        self._Tf = -1
        self._has_begun = False
        self._has_finished = False
        self._has_timouted = False
        self._stdin = None # Store the command inputs field
        self._stdout = None # Store the command outputs field
        self._stderr = None # Store the command errors field

        self.out = None # Contains something only if the job is finished
        self.err = None # Contains something only if the job is finished    
               
        self.commands = commands
        self.command = (os.path.join(self.machine.sat_path, "sat") +
                        " -l " +
                        os.path.join(self.machine.sat_path,
                                     "list_log_files.txt") +
                        " job --jobs_config " +
                        job_file +
                        " --job " +
                        self.name)
    
    def get_pids(self):
        pids = []
        cmd_pid = 'ps aux | grep "' + self.command + '" | awk \'{print $2}\''
        (_, out_pid, _) = self.machine.exec_command(cmd_pid, self.logger)
        pids_cmd = out_pid.readlines()
        pids_cmd = [str(src.only_numbers(pid)) for pid in pids_cmd]
        pids+=pids_cmd
        return pids
    
    def kill_remote_process(self, wait=1):
        '''Kills the process on the remote machine.
        
        :return: (the output of the kill, the error of the kill)
        :rtype: (str, str)
        '''
        
        pids = self.get_pids()
        cmd_kill = " ; ".join([("kill -2 " + pid) for pid in pids])
        (_, out_kill, err_kill) = self.machine.exec_command(cmd_kill, 
                                                            self.logger)
        time.sleep(wait)
        return (out_kill, err_kill)
            
    def has_begun(self):
        '''Returns True if the job has already begun
        
        :return: True if the job has already begun
        :rtype: bool
        '''
        return self._has_begun
    
    def has_finished(self):
        '''Returns True if the job has already finished 
           (i.e. all the commands have been executed)
           If it is finished, the outputs are stored in the fields out and err.
        
        :return: True if the job has already finished
        :rtype: bool
        '''
        
        # If the method has already been called and returned True
        if self._has_finished:
            return True
        
        # If the job has not begun yet
        if not self.has_begun():
            return False
        
        if self._stdout.channel.closed:
            self._has_finished = True
            # Store the result outputs
            self.out = self._stdout.read()
            self.err = self._stderr.read()
            # Put end time
            self._Tf = time.time()
            # And get the remote command status and log files
            self.get_log_files()
        
        return self._has_finished
          
    def get_log_files(self):
        if not self.has_finished():
            msg = _("Trying to get log files whereas the job is not finished.")
            self.logger.write(src.printcolors.printcWarning(msg))
            return
        
        tmp_file_path = src.get_tmp_filename(self.config, "list_log_files.txt")
        self.machine.sftp.get(
                    os.path.join(self.machine.sat_path, "list_log_files.txt"),
                    tmp_file_path)
        
        fstream_tmp = open(tmp_file_path, "r")
        file_lines = fstream_tmp.readlines()
        file_lines = [line.replace("\n", "") for line in file_lines]
        fstream_tmp.close()
        os.remove(tmp_file_path)
        self.res_job = file_lines[0]
        for job_path_remote in file_lines[1:]:
            try:
                if os.path.basename(os.path.dirname(job_path_remote)) != 'OUT':
                    local_path = os.path.join(os.path.dirname(
                                                        self.logger.logFilePath),
                                              os.path.basename(job_path_remote))
                    if not os.path.exists(local_path):
                        self.machine.sftp.get(job_path_remote, local_path)
                else:
                    local_path = os.path.join(os.path.dirname(
                                                        self.logger.logFilePath),
                                              'OUT',
                                              os.path.basename(job_path_remote))
                    if not os.path.exists(local_path):
                        self.machine.sftp.get(job_path_remote, local_path)
                self.remote_log_files.append(local_path)
            except:
                self.err += _("Unable to get %s log file from remote.") % job_path_remote

    def has_failed(self):
        '''Returns True if the job has failed. 
           A job is considered as failed if the machine could not be reached,
           if the remote command failed, 
           or if the job finished with a time out.
        
        :return: True if the job has failed
        :rtype: bool
        '''
        if not self.has_finished():
            return False
        if not self.machine.successfully_connected(self.logger):
            return True
        if self.is_timeout():
            return True
        if self.res_job == "1":
            return True
        return False
    
    def cancel(self):
        """In case of a failing job, one has to cancel every job that depend 
           on it. This method put the job as failed and will not be executed.
        """
        self._has_begun = True
        self._has_finished = True
        self.cancelled = True
        self.out = _("This job was not launched because its father has failed.")
        self.err = _("This job was not launched because its father has failed.")

    def is_running(self):
        '''Returns True if the job commands are running 
        
        :return: True if the job is running
        :rtype: bool
        '''
        return self.has_begun() and not self.has_finished()

    def is_timeout(self):
        '''Returns True if the job commands has finished with timeout 
        
        :return: True if the job has finished with timeout
        :rtype: bool
        '''
        return self._has_timouted

    def time_elapsed(self):
        if not self.has_begun():
            return -1
        T_now = time.time()
        return T_now - self._T0
    
    def check_time(self):
        if not self.has_begun():
            return
        if self.time_elapsed() > self.timeout:
            self._has_finished = True
            self._has_timouted = True
            self._Tf = time.time()
            self.get_pids()
            (out_kill, _) = self.kill_remote_process()
            self.out = "TIMEOUT \n" + out_kill.read()
            self.err = "TIMEOUT : %s seconds elapsed\n" % str(self.timeout)
            try:
                self.get_log_files()
            except:
                self.err += _("Unable to get remote log files")
            
    def total_duration(self):
        return self._Tf - self._T0
        
    def run(self, logger):
        if self.has_begun():
            print("Warn the user that a job can only be launched one time")
            return
        
        if not self.machine.successfully_connected(logger):
            self._has_finished = True
            self.out = "N\A"
            self.err = ("Connection to machine (name : %s, host: %s, port:"
                        " %s, user: %s) has failed\nUse the log command "
                        "to get more information."
                        % (self.machine.name,
                           self.machine.host,
                           self.machine.port,
                           self.machine.user))
        else:
            self._T0 = time.time()
            self._stdin, self._stdout, self._stderr = self.machine.exec_command(
                                                        self.command, logger)
            if (self._stdin, self._stdout, self._stderr) == (None, None, None):
                self._has_finished = True
                self._Tf = time.time()
                self.out = "N\A"
                self.err = "The server failed to execute the command"
        
        self._has_begun = True
    
    def write_results(self, logger):
        logger.write("name : " + self.name + "\n")
        if self.after:
            logger.write("after : %s\n" % self.after)
        logger.write("Time elapsed : %4imin %2is \n" % 
                     (self.total_duration()/60 , self.total_duration()%60))
        if self._T0 != -1:
            logger.write("Begin time : %s\n" % 
                         time.strftime('%Y-%m-%d %H:%M:%S', 
                                       time.localtime(self._T0)) )
        if self._Tf != -1:
            logger.write("End time   : %s\n\n" % 
                         time.strftime('%Y-%m-%d %H:%M:%S', 
                                       time.localtime(self._Tf)) )
        
        machine_head = "Informations about connection :\n"
        underline = (len(machine_head) - 2) * "-"
        logger.write(src.printcolors.printcInfo(machine_head+underline+"\n"))
        self.machine.write_info(logger)
        
        logger.write(src.printcolors.printcInfo("out : \n"))
        if self.out is None:
            logger.write("Unable to get output\n")
        else:
            logger.write(self.out + "\n")
        logger.write(src.printcolors.printcInfo("err : \n"))
        if self.err is None:
            logger.write("Unable to get error\n")
        else:
            logger.write(self.err + "\n")
        
    def get_status(self):
        if not self.machine.successfully_connected(self.logger):
            return "SSH connection KO"
        if not self.has_begun():
            return "Not launched"
        if self.cancelled:
            return "Cancelled"
        if self.is_running():
            return "running since " + time.strftime('%Y-%m-%d %H:%M:%S',
                                                    time.localtime(self._T0))        
        if self.has_finished():
            if self.is_timeout():
                return "Timeout since " + time.strftime('%Y-%m-%d %H:%M:%S',
                                                    time.localtime(self._Tf))
            return "Finished since " + time.strftime('%Y-%m-%d %H:%M:%S',
                                                     time.localtime(self._Tf))
    
class Jobs(object):
    '''Class to manage the jobs to be run
    '''
    def __init__(self,
                 runner,
                 logger,
                 job_file,
                 job_file_path,
                 config_jobs,
                 lenght_columns = 20):
        # The jobs configuration
        self.cfg_jobs = config_jobs
        self.job_file = job_file
        self.job_file_path = job_file_path
        # The machine that will be used today
        self.lmachines = []
        # The list of machine (hosts, port) that will be used today 
        # (a same host can have several machine instances since there 
        # can be several ssh parameters) 
        self.lhosts = []
        # The jobs to be launched today 
        self.ljobs = []
        # The jobs that will not be launched today
        self.ljobs_not_today = []
        self.runner = runner
        self.logger = logger
        # The correlation dictionary between jobs and machines
        self.dic_job_machine = {} 
        self.len_columns = lenght_columns
        
        # the list of jobs that have not been run yet
        self._l_jobs_not_started = []
        # the list of jobs that have already ran 
        self._l_jobs_finished = []
        # the list of jobs that are running 
        self._l_jobs_running = [] 
                
        self.determine_jobs_and_machines()
    
    def define_job(self, job_def, machine):
        '''Takes a pyconf job definition and a machine (from class machine)
           and returns the job instance corresponding to the definition.
        
        :param job_def src.config.Mapping: a job definition 
        :param machine machine: the machine on which the job will run
        :return: The corresponding job in a job class instance
        :rtype: job
        '''
        name = job_def.name
        cmmnds = job_def.commands
        timeout = job_def.timeout
        after = None
        if 'after' in job_def:
            after = job_def.after
        application = None
        if 'application' in job_def:
            application = job_def.application
        distribution = None
        if 'distribution' in job_def:
            distribution = job_def.distribution
        table = None
        if 'table' in job_def:
            table = job_def.table
            
        return Job(name,
                   machine,
                   application,
                   distribution,
                   table,
                   cmmnds,
                   timeout,
                   self.runner.cfg,
                   self.logger,
                   self.job_file,
                   after = after)
    
    def determine_jobs_and_machines(self):
        '''Function that reads the pyconf jobs definition and instantiates all
           the machines and jobs to be done today.

        :return: Nothing
        :rtype: N\A
        '''
        today = datetime.date.weekday(datetime.date.today())
        host_list = []
               
        for job_def in self.cfg_jobs.jobs :
                
            if not "machine" in job_def:
                msg = _('WARNING: The job "%s" do not have the key '
                       '"machine", this job is ignored.\n\n' % job_def.name)
                self.logger.write(src.printcolors.printcWarning(msg))
                continue
            name_machine = job_def.machine
            
            a_machine = None
            for mach in self.lmachines:
                if mach.name == name_machine:
                    a_machine = mach
                    break
            
            if a_machine == None:
                for machine_def in self.cfg_jobs.machines:
                    if machine_def.name == name_machine:
                        if 'host' not in machine_def:
                            host = self.runner.cfg.VARS.hostname
                        else:
                            host = machine_def.host

                        if 'user' not in machine_def:
                            user = self.runner.cfg.VARS.user
                        else:
                            user = machine_def.user

                        if 'port' not in machine_def:
                            port = 22
                        else:
                            port = machine_def.port
            
                        if 'password' not in machine_def:
                            passwd = None
                        else:
                            passwd = machine_def.password    
                            
                        if 'sat_path' not in machine_def:
                            sat_path = "salomeTools"
                        else:
                            sat_path = machine_def.sat_path
                        
                        a_machine = Machine(
                                            machine_def.name,
                                            host,
                                            user,
                                            port=port,
                                            passwd=passwd,
                                            sat_path=sat_path
                                            )
                        
                        self.lmachines.append(a_machine)
                        if (host, port) not in host_list:
                            host_list.append((host, port))
                
                if a_machine == None:
                    msg = _("WARNING: The job \"%(job_name)s\" requires the "
                            "machine \"%(machine_name)s\" but this machine "
                            "is not defined in the configuration file.\n"
                            "The job will not be launched")
                    self.logger.write(src.printcolors.printcWarning(msg))
                                  
            a_job = self.define_job(job_def, a_machine)
            self.dic_job_machine[a_job] = a_machine
                
            if today in job_def.when:    
                self.ljobs.append(a_job)
            else: # today in job_def.when
                self.ljobs_not_today.append(a_job)
                                     
        self.lhosts = host_list
        
    def ssh_connection_all_machines(self, pad=50):
        '''Function that do the ssh connection to every machine 
           to be used today.

        :return: Nothing
        :rtype: N\A
        '''
        self.logger.write(src.printcolors.printcInfo((
                        "Establishing connection with all the machines :\n")))
        for machine in self.lmachines:
            # little algorithm in order to display traces
            begin_line = (_("Connection to %s: " % machine.name))
            if pad - len(begin_line) < 0:
                endline = " "
            else:
                endline = (pad - len(begin_line)) * "." + " "
            
            step = "SSH connection"
            self.logger.write( begin_line + endline + step)
            self.logger.flush()
            # the call to the method that initiate the ssh connection
            msg = machine.connect(self.logger)
            
            # Copy salomeTools to the remote machine
            if machine.successfully_connected(self.logger):
                step = _("Copy SAT")
                self.logger.write('\r%s%s%s' % (begin_line, endline, 20 * " "),3)
                self.logger.write('\r%s%s%s' % (begin_line, endline, step), 3)
                self.logger.flush()
                res_copy = machine.copy_sat(self.runner.cfg.VARS.salometoolsway,
                                            self.job_file_path)
                # Print the status of the copy
                if res_copy == 0:
                    self.logger.write('\r%s' % 
                                ((len(begin_line)+len(endline)+20) * " "), 3)
                    self.logger.write('\r%s%s%s' % 
                        (begin_line, 
                         endline, 
                         src.printcolors.printc(src.OK_STATUS)), 3)
                else:
                    self.logger.write('\r%s' % 
                            ((len(begin_line)+len(endline)+20) * " "), 3)
                    self.logger.write('\r%s%s%s %s' % 
                        (begin_line,
                         endline,
                         src.printcolors.printc(src.OK_STATUS),
                         _("Copy of SAT failed")), 3)
            else:
                self.logger.write('\r%s' % 
                                  ((len(begin_line)+len(endline)+20) * " "), 3)
                self.logger.write('\r%s%s%s %s' % 
                    (begin_line,
                     endline,
                     src.printcolors.printc(src.KO_STATUS),
                     msg), 3)
            self.logger.write("\n", 3)
                
        self.logger.write("\n")
        

    def is_occupied(self, hostname):
        '''Function that returns True if a job is running on 
           the machine defined by its host and its port.
        
        :param hostname (str, int): the pair (host, port)
        :return: the job that is running on the host, 
                or false if there is no job running on the host. 
        :rtype: job / bool
        '''
        host = hostname[0]
        port = hostname[1]
        for jb in self.dic_job_machine:
            if jb.machine.host == host and jb.machine.port == port:
                if jb.is_running():
                    return jb
        return False
    
    def update_jobs_states_list(self):
        '''Function that updates the lists that store the currently
           running jobs and the jobs that have already finished.
        
        :return: Nothing. 
        :rtype: N\A
        '''
        jobs_finished_list = []
        jobs_running_list = []
        for jb in self.dic_job_machine:
            if jb.is_running():
                jobs_running_list.append(jb)
                jb.check_time()
            if jb.has_finished():
                jobs_finished_list.append(jb)
        
        nb_job_finished_before = len(self._l_jobs_finished)
        self._l_jobs_finished = jobs_finished_list
        self._l_jobs_running = jobs_running_list
        
        nb_job_finished_now = len(self._l_jobs_finished)
        
        return nb_job_finished_now > nb_job_finished_before
    
    def cancel_dependencies_of_failing_jobs(self):
        '''Function that cancels all the jobs that depend on a failing one.
        
        :return: Nothing. 
        :rtype: N\A
        '''
        
        for job in self.ljobs:
            if job.after is None:
                continue
            father_job = self.find_job_that_has_name(job.after)
            if father_job.has_failed():
                job.cancel()
    
    def find_job_that_has_name(self, name):
        '''Returns the job by its name.
        
        :param name str: a job name
        :return: the job that has the name. 
        :rtype: job
        '''
        for jb in self.ljobs:
            if jb.name == name:
                return jb

        # the following is executed only if the job was not found
        msg = _('The job "%s" seems to be nonexistent') % name
        raise src.SatException(msg)
    
    def str_of_length(self, text, length):
        '''Takes a string text of any length and returns 
           the most close string of length "length".
        
        :param text str: any string
        :param length int: a length for the returned string
        :return: the most close string of length "length"
        :rtype: str
        '''
        if len(text) > length:
            text_out = text[:length-3] + '...'
        else:
            diff = length - len(text)
            before = " " * (diff/2)
            after = " " * (diff/2 + diff%2)
            text_out = before + text + after
            
        return text_out
    
    def display_status(self, len_col):
        '''Takes a lenght and construct the display of the current status 
           of the jobs in an array that has a column for each host.
           It displays the job that is currently running on the host 
           of the column.
        
        :param len_col int: the size of the column 
        :return: Nothing
        :rtype: N\A
        '''
        
        display_line = ""
        for host_port in self.lhosts:
            jb = self.is_occupied(host_port)
            if not jb: # nothing running on the host
                empty = self.str_of_length("empty", len_col)
                display_line += "|" + empty 
            else:
                display_line += "|" + src.printcolors.printcInfo(
                                        self.str_of_length(jb.name, len_col))
        
        self.logger.write("\r" + display_line + "|")
        self.logger.flush()
    

    def run_jobs(self):
        '''The main method. Runs all the jobs on every host. 
           For each host, at a given time, only one job can be running.
           The jobs that have the field after (that contain the job that has
           to be run before it) are run after the previous job.
           This method stops when all the jobs are finished.
        
        :return: Nothing
        :rtype: N\A
        '''

        # Print header
        self.logger.write(src.printcolors.printcInfo(
                                                _('Executing the jobs :\n')))
        text_line = ""
        for host_port in self.lhosts:
            host = host_port[0]
            port = host_port[1]
            if port == 22: # default value
                text_line += "|" + self.str_of_length(host, self.len_columns)
            else:
                text_line += "|" + self.str_of_length(
                                "("+host+", "+str(port)+")", self.len_columns)
        
        tiret_line = " " + "-"*(len(text_line)-1) + "\n"
        self.logger.write(tiret_line)
        self.logger.write(text_line + "|\n")
        self.logger.write(tiret_line)
        self.logger.flush()
        
        # The infinite loop that runs the jobs
        l_jobs_not_started = self.dic_job_machine.keys()
        while len(self._l_jobs_finished) != len(self.dic_job_machine.keys()):
            new_job_start = False
            for host_port in self.lhosts:
                
                if self.is_occupied(host_port):
                    continue
             
                for jb in l_jobs_not_started:
                    if (jb.machine.host, jb.machine.port) != host_port:
                        continue 
                    if jb.after == None:
                        jb.run(self.logger)
                        l_jobs_not_started.remove(jb)
                        new_job_start = True
                        break
                    else:
                        jb_before = self.find_job_that_has_name(jb.after) 
                        if jb_before.has_finished():
                            jb.run(self.logger)
                            l_jobs_not_started.remove(jb)
                            new_job_start = True
                            break
            self.cancel_dependencies_of_failing_jobs()
            new_job_finished = self.update_jobs_states_list()
            
            if new_job_start or new_job_finished:
                self.gui.update_xml_files(self.ljobs)            
                # Display the current status     
                self.display_status(self.len_columns)
            
            # Make sure that the proc is not entirely busy
            time.sleep(0.001)
        
        self.logger.write("\n")    
        self.logger.write(tiret_line)                   
        self.logger.write("\n\n")
        
        self.gui.update_xml_files(self.ljobs)
        self.gui.last_update()

    def write_all_results(self):
        '''Display all the jobs outputs.
        
        :return: Nothing
        :rtype: N\A
        '''
        
        for jb in self.dic_job_machine.keys():
            self.logger.write(src.printcolors.printcLabel(
                        "#------- Results for job %s -------#\n" % jb.name))
            jb.write_results(self.logger)
            self.logger.write("\n\n")

class Gui(object):
    '''Class to manage the the xml data that can be displayed in a browser to
       see the jobs states
    '''
   
    def __init__(self, xml_dir_path, l_jobs, l_jobs_not_today):
        '''Initialization
        
        :param xml_dir_path str: The path to the directory where to put 
                                 the xml resulting files
        :param l_jobs List: the list of jobs that run today
        :param l_jobs_not_today List: the list of jobs that do not run today
        '''
        # The path of the global xml file
        self.xml_dir_path = xml_dir_path
        # Initialize the xml files
        xml_global_path = os.path.join(self.xml_dir_path, "global_report.xml")
        self.xml_global_file = src.xmlManager.XmlLogFile(xml_global_path,
                                                         "JobsReport")
        # The xml files that corresponds to the tables.
        # {name_table : xml_object}}
        self.d_xml_table_files = {}
        # Create the lines and columns
        self.initialize_arrays(l_jobs, l_jobs_not_today)
        # Write the xml file
        self.update_xml_files(l_jobs)
    
    def initialize_arrays(self, l_jobs, l_jobs_not_today):
        '''Get all the first information needed for each file and write the 
           first version of the files   
        :param l_jobs List: the list of jobs that run today
        :param l_jobs_not_today List: the list of jobs that do not run today
        '''
        # Get the tables to fill and put it in a dictionary
        # {table_name : xml instance corresponding to the table}
        for job in l_jobs + l_jobs_not_today:
            table = job.table
            if (table is not None and 
                    table not in self.d_xml_table_files.keys()):
                xml_table_path = os.path.join(self.xml_dir_path, table + ".xml")
                self.d_xml_table_files[table] =  src.xmlManager.XmlLogFile(
                                                            xml_table_path,
                                                            "JobsReport")
                self.d_xml_table_files[table].add_simple_node("distributions")
                self.d_xml_table_files[table].add_simple_node("applications")
                self.d_xml_table_files[table].add_simple_node("table", text=table)
        
        # Loop over all jobs in order to get the lines and columns for each 
        # xml file
        d_dist = {}
        d_application = {}
        for table in self.d_xml_table_files:
            d_dist[table] = []
            d_application[table] = []
            
        l_hosts_ports = []
            
        for job in l_jobs + l_jobs_not_today:
            
            if (job.machine.host, job.machine.port) not in l_hosts_ports:
                l_hosts_ports.append((job.machine.host, job.machine.port))
                
            distrib = job.distribution
            application = job.application
            
            table_job = job.table
            if table is None:
                continue
            for table in self.d_xml_table_files:
                if table_job == table:
                    if distrib is not None and distrib not in d_dist[table]:
                        d_dist[table].append(distrib)
                        src.xmlManager.add_simple_node(
                            self.d_xml_table_files[table].xmlroot.find('distributions'),
                                                   "dist",
                                                   attrib={"name" : distrib})
                    
                if table_job == table:
                    if application is not None and application not in d_application[table]:
                        d_application[table].append(application)
                        src.xmlManager.add_simple_node(self.d_xml_table_files[table].xmlroot.find('applications'),
                                                   "application",
                                                   attrib={"name" : application})

        # Initialize the hosts_ports node for the global file
        self.xmlhosts_ports = self.xml_global_file.add_simple_node("hosts_ports")
        for host, port in l_hosts_ports:
            host_port = "%s:%i" % (host, port)
            src.xmlManager.add_simple_node(self.xmlhosts_ports,
                                           "host_port",
                                           attrib={"name" : host_port})
        
        # Initialize the jobs node in all files
        for xml_file in [self.xml_global_file] + self.d_xml_table_files.values():
            xml_jobs = xml_file.add_simple_node("jobs")      
            # Get the jobs present in the config file but that will not be launched
            # today
            self.put_jobs_not_today(l_jobs_not_today, xml_jobs)
            
            xml_file.add_simple_node("infos", attrib={"name" : "last update", "JobsCommandStatus" : "running"})

    
    def put_jobs_not_today(self, l_jobs_not_today, xml_node_jobs):
        '''Get all the first information needed for each file and write the 
           first version of the files   

        :param xml_node_jobs etree.Element: the node corresponding to a job
        :param l_jobs_not_today List: the list of jobs that do not run today
        '''
        for job in l_jobs_not_today:
            xmlj = src.xmlManager.add_simple_node(xml_node_jobs,
                                                 "job",
                                                 attrib={"name" : job.name})
            src.xmlManager.add_simple_node(xmlj, "application", job.application)
            src.xmlManager.add_simple_node(xmlj,
                                           "distribution",
                                           job.distribution)
            src.xmlManager.add_simple_node(xmlj, "table", job.table)
            src.xmlManager.add_simple_node(xmlj,
                                       "commands", " ; ".join(job.commands))
            src.xmlManager.add_simple_node(xmlj, "state", "Not today")
            src.xmlManager.add_simple_node(xmlj, "machine", job.machine.name)
            src.xmlManager.add_simple_node(xmlj, "host", job.machine.host)
            src.xmlManager.add_simple_node(xmlj, "port", str(job.machine.port))
            src.xmlManager.add_simple_node(xmlj, "user", job.machine.user)
            src.xmlManager.add_simple_node(xmlj, "sat_path",
                                                        job.machine.sat_path)
    
    def update_xml_files(self, l_jobs):
        '''Write all the xml files with updated information about the jobs   

        :param l_jobs List: the list of jobs that run today
        '''
        for xml_file in [self.xml_global_file] + self.d_xml_table_files.values():
            self.update_xml_file(l_jobs, xml_file)
            
        # Write the file
        self.write_xml_files()
            
    def update_xml_file(self, l_jobs, xml_file):      
        '''update information about the jobs for the file xml_file   

        :param l_jobs List: the list of jobs that run today
        :param xml_file xmlManager.XmlLogFile: the xml instance to update
        '''
        
        xml_node_jobs = xml_file.xmlroot.find('jobs')
        # Update the job names and status node
        for job in l_jobs:
            # Find the node corresponding to the job and delete it
            # in order to recreate it
            for xmljob in xml_node_jobs.findall('job'):
                if xmljob.attrib['name'] == job.name:
                    xml_node_jobs.remove(xmljob)
            
            T0 = str(job._T0)
            if T0 != "-1":
                T0 = time.strftime('%Y-%m-%d %H:%M:%S', 
                                       time.localtime(job._T0))
            Tf = str(job._Tf)
            if Tf != "-1":
                Tf = time.strftime('%Y-%m-%d %H:%M:%S', 
                                       time.localtime(job._Tf))
            
            # recreate the job node
            xmlj = src.xmlManager.add_simple_node(xml_node_jobs,
                                                  "job",
                                                  attrib={"name" : job.name})
            src.xmlManager.add_simple_node(xmlj, "machine", job.machine.name)
            src.xmlManager.add_simple_node(xmlj, "host", job.machine.host)
            src.xmlManager.add_simple_node(xmlj, "port", str(job.machine.port))
            src.xmlManager.add_simple_node(xmlj, "user", job.machine.user)
            src.xmlManager.add_simple_node(xmlj, "sat_path",
                                           job.machine.sat_path)
            src.xmlManager.add_simple_node(xmlj, "application", job.application)
            src.xmlManager.add_simple_node(xmlj, "distribution",
                                           job.distribution)
            src.xmlManager.add_simple_node(xmlj, "table", job.table)
            src.xmlManager.add_simple_node(xmlj, "timeout", str(job.timeout))
            src.xmlManager.add_simple_node(xmlj, "commands",
                                           " ; ".join(job.commands))
            src.xmlManager.add_simple_node(xmlj, "state", job.get_status())
            src.xmlManager.add_simple_node(xmlj, "begin", T0)
            src.xmlManager.add_simple_node(xmlj, "end", Tf)
            src.xmlManager.add_simple_node(xmlj, "out",
                                           src.printcolors.cleancolor(job.out))
            src.xmlManager.add_simple_node(xmlj, "err",
                                           src.printcolors.cleancolor(job.err))
            src.xmlManager.add_simple_node(xmlj, "res", str(job.res_job))
            if len(job.remote_log_files) > 0:
                src.xmlManager.add_simple_node(xmlj,
                                               "remote_log_file_path",
                                               job.remote_log_files[0])
            else:
                src.xmlManager.add_simple_node(xmlj,
                                               "remote_log_file_path",
                                               "nothing")           
            
            xmlafter = src.xmlManager.add_simple_node(xmlj, "after", job.after)
            # get the job father
            if job.after is not None:
                job_father = None
                for jb in l_jobs:
                    if jb.name == job.after:
                        job_father = jb
                if job_father is None:
                    msg = _("The job %(father_name)s that is parent of "
                            "%(son_name)s is not in the job list." %
                            {"father_name" : job.after , "son_name" : job.name})
                    raise src.SatException(msg)
                
                if len(job_father.remote_log_files) > 0:
                    link = job_father.remote_log_files[0]
                else:
                    link = "nothing"
                src.xmlManager.append_node_attrib(xmlafter, {"link" : link})
            
        
        # Update the date
        xml_node_infos = xml_file.xmlroot.find('infos')
        src.xmlManager.append_node_attrib(xml_node_infos,
                    attrib={"value" : 
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
               

    
    def last_update(self, finish_status = "finished"):
        '''update information about the jobs for the file xml_file   

        :param l_jobs List: the list of jobs that run today
        :param xml_file xmlManager.XmlLogFile: the xml instance to update
        '''
        for xml_file in [self.xml_global_file] + self.d_xml_table_files.values():
            xml_node_infos = xml_file.xmlroot.find('infos')
            src.xmlManager.append_node_attrib(xml_node_infos,
                        attrib={"JobsCommandStatus" : finish_status})
        # Write the file
        self.write_xml_files()
    
    def write_xml_files(self):
        ''' Write the xml files   
        '''
        self.xml_global_file.write_tree(STYLESHEET_GLOBAL)
        for xml_file in self.d_xml_table_files.values():
            xml_file.write_tree(STYLESHEET_TABLE)
        
##
# Describes the command
def description():
    return _("The jobs command launches maintenances that are described"
             " in the dedicated jobs configuration file.")

##
# Runs the command.
def run(args, runner, logger):
       
    (options, args) = parser.parse_args(args)
       
    jobs_cfg_files_dir = runner.cfg.SITE.jobs.config_path
    
    l_cfg_dir = [jobs_cfg_files_dir,
                 os.path.join(runner.cfg.VARS.datadir, "jobs")]
    
    # Make sure the path to the jobs config files directory exists 
    src.ensure_path_exists(jobs_cfg_files_dir)   
    
    # list option : display all the available config files
    if options.list:
        for cfg_dir in l_cfg_dir:
            if not options.no_label:
                logger.write("------ %s\n" % 
                                 src.printcolors.printcHeader(cfg_dir))
    
            for f in sorted(os.listdir(cfg_dir)):
                if not f.endswith('.pyconf'):
                    continue
                cfilename = f[:-7]
                logger.write("%s\n" % cfilename)
        return 0

    # Make sure the jobs_config option has been called
    if not options.jobs_cfg:
        message = _("The option --jobs_config is required\n")      
        raise src.SatException( message )
    
    # Find the file in the directories
    found = False
    for cfg_dir in l_cfg_dir:
        file_jobs_cfg = os.path.join(cfg_dir, options.jobs_cfg)
        if not file_jobs_cfg.endswith('.pyconf'):
            file_jobs_cfg += '.pyconf'
        
        if not os.path.exists(file_jobs_cfg):
            continue
        else:
            found = True
            break
    
    if not found:
        msg = _("The file configuration %(name_file)s was not found."
                "\nUse the --list option to get the possible files.")
        src.printcolors.printcError(msg)
        return 1
    
    info = [
        (_("Platform"), runner.cfg.VARS.dist),
        (_("File containing the jobs configuration"), file_jobs_cfg)
    ]    
    src.print_info(logger, info)
    
    # Read the config that is in the file
    config_jobs = src.read_config_from_a_file(file_jobs_cfg)
    if options.only_jobs:
        l_jb = src.pyconf.Sequence()
        for jb in config_jobs.jobs:
            if jb.name in options.only_jobs:
                l_jb.append(jb,
                "Adding a job that was given in only_jobs option parameters")
        config_jobs.jobs = l_jb
              
    # Initialization
    today_jobs = Jobs(runner,
                      logger,
                      options.jobs_cfg,
                      file_jobs_cfg,
                      config_jobs)
    # SSH connection to all machines
    today_jobs.ssh_connection_all_machines()
    if options.test_connection:
        return 0
    
    gui = None
    if options.publish:
        gui = Gui("/export/home/serioja/LOGS",
                  today_jobs.ljobs,
                  today_jobs.ljobs_not_today,)
    
    today_jobs.gui = gui
    
    interruped = False
    try:
        # Run all the jobs contained in config_jobs
        today_jobs.run_jobs()
    except KeyboardInterrupt:
        interruped = True
        logger.write("\n\n%s\n\n" % 
                (src.printcolors.printcWarning(_("Forced interruption"))), 1)
        
    finally:
        # find the potential not finished jobs and kill them
        for jb in today_jobs.ljobs:
            if not jb.has_finished():
                jb.kill_remote_process()
        if interruped:
            today_jobs.gui.last_update(_("Forced interruption"))
        else:
            today_jobs.gui.last_update()
        # Output the results
        today_jobs.write_all_results()