#!python

import os
import sys
import time
import pprint
import logging

from twitter.common import log, options
from twitter.common.recordio import ThriftRecordReader
from twitter.tcl.loader import ThermosJobLoader, MesosJobLoader
from tcl_thrift.ttypes import ThermosJob

from twitter.thermos.runner import TaskRunner

def parse_commandline():
  options.add("--thermos", dest = "thermos",
              help = "read thermos job description from .thermos file")
  options.add("--thermos_thrift", dest = "thermos_thrift",
              help = "read thermos job description from stored thrift ThermosJob")
  options.add("--mesos", dest = "mesos",
              help = "translate from mesos job description")
  options.add("--task", dest = "task", metavar = "TASK",
              help = "run the task by name of TASK")
  options.add("--replica", dest = "replica_id", metavar = "ID",
              help = "run the replica number ID, from 0 .. number of replicas.")
  options.add("--sandbox_root", dest = "sandbox_root", metavar = "PATH",
              help = "the path root where we will spawn task sandboxes")
  options.add("--checkpoint_root", dest = "checkpoint_root", metavar = "PATH",
              help = "the path where we will store task logs and checkpoints")
  options.add("--job_uid", dest = "uid", metavar = "INT64",
              help = "the uid assigned to this process by the scheduler")
  options.add("--action", dest = "action", metavar = "ACTION", default = "run",
              help = "the action for this task runner: run, restart, kill")

  (values, args) = options.parse()

  if args:
    log.error("unrecognized arguments: %s\n" % (" ".join(args)))
    options.help()
    sys.exit(1)

  # check invariants
  if values.thermos is None and values.thermos_thrift is None and values.mesos is None:
    log.error("must supply either one of --thermos, --thermos_thrift or --mesos!\n")
    options.print_help(sys.stderr)
    sys.exit(1)

  if not (values.task and values.replica_id and values.sandbox_root and (
      values.checkpoint_root and values.uid)):
    log.error("ERROR: must supply all of: %s\n" % (
      " ".join(["--task", "--replica_id", "--sandbox_root", "--checkpoint_root", "--job_uid"])))
    options.print_help(sys.stderr)
    sys.exit(1)

  return (values, args)

def get_job_from_options(opts):
  thermos_job = None

  if opts.thermos_thrift:
    thermos_file    = opts.thermos_thrift
    thermos_file_fd = file(thermos_file, "r")
    rr              = ThriftRecordReader(thermos_file_fd, ThermosJob)
    thermos_job     = rr.read()

  elif opts.thermos:
    thermos_file   = opts.thermos
    thermos_job    = ThermosJobLoader(thermos_file).to_thrift()

  elif opts.mesos:
    mesos_file     = opts.mesos
    thermos_job    = MesosJobLoader(mesos_file).to_thrift()

  if not thermos_job:
    log.fatal("Unable to read Thermos job!")
    sys.exit(1)

  return thermos_job

def get_task_from_job(thermos_job, task, replica):
  for tsk in thermos_job.tasks:
    if tsk.name == task and tsk.replica_id == int(replica):
      return tsk
  log.error('unable to find task: %s and replica: %s!\n' % (task, replica))
  known_tasks = {}
  for tsk in thermos_job.tasks:
    if tsk.name not in known_tasks: known_tasks[tsk.name] = []
    known_tasks[tsk.name].append(tsk.replica_id)
  log.info('known task/replicas:')
  log.info(pprint.pformat(known_tasks))

def main():
  opts, _ = parse_commandline()

  twitter.common.log.init("thermos_run")

  thermos_replica = opts.replica_id
  thermos_job = get_job_from_options(opts)
  thermos_task = get_task_from_job(thermos_job, opts.task, opts.replica_id)

  if thermos_job and thermos_task:
    log.info("Woop!  Able to find task: %s" % thermos_task)
  else:
    log.fatal("Unable to synthesize task!")
    sys.exit(1)

  task_runner = TaskRunner(thermos_task, opts.sandbox_root, opts.checkpoint_root, long(opts.uid))
  task_runner.run()

if __name__ == '__main__':
  main()