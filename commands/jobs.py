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

class machine(object):
    '''Class to manage a ssh connection on a machine
    '''
    def __init__(self, name, host, user, port=22, passwd=None, sat_path="salomeTools"):
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
            message = "Warning : trying to ask if the connection to "
            "(host: %s, port: %s, user: %s) is OK whereas there were"
            " no connection request" % \
            (machine.host, machine.port, machine.user)
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


class job(object):
    '''Class to manage one job
    '''
    def __init__(self, name, machine, application, distribution,
                 commands, timeout, logger, job_file, after=None):

        self.name = name
        self.machine = machine
        self.after = after
        self.timeout = timeout
        self.application = application
        self.distribution = distribution
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
                        " -v1 job --jobs_config " +
                        job_file +
                        " --job " +
                        self.name)
    
    def get_pids(self):
        pids = []
        cmd_pid = 'ps aux | grep "sat -v1 job --jobs_config" | awk \'{print $2}\''
        (_, out_pid, _) = self.machine.exec_command(cmd_pid, self.logger)
        pids_cmd = out_pid.readlines()
        pids_cmd = [str(src.only_numbers(pid)) for pid in pids_cmd]
        pids+=pids_cmd
        return pids
    
    def kill_remote_process(self):
        '''Kills the process on the remote machine.
        
        :return: (the output of the kill, the error of the kill)
        :rtype: (str, str)
        '''
        
        pids = self.get_pids()
        cmd_kill = " ; ".join([("kill -9 " + pid) for pid in pids])
        (_, out_kill, err_kill) = self.machine.exec_command(cmd_kill, 
                                                            self.logger)
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
    
    def get_log_files(self):
        if not self.has_finished():
            msg = _("Trying to get log files whereas the job is not finished.")
            self.logger.write(src.printcolors.printcWarning(msg))
            return
        out_lines = self.out.split("\n")
        out_lines = [line for line in out_lines if line != '']
        self.res_job = out_lines[0]
        for job_path_remote in out_lines[1:]:
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
    
    def total_duration(self):
        return self._Tf - self._T0
        
    def run(self, logger):
        if self.has_begun():
            print("Warn the user that a job can only be launched one time")
            return
        
        if not self.machine.successfully_connected(logger):
            self._has_finished = True
            self.out = "N\A"
            self.err = ("Connection to machine (name : %s, host: %s, port: %s, user: %s) has failed\nUse the log command to get more information." 
                        % (self.machine.name, self.machine.host, self.machine.port, self.machine.user))
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
        self.ljobsdef_not_today = []
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
                
        self.determine_products_and_machines()
    
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
            
        return job(name,
                   machine,
                   application,
                   distribution,
                   cmmnds,
                   timeout,
                   self.logger,
                   self.job_file,
                   after = after)
    
    def determine_products_and_machines(self):
        '''Function that reads the pyconf jobs definition and instantiates all
           the machines and jobs to be done today.

        :return: Nothing
        :rtype: N\A
        '''
        today = datetime.date.weekday(datetime.date.today())
        host_list = []
               
        for job_def in self.cfg_jobs.jobs :
            if today in job_def.when:
                
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
                            
                            a_machine = machine(
                                                machine_def.name,
                                                host,
                                                user,
                                                port=port,
                                                passwd=passwd,
                                                sat_path=sat_path
                                                )
                            
                            if (host, port) not in host_list:
                                host_list.append((host, port))
                                             
                            self.lmachines.append(a_machine)
                
                if a_machine == None:
                    msg = _("WARNING: The job \"%(job_name)s\" requires the "
                            "machine \"%(machine_name)s\" but this machine "
                            "is not defined in the configuration file.\n"
                            "The job will not be launched")
                    self.logger.write(src.printcolors.printcWarning(msg))
                                  
                a_job = self.define_job(job_def, a_machine)
                self.dic_job_machine[a_job] = a_machine
                
                self.ljobs.append(a_job)
            else: # today in job_def.when
                self.ljobsdef_not_today.append(job_def)
                                     
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
                self.gui.update_xml_file(self.ljobs)            
                # Display the current status     
                self.display_status(self.len_columns)
            
            # Make sure that the proc is not entirely busy
            time.sleep(0.001)
        
        self.logger.write("\n")    
        self.logger.write(tiret_line)                   
        self.logger.write("\n\n")
        
        self.gui.update_xml_file(self.ljobs)
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
    
    """
    <?xml version='1.0' encoding='utf-8'?>
    <?xml-stylesheet type='text/xsl' href='job_report.xsl'?>
    <JobsReport>
      <infos>
        <info name="generated" value="2016-06-02 07:06:45"/>
      </infos>
      <hosts>
          <host name=is221553 port=22 distribution=UB12.04/>
          <host name=is221560 port=22/>
          <host name=is221553 port=22 distribution=FD20/>
      </hosts>
      <applications>
          <application name=SALOME-7.8.0/>
          <application name=SALOME-master/>
          <application name=MED-STANDALONE-master/>
          <application name=CORPUS/>
      </applications>
      
      <jobs>
          <job name="7.8.0 FD22">
                <host>is228809</host>
                <port>2200</port>
                <application>SALOME-7.8.0</application>
                <user>adminuser</user>
                <timeout>240</timeout>
                <commands>
                    export DISPLAY=is221560
                    scp -p salome@is221560.intra.cea.fr:/export/home/salome/SALOME-7.7.1p1-src.tgz /local/adminuser         
                    tar xf /local/adminuser/SALOME-7.7.1p1-src.tgz -C /local/adminuser
                </commands>
                <state>Not launched</state>
          </job>

          <job name="master MG05">
                <host>is221560</host>
                <port>22</port>
                <application>SALOME-master</application>
                <user>salome</user>
                <timeout>240</timeout>
                <commands>
                    export DISPLAY=is221560
                    scp -p salome@is221560.intra.cea.fr:/export/home/salome/SALOME-7.7.1p1-src.tgz /local/adminuser         
                    sat prepare SALOME-master
                    sat compile SALOME-master
                    sat check SALOME-master
                    sat launcher SALOME-master
                    sat test SALOME-master
                </commands>
                <state>Running since 23 min</state>
                <!-- <state>time out</state> -->
                <!-- <state>OK</state> -->
                <!-- <state>KO</state> -->
                <begin>10/05/2016 20h32</begin>
                <end>10/05/2016 22h59</end>
          </job>

      </jobs>
    </JobsReport>
    
    """
    
    def __init__(self, xml_file_path, l_jobs, l_jobs_not_today, stylesheet):
        # The path of the xml file
        self.xml_file_path = xml_file_path
        # The stylesheet
        self.stylesheet = stylesheet
        # Open the file in a writing stream
        self.xml_file = src.xmlManager.XmlLogFile(xml_file_path, "JobsReport")
        # Create the lines and columns
        self.initialize_array(l_jobs, l_jobs_not_today)
        # Write the wml file
        self.update_xml_file(l_jobs)
    
    def initialize_array(self, l_jobs, l_jobs_not_today):
        l_dist = []
        l_applications = []
        for job in l_jobs:
            distrib = job.distribution
            if distrib is not None and distrib not in l_dist:
                l_dist.append(distrib)
            
            application = job.application
            if application is not None and application not in l_applications:
                l_applications.append(application)
        
        for job_def in l_jobs_not_today:
            distrib = src.get_cfg_param(job_def, "distribution", "nothing")
            if distrib is not "nothing" and distrib not in l_dist:
                l_dist.append(distrib)
                
            application = src.get_cfg_param(job_def, "application", "nothing")
            if application is not "nothing" and application not in l_applications:
                l_applications.append(application)
        
        self.l_dist = l_dist
        self.l_applications = l_applications
        
        # Update the hosts node
        self.xmldists = self.xml_file.add_simple_node("distributions")
        for dist_name in self.l_dist:
            src.xmlManager.add_simple_node(self.xmldists, "dist", attrib={"name" : dist_name})
            
        # Update the applications node
        self.xmlapplications = self.xml_file.add_simple_node("applications")
        for application in self.l_applications:
            src.xmlManager.add_simple_node(self.xmlapplications, "application", attrib={"name" : application})
        
        # Initialize the jobs node
        self.xmljobs = self.xml_file.add_simple_node("jobs")
        
        # 
        self.put_jobs_not_today(l_jobs_not_today)
        
        # Initialize the info node (when generated)
        self.xmlinfos = self.xml_file.add_simple_node("infos", attrib={"name" : "last update", "JobsCommandStatus" : "running"})
    
    def put_jobs_not_today(self, l_jobs_not_today):
        for job_def in l_jobs_not_today:
            xmlj = src.xmlManager.add_simple_node(self.xmljobs, "job", attrib={"name" : job_def.name})
            src.xmlManager.add_simple_node(xmlj, "application", src.get_cfg_param(job_def, "application", "nothing"))
            src.xmlManager.add_simple_node(xmlj, "distribution", src.get_cfg_param(job_def, "distribution", "nothing"))
            src.xmlManager.add_simple_node(xmlj, "commands", " ; ".join(job_def.commands))
            src.xmlManager.add_simple_node(xmlj, "state", "Not today")        
        
    def update_xml_file(self, l_jobs):      
        
        # Update the job names and status node
        for job in l_jobs:
            # Find the node corresponding to the job and delete it
            # in order to recreate it
            for xmljob in self.xmljobs.findall('job'):
                if xmljob.attrib['name'] == job.name:
                    self.xmljobs.remove(xmljob)
            
            T0 = str(job._T0)
            if T0 != "-1":
                T0 = time.strftime('%Y-%m-%d %H:%M:%S', 
                                       time.localtime(job._T0))
            Tf = str(job._Tf)
            if Tf != "-1":
                Tf = time.strftime('%Y-%m-%d %H:%M:%S', 
                                       time.localtime(job._Tf))
            
            # recreate the job node
            xmlj = src.xmlManager.add_simple_node(self.xmljobs, "job", attrib={"name" : job.name})
            src.xmlManager.add_simple_node(xmlj, "host", job.machine.host)
            src.xmlManager.add_simple_node(xmlj, "port", str(job.machine.port))
            src.xmlManager.add_simple_node(xmlj, "user", job.machine.user)
            src.xmlManager.add_simple_node(xmlj, "sat_path", job.machine.sat_path)
            src.xmlManager.add_simple_node(xmlj, "application", job.application)
            src.xmlManager.add_simple_node(xmlj, "distribution", job.distribution)
            src.xmlManager.add_simple_node(xmlj, "timeout", str(job.timeout))
            src.xmlManager.add_simple_node(xmlj, "commands", " ; ".join(job.commands))
            src.xmlManager.add_simple_node(xmlj, "state", job.get_status())
            src.xmlManager.add_simple_node(xmlj, "begin", T0)
            src.xmlManager.add_simple_node(xmlj, "end", Tf)
            src.xmlManager.add_simple_node(xmlj, "out", src.printcolors.cleancolor(job.out))
            src.xmlManager.add_simple_node(xmlj, "err", src.printcolors.cleancolor(job.err))
            src.xmlManager.add_simple_node(xmlj, "res", str(job.res_job))
            if len(job.remote_log_files) > 0:
                src.xmlManager.add_simple_node(xmlj, "remote_log_file_path", job.remote_log_files[0])
            else:
                src.xmlManager.add_simple_node(xmlj, "remote_log_file_path", "nothing")           
            
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
        src.xmlManager.append_node_attrib(self.xmlinfos,
                    attrib={"value" : 
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
               
        # Write the file
        self.write_xml_file()
    
    def last_update(self, finish_status = "finished"):
        src.xmlManager.append_node_attrib(self.xmlinfos,
                    attrib={"JobsCommandStatus" : finish_status})
        # Write the file
        self.write_xml_file()
    
    def write_xml_file(self):
        self.xml_file.write_tree(self.stylesheet)
        
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
    
    l_cfg_dir = [jobs_cfg_files_dir, os.path.join(runner.cfg.VARS.datadir, "jobs")]
    
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
    today_jobs = Jobs(runner, logger, options.jobs_cfg, file_jobs_cfg, config_jobs)
    # SSH connection to all machines
    today_jobs.ssh_connection_all_machines()
    if options.test_connection:
        return 0
    
    gui = None
    if options.publish:
        gui = Gui("/export/home/serioja/LOGS/test.xml", today_jobs.ljobs, today_jobs.ljobsdef_not_today, "job_report.xsl")
    
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
